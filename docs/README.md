# AgentFlow — Reliability Case Study

## The problem

Autonomous agent workflows fail in production because reliability is
treated as an afterthought, not infrastructure: no recoverable state,
uncontrolled autonomy, reactive oversight, and limited observability.

## The mechanism, proven

| Gap | Mechanism | Proof |
|---|---|---|
| No recoverable state | Checkpointing engine | Kill process mid-run, resume, no redo — see `backend/tests/test_checkpointing.py` |
| Uncontrolled autonomy | Sandboxed execution boundary | Out-of-policy action blocked and logged — see `backend/tests/test_sandbox_violations.py` |
| Reactive oversight | Quantitative escalation scoring | 8+ synthetic scenarios escalate correctly — see `backend/tests/test_escalation_scenarios.py` |
| Limited observability | Structured event log + tracing | Full run timeline replayable via `/runs/{id}/timeline` |

## Running the demo

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
```

Then hit `POST /runs` with `{"task": "..."}`, kill the API mid-run, restart,
and call `POST /runs/{id}/resume` to show state was preserved.
