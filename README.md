# AgentFlow

> **A reliability control plane for autonomous AI agents.**
> AgentFlow wraps any LLM-based agent with hard guarantees: crash recovery,
> risk-gated execution, quantitative escalation scoring, and a full
> observability audit trail — without replacing the underlying model.

---

## The Problem We Are Solving

Modern AI agents fail in production for four structural reasons, none of which
are solved by making the model smarter:

| Production Failure | What Actually Happens |
|---|---|
| **No recoverable state** | A 4-hour agent run crashes at step 3. Everything restarts from zero. Cost doubles, trust collapses. |
| **Uncontrolled autonomy** | The agent decides to `DROP TABLE users` or `rm -rf /`. There is no guardrail between "plan approved" and "action executed". |
| **Reactive oversight** | A human only sees a problem *after* the agent acts. There is no signal to route borderline decisions to a human *before* they execute. |
| **No observability** | When something goes wrong, you have no structured record of what the agent decided, why, and in what order. Debugging is forensic archaeology. |

**AgentFlow's answer:** treat reliability as infrastructure, not an afterthought.
Build a graph-native execution harness where every node transition is
checkpointed, every output is risk-scored, every borderline decision is
escalated, and every event is structured and replayable.

---

## Solution Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AgentFlow System                              │
│                                                                       │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐   │
│  │ research │───▶│  draft   │───▶│  verify  │───▶│     act      │   │
│  │   node   │    │   node   │    │   node   │    │    node      │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────┬───────┘   │
│       │               │               │                  │           │
│       ▼               ▼               ▼                  ▼           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              SQLite Checkpoint Store (LangGraph)             │    │
│  │         State persisted after EVERY node transition          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                          │                            │
│                              risk_score > threshold?                  │
│                              ┌───────────┴───────────┐               │
│                           ≤ 0.35                  0.35–0.70  > 0.70  │
│                           CONTINUE            REQUEST_APPROVAL  HALT  │
│                              │                    │              │    │
│                           act node           Human Review    Stop     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow Per Run

```
Client → POST /runs  ─────────────────────────────────────────────────┐
                                                                        │
AgentState = {                                                          │
  run_id, task, step_index,                                             │
  history[], last_output,                                               │
  risk_score, status, error                                             │
}                                                                       │
                                                                        ▼
research_step(state) → { last_output, tool_calls, step_index: 1 }     │
         ↓ [CHECKPOINT WRITTEN]                                         │
draft_step(state) → { last_output, step_index: 2 }                    │
         ↓ [CHECKPOINT WRITTEN]                                         │
verify_step(state) → { risk_score, violations, step_index: 3 }        │
         ↓ [CHECKPOINT WRITTEN]                                         │
         ↓                                                              │
    route_after_verify()                                                │
         ├─ risk ≤ 0.35  → act_step → status="completed"              │
         ├─ risk ≤ 0.70  → END (awaiting human approval)              │
         └─ risk > 0.70  → END (halted, too risky)                    │
                                                                        │
← Response: { run_id, step_index: 4, status, history[], ... } ────────┘
```

### Crash Recovery Flow

```
PROCESS 1:  research ✓ → draft ✓ → [KILL -9 / crash]
                                          │
                                    SQLite on disk:
                                    step_index=2
                                    history=['research','draft']
                                    next=['verify']
                                          │
PROCESS 2:  (new Python process, same DB)
            POST /runs/{id}/resume
            → verify ✓ → act ✓ → status="completed"
            step_index advances 2→4, zero work repeated
```

---

## Repository Layout

