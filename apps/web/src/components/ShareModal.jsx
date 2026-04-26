import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { listUsers, sendMessage } from '../api/client'
import './ShareModal.css'

export default function ShareModal({ videoId, videoCaption, videoGcsPath, onClose }) {
  const [users,   setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [sent,    setSent]    = useState({}) // uid → true when sent
  const [sending, setSending] = useState(null) // uid currently sending
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true))
    return () => cancelAnimationFrame(id)
  }, [])

  useEffect(() => {
    listUsers()
      .then(setUsers)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  function handleClose() {
    setVisible(false)
    setTimeout(onClose, 280)
  }

  async function handleSend(user) {
    if (sent[user.uid] || sending) return
    setSending(user.uid)
    try {
      await sendMessage(user.uid, videoId, videoCaption, videoGcsPath)
      setSent(s => ({ ...s, [user.uid]: true }))
    } catch (_) {
      // TODO: show error toast
    } finally {
      setSending(null)
    }
  }

  return createPortal(
    <div
      className={`sm-overlay ${visible ? 'sm-overlay--in' : ''}`}
      onClick={handleClose}
    >
      <div
        className={`sm-panel ${visible ? 'sm-panel--in' : ''}`}
        onClick={e => e.stopPropagation()}
      >
        <div className="sm-handle" />

        <div className="sm-header">
          <span className="sm-title">Send to…</span>
          <button className="sm-close" onClick={handleClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>

        {videoCaption && (
          <div className="sm-video-label">
            <span className="sm-video-dot" />
            <span className="sm-video-caption">{videoCaption}</span>
          </div>
        )}

        {loading ? (
          <div className="sm-loading">Loading…</div>
        ) : users.length === 0 ? (
          <div className="sm-empty">No one to send to yet.</div>
        ) : (
          <ul className="sm-list">
            {users.map(user => {
              const isSent    = sent[user.uid]
              const isSending = sending === user.uid
              return (
                <li key={user.uid} className="sm-user">
                  <div className="sm-avatar">
                    {(user.display_name || user.email)[0].toUpperCase()}
                  </div>
                  <div className="sm-user-info">
                    <span className="sm-user-name">
                      {user.display_name || user.email.split('@')[0]}
                    </span>
                    <span className="sm-user-email">{user.email}</span>
                  </div>
                  <button
                    className={`sm-send-btn ${isSent ? 'sm-send-btn--sent' : ''}`}
                    onClick={() => handleSend(user)}
                    disabled={isSent || !!sending}
                  >
                    {isSending ? '…' : isSent ? <CheckIcon /> : 'Send'}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>,
    document.body
  )
}

function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6"  y1="6" x2="18" y2="18" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}
