# Ambient Fraud Detection — Durable Agentic Workflow

A production-grade reference architecture for **ambient, long-running, durable, fail-over capable AI agent workflows** with human-in-the-loop (HITL) decision gates.

This demo implements the complete lifecycle of a background (ambient) agent system: continuous telemetry monitoring → anomaly detection → multi-agent investigation → human approval → action execution — all with crash recovery, persistent state, and real-time UI visualization.

> 📐 **Taking this to production?** See [PRODUCTION_ARCHITECTURE.md](PRODUCTION_ARCHITECTURE.md) for the Azure Container Apps deployment topology, security model, and scaling characteristics.

---

## 🎯 Workshop Learning Objectives

After this workshop you will understand how to:

1. **Design a 3-layer ambient agent architecture** (Detection → Investigation → Decision)
2. **Choose the right durability boundary** — what needs DTS checkpointing vs. what doesn't
3. **Implement human-in-the-loop** with durable external events that survive process restarts
4. **Build stateful feedback loops** — analyst rejects → agent re-investigates with full context
5. **Integrate MCP tools** for real-time data access within agent workflows
6. **Add observability** with OpenTelemetry + Application Insights
7. **Explain _why_ this architecture is truly durable** — not just buzzwords, but the concrete mechanics

---

## 🏗️ Architecture: The 3-Layer Pattern

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#4A90D9', 'primaryTextColor': '#fff', 'lineColor': '#5C6B77' }}}%%
flowchart TB
    subgraph LAYER1["🟢 Layer 1 — Detection · Ambient Monitoring"]
        direction LR
        TELEMETRY["📊 Telemetry<br/>Generator<br/><i>2–5s interval</i>"]
        RULES["⚡ Rule Engine<br/><i>Python, no LLM</i><br/>• Multi-country login<br/>• Spending spike > 3×<br/>• Burst API calls<br/>• Repeated auth failures"]
        SUBMIT["🚨 Auto-submit<br/>POST /api/workflow/start"]
        SSE_OUT["📺 SSE Stream<br/>→ React Live Feed"]

        TELEMETRY --> RULES
        RULES -->|"anomaly detected"| SUBMIT
        TELEMETRY -->|"all events"| SSE_OUT
        RULES -->|"flagged events"| SSE_OUT
    end

    subgraph LAYER2["🔵 Layer 2 — Investigation · Durable Agent Orchestration"]
        direction TB
        ORCH["🔷 DTS Orchestration<br/><i>checkpointed, crash-recoverable</i>"]

        subgraph ENTITY["dafx-FraudAnalysisAgent Entity"]
            direction TB
            INNER["Inner Workflow<br/><i>(fast, async, in-memory)</i>"]

            subgraph FANOUT["Fan-out / Fan-in"]
                direction LR
                ROUTER["AlertRouter"] --> USAGE["📈 Usage<br/>Analyst"]
                ROUTER --> LOCATION["🌍 Location<br/>Analyst"]
                ROUTER --> BILLING["💳 Billing<br/>Analyst"]
            end

            USAGE -->|"MCP tools"| AGG["🧠 FraudRisk<br/>Aggregator<br/><i>(LLM)</i>"]
            LOCATION -->|"MCP tools"| AGG
            BILLING -->|"MCP tools"| AGG
            AGG --> ASSESSMENT["📋 FraudRisk<br/>Assessment"]

            INNER --- FANOUT
        end

        ORCH -->|"yield fraud_agent.run()"| ENTITY
    end

    subgraph LAYER3["🟠 Layer 3 — Decision & Action · HITL + Execution"]
        direction TB
        RISK_CHECK{"Risk ≥ 0.6?"}

        subgraph HITL_LOOP["HITL Feedback Loop<br/><i>durable, stateful, crash-safe</i>"]
            direction TB
            NOTIFY["📧 Notify Analyst<br/><i>DTS Activity</i>"]
            WAIT["⏳ Wait for Decision<br/><i>when_any(event, 72h timer)</i><br/><b>Survives process death</b>"]
            DECIDE{"Analyst<br/>Decision?"}
            EXECUTE["✅ Execute Action<br/><i>DTS Activity</i>"]
            REINVEST["🔄 Re-investigate<br/><i>same session = full history</i>"]
            TIMEOUT_ACT["⏰ Escalate Timeout<br/><i>DTS Activity</i>"]
        end

        AUTO_CLEAR["🟢 Auto-clear<br/><i>DTS Activity</i>"]
        FINAL["📨 Send Notification<br/><i>DTS Activity</i>"]

        RISK_CHECK -->|"YES"| NOTIFY
        NOTIFY --> WAIT
        WAIT --> DECIDE
        DECIDE -->|"Approve"| EXECUTE
        DECIDE -->|"Reject + feedback"| REINVEST
        DECIDE -->|"Timeout"| TIMEOUT_ACT
        REINVEST -->|"loop back"| NOTIFY
        RISK_CHECK -->|"NO"| AUTO_CLEAR

        EXECUTE --> FINAL
        TIMEOUT_ACT --> FINAL
        AUTO_CLEAR --> FINAL
    end

    SUBMIT -->|"triggers"| ORCH
    ENTITY -->|"risk score"| RISK_CHECK

    style LAYER1 fill:#d4edda,stroke:#28a745,stroke-width:2px
    style LAYER2 fill:#cce5ff,stroke:#004085,stroke-width:2px
    style LAYER3 fill:#fff3cd,stroke:#856404,stroke-width:2px
    style ENTITY fill:#e8f4fd,stroke:#4A90D9
    style HITL_LOOP fill:#ffeeba,stroke:#ffc107
    style FANOUT fill:#f0f4f8,stroke:#adb5bd