```
agentflow/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entrypoint (8 live routes)
│   │   ├── config.py                  # Env-driven settings (pydantic-settings)
│   │   ├── api/routes/
│   │   │   ├── runs.py                # POST /runs, POST /runs/{id}/resume
│   │   │   ├── checkpoints.py         # GET /runs/{id}/checkpoints
│   │   │   ├── escalations.py         # GET/POST /runs/{id}/escalations/*
│   │   │   └── traces.py              # GET /runs/{id}/timeline
│   │   └── core/
│   │       ├── graph/
│   │       │   ├── schemas.py         # AgentState TypedDict (shared state shape)
│   │       │   ├── nodes.py           # research, draft, verify, act node fns
│   │       │   └── state_graph.py     # LangGraph wiring + checkpointer attach
│   │       ├── checkpointing/
│   │       │   ├── checkpointer.py    # SqliteSaver setup (thread-safe)
│   │       │   └── recovery.py        # resume_run, get_latest_checkpoint,
│   │       │                          #   get_checkpoint_history + typed errors
│   │       ├── escalation/
│   │       │   ├── scoring.py         # risk_score computation (weighted signals)
│   │       │   └── thresholds.py      # CONTINUE / REQUEST_APPROVAL / HALT routing
│   │       ├── sandbox/               # [Stage 4] sandboxed act execution
│   │       └── memory/                # [Stage 10] cross-run vector memory
│   ├── tests/
│   │   └── test_checkpointing.py      # 8 tests incl. real crash simulation
│   ├── scripts/
│   │   └── verify_checkpointing.py    # 2-invocation human crash-recovery proof
│   ├── agentflow_checkpoints.db       # SQLite checkpoint store (auto-created)
│   └── requirements.txt
├── frontend/                          # [Stage 9] React/TS dashboard
├── infra/                             # [Stage 11] Docker + cloud deploy
└── docs/
    ├── README.md
    └── architecture.md
```

---

## Stage Progress

### ✅ Stage 1 — Core Graph & State Layer

**Goal:** Build the 4-node agent pipeline with deterministic routing and
no placeholder logic — every function does real work that a reviewer can verify.

**What was built:**

#### `backend/app/core/graph/schemas.py` — Shared State Contract
```python
class AgentState(TypedDict, total=False):
    run_id: str          # UUID, used as thread_id in the checkpoint store
    task: str            # Natural-language goal driving the run
    step_index: int      # Monotonically incremented after every node (0 → 4)
    history: list[dict]  # Append-only per-node output record
    last_output: str     # Most recent node's primary text output
    tool_calls: list     # Every tool invocation made this run
    risk_score: float    # [0.0–1.0] computed by verify_step
    status: Literal["running","awaiting_approval","halted","completed","failed"]
    error: str | None    # Set by any node's except block
    retry_count: int     # [Stage 3] exponential back-off counter
```

#### `backend/app/core/graph/nodes.py` — Four Real Node Functions

| Node | Real Logic | Output Example |
|---|---|---|
| `research_step` | Simulated retrieval + LLM keyword extraction over the task | `RESEARCH \| task='...' \| retrieval_score=0.82 \| keywords=[...]` |
| `draft_step` | Transforms research into a numbered 3-step action plan | `DRAFT \| plan_steps=3 \| Step 1: Process 'revenue' sub-task \| ...` |
| `verify_step` | Rule-based safety checks + escalation scorer → `risk_score` | `risk_score=0.14`, `violations=[]` |
| `act_step` | Executes each plan step, marks run `completed` | `ACT \| steps_executed=3 \| EXECUTED: Step 1 \| ...` |

Every node follows the same contract:
1. Log entry via `log_event()`
2. Do real work (stub LLM, real keyword extraction)
3. Append to `history[]`
4. Return a **partial** `AgentState` dict — LangGraph merges, never replaces
5. On exception: return `status="failed"`, `error=str(exc)`

#### `backend/app/core/graph/state_graph.py` — Graph Wiring

```
research ──→ draft ──→ verify ──→ [route_after_verify]
                                        │
                           risk_score ≤ 0.35 → act → END  (COMPLETED)
                           risk_score ≤ 0.70 → END         (AWAITING APPROVAL)
                           risk_score > 0.70 → END         (HALTED)
```

**Routing thresholds** (configurable via `.env`):
- `escalation_continue_max = 0.35` — safe to execute
- `escalation_approve_max  = 0.70` — needs human sign-off
- Above 0.70 → halt immediately, do not execute

**Stage 1 verification passed:**
```
Scenario A: status=completed, step_index=4, last_output starts with "ACT" ✅
Scenario B: risk_score > 0.35, act_step NOT reached, run halted ✅
py_compile: schemas.py, nodes.py, state_graph.py → exit 0 ✅
```

---

### ✅ Stage 2 — Checkpointing Subsystem

**Goal:** Prove that a hard process kill mid-run loses zero state — the single
most important reliability guarantee in the whole system.

**What was built:**

#### Thread-Safety Fix — `checkpointer.py`

