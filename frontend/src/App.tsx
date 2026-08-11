import { useState } from 'react'
import GraphView from './components/GraphView'
import EscalationPanel from './components/EscalationPanel'
import Timeline from './components/Timeline'
import MemoryInspector from './components/MemoryInspector'

export default function App() {
  const [runId, setRunId] = useState<string | null>(null)

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '1.5rem' }}>
      <h1>AgentFlow Dashboard</h1>
      <p>Reliability control plane: checkpoints, sandbox, escalation, tracing.</p>

      {!runId && (
        <button onClick={() => setRunId('demo-run-placeholder')}>
          Start demo run
        </button>
      )}

      {runId && (
        <>
          <GraphView runId={runId} />
          <EscalationPanel runId={runId} />
          <Timeline runId={runId} />
          <MemoryInspector runId={runId} />
        </>
      )}
    </div>
  )
}
