/**
 * AgentFlow API client — Stage 5 frontend (read-only).
 *
 * All requests go through Vite's /api proxy to http://localhost:8000 in dev,
 * and through a Vercel rewrite rule in production.
 *
 * Error handling contract:
 *   - Network/fetch failures throw NetworkError (subclass of Error).
 *   - Non-2xx responses throw ApiError with .status and .body.
 *   - Callers decide whether to surface the error or swallow it.
 */

const BASE_URL = "/api";

// ── Typed error classes ───────────────────────────────────────────────────────

export class NetworkError extends Error {
  constructor(message: string, public readonly cause?: unknown) {
    super(message);
    this.name = "NetworkError";
  }
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Internal fetch wrapper ────────────────────────────────────────────────────

async function apiFetch(path: string, init?: RequestInit): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, init);
  } catch (err) {
    // fetch() itself threw — backend unreachable, DNS failure, etc.
    throw new NetworkError(
      "Backend is unreachable. Check that the AgentFlow server is running.",
      err,
    );
  }

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => "(no body)");
    }
    throw new ApiError(res.status, body, `HTTP ${res.status} from ${path}`);
  }

  return res.json();
}

// ── Public API ────────────────────────────────────────────────────────────────

export interface RunCreated {
  run_id: string;
  status: string;
}

/**
 * POST /runs — start a new agent run with the given task string.
 * Returns { run_id, status } from the backend.
 */
export async function createRun(task: string): Promise<RunCreated> {
  return apiFetch("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task }),
  }) as Promise<RunCreated>;
}

export interface CheckpointEntry {
  checkpoint_id: string;
  step_index: number;
  status: string;
  timestamp: string;
}

/**
 * GET /runs/{id}/checkpoints — fetch saved checkpoints for a run.
 * Useful for verifying the Stage 2 persistence guarantee.
 */
export async function getRun(runId: string): Promise<CheckpointEntry[]> {
  const data = await apiFetch(`/runs/${runId}/checkpoints`);
  return ((data as { checkpoints?: CheckpointEntry[] }).checkpoints ?? []);
}

export interface TimelineEvent {
  event_type: string;
  timestamp: string;
  payload?: Record<string, unknown>;
}

/**
 * GET /runs/{id}/timeline — fetch the full event log for a run.
 * Polled every 800 ms by RunViewer to drive live progress display.
 */
export async function getTimeline(runId: string): Promise<TimelineEvent[]> {
  const data = await apiFetch(`/runs/${runId}/timeline`);
  return ((data as { events?: TimelineEvent[] }).events ?? []);
}
