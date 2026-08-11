# 3-Minute Live-Failure Demo Script

1. **Set up** (10s): show the architecture diagram / gap-to-mechanism table.
2. **Start a run** (20s): `POST /runs` with a multi-step task; show it
   progressing through research → draft → verify in the dashboard timeline.
3. **Kill mid-run** (30s): stop the API process after step 2 completes.
   Restart it. Call `POST /runs/{id}/resume` — show step_index picks up
   from 3, not 1. This is the checkpointing proof.
4. **Trigger a risky action** (40s): run a task that calls the `file_write`
   tool. Show the sandbox policy either blocking an out-of-policy action
   (violations log) or the escalation model flagging it as
   REQUEST_APPROVAL before it executes.
5. **Approve/reject** (20s): use the dashboard's Escalation Panel to
   approve the pending action; show it then completes.
6. **Show the timeline** (30s): open `/runs/{id}/timeline` and walk through
   the structured event log — every decision point is inspectable.
7. **Close** (10s): tie back to the four-gap table — "each of these was a
   named failure mode in the brief; here's the mechanism and the proof."