**Problem found:** SQLite's default `check_same_thread=True` raises
`ProgrammingError` when any thread other than the creator uses the connection.
FastAPI's `ThreadPoolExecutor` assigns each request to a **different** thread —
so every request after the first would fail in a multi-user deployment.

**Fix applied:**
```python
conn = sqlite3.connect("agentflow_checkpoints.db", check_same_thread=False)
```
Safe because SQLite serialises writes internally and `SqliteSaver` wraps
every write in its own cursor/transaction.

**Two factories provided:**
- `get_checkpointer()` — process-wide singleton (FastAPI production use)
- `get_checkpointer_for_path(db_path)` — fresh independent instance (tests/scripts
  that must simulate a new process reading from the same on-disk DB)

#### Typed Error Model — `recovery.py`

Two failure cases, two distinct exceptions — callers never see a bare `KeyError`:

```python
class RunNotFoundError(CheckpointError):
    # No checkpoint at all for this run_id → HTTP 404 (Stage 7)

class RunAlreadyCompletedError(CheckpointError):
    # Checkpoint exists but graph is at END → HTTP 409 (Stage 7)
```

**Public API:**
```python
resume_run(run_id)              # Resume from last checkpoint; raises typed errors
get_latest_checkpoint(run_id)   # Read-only probe; returns None if not found
get_checkpoint_history(run_id)  # ALL checkpoints oldest-first (Stage 9 timeline)
```

#### Test Suite — `tests/test_checkpointing.py`

8 tests, 0 mocks, 1.73s total:

| Test | What it proves |
|---|---|
| `test_resume_continues_from_last_checkpoint` | **Core crash-sim**: stream 2 nodes, `del graph1`, new graph from same DB, resume → `step_index` 2→4, history intact, `status=completed` |
| `test_resume_raises_run_not_found_for_unknown_id` | `RunNotFoundError` raised for unknown run_id |
| `test_resume_raises_already_completed_for_finished_run` | `RunAlreadyCompletedError` raised for terminal run |
| `test_get_latest_checkpoint_returns_none_for_unknown` | Returns `None`, never raises |
| `test_get_latest_checkpoint_returns_state_dict` | Returns `dict` with `status=completed` |
| `test_get_checkpoint_history_returns_ordered_entries` | ≥ 5 entries, ascending step order |
| `test_get_checkpoint_history_empty_for_unknown` | Returns `[]` for unknown run |
| `test_sqlite_rows_exist_after_run` | **Direct DB inspection**: ≥ 5 rows in `checkpoints` table |

#### Manual Crash Proof — `scripts/verify_checkpointing.py`

Run in two separate terminal processes:

```bash
# Terminal 1 — starts a run and crashes after 2 nodes
python scripts/verify_checkpointing.py start

# Terminal 2 — fresh process, same DB, resumes
python scripts/verify_checkpointing.py resume <thread_id>
```

**Actual output (live run):**

```
=== FIRST INVOCATION ===
  STARTING step_index = 0
  [node=research]  step_index: 1  history: ['research']
  [node=draft]     step_index: 2  history: ['research', 'draft']
CRASH: exiting after 2 nodes    LAST SEEN step_index = 2

=== SECOND INVOCATION (brand new Python object, same DB) ===
  STARTING step_index (from checkpoint) = 2
  PENDING nodes = ('verify',)
  [RESUME...]
  step_index before: 2  →  step_index after: 4
  history: ['research', 'draft', 'verify', 'act']
  [PASS] status = 'completed'
  [PASS] step_index advanced (no restart from 0)
  [PASS] no duplicate history entries
  Stage-2 VERIFIED: checkpoint survived the simulated crash.
```

**SQLite confirmed:** 6 rows for the verification thread (steps −1 to 4),
queried directly via `sqlite3` — not trusting the API call alone.

---

## Live API (Running Now)

**Server:** `http://localhost:8000`  
**Interactive docs:** `http://localhost:8000/docs`

```bash
# Start the server
cd backend
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoints

```
POST   /runs                           Start a new agent run
POST   /runs/{run_id}/resume           Resume a crashed/interrupted run
GET    /runs/{run_id}/checkpoints      Get latest persisted AgentState
GET    /runs/{run_id}/timeline         Full structured event audit trail
GET    /runs/{run_id}/escalations      View pending human-approval requests
POST   /runs/{run_id}/escalations/approve
POST   /runs/{run_id}/escalations/reject
GET    /health                         Server health check
```

### Example: Start a run

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"task": "Analyse quarterly revenue and identify growth opportunities"}'
```

