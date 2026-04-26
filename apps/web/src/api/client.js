// All calls go to /api, proxied to http://localhost:8000 by Vite in dev.

export async function uploadPdf(file, gameplayStyle) {
  const form = new FormData()
  form.append('file', file)
  if (gameplayStyle) form.append('gameplay_style', gameplayStyle)
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

export async function generateFromTopic(topic, gameplayStyle) {
  const res = await fetch('/api/topics/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, gameplay_style: gameplayStyle }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || 'Failed to start topic research')
  }
  return res.json()  // { topic_id, uid, status }
}

export async function getTopicStatus(topicId) {
  const res = await fetch(`/api/topics/${topicId}`)
  if (!res.ok) throw new Error('Failed to get topic status')
  return res.json()  // { topic_id, topic, status, error_message }
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
