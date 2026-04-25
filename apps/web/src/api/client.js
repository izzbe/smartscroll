// All calls go to /api, proxied to http://localhost:8000 by Vite in dev.

export async function uploadPdf(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/pdfs/upload', { method: 'POST', body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || 'Upload failed')
  }
  return res.json()
}

export async function getPdf(pdfId) {
  const res = await fetch(`/api/pdfs/${pdfId}`)
  if (!res.ok) throw new Error('Failed to get PDF status')
  return res.json()
}

export async function getFeed(cursor) {
  const url = cursor ? `/api/feed?cursor=${encodeURIComponent(cursor)}` : '/api/feed'
  const res = await fetch(url)
  if (!res.ok) throw new Error('Failed to load feed')
  return res.json()
}

export async function sendChat(pdfId, message, history) {
  const res = await fetch(`/api/chat/${pdfId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
  if (!res.ok) throw new Error('Chat request failed')
  return res.json()
}