```json
{
  "run_id": "1bdbd844-b6f3-4908-a0de-14356fcb82d5",
  "result": {
    "step_index": 4,
    "status": "completed",
    "risk_score": 0.14,
    "history": [
      {"node": "research", "step_index": 0, ...},
      {"node": "draft",    "step_index": 1, ...},
      {"node": "verify",   "step_index": 2, "risk_score": 0.14, "violations": []},
      {"node": "act",      "step_index": 3, "steps_executed": 3}
    ]
  }
}
```

### Example: Crash recovery

```bash
# 1. Start a run (note the run_id)
curl -X POST http://localhost:8000/runs -d '{"task": "..."}'

# 2. Kill the server mid-run (Ctrl+C)
# 3. Restart the server
# 4. Resume — zero work redone
curl -X POST http://localhost:8000/runs/{run_id}/resume
```

---

## 11-Stage Build Plan

| Stage | Name | Status | What It Adds |
|---|---|---|---|
| **1** | Core Graph & State | ✅ **Done** | 4-node pipeline, risk routing, stub LLM |
| **2** | Checkpointing Subsystem | ✅ **Done** | Crash recovery, typed errors, history API |
| 3 | Retry Logic | ⬜ Pending | Exponential back-off, `retry_count` field |
| 4 | Sandbox Isolation | ⬜ Pending | `act_step` runs in subprocess/Docker container |
| 5 | Escalation Hooks | ⬜ Pending | Slack / human-in-the-loop approval flow |
| 6 | Real LLM Calls | ⬜ Pending | Anthropic/OpenAI replaces stub LLM |
| 7 | REST API Hardening | ⬜ Pending | Proper HTTP 404/409, request validation, auth |
| 8 | Observability | ⬜ Pending | OpenTelemetry traces, Postgres checkpoint store |
| 9 | Dashboard | ⬜ Pending | React/TS frontend, checkpoint timeline, run list |
| 10 | Memory Tiers | ⬜ Pending | Chroma vector store for cross-run context |
| 11 | Infra & Deployment | ⬜ Pending | Docker Compose, cloud deploy, load testing |

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **LangGraph StateGraph** | Graph-native checkpointing is built-in — every node transition is a save point with zero extra code |
| **TypedDict state (total=False)** | Nodes return *partial* updates; LangGraph merges them. Prevents accidental state wipes |
| **SQLite for dev, Postgres for prod** | Zero infra locally; swap `SqliteSaver` → `AsyncPostgresSaver` in Stage 8 with no code changes |
| **`check_same_thread=False`** | Required for FastAPI's multi-threaded request handling — documented with full rationale in `checkpointer.py` |
| **Typed exceptions over bare errors** | `RunNotFoundError` vs `RunAlreadyCompletedError` gives the API layer (Stage 7) clean HTTP 404 vs 409 mapping |
| **Stub LLM with real keyword extraction** | Proves infrastructure (routing, checkpointing) is correct before spending API credits in Stage 6 |

---

## Running Tests

```bash
cd backend

# Stage 1 verification script
venv\Scripts\python.exe verify_stage1.py

# Stage 2 test suite (8 tests)
venv\Scripts\python.exe -m pytest tests/test_checkpointing.py -v

# Stage 2 manual crash proof (run twice)
venv\Scripts\python.exe scripts/verify_checkpointing.py start
venv\Scripts\python.exe scripts/verify_checkpointing.py resume <thread_id>
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) (StateGraph + SqliteSaver) |
| Backend API | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| State schema | Python `TypedDict` (Pydantic-compatible) |
| Checkpoint store | SQLite (dev) → PostgreSQL (Stage 8 prod) |
| Risk scoring | Custom weighted signal model (`core/escalation/`) |
| LLM (current) | Deterministic stub (Stage 6: Anthropic Claude / OpenAI GPT-4) |
| Testing | pytest 9.x, no mocks for crash simulation |
| Frontend | React + TypeScript (Stage 9) |
| Observability | OpenTelemetry (Stage 8) |
| Infra | Docker Compose + cloud (Stage 11) |
# agent-flow
