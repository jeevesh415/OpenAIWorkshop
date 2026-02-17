"""
Durable Task Worker for Fraud Detection.

This worker hosts:
1. The main fraud_detection_orchestration (outer layer)
2. Activity functions for side effects
3. The inner workflow runs as an activity

Architecture:
- DTS Orchestration handles: durability, HITL, timeouts, crash recovery
- Inner Workflow handles: complex fan-out/fan-in topology

Prerequisites:
- Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_CHAT_DEPLOYMENT
- Start Durable Task Scheduler: docker run -d --name dts -p 8080:8080 -p 8082:8082 mcr.microsoft.com/dts/dts-emulator:latest
- Start MCP Server: cd mcp && uv run mcp_service.py
"""

import asyncio
import json
import logging
import os
import sys
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment first so observability can read connection string
load_dotenv()

# ------------------------------------------------------------------
# Observability (must be before any agent imports)
# ------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # agentic_ai/

try:
    from observability import setup_observability
    _observability_enabled = setup_observability(
        service_name="contoso-fraud-worker",
        enable_live_metrics=True,
        enable_sensitive_data=os.getenv("ENABLE_SENSITIVE_DATA", "false").lower() in ("1", "true", "yes"),
    )
except ImportError:
    _observability_enabled = False

# ------------------------------------------------------------------
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker
from durabletask.task import ActivityContext, OrchestrationContext, Task, when_any, when_all
from pydantic import BaseModel, ValidationError

from agent_framework import MCPStreamableHTTPTool, WorkflowEvent
from agent_framework.azure import AzureOpenAIChatClient

