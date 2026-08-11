import { useEffect, useState } from 'react'
import { getEscalations, approveEscalation } from '../api/client'

export default function EscalationPanel({ runId }: { runId: string }) {
  const [pending, setPending] = useState<unknown>(null)

  useEffect(() => {
    getEscalations(runId).then((d) => setPending(d.pending)).catch(() => {})
  }, [runId])

  if (!pending) return null

  return (
    <section>
      <h2>Pending Escalation</h2>
      <pre>{JSON.stringify(pending, null, 2)}</pre>
      <button onClick={() => approveEscalation(runId)}>Approve</button>
    </section>
  )
}
