import { useCallback, useEffect, useRef, useState } from "react";
import {
  NetworkError,
  TimelineEvent,
  createRun,
  getTimeline,
} from "../api/client";

// ── Types ─────────────────────────────────────────────────────────────────────

type RunStatus = "idle" | "running" | "completed" | "halted" | "failed";

// ── Constants ─────────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 800;

const NODES = ["research", "draft", "verify", "act"] as const;
type NodeName = (typeof NODES)[number];

/**
 * Map an event_type string to which node it belongs to.
 * "node_complete" events carry the node name inside their event_type
 * (e.g. "node_complete" with payload.node) or as suffixed strings.
 * We match against the stage-2 event log format:
 *   { event_type: "node_complete", payload: { node: "research" } }
 */
function nodeFromEvent(e: TimelineEvent): NodeName | null {
  const p = e.payload as { node?: string } | undefined;
  const nodeName = p?.node?.toLowerCase();
  if (nodeName && (NODES as readonly string[]).includes(nodeName)) {
    return nodeName as NodeName;
  }
  // Also handle flat event types like "research_complete" (forward compat).
  for (const n of NODES) {
    if (e.event_type.toLowerCase().includes(n)) return n;
  }
  return null;
}

function statusFromEvents(events: TimelineEvent[]): RunStatus {
  // Walk backwards — the most recent status-bearing event wins.
  for (let i = events.length - 1; i >= 0; i--) {
    const et = events[i].event_type.toLowerCase();
    const payload = events[i].payload as { status?: string } | undefined;
    const s = payload?.status?.toLowerCase() ?? et;
    if (s === "completed") return "completed";
    if (s === "halted" || et === "run_halted") return "halted";
    if (s === "failed" || et === "run_failed") return "failed";
    if (s === "running" || et === "node_start" || et === "node_complete")
      return "running";
  }
  return "idle";
}

// ── Styles ────────────────────────────────────────────────────────────────────

