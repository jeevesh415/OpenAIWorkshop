"""
Evaluation metrics for AI Agent performance assessment.
Supports both automated and LLM-as-judge evaluation approaches.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class MetricType(Enum):
    """Types of evaluation metrics."""
    TOOL_USAGE = "tool_usage"
    RESPONSE_QUALITY = "response_quality"
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    RELEVANCE = "relevance"


@dataclass
class EvaluationResult:
    """Result of a single evaluation metric."""
    metric_name: str
    metric_type: MetricType
    score: float  # 0.0 to 1.0
    passed: bool
    details: Dict[str, Any]
    explanation: str


class ToolUsageEvaluator:
    """Evaluates whether the agent used the correct tools."""
    
    def evaluate(
        self,
        expected_tools: List[str],
        actual_tools: List[str],
        required_tools: Optional[List[str]] = None
    ) -> EvaluationResult:
        """
        Evaluate tool usage correctness.
        
        Args:
            expected_tools: List of tools that should be used
            actual_tools: List of tools actually used by the agent
            required_tools: Subset of expected_tools that are mandatory
            
        Returns:
            EvaluationResult with tool usage metrics
        """
        required_tools = required_tools or expected_tools
        
        # Check if all required tools were used
        missing_required = set(required_tools) - set(actual_tools)
        extra_tools = set(actual_tools) - set(expected_tools)
        correct_tools = set(expected_tools) & set(actual_tools)
        
        # Calculate score
        if not required_tools:
            score = 1.0
        else:
            score = len(set(required_tools) & set(actual_tools)) / len(required_tools)
        
        # Determine pass/fail
        passed = len(missing_required) == 0
        
        details = {
            "expected_tools": expected_tools,
            "actual_tools": actual_tools,
            "required_tools": required_tools,
            "missing_required": list(missing_required),
            "extra_tools": list(extra_tools),
            "correct_tools": list(correct_tools),
            "coverage": f"{len(correct_tools)}/{len(expected_tools)}"
        }
        
        explanation = self._generate_explanation(missing_required, extra_tools, correct_tools)
        
        return EvaluationResult(
            metric_name="tool_usage",
            metric_type=MetricType.TOOL_USAGE,
            score=score,
            passed=passed,
            details=details,
            explanation=explanation
        )
    
    def _generate_explanation(
        self,
        missing_required: set,
        extra_tools: set,
        correct_tools: set
    ) -> str:
        """Generate human-readable explanation."""
        parts = []
        
        if correct_tools:
            parts.append(f"✓ Correctly used: {', '.join(correct_tools)}")
        
        if missing_required:
            parts.append(f"✗ Missing required: {', '.join(missing_required)}")
        
        if extra_tools:
            parts.append(f"⚠ Unexpected tools: {', '.join(extra_tools)}")
        
        return " | ".join(parts) if parts else "No tools used"


class CompletenessEvaluator:
    """Evaluates whether the agent addressed all required criteria."""
    
    def evaluate(
        self,
        success_criteria: Dict[str, bool],
        agent_response: str,
        tool_calls: List[Dict[str, Any]]
    ) -> EvaluationResult:
        """
        Evaluate if agent response meets success criteria.
        
        Args:
            success_criteria: Dict of criteria that must be met
            agent_response: The agent's response text
            tool_calls: List of tool calls made by the agent
            
        Returns:
            EvaluationResult with completeness metrics
        """
        criteria_results = {}
        
        for criterion, required in success_criteria.items():
            if not required:
                criteria_results[criterion] = True
                continue
            
            # Check based on criterion type
            met = self._check_criterion(criterion, agent_response, tool_calls)
            criteria_results[criterion] = met
        
        # Calculate score
        total_required = sum(1 for v in success_criteria.values() if v)
        met_count = sum(1 for k, v in criteria_results.items() if v and success_criteria[k])
        score = met_count / total_required if total_required > 0 else 1.0
        
        passed = all(criteria_results[k] for k, v in success_criteria.items() if v)
        
        details = {
            "criteria_results": criteria_results,
            "total_required": total_required,
            "met_count": met_count
        }
        
        explanation = self._generate_explanation(criteria_results, success_criteria)
        
        return EvaluationResult(
            metric_name="completeness",
            metric_type=MetricType.COMPLETENESS,
            score=score,
            passed=passed,
            details=details,
            explanation=explanation
        )
    
    def _check_criterion(
        self,
        criterion: str,
        response: str,
        tool_calls: List[Dict[str, Any]]
    ) -> bool:
        """Check if a specific criterion is met."""
        # Map criterion names to tool checks
        criterion_tool_mapping = {
            "must_access_billing": ["get_billing_summary", "get_subscription_detail"],
            "must_access_knowledge_base": ["search_knowledge_base"],
            "must_check_subscription": ["get_subscription_detail", "get_customer_detail"],
            "must_check_service_incidents": ["get_subscription_detail"],
            "must_check_current_plan": ["get_subscription_detail"],
            "must_check_roaming_options": ["get_products", "search_knowledge_base"],
            "must_check_security_logs": ["get_security_logs"],
            "must_offer_unlock": ["unlock_account"],
            "must_check_customer_profile": ["get_customer_detail"],
            "must_check_promotions": ["get_eligible_promotions", "get_promotions"],
            "must_check_orders": ["get_customer_orders"],
        }
        
        # Check if relevant tools were called
        if criterion in criterion_tool_mapping:
            required_tools = criterion_tool_mapping[criterion]
            tool_names = [call.get("name", "") for call in tool_calls]
            return any(tool in tool_names for tool in required_tools)
        
        # For explanation criteria, check response content
        explanation_keywords = {
            "must_explain_charges": ["charge", "billing", "invoice", "cost"],
            "must_mention_policy": ["policy", "guideline", "procedure"],
            "must_provide_troubleshooting": ["troubleshoot", "check", "issue", "problem"],
            "must_explain_lockout_reason": ["lockout", "locked", "security", "login"],
            "must_explain_eligibility": ["eligible", "qualify", "criteria"],
            "must_explain_return_policy": ["return", "policy", "refund"],
            "must_check_eligibility": ["eligible", "eligibility", "qualify"],
            "must_explain_roaming_charges": ["roaming", "international", "charge", "fee"],
        }
        
        if criterion in explanation_keywords:
            keywords = explanation_keywords[criterion]
            response_lower = response.lower()
            return any(keyword in response_lower for keyword in keywords)
        
        # Default: assume not met if we can't check
        return False
    
    def _generate_explanation(
        self,
        criteria_results: Dict[str, bool],
        success_criteria: Dict[str, bool]
    ) -> str:
        """Generate human-readable explanation."""
        met = [k for k, v in criteria_results.items() if v and success_criteria[k]]
        not_met = [k for k, v in criteria_results.items() if not v and success_criteria[k]]
        
        parts = []
        if met:
            parts.append(f"✓ Met: {', '.join(met)}")
        if not_met:
            parts.append(f"✗ Not met: {', '.join(not_met)}")
        
        return " | ".join(parts) if parts else "All criteria met"


class ResponseQualityEvaluator:
    """Evaluates the quality of the agent's response using LLM-as-judge."""
    
    def __init__(self, azure_openai_client=None):
        """
        Initialize evaluator with Azure OpenAI client.
        
        Args:
            azure_openai_client: AzureOpenAI client instance for LLM-as-judge
        """
        self.client = azure_openai_client
    
    def evaluate(
        self,
        query: str,
        response: str,
        context: Dict[str, Any]
    ) -> EvaluationResult:
        """
        Evaluate response quality using LLM-as-judge.
        
        Args:
            query: Original customer query
            response: Agent's response
            context: Additional context (tools used, etc.)
            
        Returns:
            EvaluationResult with quality metrics
        """
        if not self.client:
            # If no LLM available, do basic checks
            return self._basic_quality_check(query, response)
        
        # Use LLM-as-judge
        return self._llm_judge(query, response, context)
    
    def _basic_quality_check(self, query: str, response: str) -> EvaluationResult:
        """Basic quality checks without LLM."""
        checks = {
            "has_content": len(response.strip()) > 0,
            "sufficient_length": len(response.split()) >= 20,
            "not_error_message": "error" not in response.lower()[:50],
        }
        
        score = sum(checks.values()) / len(checks)
        passed = all(checks.values())
        
        return EvaluationResult(
            metric_name="response_quality_basic",
            metric_type=MetricType.RESPONSE_QUALITY,
            score=score,
            passed=passed,
            details=checks,
            explanation=f"Basic quality score: {score:.2f}"
        )
    
    def _llm_judge(
        self,
        query: str,
        response: str,
        context: Dict[str, Any]
    ) -> EvaluationResult:
        """Use LLM to judge response quality."""
        
        evaluation_prompt = f"""You are evaluating a customer service agent's response.

Customer Query: {query}

Agent Response: {response}

Context: {context}

Evaluate the response on the following criteria (score each 0-10):
1. Relevance: Does the response address the customer's question?
2. Accuracy: Is the information provided accurate and appropriate?
3. Completeness: Does it fully address all aspects of the query?
4. Clarity: Is the response clear and easy to understand?
5. Professionalism: Is the tone appropriate for customer service?

Provide your evaluation in JSON format:
{{
  "relevance": <score>,
  "accuracy": <score>,
  "completeness": <score>,
  "clarity": <score>,
  "professionalism": <score>,
  "overall_score": <average>,
  "explanation": "<brief explanation>"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Using deployment name from env
                messages=[
                    {"role": "system", "content": "You are an expert evaluator of AI customer service responses."},
                    {"role": "user", "content": evaluation_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            import json
            eval_result = json.loads(response.choices[0].message.content)
            
            # Normalize score to 0-1 range
            score = eval_result.get("overall_score", 0) / 10.0
            passed = score >= 0.7  # 70% threshold
            
            return EvaluationResult(
                metric_name="response_quality_llm",
                metric_type=MetricType.RESPONSE_QUALITY,
                score=score,
                passed=passed,
                details=eval_result,
                explanation=eval_result.get("explanation", "LLM evaluation complete")
            )
        except Exception as e:
            # Fallback to basic check if LLM fails
            return self._basic_quality_check(query, response)


class AccuracyEvaluator:
    """Evaluates factual accuracy of the response."""
    
    def evaluate(
        self,
        response: str,
        ground_truth: Optional[Dict[str, Any]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None
    ) -> EvaluationResult:
        """
        Evaluate response accuracy against ground truth or tool results.
        
        Args:
            response: Agent's response
            ground_truth: Expected facts/information
            tool_results: Results from tool calls
            
        Returns:
            EvaluationResult with accuracy metrics
        """
        # This is a placeholder - in practice, you'd implement more sophisticated checks
        # based on your specific domain knowledge and available ground truth
        
        score = 1.0  # Default to passing if no ground truth
        passed = True
        details = {
            "has_ground_truth": ground_truth is not None,
            "has_tool_results": tool_results is not None
        }
        
        explanation = "Accuracy check not implemented - default pass"
        
        return EvaluationResult(
            metric_name="accuracy",
            metric_type=MetricType.ACCURACY,
            score=score,
            passed=passed,
            details=details,
            explanation=explanation
        )
