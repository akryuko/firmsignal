const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"

export async function startAnalysis(company: string) {
  const res = await fetch(`${API}/analyze`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ company }),
  })
  if (!res.ok) throw new Error(`Failed to start: ${res.statusText}`)
  return res.json() as Promise<{ run_id: string; company: string }>
}

export async function resumeRun(
  runId: string,
  approved: boolean,
  edits?: string | null,
) {
  const res = await fetch(`${API}/resume/${runId}`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ approved, edits: edits ?? null }),
  })
  if (!res.ok) throw new Error(`Resume failed: ${res.statusText}`)
  return res.json()
}

export function getStreamUrl(runId: string) {
  return `${API}/stream/${runId}`
}

export async function downloadPdf(payload: {
  company: string
  brief: string | null
  accountant: object | null
  skeptic: object | null
  sources: object[]
  ticker: string | null
  correction_note: string | null
}): Promise<Blob> {
  const res = await fetch(`${API}/pdf`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`PDF generation failed: ${res.statusText}`)
  return res.blob()
}