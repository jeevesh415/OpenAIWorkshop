"""
Part 4 — Typed-Contract Multi-Agent Workflow (Structured Data Exchange)

Demonstrates WHY strict typed data exchange between agents matters in
business-critical multi-agent orchestrations.  This security incident
response pipeline — built for an IT management / MSP platform — has
Pydantic-enforced INPUT and OUTPUT contracts at every agent boundary.
If any agent's output violates the schema the pipeline fails fast —
no silent corruption, no LLM "interpretation" of malformed data.

Pipeline (IT Security Incident Response):

  ┌──────────────┐  SecurityAlert    ┌──────────────┐  ThreatAssessment
  │  Alert       │ ────────────────▶ │  Threat      │ ────────────────────▶
  │  Triage      │  (Pydantic)       │  Intel       │  (Pydantic)
  └──────────────┘                   └──────────────┘
                                                              │
  ┌──────────────┐  IncidentResponse                          ▼
  │  Response    │ ◀──────────────── ┌──────────────┐  ImpactAnalysis
  │  Orchestrator│  (Pydantic)       │  Impact      │ ────────────────────▶
  └──────────────┘                   │  Analyzer    │  (Pydantic)
         │                           └──────────────┘
         ▼
   IncidentResponse  (Pydantic — drives automated remediation)

Why typed contracts matter in IT security:
  - Wrong severity enum → wrong SLA timer → breached customer SLA
  - Misclassified attack vector → wrong containment playbook executed
  - Ambiguous "some endpoints affected" → automated isolation skips hosts
  - "Risk seems high" vs risk_score=87 → completely different escalation path

Usage:
    cd agentic_ai/agents/mcp_agent_demo
    uv run python workflow_typed_contracts.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from enum import Enum
from typing import cast

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# ── Load credentials ────────────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp", ".env")
load_dotenv(env_path)


# ═══════════════════════════════════════════════════════════════════════════
#  CONTRACTS — Pydantic models that form the typed data-exchange boundary
#  between agents.  Each model is both a SCHEMA (for the LLM) and a
#  VALIDATOR (for the runtime).
#
#  In an MSP / IT management platform, these contracts drive automation:
#  - Automated ticket creation (needs exact severity + category)
#  - SLA timers (wrong severity = wrong SLA = contractual breach)
#  - Playbook selection (wrong attack_vector = wrong containment)
#  - Customer notifications (requires structured, auditable data)
# ═══════════════════════════════════════════════════════════════════════════


class AlertSource(str, Enum):
    """Where the raw alert originated."""
    EDR = "edr"                    # Endpoint Detection & Response
    SIEM = "siem"                  # Security Information & Event Management
    NETWORK_IDS = "network_ids"    # Network Intrusion Detection System
    EMAIL_GATEWAY = "email_gateway"
    VULNERABILITY_SCANNER = "vulnerability_scanner"
    USER_REPORT = "user_report"


class Severity(str, Enum):
    """NIST-aligned severity levels — drives SLA timers."""
    CRITICAL = "critical"   # SLA: 15 min response, 1 hr containment
    HIGH = "high"           # SLA: 30 min response, 4 hr containment
    MEDIUM = "medium"       # SLA: 2 hr response, 24 hr containment
    LOW = "low"             # SLA: 8 hr response, 72 hr containment
    INFORMATIONAL = "informational"


class AttackVector(str, Enum):
    """MITRE ATT&CK-aligned attack vector classification."""
    RANSOMWARE = "ransomware"
    PHISHING = "phishing"
    LATERAL_MOVEMENT = "lateral_movement"
    CREDENTIAL_THEFT = "credential_theft"
    MALWARE_EXECUTION = "malware_execution"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    COMMAND_AND_CONTROL = "command_and_control"
    SUPPLY_CHAIN = "supply_chain"
    UNKNOWN = "unknown"


class SecurityAlert(BaseModel):
    """Contract: Alert Triage Agent → Threat Intel Agent.

    Structured extraction from raw SIEM/EDR noise into actionable alert.
    Every field drives downstream automation — no ambiguity allowed.
    """
    alert_id: str = Field(description="Unique alert identifier (e.g. ALT-2026-00847)")
    timestamp: str = Field(description="ISO 8601 timestamp of first detection")
    source: AlertSource = Field(description="System that generated the alert")
    severity: Severity = Field(description="Triage-assessed severity level")
    title: str = Field(description="One-line alert title")
    description: str = Field(description="Concise description of observed activity")
    affected_hostname: str = Field(description="Primary affected endpoint hostname")
    affected_ip: str = Field(description="IP address of affected endpoint")
    affected_user: str = Field(description="Username associated with the activity")
    tenant_id: str = Field(description="MSP customer/tenant identifier")
    indicators_of_compromise: list[str] = Field(
        description="List of IOCs: file hashes, IPs, domains, registry keys"
    )
    raw_log_snippet: str = Field(description="Relevant log excerpt (first 500 chars)")


class ThreatCategory(str, Enum):
    """Threat categorization — determines which playbook runs."""
    APT = "apt"                        # Advanced Persistent Threat
    COMMODITY_MALWARE = "commodity_malware"
    INSIDER_THREAT = "insider_threat"
    OPPORTUNISTIC_ATTACK = "opportunistic_attack"
    TARGETED_ATTACK = "targeted_attack"
    FALSE_POSITIVE = "false_positive"


class ThreatAssessment(BaseModel):
    """Contract: Threat Intel Agent → Impact Analyzer.

    Enriched intelligence assessment with confidence scores.
    threat_score drives escalation; attack_vector selects containment playbook.
    """
    alert_id: str = Field(description="Alert ID (pass-through for traceability)")
    threat_category: ThreatCategory = Field(description="Classified threat category")
    attack_vector: AttackVector = Field(description="MITRE ATT&CK vector classification")
    threat_score: float = Field(
        ge=0, le=100, description="Threat confidence score 0-100 (higher = more dangerous)"
    )
    known_threat_actor: str | None = Field(
        description="Known threat actor/group name, or null if unknown"
    )
    mitre_techniques: list[str] = Field(
        description="MITRE ATT&CK technique IDs (e.g. T1566.001, T1059.001)"
    )
    ioc_matches: list[str] = Field(
        description="IOCs that matched known threat intelligence feeds"
    )
    confidence_pct: float = Field(
        ge=0, le=100, description="Analyst confidence in classification (0-100%)"
    )
    is_known_campaign: bool = Field(
        description="True if IOCs match a known active campaign"
    )
    recommended_severity_override: Severity | None = Field(
        description="Override triage severity if intel warrants it, null to keep original"
    )
    intel_summary: str = Field(description="Brief threat intelligence narrative")


class ImpactScope(str, Enum):
    """Blast radius classification — drives isolation scope."""
    SINGLE_ENDPOINT = "single_endpoint"
    MULTIPLE_ENDPOINTS = "multiple_endpoints"
    SUBNET = "subnet"
    SITE = "site"
    TENANT_WIDE = "tenant_wide"
    CROSS_TENANT = "cross_tenant"       # MSP nightmare scenario


class ImpactAnalysis(BaseModel):
    """Contract: Impact Analyzer → Response Orchestrator.

    Precise blast-radius assessment across the managed endpoint fleet.
    Numbers here drive automated isolation — wrong count = missed endpoints.
    """
    alert_id: str = Field(description="Alert ID (pass-through for traceability)")
    impact_scope: ImpactScope = Field(description="Blast radius classification")
    affected_endpoint_count: int = Field(
        ge=0, description="Number of confirmed affected endpoints"
    )
    at_risk_endpoint_count: int = Field(
        ge=0, description="Number of endpoints at risk but not yet confirmed compromised"
    )
    affected_hostnames: list[str] = Field(description="List of confirmed affected hostnames")
    compromised_accounts: list[str] = Field(
        description="User accounts confirmed or suspected compromised"
    )
    data_at_risk: bool = Field(
        description="True if sensitive/regulated data may be exposed"
    )
    business_services_affected: list[str] = Field(
        description="Business services/applications impacted (e.g. 'Exchange', 'ERP', 'File Server')"
    )
    lateral_movement_detected: bool = Field(
        description="True if evidence of lateral movement across hosts"
    )
    estimated_dwell_time_hours: float = Field(
        ge=0, description="Estimated hours the threat has been present"
    )
    impact_summary: str = Field(description="Brief impact assessment narrative")


class RemediationAction(str, Enum):
    """Specific automated actions the response system can execute."""
    ISOLATE_ENDPOINT = "isolate_endpoint"
    DISABLE_ACCOUNT = "disable_account"
    BLOCK_IP = "block_ip"
    BLOCK_HASH = "block_hash"
    FORCE_PASSWORD_RESET = "force_password_reset"
    REVOKE_SESSIONS = "revoke_sessions"
    QUARANTINE_EMAIL = "quarantine_email"
    DEPLOY_PATCH = "deploy_patch"
    RESTORE_FROM_BACKUP = "restore_from_backup"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class ResponsePriority(str, Enum):
    """Incident response priority — maps to SLA commitments."""
    P1 = "P1"   # Immediate automated action + SOC notification
    P2 = "P2"   # Automated action within 15 min + analyst review
    P3 = "P3"   # Queued for analyst review, auto-action optional
    P4 = "P4"   # Logged, no immediate action required


class IncidentResponse(BaseModel):
    """Contract: Response Orchestrator → Automation Engine / Ticket System.

    This is the OUTPUT that drives real-world automated remediation.
    Every field maps directly to an API call or ticket field.
    Wrong data here = wrong containment = breach.
    """
    incident_id: str = Field(description="Generated incident ID (e.g. INC-2026-00412)")
    alert_id: str = Field(description="Originating alert ID (traceability)")
    priority: ResponsePriority = Field(description="Response priority (P1-P4)")
    final_severity: Severity = Field(description="Final assessed severity after all analysis")
    immediate_actions: list[RemediationAction] = Field(
        description="Ordered list of automated remediation actions to execute NOW"
    )
    endpoints_to_isolate: list[str] = Field(
        description="Specific hostnames to network-isolate"
    )
    accounts_to_disable: list[str] = Field(
        description="Specific accounts to disable/lock"
    )
    ips_to_block: list[str] = Field(description="IPs to add to firewall blocklist")
    hashes_to_block: list[str] = Field(description="File hashes to block across fleet")
    notification_list: list[str] = Field(
        description="Roles/teams to notify (e.g. 'soc_lead', 'tenant_admin', 'ciso')"
    )
    customer_communication_required: bool = Field(
        description="True if MSP must notify the customer per SLA"
    )
    compliance_flags: list[str] = Field(
        description="Regulatory notifications needed (e.g. 'GDPR_72hr', 'HIPAA_breach', 'SOC2_incident')"
    )
    sla_response_deadline: str = Field(
        description="ISO 8601 deadline for initial response per SLA"
    )
    sla_containment_deadline: str = Field(
        description="ISO 8601 deadline for containment per SLA"
    )
    decision_rationale: str = Field(description="Brief explanation of response decisions")


# ═══════════════════════════════════════════════════════════════════════════
#  PIPELINE — sequential agent chain with typed contracts at each boundary
# ═══════════════════════════════════════════════════════════════════════════


async def main() -> None:
    from agent_framework import Agent, AgentResponse
    from agent_framework.azure import AzureOpenAIChatClient

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")

    if not endpoint or not api_key:
        print("ERROR: Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in mcp/.env")
        sys.exit(1)

    client = AzureOpenAIChatClient(
        api_key=api_key,
        endpoint=endpoint,
        deployment_name=deployment,
        api_version=api_version,
    )

    now = datetime.now(timezone.utc)

    # ── Agent 1: Alert Triage ───────────────────────────────────────────
    triage_agent = Agent(
        client=client,
        name="AlertTriageAgent",
        instructions=(
            "You are a Tier-1 SOC analyst performing initial alert triage for a "
            "managed security services provider (MSP). You receive raw SIEM/EDR "
            "alerts and extract structured, actionable security alert data.\n\n"
            "Rules:\n"
            "- Assign severity based on: critical=active ransomware/data exfil, "
            "high=credential theft/lateral movement, medium=suspicious behavior, "
            "low=policy violation, informational=benign anomaly\n"
            "- Extract ALL IOCs: file hashes (SHA-256), IP addresses, domains, "
            "registry keys, email addresses\n"
            "- alert_id format: ALT-YYYY-NNNNN\n"
            "- Include the raw log snippet (first 500 chars)\n"
            "- Be precise with hostnames, IPs, and usernames — these drive automation\n"
            f"- Current UTC time: {now.isoformat()}"
        ),
    )

    # ── Agent 2: Threat Intelligence ────────────────────────────────────
    threat_intel_agent = Agent(
        client=client,
        name="ThreatIntelAgent",
        instructions=(
            "You are a threat intelligence analyst. You receive a structured "
            "SecurityAlert and produce a ThreatAssessment by enriching it with "
            "threat intelligence.\n\n"
            "Rules:\n"
            "- Classify using MITRE ATT&CK framework — list specific technique IDs\n"
            "- threat_score formula: base 50, +20 if matches known campaign, "
            "+15 if credential theft involved, +10 per IOC matching known feeds, "
            "-20 if likely false positive\n"
            "- confidence_pct: 90%+ only if multiple IOC matches, 60-89% for "
            "behavioral match, <60% for heuristic-only\n"
            "- Override severity ONLY if intel clearly contradicts triage assessment\n"
            "- Mark is_known_campaign=true only if IOCs match documented campaigns\n"
            "- For unknown actors, set known_threat_actor to null"
        ),
    )

    # ── Agent 3: Impact Analysis ────────────────────────────────────────
    impact_agent = Agent(
        client=client,
        name="ImpactAnalyzer",
        instructions=(
            "You are an impact assessment specialist for a managed IT platform. "
            "You receive a ThreatAssessment and determine the blast radius across "
            "the managed endpoint fleet.\n\n"
            "Rules:\n"
            "- Scope: single_endpoint (1 host), multiple_endpoints (2-10), "
            "subnet (same /24), site (same location), tenant_wide (all customer endpoints), "
            "cross_tenant (MSP-level compromise affecting multiple customers)\n"
            "- If lateral_movement is the attack vector, assume at_risk_endpoint_count "
            "is at least 3x the confirmed affected count\n"
            "- Check if affected services include any regulated data "
            "(healthcare→HIPAA, financial→SOX, EU data→GDPR)\n"
            "- estimated_dwell_time: check timestamps, assume minimum 1 hour if "
            "first detection was from automated tools, 24+ hours if from user report\n"
            "- List specific business services that rely on affected endpoints"
        ),
    )

    # ── Agent 4: Response Orchestration ─────────────────────────────────
    response_agent = Agent(
        client=client,
        name="ResponseOrchestrator",
        instructions=(
            "You are the automated incident response engine for an MSP platform. "
            "You receive an ImpactAnalysis and produce the final IncidentResponse "
            "that drives automated remediation and ticket creation.\n\n"
            "SLA matrix (from detection to response / containment):\n"
            "- CRITICAL: P1, respond 15 min, contain 1 hr\n"
            "- HIGH: P2, respond 30 min, contain 4 hrs\n"
            "- MEDIUM: P3, respond 2 hrs, contain 24 hrs\n"
            "- LOW: P4, respond 8 hrs, contain 72 hrs\n\n"
            "Response rules:\n"
            "- Ransomware/data_exfil → ALWAYS isolate endpoints + disable accounts\n"
            "- Credential theft → force password reset + revoke sessions\n"
            "- Lateral movement → isolate ALL affected + at-risk endpoints\n"
            "- Phishing → quarantine email + block sender IP/domain\n"
            "- If data_at_risk=true AND regulated data → add compliance flags\n"
            "- Customer communication required for P1 and P2\n"
            "- Always notify soc_lead; add tenant_admin for P1-P2, ciso for P1\n"
            "- incident_id format: INC-YYYY-NNNNN\n"
            f"- Current UTC time: {now.isoformat()}\n"
            "- Calculate SLA deadlines from current time based on severity"
        ),
    )

    # ── Raw security alert (simulating SIEM/EDR output) ─────────────────

    raw_alert = """
    === EDR ALERT — Managed Endpoint Security ===
    Timestamp: 2026-02-19T14:23:17Z
    Source: Endpoint Detection & Response (EDR Agent v4.2)
    Tenant: Contoso Financial Services (tenant: contoso-fin-2024)

    ALERT: Suspicious PowerShell execution detected on CONTOSO-DC01

    Endpoint: CONTOSO-DC01 (10.42.1.5) — Domain Controller
    User Context: CONTOSO\\svc_backup (service account)

    Observed Activity:
    - PowerShell process spawned by svc_backup at 14:23:17Z
    - Encoded command detected: Base64-encoded Invoke-Mimikatz variant
    - LSASS memory access attempted (credential dumping pattern)
    - Outbound connection to 185.220.101.42:443 (known C2 infrastructure)
    - Kerberos ticket request anomaly: TGT requested for domain admin group
    - Shadow copy deletion command queued (vssadmin delete shadows)

    File Hash (SHA-256): a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890
    Secondary Hash: f0e1d2c3b4a596870fedcba9876543210fedcba9876543210fedcba987654321
    DNS Query: update-service.kfrp[.]xyz (suspicious DGA-like domain)

    Additional Telemetry:
    - 3 failed RDP attempts from CONTOSO-WS-047 to CONTOSO-DC01 prior to event
    - svc_backup account password last changed 847 days ago
    - Similar PowerShell pattern seen on CONTOSO-FS01 (file server) 47 min earlier
    - No MFA enforcement on service accounts per tenant policy

    Raw Log: EventID=4688|ProcessName=powershell.exe|CommandLine=-enc
    SQBtAHAAbwByAHQALQBNAG8AZAB1AGwAZQAgAC4AXABJAHaA...|ParentProcess=cmd.exe
    |User=CONTOSO\\svc_backup|LogonType=3|SourceIP=10.42.3.47
    """

    print("=" * 78)
    print("🛡️   IT SECURITY INCIDENT RESPONSE — Typed-Contract Multi-Agent Pipeline")
    print("=" * 78)
    print()
    print("  Scenario: MSP platform processes a critical endpoint alert through a")
    print("  4-agent pipeline where EVERY hand-off is a Pydantic-validated contract.")
    print("  Wrong data at any step → wrong automated response → customer breach.")
    print()
    print("  Why typed contracts, not natural language (A2A)?")
    print("  • severity=CRITICAL → 15-min SLA timer starts (not 'seems pretty bad')")
    print("  • attack_vector=CREDENTIAL_THEFT → Mimikatz playbook (not 'suspicious PS')")
    print("  • endpoints_to_isolate=['DC01','FS01'] → exact API calls (not 'some hosts')")
    print()

    # ────────────────────────────────────────────────────────────────────
    #  STEP 1 → Alert Triage: raw EDR alert → SecurityAlert
    # ────────────────────────────────────────────────────────────────────
    print("━" * 78)
    print("STEP 1 │ AlertTriageAgent: Raw EDR Alert → SecurityAlert (typed)")
    print("━" * 78)
    print(f"  Input  : Raw EDR alert text ({len(raw_alert.strip())} chars)")
    print(f"  Output : SecurityAlert (12 typed fields, enum-constrained)")
    print()

    step1_response: AgentResponse = await triage_agent.run(
        f"Triage this security alert and extract structured data:\n\n{raw_alert}",
        options={"response_format": SecurityAlert},
    )
    alert = cast(SecurityAlert, step1_response.value)
    _print_contract("SecurityAlert", alert)

    # ────────────────────────────────────────────────────────────────────
    #  STEP 2 → Threat Intel: SecurityAlert → ThreatAssessment
    # ────────────────────────────────────────────────────────────────────
    print("━" * 78)
    print("STEP 2 │ ThreatIntelAgent: SecurityAlert → ThreatAssessment (typed)")
    print("━" * 78)
    print(f"  Input  : SecurityAlert (validated Pydantic model)")
    print(f"  Output : ThreatAssessment (11 typed fields, range + enum constrained)")
    print()

    step2_response: AgentResponse = await threat_intel_agent.run(
        (
            "Analyze this security alert with threat intelligence and classify the threat.\n\n"
            f"Alert data:\n{alert.model_dump_json(indent=2)}"
        ),
        options={"response_format": ThreatAssessment},
    )
    threat = cast(ThreatAssessment, step2_response.value)
    _print_contract("ThreatAssessment", threat)

    # ────────────────────────────────────────────────────────────────────
    #  STEP 3 → Impact Analysis: ThreatAssessment → ImpactAnalysis
    # ────────────────────────────────────────────────────────────────────
    print("━" * 78)
    print("STEP 3 │ ImpactAnalyzer: ThreatAssessment → ImpactAnalysis (typed)")
    print("━" * 78)
    print(f"  Input  : ThreatAssessment (validated Pydantic model)")
    print(f"  Output : ImpactAnalysis (11 typed fields, scope + count constrained)")
    print()

    step3_response: AgentResponse = await impact_agent.run(
        (
            "Assess the impact and blast radius of this threat.\n\n"
            f"Threat assessment:\n{threat.model_dump_json(indent=2)}\n\n"
            f"Additional context from original alert:\n"
            f"- Affected endpoint: {alert.affected_hostname} ({alert.affected_ip})\n"
            f"- Tenant: {alert.tenant_id}\n"
            f"- IOCs: {json.dumps(alert.indicators_of_compromise)}\n"
            f"- Raw log mentions: CONTOSO-FS01 also affected 47 min earlier, "
            f"3 failed RDP attempts from CONTOSO-WS-047"
        ),
        options={"response_format": ImpactAnalysis},
    )
    impact = cast(ImpactAnalysis, step3_response.value)
    _print_contract("ImpactAnalysis", impact)

    # ────────────────────────────────────────────────────────────────────
    #  STEP 4 → Response: ImpactAnalysis → IncidentResponse
    # ────────────────────────────────────────────────────────────────────
    print("━" * 78)
    print("STEP 4 │ ResponseOrchestrator: ImpactAnalysis → IncidentResponse (typed)")
    print("━" * 78)
    print(f"  Input  : ImpactAnalysis (validated Pydantic model)")
    print(f"  Output : IncidentResponse (15 typed fields, action-ready)")
    print()

    step4_response: AgentResponse = await response_agent.run(
        (
            "Generate the incident response plan with specific automated actions.\n\n"
            f"Impact analysis:\n{impact.model_dump_json(indent=2)}\n\n"
            f"Threat context: {threat.attack_vector.value}, "
            f"threat_score={threat.threat_score}, "
            f"severity={alert.severity.value}\n"
            f"Affected user: {alert.affected_user}\n"
            f"IOCs to block: {json.dumps(alert.indicators_of_compromise)}"
        ),
        options={"response_format": IncidentResponse},
    )
    response = cast(IncidentResponse, step4_response.value)
    _print_contract("IncidentResponse", response)

    # ────────────────────────────────────────────────────────────────────
    #  SUMMARY — the full typed data chain
    # ────────────────────────────────────────────────────────────────────
    print()
    print("=" * 78)
    print("📊  PIPELINE SUMMARY — Typed Contract Chain")
    print("=" * 78)
    print()
    print(f"  📡  Raw EDR alert      →  free text ({len(raw_alert.strip())} chars)")
    print(f"  🚨  SecurityAlert      →  {alert.severity.value.upper()} | "
          f"{alert.affected_hostname} | {len(alert.indicators_of_compromise)} IOCs")
    print(f"  🔍  ThreatAssessment   →  {threat.attack_vector.value} | "
          f"score={threat.threat_score:.0f}/100 | "
          f"confidence={threat.confidence_pct:.0f}%")
    print(f"  💥  ImpactAnalysis     →  {impact.impact_scope.value} | "
          f"{impact.affected_endpoint_count} affected | "
          f"{impact.at_risk_endpoint_count} at risk")
    print(f"  🛡️   IncidentResponse   →  {response.priority.value} | "
          f"{len(response.immediate_actions)} actions | "
          f"notify: {', '.join(response.notification_list)}")
    print()

    # Show the automated actions that would execute
    print("  ⚡ AUTOMATED ACTIONS (would execute immediately):")
    for i, action in enumerate(response.immediate_actions, 1):
        print(f"     {i}. {action.value}")
    if response.endpoints_to_isolate:
        print(f"     🔌 Isolate: {', '.join(response.endpoints_to_isolate)}")
    if response.accounts_to_disable:
        print(f"     🔒 Disable: {', '.join(response.accounts_to_disable)}")
    if response.ips_to_block:
        print(f"     🚫 Block IPs: {', '.join(response.ips_to_block)}")
    if response.compliance_flags:
        print(f"     📋 Compliance: {', '.join(response.compliance_flags)}")
    print(f"     ⏱️  SLA response by: {response.sla_response_deadline}")
    print(f"     ⏱️  SLA contain by:  {response.sla_containment_deadline}")

    print()
    print("─" * 78)
    print("🔑  WHY THIS MATTERS — natural language vs. typed contracts in IT security:")
    print("─" * 78)
    print("""
    ┌─────────────────────────────────┬────────────────────────────────────────┐
    │  Natural Language (A2A)         │  Typed Contracts (this demo)           │
    ├─────────────────────────────────┼────────────────────────────────────────┤
    │  "The threat seems pretty       │  threat.threat_score = 85.0            │
    │   serious, probably critical"   │  alert.severity = Severity.CRITICAL    │
    │   → Which SLA timer starts?     │  → 15-min SLA timer, no ambiguity     │
    ├─────────────────────────────────┼────────────────────────────────────────┤
    │  "Looks like credential theft   │  threat.attack_vector =                │
    │   with some lateral movement"   │    AttackVector.CREDENTIAL_THEFT       │
    │   → Which playbook runs?        │  → Mimikatz containment playbook      │
    ├─────────────────────────────────┼────────────────────────────────────────┤
    │  "Several servers are affected, │  impact.affected_hostnames =           │
    │   should probably isolate them" │    ["CONTOSO-DC01", "CONTOSO-FS01"]    │
    │   → Which endpoints get API     │  → Exact isolation API calls fired     │
    │     isolation calls?            │                                        │
    ├─────────────────────────────────┼────────────────────────────────────────┤
    │  "There might be compliance     │  response.compliance_flags =           │
    │   implications"                 │    ["SOX_incident", "SOC2_incident"]   │
    │   → Which regulators get        │  → Exact notification workflows        │
    │     notified? Within what SLA?  │    triggered with deadlines            │
    └─────────────────────────────────┴────────────────────────────────────────┘

    In IT security, "approximately right" gets customers breached.
    Typed contracts ensure machines act on EXACT data, not interpretations.
    """)
    print("=" * 78)
    print("✅  Pipeline complete — 4 agents, 4 typed contracts, zero ambiguity.")
    print("=" * 78)


def _print_contract(name: str, model: BaseModel) -> None:
    """Pretty-print a Pydantic model as the validated contract output."""
    data = model.model_dump(mode="json")
    print(f"  ✅ {name} — validated successfully ({len(data)} fields)")
    print(f"  {'─' * 60}")
    for key, value in data.items():
        if isinstance(value, list):
            val_str = json.dumps(value)
            if len(val_str) > 100:
                print(f"    {key}: {val_str[:100]}...")
            else:
                print(f"    {key}: {val_str}")
        elif isinstance(value, float):
            print(f"    {key}: {value}")
        else:
            val_str = str(value)
            if len(val_str) > 100:
                print(f"    {key}: {val_str[:100]}...")
            else:
                print(f"    {key}: {value}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