```

### Why This Layering?

| Layer | Uses LLM? | Durable? | Why? |
|-------|-----------|----------|------|
| **Layer 1** — Detection | ❌ No | ❌ No | Events arrive every 2–5s. An LLM call takes 2–5s and costs money. Simple rules catch 95% of benign events at zero cost. |
| **Layer 2** — Investigation | ✅ Yes | ✅ Yes (entity) | Complex multi-signal reasoning is the LLM's strength. Entity state persists the full conversation for re-investigation. |
| **Layer 3** — Decision | ❌ No | ✅ Yes (orchestration) | Human decisions can take hours/days. DTS timers and external events survive crashes and restarts. |

---

## 🔑 Key Patterns

### Pattern 1: Durability Boundaries — What Gets Checkpointed?

Not everything needs to be durable. The key architectural insight is choosing **where** to draw the durability boundary:

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart LR
    subgraph DURABLE["✅ DTS-Managed · each yield = checkpoint"]
        direction TB
        D1["yield fraud_agent.run(...)"]
        D2["yield wait_for_external_event()"]
        D3["yield create_timer(72h)"]
        D4["yield call_activity(...)"]
    end

    subgraph FAST["⚡ Fast Async · retry on failure"]
        direction TB
        F1["Inner workflow fan-out/fan-in"]
        F2["MCP tool calls via HTTP"]
        F3["LLM calls to Azure OpenAI"]
    end

    DURABLE ~~~ FAST

    style DURABLE fill:#d4edda,stroke:#28a745,stroke-width:2px
    style FAST fill:#fff3cd,stroke:#856404,stroke-width:2px
```

**Why not checkpoint every LLM call?** Adding DTS checkpoints to each LLM call would add ~200ms overhead per call and massively complicate the agent topology. The inner workflow runs in ~10–20s — fast enough that retry-on-failure is the right strategy. If the worker crashes mid-inner-workflow, the entity call simply retries from the beginning.

### Pattern 2: Stateful Feedback Loop via Durable Entity

The `FraudAnalysisAgent` is registered as a DTS entity (`dafx-FraudAnalysisAgent`). The entity persists conversation history via `DurableAgentState`, enabling meaningful re-investigation:

```mermaid
sequenceDiagram
    participant O as DTS Orchestration
    participant E as Entity<br/>(dafx-FraudAnalysisAgent)
    participant S as DurableAgentState
    participant LLM as Azure OpenAI

    Note over O,S: First Investigation
    O->>E: yield fraud_agent.run(alert_json, session)
    E->>S: Load state (empty)
    E->>S: Append user message (alert)
    E->>LLM: Chat with full history
    LLM-->>E: Risk assessment
    E->>S: Append assistant response
    E->>S: Persist state ← saved to DTS storage
    E-->>O: AgentResponse (risk=0.85)

    Note over O,S: Analyst Rejects — Re-investigation
    O->>E: yield fraud_agent.run(feedback, same session!)
    E->>S: Load state (has alert + first analysis)
    E->>S: Append user message (feedback)
    E->>LLM: Chat with FULL history<br/>(alert + analysis + feedback)
    LLM-->>E: Deeper assessment
    E->>S: Append assistant response
    E->>S: Persist state
    E-->>O: AgentResponse (risk=0.72)
```

The agent doesn't start from scratch — it sees the original alert, its first analysis, AND the analyst's feedback. This is what makes re-investigation meaningful.

### Pattern 3: Ambient Detection Without LLM Overhead

Layer 1 uses fast Python rule evaluation, not LLM inference:

```python
# Rule: Multi-country login within 2 hours
if event.type == "login" and event.country != last_login_country:
    if time_delta < timedelta(hours=2):
        trigger_alert(event)  # → Layer 2 DTS orchestration

# Rule: Spending spike > 3× average
if event.type == "transaction" and event.amount > 3 * customer_average:
    trigger_alert(event)
```

At 1 event every 2–5 seconds, an LLM call (2–5s each) can't keep up. Rules handle the 95% of benign events at zero cost. The LLM's value is in Layer 2, where it reasons about complex multi-signal patterns.

### Pattern 4: Backend-For-Frontend (BFF) for Durable Workflows

The browser cannot call DTS's gRPC SDK directly. The FastAPI backend translates REST/WebSocket into SDK calls:

```mermaid
flowchart LR
    BROWSER["🌐 Browser<br/>(REST / SSE / WS)"]
    BACKEND["⚙️ Backend<br/>(FastAPI)"]
    DTS["🔷 DTS<br/>(gRPC SDK)"]
    WORKER["🔧 Worker"]

    BROWSER -->|"HTTP"| BACKEND
    BACKEND -->|"gRPC"| DTS
    DTS -.->|"pull"| WORKER

    style BROWSER fill:#e8f4fd,stroke:#4A90D9
    style BACKEND fill:#d4edda,stroke:#28a745
    style DTS fill:#cce5ff,stroke:#004085
    style WORKER fill:#ffeeba,stroke:#ffc107
```

In production, swap `DTS_ENDPOINT` from `localhost:8080` to your Azure DTS endpoint. **Zero code changes.** See [PRODUCTION_ARCHITECTURE.md](PRODUCTION_ARCHITECTURE.md).

---

## 🛡️ Why Is This Actually Durable? — Deep Dive

This section explains the **concrete mechanics** that make this architecture truly durable, not just the claim. Understanding these internals is critical for the workshop.

### The Durability Stack

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart TB
    subgraph YOUR_CODE["Your Code"]
        A["worker.py<br/>Orchestration generator + activities"]
    end

    subgraph AF["agent-framework DTS Layer"]
        B["DurableAIAgentWorker<br/>DurableAIAgentOrchestrationContext<br/>DurableAgentState"]
    end

    subgraph SDK["DTS Python SDK"]
        C["DurableTaskSchedulerWorker<br/>gRPC protocol"]
    end

    subgraph DTS["Azure Durable Task Scheduler"]
        D["Event Store · Timer Service<br/>Entity State Store · Task Queue"]
    end

    YOUR_CODE --> AF
    AF --> SDK
    SDK --> DTS

    style YOUR_CODE fill:#d4edda,stroke:#28a745,stroke-width:2px
    style AF fill:#e2d5f1,stroke:#6f42c1,stroke-width:2px
    style SDK fill:#cce5ff,stroke:#004085,stroke-width:2px
    style DTS fill:#fff3cd,stroke:#856404,stroke-width:2px
