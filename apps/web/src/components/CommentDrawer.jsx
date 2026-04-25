import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import './CommentDrawer.css'

const INITIAL_MESSAGES = [
  {
    id: 0,
    role: 'gemma',
    text: "Hey! I'm Gemma. Ask me anything about this topic and I'll break it down for you. 🧠",
  },
]

export default function CommentDrawer({ topic, onClose }) {
  const [messages, setMessages] = useState(INITIAL_MESSAGES)
  const [input, setInput]       = useState('')
  const [visible, setVisible]   = useState(false)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  // Trigger slide-in on mount
  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true))
    return () => cancelAnimationFrame(id)
  }, [])

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleClose() {
    setVisible(false)
    setTimeout(onClose, 300)
  }

  function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text) return

    const userMsg = { id: Date.now(), role: 'user', text }
    // Placeholder Gemma reply — will be real once backend is wired up
    const gemmaMsg = {
      id: Date.now() + 1,
      role: 'gemma',
      text: `Great question! Once I'm connected to the backend, I'll give you a full explanation about "${topic}". For now — keep the curiosity going! 🚀`,
    }

    setMessages(prev => [...prev, userMsg, gemmaMsg])
    setInput('')
    inputRef.current?.focus()
  }

  // Render into document.body so position:fixed is relative to the viewport,
  // not the transformed .shell-slides-track ancestor.
  return createPortal(
    <div
      className={`cd-overlay ${visible ? 'cd-overlay--in' : ''}`}
      onClick={handleClose}
    >
      <div
        className={`cd-panel ${visible ? 'cd-panel--in' : ''}`}
        onClick={e => e.stopPropagation()}
      >
        {/* Drag handle */}
        <div className="cd-handle" />

        {/* Header */}
        <div className="cd-header">
          <div className="cd-header-left">
            <div className="cd-gemma-badge">G</div>
            <div>
              <p className="cd-header-title">Ask Gemma</p>
              <p className="cd-header-sub">About: {topic}</p>
            </div>
          </div>
          <button className="cd-close-btn" onClick={handleClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>

        {/* Message thread */}
        <div className="cd-messages">
          {messages.map(msg => (
            <div key={msg.id} className={`cd-row cd-row--${msg.role}`}>
              {msg.role === 'gemma' && (
                <div className="cd-gemma-dot">G</div>
              )}
              <div className={`cd-bubble cd-bubble--${msg.role}`}>
                {msg.text}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input row */}
        <form className="cd-input-row" onSubmit={handleSend}>
          <input
            ref={inputRef}
            className="cd-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={`Ask about ${topic}…`}
            autoComplete="off"
          />
          <button
            className={`cd-send-btn ${input.trim() ? 'cd-send-btn--active' : ''}`}
            type="submit"
            disabled={!input.trim()}
            aria-label="Send"
          >
            <SendIcon />
          </button>
        </form>
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

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </svg>
  )
}
