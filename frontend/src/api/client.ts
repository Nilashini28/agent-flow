const BASE_URL = '/api'

export async function createRun(task: string) {
  const res = await fetch(`${BASE_URL}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task }),
  })
  return res.json()
}

export async function getCheckpoint(runId: string) {
  const res = await fetch(`${BASE_URL}/runs/${runId}/checkpoints`)
  return res.json()
}

export async function getTimeline(runId: string) {
  const res = await fetch(`${BASE_URL}/runs/${runId}/timeline`)
  return res.json()
}

export async function getEscalations(runId: string) {
  const res = await fetch(`${BASE_URL}/runs/${runId}/escalations`)
  return res.json()
}

export async function approveEscalation(runId: string) {
  const res = await fetch(`${BASE_URL}/runs/${runId}/escalations/approve`, { method: 'POST' })
  return res.json()
}
