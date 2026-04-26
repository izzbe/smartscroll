import { useEffect, useState } from 'react'
import { getInbox, markMessageRead } from '../api/client'
import './InboxPage.css'

export default function InboxPage() {
  const [messages, setMessages] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')
  const [playing,  setPlaying]  = useState(null) // message_id of open video

  useEffect(() => {
    getInbox()
      .then(setMessages)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  async function openVideo(msg) {
    setPlaying(msg.message_id)
    if (!msg.read) {
      await markMessageRead(msg.message_id).catch(() => {})
      setMessages(prev =>
        prev.map(m => m.message_id === msg.message_id ? { ...m, read: true } : m)
      )
    }
  }

  const unread = messages.filter(m => !m.read).length

  return (
    <div className="inbox-page">
      <div className="inbox-header">
        <h2 className="inbox-title">
          Inbox
          {unread > 0 && <span className="inbox-badge">{unread}</span>}
        </h2>
      </div>

      {error && <p className="inbox-error">{error}</p>}

      {loading ? (
        <div className="inbox-loading">Loading…</div>
      ) : messages.length === 0 ? (
        <div className="inbox-empty">
          <p>No messages yet.</p>
          <p className="inbox-empty-sub">When someone shares a video with you, it'll appear here.</p>
        </div>
      ) : (
        <ul className="inbox-list">
          {messages.map(msg => (
            <li
              key={msg.message_id}
              className={`inbox-item ${!msg.read ? 'inbox-item--unread' : ''}`}
              onClick={() => openVideo(msg)}
            >
              <div className="inbox-avatar">
                {(msg.from_display_name || '?')[0].toUpperCase()}
              </div>
              <div className="inbox-info">
                <span className="inbox-from">
                  {msg.from_display_name || 'Someone'} shared a video
                </span>
                <span className="inbox-caption">{msg.video_caption || 'Untitled video'}</span>
                <span className="inbox-time">{timeAgo(msg.created_at)}</span>
              </div>
              <div className="inbox-play-icon">
                <PlayIcon />
              </div>
              {!msg.read && <div className="inbox-dot" />}
            </li>
          ))}
        </ul>
      )}

      {/* Video overlay */}
      {playing && (() => {
        const msg = messages.find(m => m.message_id === playing)
        if (!msg) return null
        return (
          <div className="inbox-video-overlay">
            <div className="inbox-video-bar">
              <button className="inbox-video-back" onClick={() => setPlaying(null)}>
                <BackIcon />
              </button>
              <span className="inbox-video-title">{msg.video_caption || 'Video'}</span>
              <span className="inbox-video-from">from {msg.from_display_name}</span>
            </div>
            {msg.video_url ? (
              <video
                className="inbox-video"
                src={msg.video_url}
                controls
                autoPlay
                playsInline
              />
            ) : (
              <div className="inbox-video-unavailable">Video unavailable</div>
            )}
          </div>
        )
      })()}
    </div>
  )
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60)   return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function PlayIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

function BackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 5l-7 7 7 7" />
    </svg>
  )
}