const S = {
  root: {
    fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
    background: "#0f1117",
    minHeight: "100vh",
    color: "#e8eaf0",
    padding: "2.5rem",
    boxSizing: "border-box" as const,
  },
  heading: {
    fontSize: "2.2rem",
    fontWeight: 700,
    letterSpacing: "-0.02em",
    margin: "0 0 0.3rem",
    background: "linear-gradient(135deg, #818cf8 0%, #38bdf8 100%)",
    WebkitBackgroundClip: "text" as const,
    WebkitTextFillColor: "transparent" as const,
  },
  subheading: {
    fontSize: "1rem",
    color: "#6b7280",
    margin: "0 0 2.5rem",
  },
  card: {
    background: "#1a1d2e",
    border: "1px solid #2d3148",
    borderRadius: "12px",
    padding: "1.5rem",
    marginBottom: "1.5rem",
  },
  inputRow: {
    display: "flex",
    gap: "0.75rem",
    alignItems: "center",
  },
  input: {
    flex: 1,
    fontSize: "1.1rem",
    padding: "0.7rem 1rem",
    background: "#0f1117",
    border: "1.5px solid #374151",
    borderRadius: "8px",
    color: "#e8eaf0",
    outline: "none",
    transition: "border-color 0.15s",
  },
  button: {
    padding: "0.7rem 1.6rem",
    fontSize: "1.05rem",
    fontWeight: 600,
    background: "linear-gradient(135deg, #6366f1, #38bdf8)",
    color: "#fff",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
    transition: "opacity 0.15s",
  },
  buttonDisabled: {
    opacity: 0.5,
    cursor: "not-allowed" as const,
  },
  offlineBanner: {
    display: "flex",
    alignItems: "center",
    gap: "0.6rem",
    padding: "0.8rem 1.2rem",
    background: "#450a0a",
    border: "1px solid #7f1d1d",
    borderRadius: "8px",
    color: "#fca5a5",
    fontSize: "1rem",
    marginBottom: "1.5rem",
  },
  // ── Progress rail ──────────────────────────────────────────────────────────
  rail: {
    display: "flex",
    alignItems: "center",
    gap: 0,
    margin: "0 0 2rem",
  },
  railNode: (active: boolean, done: boolean): React.CSSProperties => ({
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "0.5rem",
    flex: 1,
  }),
  railCircle: (active: boolean, done: boolean): React.CSSProperties => ({
    width: "48px",
    height: "48px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "1.4rem",
    border: `2.5px solid ${done ? "#22d3ee" : active ? "#818cf8" : "#374151"}`,
    background: done ? "#164e63" : active ? "#1e1b4b" : "#1a1d2e",
    color: done ? "#22d3ee" : active ? "#818cf8" : "#4b5563",
    transition: "all 0.3s ease",
    boxShadow: done
      ? "0 0 16px rgba(34,211,238,0.35)"
      : active
        ? "0 0 16px rgba(129,140,248,0.35)"
        : "none",
  }),
  railLabel: (active: boolean, done: boolean): React.CSSProperties => ({
    fontSize: "0.85rem",
    fontWeight: done || active ? 600 : 400,
    color: done ? "#22d3ee" : active ? "#818cf8" : "#4b5563",
    textTransform: "uppercase" as const,
    letterSpacing: "0.06em",
    transition: "color 0.3s",
  }),
  railConnector: (done: boolean): React.CSSProperties => ({
    flex: 1,
    height: "2.5px",
    background: done
      ? "linear-gradient(90deg, #22d3ee, #38bdf8)"
      : "#2d3148",
    transition: "background 0.4s",
    margin: "0 4px",
    marginBottom: "1.5rem", // align with circles
  }),
  // ── Status badge ───────────────────────────────────────────────────────────
  statusRow: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    marginBottom: "1.5rem",
  },
  statusLabel: {
    fontSize: "0.9rem",
    color: "#6b7280",
    fontWeight: 500,
  },
  badge: (status: RunStatus): React.CSSProperties => {
    const map: Record<RunStatus, { bg: string; color: string; glow: string }> = {
      idle:      { bg: "#1f2937", color: "#9ca3af", glow: "none" },
      running:   { bg: "#1e1b4b", color: "#818cf8", glow: "0 0 12px rgba(129,140,248,0.4)" },
      completed: { bg: "#052e16", color: "#4ade80", glow: "0 0 12px rgba(74,222,128,0.4)" },
      halted:    { bg: "#450a0a", color: "#f87171", glow: "0 0 12px rgba(248,113,113,0.4)" },
      failed:    { bg: "#431407", color: "#fb923c", glow: "0 0 12px rgba(251,146,60,0.4)" },
    };
    const { bg, color, glow } = map[status];
    return {
      padding: "0.3rem 0.9rem",
      borderRadius: "999px",
      background: bg,
      color,
      fontWeight: 700,
      fontSize: "0.9rem",
      letterSpacing: "0.06em",
      textTransform: "uppercase" as const,
      boxShadow: glow,
      border: `1px solid ${color}44`,
      transition: "all 0.3s",
    };
  },
  // ── Run ID chip ────────────────────────────────────────────────────────────
  runIdChip: {
    padding: "0.25rem 0.7rem",
    background: "#0f1117",
    border: "1px solid #2d3148",
    borderRadius: "6px",
    fontFamily: "monospace",
    fontSize: "0.8rem",
    color: "#6b7280",
  },
  // ── Timeline ───────────────────────────────────────────────────────────────
  timelineHeader: {
    fontSize: "0.85rem",
    fontWeight: 600,
    color: "#4b5563",
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
    marginBottom: "0.75rem",
  },
  timelineScroll: {
    height: "280px",
    overflowY: "auto" as const,
    display: "flex",
    flexDirection: "column" as const,
    gap: "2px",
  },
  timelineRow: (highlight: boolean): React.CSSProperties => ({
    display: "flex",
    gap: "0.75rem",
    padding: "0.45rem 0.6rem",
    borderRadius: "6px",
    background: highlight ? "#1e1b4b" : "transparent",
    alignItems: "baseline",
    transition: "background 0.2s",
  }),
  timelineTs: {
    fontSize: "0.75rem",
    fontFamily: "monospace",
    color: "#4b5563",
    flexShrink: 0,
    minWidth: "80px",
  },
  timelineType: (etype: string): React.CSSProperties => {
    const c =
      etype.includes("violation")
        ? "#f87171"
        : etype.includes("complete")
          ? "#4ade80"
          : etype.includes("start")
            ? "#818cf8"
            : etype.includes("retry") || etype.includes("backoff")
              ? "#fb923c"
              : etype.includes("sandbox")
                ? "#38bdf8"
                : "#9ca3af";
    return { fontSize: "0.9rem", fontWeight: 500, color: c };
  },
};

