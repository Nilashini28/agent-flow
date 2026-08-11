import { useEffect, useState } from 'react'
import { getTimeline } from '../api/client'

export default function Timeline({ runId }: { runId: string }) {
  const [events, setEvents] = useState<any[]>([])

  useEffect(() => {
    getTimeline(runId).then((d) => setEvents(d.events || [])).catch(() => {})
  }, [runId])

  return (
    <section>
      <h2>Event Timeline</h2>
      <ul>
        {events.map((e, i) => (
          <li key={i}>
            {e.timestamp} — {e.event_type}
          </li>
        ))}
      </ul>
    </section>
  )
}