from fraud_analysis_workflow import (
    SuspiciousActivityAlert,
    FraudRiskAssessment,
    create_fraud_analysis_workflow,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
if _observability_enabled:
    logger.info("✅ Application Insights observability enabled for fraud workflow worker")

# Constants
ANALYST_APPROVAL_EVENT = "AnalystDecision"


# ============================================================================
# Input/Output Models
# ============================================================================


class FraudDetectionInput(BaseModel):
    """Input for the fraud detection orchestration."""
    alert_id: str
    customer_id: int
    alert_type: str
    description: str = ""
    timestamp: str = ""
    severity: str = "medium"
    approval_timeout_hours: float = 72.0  # 72 hours for analyst review
    max_review_attempts: int = 3


class AnalystDecision(BaseModel):
    """Human analyst decision."""
    alert_id: str
    approved_action: str  # "lock_account", "refund_charges", "clear", "both"
    analyst_notes: str = ""
    analyst_id: str = "analyst"


class ActionResult(BaseModel):
    """Result from fraud action execution."""
    alert_id: str
    action_taken: str
    success: bool
    details: str


# ============================================================================
# Global Resources (initialized once)
# ============================================================================

_mcp_tool: MCPStreamableHTTPTool | None = None
_chat_client: AzureOpenAIChatClient | None = None
_main_loop: asyncio.AbstractEventLoop | None = None


async def _ensure_resources():
    """Initialize global resources if not already done."""
    global _mcp_tool, _chat_client
    
    if _mcp_tool is None:
        mcp_uri = os.getenv("MCP_SERVER_URI", "http://localhost:8000/mcp")
        _mcp_tool = MCPStreamableHTTPTool(name="contoso_mcp", url=mcp_uri, timeout=30)
        await _mcp_tool.__aenter__()
        logger.info(f"✓ MCP tool initialized at {mcp_uri}")
    
    if _chat_client is None:
        # Use managed identity if AZURE_CLIENT_ID is set, otherwise DefaultAzureCredential
        azure_client_id = os.getenv("AZURE_CLIENT_ID")
        if azure_client_id:
            from azure.identity import ManagedIdentityCredential
            credential = ManagedIdentityCredential(client_id=azure_client_id)
            logger.info(f"Using ManagedIdentityCredential with client_id: {azure_client_id}")
        else:
            credential = DefaultAzureCredential()
            logger.info("Using DefaultAzureCredential")
        
        _chat_client = AzureOpenAIChatClient(
            credential=credential,
            deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o"),
        )
        logger.info("✓ Azure OpenAI client initialized")
    
    return _mcp_tool, _chat_client


# ============================================================================
# Activity Functions
# ============================================================================


def run_fraud_analysis(context: ActivityContext, alert_dict: dict) -> dict:
    """
    Activity that runs the inner fraud analysis workflow.
    
    This is the bridge between Durable Task and the Workflow:
    - Receives alert as dict
    - Runs the fan-out → aggregate workflow
    - Returns FraudRiskAssessment as dict
    """
    logger.info(f"[Activity] run_fraud_analysis starting for alert {alert_dict.get('alert_id')}")
    
    async def _run_workflow():
        mcp_tool, chat_client = await _ensure_resources()
        
        # Create the workflow
        workflow = create_fraud_analysis_workflow(mcp_tool, chat_client)
        
        # Create alert object
        alert = SuspiciousActivityAlert(**alert_dict)
        
        # Run workflow and collect output
        assessment: FraudRiskAssessment | None = None
        
        async for event in workflow.run(alert, stream=True):
            if isinstance(event, WorkflowEvent) and event.type == "output":
                if isinstance(event.data, FraudRiskAssessment):
                    assessment = event.data
                    break
        
        if assessment is None:
            raise ValueError("Workflow did not produce FraudRiskAssessment")
        
        # Add customer_id from original alert
        assessment_dict = assessment.model_dump()
        assessment_dict["customer_id"] = alert.customer_id
        
        return assessment_dict
    
    # Run the async workflow on the main event loop (where MCP tool was initialized)
    if _main_loop is None or _main_loop.is_closed():
        raise RuntimeError("Main event loop not available. Was the worker started correctly?")
    try:
        future = asyncio.run_coroutine_threadsafe(_run_workflow(), _main_loop)
        result = future.result(timeout=300)  # 5 minute timeout
    except Exception as e:
        logger.error(f"[Activity] run_fraud_analysis FAILED: {type(e).__name__}: {e}", exc_info=True)
        raise
    logger.info(f"[Activity] run_fraud_analysis completed, risk_score={result.get('overall_risk_score')}")
    return result


def notify_analyst(context: ActivityContext, assessment_dict: dict) -> str:
    """
    Activity to notify analyst for review.
    
    In production, this would:
    - Send email/Slack notification
    - Create ticket in ITSM system
    - Push to analyst dashboard
    """
    alert_id = assessment_dict.get("alert_id")
    risk_score = assessment_dict.get("overall_risk_score", 0)
    recommended_action = assessment_dict.get("recommended_action", "unknown")
    
    logger.info(f"[Activity] NOTIFICATION: Analyst review required for alert {alert_id}")
    logger.info(f"[Activity] Risk Score: {risk_score:.2f}, Recommended: {recommended_action}")
    logger.info(f"[Activity] Reasoning: {assessment_dict.get('reasoning', 'N/A')}")
    
    # In production: send notification via email, Slack, etc.
    return f"Analyst notified for alert {alert_id}"


def execute_fraud_action(context: ActivityContext, decision_dict: dict) -> dict:
    """
    Activity to execute the approved fraud action.
    
    In production, this would:
    - Lock account via API
    - Process refunds
    - Update fraud database
    """
    alert_id = decision_dict.get("alert_id")
    action = decision_dict.get("approved_action", "unknown")
    analyst_id = decision_dict.get("analyst_id", "unknown")
    
    logger.info(f"[Activity] Executing fraud action: {action} for alert {alert_id}")
    logger.info(f"[Activity] Approved by analyst: {analyst_id}")
    
    # In production: execute actual action
    success = True
    details = f"Action '{action}' executed successfully"
    
    if action == "lock_account":
        logger.info(f"[Activity] 🔒 Account locked for alert {alert_id}")
    elif action == "refund_charges":
        logger.info(f"[Activity] 💰 Charges refunded for alert {alert_id}")
    elif action == "both":
        logger.info(f"[Activity] 🔒💰 Account locked and charges refunded for alert {alert_id}")
    elif action == "clear":
        logger.info(f"[Activity] ✅ Alert cleared for {alert_id}")
    
    return ActionResult(
        alert_id=alert_id,
        action_taken=action,
        success=success,
        details=details,
    ).model_dump()


def auto_clear_alert(context: ActivityContext, assessment_dict: dict) -> dict:
    """
    Activity to auto-clear low-risk alerts.
    """
    alert_id = assessment_dict.get("alert_id")
    risk_score = assessment_dict.get("overall_risk_score", 0)
    
    logger.info(f"[Activity] Auto-clearing low-risk alert {alert_id} (risk={risk_score:.2f})")
    
    return ActionResult(
        alert_id=alert_id,
        action_taken="auto_clear",
        success=True,
        details=f"Alert auto-cleared due to low risk score ({risk_score:.2f})",
    ).model_dump()


def escalate_timeout(context: ActivityContext, assessment_dict: dict) -> dict:
    """
    Activity to escalate when analyst review times out.
    """
    alert_id = assessment_dict.get("alert_id")
    
    logger.warning(f"[Activity] ⚠️ ESCALATION: Analyst review timed out for alert {alert_id}")
    logger.warning(f"[Activity] Escalating to fraud manager...")
    
    # In production: escalate to manager, auto-lock account, etc.
    return ActionResult(
        alert_id=alert_id,
        action_taken="escalate_timeout",
        success=True,
        details="Escalated to fraud manager due to review timeout",
    ).model_dump()


def send_notification(context: ActivityContext, result_dict: dict) -> str:
    """
    Activity to send final notification.
    """
    alert_id = result_dict.get("alert_id")
    action_taken = result_dict.get("action_taken", "unknown")
    
    logger.info(f"[Activity] Sending final notification for alert {alert_id}")
    logger.info(f"[Activity] Action taken: {action_taken}")
    
    # In production: send customer notification, update audit log
    return f"Notification sent for alert {alert_id}, action: {action_taken}"


# ============================================================================
# Main Orchestration
# ============================================================================


def fraud_detection_orchestration(
    context: OrchestrationContext,
    payload_raw: Any
) -> Generator[Task[Any], Any, dict]:
    """
    Main Durable Task orchestration for fraud detection.
    
    This orchestration:
    1. Runs the inner workflow (fan-out → aggregate) as an activity
    2. Routes based on risk score (simple if/else)
    3. For high risk: waits for analyst decision with timeout
    4. Executes approved action or auto-clears
    5. Sends final notification
    
    Args:
        context: The orchestration context
        payload_raw: The input payload (alert data)
        
    Returns:
        dict: Final result with status and action taken
    """
    logger.info("[Orchestration] Starting fraud detection orchestration")
    
    # Validate input
    if not isinstance(payload_raw, dict):
        raise ValueError("Alert data is required")
    
    try:
        payload = FraudDetectionInput.model_validate(payload_raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid alert input: {exc}") from exc
    
    alert_id = payload.alert_id
    logger.info(f"[Orchestration] Processing alert {alert_id}")
    
    context.set_custom_status(json.dumps({
        "message": f"Running fraud analysis for {alert_id}",
        "step_details": {},
        "risk_score": None,
    }))
    
    # ========================================================================
    # Step 1: Run the inner workflow (fan-out → aggregate)
    # ========================================================================
    
    logger.info("[Orchestration] Step 1: Running fraud analysis workflow...")
    
    alert_dict = {
        "alert_id": payload.alert_id,
        "customer_id": payload.customer_id,
        "alert_type": payload.alert_type,
        "description": payload.description,
        "timestamp": payload.timestamp,
        "severity": payload.severity,
    }
    
    assessment_task: Task[dict] = context.call_activity("run_fraud_analysis", input=alert_dict)
    assessment: dict = yield assessment_task
    
    risk_score = assessment.get("overall_risk_score", 0)
    recommended_action = assessment.get("recommended_action", "unknown")
    step_details = assessment.get("step_details", {})
    
    logger.info(f"[Orchestration] Analysis complete: risk={risk_score:.2f}, recommended={recommended_action}")
    
    # ========================================================================
    # Step 2: Route based on risk score
    # ========================================================================
    
    result: dict
    
    if risk_score >= 0.6:
        # HIGH RISK - Human-in-the-loop
        logger.info(f"[Orchestration] HIGH RISK ({risk_score:.2f}) - Requiring analyst review")
        context.set_custom_status(json.dumps({
            "message": f"Awaiting analyst review (risk={risk_score:.2f})",
            "step_details": step_details,
            "risk_score": risk_score,
        }))
        
        # Notify analyst
        yield context.call_activity("notify_analyst", input=assessment)
        
        # Wait for analyst decision OR timeout
        approval_task: Task[Any] = context.wait_for_external_event(ANALYST_APPROVAL_EVENT)
        timeout_task: Task[Any] = context.create_timer(
            context.current_utc_datetime + timedelta(hours=payload.approval_timeout_hours)
        )
        
        logger.info(f"[Orchestration] Waiting for analyst decision (timeout: {payload.approval_timeout_hours}h)")
        
        winner_task = yield when_any([approval_task, timeout_task])
        
        if winner_task == approval_task:
            # Analyst responded
            decision_data: Any = approval_task.get_result()
            logger.info(f"[Orchestration] Received analyst decision: {decision_data}")
            
            # Parse decision
            if isinstance(decision_data, dict):
                decision = AnalystDecision.model_validate(decision_data)
            else:
                # Handle string or other formats
                decision = AnalystDecision(
                    alert_id=alert_id,
                    approved_action=str(decision_data),
                    analyst_notes="",
                    analyst_id="unknown",
                )
            
            # Update step_details with review_gateway completion
            step_details["review_gateway"] = {
                "status": "completed",
                "tool_calls": [{
                    "name": "analyst_decision",
                    "arguments": {"action": decision.approved_action},
                    "result": f"Approved by {decision.analyst_id}: {decision.analyst_notes or 'No notes'}"
                }],
                "output": f"Action approved: {decision.approved_action}",
            }
            
            context.set_custom_status(json.dumps({
                "message": "Executing analyst-approved action",
                "step_details": step_details,
                "risk_score": risk_score,
            }))
            
            # Execute the approved action
            action_result: dict = yield context.call_activity(
                "execute_fraud_action",
                input=decision.model_dump()
            )
            result = action_result
            
            # Update step_details with fraud_action_executor completion
            step_details["fraud_action_executor"] = {
                "status": "completed",
                "tool_calls": [{
                    "name": "execute_fraud_action",
                    "arguments": {"action": decision.approved_action, "alert_id": alert_id},
                    "result": f"Action executed: {result.get('action_taken', 'unknown')}"
                }],
                "output": result.get("details", f"Executed action: {decision.approved_action}"),
            }
            
        else:
            # Timeout - escalate
            logger.warning(f"[Orchestration] Analyst review timed out after {payload.approval_timeout_hours}h")
            context.set_custom_status(json.dumps({
                "message": "Review timed out - escalating",
                "step_details": step_details,
                "risk_score": risk_score,
            }))
            
            escalation_result: dict = yield context.call_activity(
                "escalate_timeout",
                input=assessment
            )
            result = escalation_result
    
    else:
        # LOW RISK - Auto-clear
        logger.info(f"[Orchestration] LOW RISK ({risk_score:.2f}) - Auto-clearing")
        context.set_custom_status(json.dumps({
            "message": f"Auto-clearing alert (risk={risk_score:.2f})",
            "step_details": step_details,
            "risk_score": risk_score,
        }))
        
        clear_result: dict = yield context.call_activity("auto_clear_alert", input=assessment)
        result = clear_result
        
        # Update step_details with auto_clear_executor completion
        step_details["auto_clear_executor"] = {
            "status": "completed",
            "tool_calls": [{
                "name": "auto_clear_alert",
                "arguments": {"alert_id": alert_id, "risk_score": risk_score},
                "result": f"Alert auto-cleared (low risk: {risk_score:.2f})"
            }],
            "output": result.get("details", "Alert automatically cleared due to low risk score"),
        }
    
    # ========================================================================
    # Step 3: Send final notification
    # ========================================================================
    
    logger.info("[Orchestration] Step 3: Sending final notification")
    context.set_custom_status(json.dumps({
        "message": "Sending notification",
        "step_details": step_details,
        "risk_score": risk_score,
    }))
    
    yield context.call_activity("send_notification", input=result)
    
    # Update step_details with final_notification_executor completion
    step_details["final_notification_executor"] = {
        "status": "completed",
        "tool_calls": [{
            "name": "send_notification",
            "arguments": {"alert_id": alert_id, "action_taken": result.get("action_taken")},
            "result": "Notification sent to customer and internal teams"
        }],
        "output": f"Notification sent for alert {alert_id}",
    }
    
    # ========================================================================
    # Complete
    # ========================================================================
    
    logger.info(f"[Orchestration] ✅ Fraud detection completed for alert {alert_id}")
    context.set_custom_status(json.dumps({
        "message": "Completed",
        "step_details": step_details,
        "risk_score": risk_score,
    }))
    
    return {
        "alert_id": alert_id,
        "status": "completed",
        "risk_score": risk_score,
        "action_taken": result.get("action_taken"),
        "success": result.get("success"),
        "step_details": step_details,
    }


# ============================================================================
# Worker Setup
# ============================================================================


def get_worker(
    taskhub: str | None = None,
    endpoint: str | None = None,
) -> DurableTaskSchedulerWorker:
    """Create a configured DurableTaskSchedulerWorker."""
    taskhub_name = taskhub or os.getenv("DTS_TASKHUB", "default")
    endpoint_url = endpoint or os.getenv("DTS_ENDPOINT", "http://localhost:8080")
    
    logger.info(f"Using DTS endpoint: {endpoint_url}")
    logger.info(f"Using taskhub: {taskhub_name}")
    
    # Use credentials for Azure-hosted DTS, None for local emulator
    credential = None if endpoint_url.startswith("http://localhost") else DefaultAzureCredential()
    
    return DurableTaskSchedulerWorker(
        host_address=endpoint_url,
        secure_channel=not endpoint_url.startswith("http://localhost"),
        taskhub=taskhub_name,
        token_credential=credential,
    )


def setup_worker(worker: DurableTaskSchedulerWorker) -> None:
    """Set up the worker with orchestrations and activities."""
    
    logger.info("Registering activities...")
    worker.add_activity(run_fraud_analysis)
    worker.add_activity(notify_analyst)
    worker.add_activity(execute_fraud_action)
    worker.add_activity(auto_clear_alert)
    worker.add_activity(escalate_timeout)
    worker.add_activity(send_notification)
    logger.info("✓ Activities registered")
    
    logger.info("Registering orchestration...")
    worker.add_orchestrator(fraud_detection_orchestration)
    logger.info("✓ Orchestration registered")


async def main():
    """Main entry point for the worker process."""
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    
    logger.info("="*60)
    logger.info("Starting Durable Fraud Detection Worker")
    logger.info("="*60)
    
    # Pre-initialize resources
    logger.info("Initializing resources...")
    try:
        await _ensure_resources()
    except Exception as e:
        logger.error(f"Failed to initialize resources: {e}")
        logger.error("Make sure MCP server is running and Azure OpenAI is configured")
        return
    
    # Create and setup worker
    worker = get_worker()
    setup_worker(worker)
    
    logger.info("")
    logger.info("Worker is ready and listening for orchestrations!")
    logger.info("Dashboard: http://localhost:8082")
    logger.info("Press Ctrl+C to stop.")
    logger.info("")
    
    try:
        worker.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Worker shutdown initiated")
    
    logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
