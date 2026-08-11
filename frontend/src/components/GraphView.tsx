import { useEffect, useState } from 'react'
import { getCheckpoint } from '../api/client'

export default function GraphView({ runId }: { runId: string }) {
  const [checkpoint, setCheckpoint] = useState<unknown>(null)

  useEffect(() => {
    getCheckpoint(runId).then(setCheckpoint).catch(() => {})
  }, [runId])

  return (
    <section>
      <h2>Execution Graph</h2>
      {/* TODO: render nodes/edges with checkpoint markers, e.g. via react-flow */}
      <pre>{JSON.stringify(checkpoint, null, 2)}</pre>
    </section>
  )
}
