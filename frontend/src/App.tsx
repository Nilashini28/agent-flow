import RunViewer from "./components/RunViewer";

/**
 * AgentFlow — Stage 5 frontend entry point.
 *
 * For this stage, App renders only the RunViewer: a live read-only
 * view of an agent run progressing through research → draft → verify → act.
 *
 * Approve/reject controls, memory inspector, and multi-run comparison
 * are deferred to later stages (they depend on backend Stages 5+).
 */
export default function App() {
  return <RunViewer />;
}