// ── Node icons ─────────────────────────────────────────────────────────────────

const NODE_ICONS: Record<NodeName, string> = {
  research: "🔍",
  draft: "✏️",
  verify: "🛡️",
  act: "⚡",
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function RunViewer() {
  const [task, setTask] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [completedNodes, setCompletedNodes] = useState<Set<NodeName>>(new Set());
  const [activeNode, setActiveNode] = useState<NodeName | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [offline, setOffline] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-scroll timeline to bottom whenever events change.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events]);

  // Derive progress state from event list.
  const applyEvents = useCallback((evts: TimelineEvent[]) => {
    setEvents(evts);
    setStatus(statusFromEvents(evts));

    const done = new Set<NodeName>();
    let lastActive: NodeName | null = null;

    for (const e of evts) {
      const node = nodeFromEvent(e);
      if (!node) continue;
      if (e.event_type.toLowerCase().includes("complete")) {
        done.add(node);
        lastActive = null;
      } else if (e.event_type.toLowerCase().includes("start")) {
        lastActive = node;
      }
    }
    setCompletedNodes(done);
    setActiveNode(lastActive);
  }, []);

  // Start polling when we have a run ID.
  useEffect(() => {
    if (!runId) return;

    let alive = true;

    const poll = async () => {
      try {
        const evts = await getTimeline(runId);
        if (!alive) return;
        setOffline(false);
        applyEvents(evts);

        // Stop polling once terminal state reached.
        const s = statusFromEvents(evts);
        if (s === "completed" || s === "halted" || s === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch (err) {
        if (!alive) return;
        if (err instanceof NetworkError) {
          setOffline(true);
        }
        // ApiError (e.g. 404 run not found yet) — keep polling silently.
      }
    };

    poll(); // immediate first fetch
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      alive = false;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [runId, applyEvents]);

  const handleStart = async () => {
    if (!task.trim()) return;
    setStarting(true);
    setError(null);
    setEvents([]);
    setCompletedNodes(new Set());
    setActiveNode(null);
    setStatus("idle");
    setOffline(false);

    try {
      const result = await createRun(task.trim());
      setRunId(result.run_id);
      setStatus("running");
    } catch (err) {
      if (err instanceof NetworkError) {
        setOffline(true);
        setError("Could not reach the backend. Is the AgentFlow server running?");
      } else {
        setError(`Failed to start run: ${(err as Error).message}`);
      }
    } finally {
      setStarting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleStart();
  };

  const resetRun = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setRunId(null);
    setEvents([]);
    setCompletedNodes(new Set());
    setActiveNode(null);
    setStatus("idle");
    setOffline(false);
    setError(null);
    setTask("");
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div style={S.root}>
      {/* Header */}
      <h1 style={S.heading}>AgentFlow</h1>
      <p style={S.subheading}>
        Reliability control plane · Live run viewer · Stages 1–4
      </p>

      {/* Offline banner */}
      {offline && (
        <div style={S.offlineBanner}>
          <span>⚠️</span>
          <span>
            <strong>Backend offline</strong> — cannot reach AgentFlow server.
            Retrying automatically every {POLL_INTERVAL_MS}ms…
          </span>
        </div>
      )}

      {/* Error message (non-offline errors) */}
      {error && !offline && (
        <div style={{ ...S.offlineBanner, marginBottom: "1.5rem" }}>
          <span>❌</span>
          <span>{error}</span>
        </div>
      )}

      {/* Input card */}
      <div style={S.card}>
        <div style={S.inputRow}>
          <input
            style={S.input}
            type="text"
            placeholder="Enter a task for the agent…"
            value={task}
            onChange={(e) => setTask(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={starting || !!runId}
            aria-label="Task input"
          />
          {!runId ? (
            <button
              style={{
                ...S.button,
                ...(starting || !task.trim() ? S.buttonDisabled : {}),
              }}
              onClick={handleStart}
              disabled={starting || !task.trim()}
              aria-label="Start run"
            >
              {starting ? "Starting…" : "▶ Start run"}
            </button>
          ) : (
            <button
              style={{ ...S.button, background: "#374151" }}
              onClick={resetRun}
              aria-label="New run"
            >
              ↺ New run
            </button>
          )}
        </div>
      </div>

      {/* Run content — only shown once a run exists */}
      {runId && (
        <>
          {/* Status row */}
          <div style={S.statusRow}>
            <span style={S.statusLabel}>Status</span>
            <span style={S.badge(status)}>{status}</span>
            <span style={S.runIdChip}>{runId}</span>
          </div>

          {/* Progress rail */}
          <div style={S.rail}>
            {NODES.map((node, i) => {
              const done = completedNodes.has(node);
              const active = activeNode === node;
              const connectorDone =
                i < NODES.length - 1 && completedNodes.has(NODES[i + 1]);

              return (
                <div
                  key={node}
                  style={{ display: "flex", alignItems: "center", flex: 1 }}
                >
                  <div style={S.railNode(active, done)}>
                    <div style={S.railCircle(active, done)}>
                      {done ? "✓" : NODE_ICONS[node]}
                    </div>
                    <span style={S.railLabel(active, done)}>{node}</span>
                  </div>
                  {i < NODES.length - 1 && (
                    <div style={S.railConnector(connectorDone)} />
                  )}
                </div>
              );
            })}
          </div>

          {/* Timeline */}
          <div style={S.card}>
            <div style={S.timelineHeader}>
              Event timeline
              {events.length > 0 && (
                <span style={{ marginLeft: "0.5rem", fontWeight: 400, color: "#374151" }}>
                  ({events.length} events)
                </span>
              )}
            </div>
            {events.length === 0 ? (
              <div style={{ color: "#4b5563", fontSize: "0.95rem", padding: "0.5rem 0" }}>
                Waiting for events…
              </div>
            ) : (
              <div style={S.timelineScroll} ref={scrollRef}>
                {events.map((e, i) => {
                  const ts = new Date(e.timestamp);
                  const timeStr = ts.toLocaleTimeString("en-US", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  });
                  const isHighlight =
                    e.event_type.includes("complete") ||
                    e.event_type.includes("violation");
                  return (
                    <div key={i} style={S.timelineRow(isHighlight)}>
                      <span style={S.timelineTs}>{timeStr}</span>
                      <span style={S.timelineType(e.event_type)}>
                        {e.event_type}
                      </span>
                      {e.payload?.node != null && (
                        <span style={{ color: "#4b5563", fontSize: "0.82rem" }}>
                          · {String(e.payload.node)}
                        </span>
                      )}
                      {e.payload?.risk_score != null && (
                        <span style={{ color: "#fb923c", fontSize: "0.82rem" }}>
                          · risk {Number(e.payload.risk_score).toFixed(2)}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}

      {/* Empty idle state hint */}
      {!runId && !error && !offline && (
        <div
          style={{
            textAlign: "center",
            color: "#374151",
            fontSize: "1rem",
            marginTop: "3rem",
          }}
        >
          Enter a task above to watch AgentFlow run live →
          research · draft · verify · act
        </div>
      )}
    </div>
  );
}
