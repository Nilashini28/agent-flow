export default function MemoryInspector({ runId }: { runId: string }) {
  // TODO: hook up to a /runs/{run_id}/memory endpoint once implemented
  return (
    <section>
      <h2>Memory Inspector</h2>
      <p>Short-term / episodic / long-term memory contents for run {runId}.</p>
    </section>
  )
}