```

### 1. Event Sourcing — Checkpoints via `yield`

Every `yield` in the orchestration generator is a **checkpoint written to DTS's event store**:

```python
# Each yield writes an event to DTS's append-only log
response = yield fraud_agent.run(messages=alert, session=session)  # ← checkpoint
yield context.call_activity("notify_analyst", input=assessment)     # ← checkpoint
winner = yield when_any([wait_for_event(...), create_timer(72h)])    # ← checkpoint
```

These aren't in-memory variables — they're **persisted facts** in DTS storage. If the process crashes after step 2, DTS knows steps 1 and 2 completed because their completion events exist in the log.

### 2. Replay, Not Restore — How Crash Recovery Works

When a worker restarts after a crash, it doesn't "load state" — it **replays the orchestration function from the beginning**, but with a twist:

```mermaid
flowchart TB
    subgraph REPLAY["Orchestration Replay After Crash"]
        direction TB
        Y1["yield fraud_agent.run(...)"] -->|"DTS has completion event<br/>→ returns cached result instantly<br/>(no actual agent call)"| Y2["yield call_activity('notify_analyst')"]
        Y2 -->|"DTS has completion event<br/>→ returns cached result instantly"| Y3["yield when_any([event, timer])"]
        Y3 -->|"No completion event yet<br/>→ SUSPENDS HERE<br/>waiting for real event"| WAIT["⏳ Waiting..."]
    end

    style REPLAY fill:#e8f4fd,stroke:#4A90D9,stroke-width:2px
    style WAIT fill:#ffeeba,stroke:#ffc107
```

The generator function re-executes, but each `yield` that already completed **returns its cached result instantly** without re-executing the actual work. The orchestration replays forward until it reaches the first incomplete step, then suspends. This is why your orchestration code must be **deterministic** — it's replayed, not restored.

### 3. External Events Survive Process Death

The `wait_for_external_event("AnalystDecision")` call is especially powerful:

```mermaid
sequenceDiagram
    participant W1 as Worker (original)
    participant DTS as DTS Storage
    participant W2 as Worker (restarted)
    participant BE as Backend
    participant UI as Analyst

    W1->>DTS: yield when_any([event, timer])
    Note over W1: Worker crashes! 💥

    Note over DTS: Event subscription persists<br/>Timer ticks in DTS storage

    UI->>BE: POST /api/workflow/decision
    BE->>DTS: raise_orchestration_event<br/>("AnalystDecision", data)
    Note over DTS: Event stored in event log

    W2->>DTS: Start + long-poll for work
    DTS->>W2: Orchestration has pending event
    W2->>W2: Replay generator → resume at yield
    W2->>W2: Process analyst decision
