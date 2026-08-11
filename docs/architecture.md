# AgentFlow Architecture

## Control plane, not a replacement model

AgentFlow wraps any agent/LLM with four subsystems. The underlying model
(e.g. Claude via LangGraph nodes) is untouched — reliability is added
around it.

## Subsystems

### 1. Checkpointing (`backend/app/core/checkpointing`)
LangGraph's checkpointer persists state after every node transition, keyed
by `thread_id` (= `run_id`). Recovery re-invokes the compiled graph with
`input=None`, which resumes from the last saved checkpoint instead of
restarting.

### 2. Execution boundary / sandbox (`backend/app/core/sandbox`)
Every tool call is looked up against a `ToolPolicy` (risk tier, network
access, filesystem access, resource limits, reversibility). Execution runs
via `run_sandboxed`, which dispatches to Docker (local/full-Docker hosts)
or a resource-limited subprocess (free-tier hosts without a Docker socket)
behind the same interface.

### 3. Escalation scoring (`backend/app/core/escalation`)
A transparent weighted-sum function over four signals (reversibility, tool
risk tier, inverted confidence, historical failure rate) produces a 0-1
risk score, mapped to CONTINUE / REQUEST_APPROVAL / HALT via configurable
thresholds.

### 4. Observability + memory (`backend/app/observability`, `backend/app/core/memory`)
Every event (node start, escalation decision, sandbox violation, memory
read/write) is logged as a structured record, replayable per run. Memory
is split into three tiers: short-term (in-process/Redis scratchpad),
episodic (Chroma collection of past steps), and long-term (a second Chroma
collection by default; swappable for Pinecone at scale via the same
add/query interface).

## Request flow

1. `POST /runs` creates a run, compiles the graph, and invokes it.
2. Each node logs an event and, if it's a `verify` step, computes a risk
   score and routes to `act`, or ends the graph pending approval/halt.
3. `POST /runs/{id}/resume` re-invokes the graph from the last checkpoint.
4. `GET /runs/{id}/timeline` replays the full structured event history.

## Zero-cost deployment mapping

| Component | Local dev | Zero-cost hosted |
|---|---|---|
| API | uvicorn | Render / Fly.io free web service |
| DB | Postgres via docker-compose | Neon / Supabase free Postgres |
| Redis | Redis via docker-compose | Upstash free tier |
| Chroma | Embedded, local disk | Embedded, persisted on host's disk (or Chroma Cloud free tier) |
| Sandbox | Docker (`SANDBOX_MODE=docker`) | Subprocess fallback (`SANDBOX_MODE=subprocess`) |
| Frontend | Vite dev server | Vercel / Netlify free tier |
