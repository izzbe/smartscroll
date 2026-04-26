// All calls go to /api, proxied to http://localhost:8000 by Vite in dev.
import { getAuth } from 'firebase/auth'
import { firebaseApp } from '../firebase'

async function _getToken() {
  const user = getAuth(firebaseApp).currentUser
  if (!user) return null
  return user.getIdToken()
}

async function authHeaders(extra = {}) {
  const token = await _getToken()
  return token
    ? { Authorization: `Bearer ${token}`, ...extra }
    : { ...extra }
}

async function apiFetch(url, options = {}) {
  const headers = await authHeaders(options.headers)
  const res = await fetch(url, { ...options, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export async function uploadPdf(file, gameplayStyle) {
  const form = new FormData()
  form.append('file', file)
  if (gameplayStyle) form.append('gameplay_style', gameplayStyle)
  const token = await getIdToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const res = await fetch('/api/pdfs/upload', { method: 'POST', body: form, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || 'Upload failed')
  }
  return res.json()
}

export async function getPdf(pdfId) {
  return apiFetch(`/api/pdfs/${pdfId}`)
}

export async function getFeed(cursor, creatorUid) {
  const params = new URLSearchParams()
  if (cursor) params.set('cursor', cursor)
  if (creatorUid) params.set('creator_uid', creatorUid)
  const qs = params.toString()
  return apiFetch(qs ? `/api/feed?${qs}` : '/api/feed')
}

export async function generateFromTopic(topic, gameplayStyle) {
  return apiFetch('/api/topics/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, gameplay_style: gameplayStyle }),
  })
}

export async function getTopicStatus(topicId) {
  return apiFetch(`/api/topics/${topicId}`)
}

export async function sendChat(pdfId, message, history) {
  return apiFetch(`/api/chat/${pdfId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
}

// User / social

export async function upsertMe(email, displayName = '') {
  return apiFetch('/api/users/me', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, display_name: displayName }),
  })
}

export async function listUsers() {
  return apiFetch('/api/users')
}

export async function followUser(targetUid) {
  const headers = await authHeaders()
  const res = await fetch(`/api/users/${targetUid}/follow`, { method: 'POST', headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || 'Follow failed')
  }
}

// Messages

export async function sendMessage(toUid, videoId, videoCaption, videoGcsPath) {
  return apiFetch('/api/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      to_uid: toUid,
      video_id: videoId,
      video_caption: videoCaption,
      video_gcs_path: videoGcsPath,
    }),
  })
}

export async function getInbox() {
  return apiFetch('/api/messages/inbox')
}

export async function markMessageRead(messageId) {
  const headers = await authHeaders()
  await fetch(`/api/messages/${messageId}/read`, { method: 'POST', headers })
}

export async function judgeAnswer(videoId, answer) {
  return apiFetch(`/api/quiz/${videoId}/judge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer }),
  })
}

export async function unfollowUser(targetUid) {
  const headers = await authHeaders()
  const res = await fetch(`/api/users/${targetUid}/follow`, { method: 'DELETE', headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || 'Unfollow failed')
  }
}