```

The event subscription, the timer countdown, and the eventual analyst response — **all live in DTS storage**, not in the worker's memory. The worker is just a stateless compute runtime that pulls work.

### 4. The Worker Is Stateless — All State Lives in DTS

This is the fundamental insight. The worker process holds **zero durable state**:

| What | Where It Lives | Survives Crash? |
|------|---------------|-----------------|
| Orchestration progress (which step) | DTS event log | ✅ Yes |
| Agent conversation history | DTS entity state (`DurableAgentState`) | ✅ Yes |
| Pending timers (72h analyst timeout) | DTS timer service | ✅ Yes |
| External event subscriptions | DTS event store | ✅ Yes |
| Activity results | DTS event log | ✅ Yes |
| In-flight LLM call | Worker memory | ❌ No (retried) |
| In-flight MCP tool call | Worker memory | ❌ No (retried) |

When the worker crashes, the only things lost are in-flight LLM/MCP calls — and those are inside the inner workflow, which retries as a unit when the entity operation is re-dispatched.

### 5. Entity State Persistence (`DurableAgentState`)

The `agent-framework` library stores the full agent conversation in a structured schema:

```mermaid
%%{init: {'theme': 'base'}}%%
erDiagram
    ENTITY["dafx-FraudAnalysisAgent"] {
        string instance_key "session_id"
    }

    STATE["DurableAgentState"] {
        string schema_version "v1.1.0"
    }

    ENTRY["ConversationEntry"] {
        string type "request or response"
        json messages "Message array"
        json tool_calls "ToolCall array"
        json errors "Error array"
        json token_usage "TokenUsage"
    }

    ENTITY ||--|| STATE : "persists"
    STATE ||--o{ ENTRY : "conversationHistory"
```

Every time the entity processes a request, the cycle is:
1. **Load** state from DTS → `DurableAgentState`
2. **Append** user message (alert or feedback)
3. **Rebuild** full chat history from all entries (filtering out errors)
4. **Call** LLM with complete conversation
5. **Append** assistant response
6. **Persist** state back to DTS via `self.persist_state()`

This is why the agent can re-investigate with full context — the conversation history is a **durable, append-only log** stored in DTS, not in worker memory.

### 6. What DTS Provides vs. What It Doesn't

Understanding the **scope boundary** is critical:

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart LR
    subgraph DTS_SCOPE["🔷 DTS Provides"]
        direction TB
        DS1["Persistent task queue"]
        DS2["Event store · append-only log"]
        DS3["Timer service"]
        DS4["Entity state storage"]
        DS5["Work item distribution"]
        DS6["At-least-once delivery"]
    end

    subgraph WORKER_SCOPE["🔧 Worker Provides"]
        direction TB
        WS1["Compute runtime · Python"]
        WS2["LLM calls · Azure OpenAI"]
        WS3["MCP tool calls · HTTP"]
        WS4["Business logic · orchestration"]
        WS5["Agent framework integration"]
    end

    DTS_SCOPE ~~~ WORKER_SCOPE

    style DTS_SCOPE fill:#cce5ff,stroke:#004085,stroke-width:2px
    style WORKER_SCOPE fill:#ffeeba,stroke:#ffc107,stroke-width:2px
```

DTS is a **persistent task queue + event store + timer service**. It doesn't run your code — it stores the _record of what happened_ and _dispatches work items_ to workers. The worker is a **stateless compute runtime** that pulls tasks, executes your Python/LLM/MCP logic, and reports results back. If the worker dies, DTS still has the full event log; a new worker replays it and picks up where things left off.

---

## 📁 Project Structure

```
fraud_detection_durable/
├── worker.py                       # DTS Worker: orchestration + agent entity + activities
├── backend.py                      # FastAPI BFF: REST API, WebSocket, SSE, event producer
├── event_producer.py               # Layer 1: telemetry generation + anomaly detection
├── fraud_analysis_workflow.py      # Inner workflow: fan-out → aggregate (Layer 2)
├── provision_dts.ps1               # Azure DTS provisioning script
├── .env                            # Configuration (Azure OpenAI, DTS, App Insights)
├── pyproject.toml                  # Dependencies
├── README.md                       # This file
├── PRODUCTION_ARCHITECTURE.md      # Production deployment on Azure Container Apps
└── ui/                             # React/Vite UI
    ├── src/
    │   ├── App.jsx                 # Main app: WebSocket + SSE connections
    │   └── components/
    │       ├── ControlPanel.jsx    # Alert selector + start button
    │       ├── WorkflowVisualizer.jsx  # React Flow DAG visualization
    │       ├── AnalystDecisionPanel.jsx  # HITL approve/reject/feedback
    │       └── EventFeed.jsx       # Live telemetry feed (Layer 1)
    └── package.json
```

---

## 🚀 Quick Start

### Prerequisites

- **Docker** — for DTS emulator
- **Python 3.12+** with **uv**
- **Node.js 18+** — for React UI
- **Azure OpenAI** — with a deployed chat model
- **MCP Server** — Contoso tools on port 8000

### Service Startup

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart LR
    S1["1️⃣ DTS Emulator<br/>Port 8080"]
    S2["2️⃣ MCP Server<br/>Port 8000"]
    S3["3️⃣ Worker<br/>Pulls from DTS"]
    S4["4️⃣ Backend<br/>Port 8001"]
    S5["5️⃣ React UI<br/>Port 3000"]

    S1 --> S2 --> S3 --> S4 --> S5

    style S1 fill:#cce5ff,stroke:#004085
    style S2 fill:#d6d8db,stroke:#6c757d
    style S3 fill:#ffeeba,stroke:#ffc107
    style S4 fill:#d4edda,stroke:#28a745
    style S5 fill:#e8f4fd,stroke:#4A90D9
```

#### 1. Start DTS Emulator

```bash
docker run -d --name dts-emulator \
  -p 8080:8080 -p 8082:8082 \
  mcr.microsoft.com/dts/dts-emulator:latest
```

Dashboard: http://localhost:8082

> **Production:** Replace with Azure DTS — same SDK, just change `DTS_ENDPOINT`. See [provision_dts.ps1](provision_dts.ps1).

#### 2. Start MCP Server

```bash
cd mcp && uv run python mcp_service.py
```

#### 3. Start Worker

```bash
cd agentic_ai/workflow/fraud_detection_durable
uv sync && uv run python worker.py
```

#### 4. Start Backend

```bash
uv run python backend.py
```

#### 5. Start React UI

```bash
cd ui && npm install && npm run dev
# Open http://localhost:3000
```

---

## 🧪 Demo Scenarios

### Scenario 1: Ambient Detection → Auto-Clear

Watch the event feed — a multi-country login anomaly triggers automatic investigation. Low risk → auto-cleared.

### Scenario 2: Ambient Detection → HITL Approval

A spending spike triggers investigation. High risk → analyst reviews → approves "lock account".

### Scenario 3: Reject → Stateful Re-investigation

Analyst rejects with feedback "check if VPN usage". Agent re-investigates with **full conversation history** (original alert + first analysis + analyst feedback).

### Scenario 4: Kill & Recover (Durability Proof) 💥

This is the most important demo — it proves the architecture isn't just theoretical:

```mermaid
sequenceDiagram
    participant UI as Analyst
    participant BE as Backend
    participant DTS as DTS
    participant W1 as Worker v1

    UI->>BE: Start high-risk workflow
    BE->>DTS: schedule_new_orchestration()
    DTS->>W1: Work item: run orchestration
    W1->>W1: yield fraud_agent.run() ✅
    W1->>W1: yield notify_analyst() ✅
    W1->>DTS: yield wait_for_external_event()
    Note over W1: Status: Awaiting analyst review

    Note over W1: 💥 taskkill /F /IM python.exe

    participant W2 as Worker v2
    Note over W2: uv run python worker.py

    UI->>BE: POST /api/workflow/decision (approve)
    BE->>DTS: raise_orchestration_event()
    DTS->>W2: Orchestration has pending event
    W2->>W2: Replay: yield agent.run() → cached ✅
    W2->>W2: Replay: yield notify() → cached ✅
    W2->>W2: Resume: when_any() → event arrived!
    W2->>W2: yield execute_fraud_action() ✅
    Note over W2: Workflow completes normally! 🎉
```

1. Start a high-risk workflow → reaches "Awaiting analyst review"
2. `taskkill /F /IM python.exe` — kill all Python processes
3. `uv run python worker.py` — restart the worker
4. Submit analyst decision via UI
5. **Workflow completes normally** — DTS replayed the orchestration from its event log ✅

---

## 🔧 Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | Required |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Model deployment name | `gpt-4o` |
| `MCP_SERVER_URI` | MCP server URL | `http://localhost:8000/mcp` |
| `DTS_ENDPOINT` | DTS endpoint (local or Azure) | `http://localhost:8080` |
| `DTS_TASKHUB` | DTS task hub name | `default` |
| `ANALYST_APPROVAL_TIMEOUT_HOURS` | HITL timeout | `72` |
| `MAX_REVIEW_ATTEMPTS` | Max reject → re-investigate cycles | `3` |
| `EVENT_PRODUCER_ENABLED` | Enable Layer 1 event producer | `true` |
| `EVENT_INTERVAL_SECONDS` | Seconds between telemetry events | `3` |
| `BACKEND_OBSERVABILITY` | Enable Application Insights | `false` |

---

## 📐 Production Deployment

For Azure Container Apps deployment topology, security with Managed Identity, KEDA scaling, and cost estimation, see:

👉 **[PRODUCTION_ARCHITECTURE.md](PRODUCTION_ARCHITECTURE.md)**

---

*Copyright (c) Microsoft. All rights reserved.*
