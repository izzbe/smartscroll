import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { sendChat } from '../api/client'
import './CommentDrawer.css'

const INITIAL_MESSAGES = [
  {
    id: 0,
    role: 'gemma',
    text: "Hey! I'm Gemma. Ask me anything about this topic and I'll break it down for you.",
  },
]

export default function CommentDrawer({ topic, pdfId, onClose }) {
  const [messages, setMessages] = useState(INITIAL_MESSAGES)
  const [history, setHistory]   = useState([]) // {role, content} for multi-turn API
  const [input, setInput]       = useState('')
  const [sending, setSending]   = useState(false)
  const [visible, setVisible]   = useState(false)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true))
    return () => cancelAnimationFrame(id)
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleClose() {
    setVisible(false)
    setTimeout(onClose, 300)
  }

  async function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return

    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text }])
    setInput('')
    setSending(true)

    try {
      if (pdfId) {
        const { reply } = await sendChat(pdfId, text, history)
        setHistory(prev => [
          ...prev,
          { role: 'user', content: text },
          { role: 'assistant', content: reply },
        ])
        setMessages(prev => [...prev, { id: Date.now(), role: 'gemma', text: reply }])
      } else {
        setMessages(prev => [
          ...prev,
          {
            id: Date.now(),
            role: 'gemma',
            text: `Great question about "${topic}"! Upload a PDF to get real AI answers about its content.`,
          },
        ])
      }
    } catch {
      setMessages(prev => [
        ...prev,
        { id: Date.now(), role: 'gemma', text: 'Sorry, something went wrong. Try again!' },
      ])
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  return createPortal(
    <div
      className={`cd-overlay ${visible ? 'cd-overlay--in' : ''}`}
      onClick={handleClose}
    >
      <div
        className={`cd-panel ${visible ? 'cd-panel--in' : ''}`}
        onClick={e => e.stopPropagation()}
      >
        <div className="cd-handle" />

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
          {sending && (
            <div className="cd-row cd-row--gemma">
              <div className="cd-gemma-dot">G</div>
              <div className="cd-bubble cd-bubble--gemma cd-bubble--thinking">
                <span className="cd-dot" /><span className="cd-dot" /><span className="cd-dot" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form className="cd-input-row" onSubmit={handleSend}>
          <input
            ref={inputRef}
            className="cd-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={`Ask about ${topic}…`}
            autoComplete="off"
            disabled={sending}
          />
          <button
            className={`cd-send-btn ${input.trim() && !sending ? 'cd-send-btn--active' : ''}`}
            type="submit"
            disabled={!input.trim() || sending}
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
