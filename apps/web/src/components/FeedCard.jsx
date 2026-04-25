import { useState } from 'react'
import CommentDrawer from './CommentDrawer'
import './FeedCard.css'

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (n >= 10_000)    return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

export default function FeedCard({ item }) {
  const [liked,    setLiked]    = useState(false)
  const [likeCount, setLikeCount] = useState(item.likes)
  const [saved,    setSaved]    = useState(false)
  const [saveCount, setSaveCount] = useState(item.saves ?? 0)
  const [commentOpen, setCommentOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)

  function handleLike() {
    const next = !liked
    setLiked(next)
    setLikeCount(c => next ? c + 1 : c - 1)
  }

  function handleSave() {
    const next = !saved
    setSaved(next)
    setSaveCount(c => next ? c + 1 : c - 1)
  }

  const captionLimit = 90
  const isLong = item.caption.length > captionLimit

  return (
    <>
      <div className="fc-card" style={{ background: item.gradient }}>

        {/* Bottom gradient overlay */}
        <div className="fc-overlay" />

        {/* ── Brainrot subtitle (center) ── */}
        <div className="fc-subtitle-zone">
          <p className="fc-subtitle">{item.subtitle}</p>
        </div>

        {/* ── Right action sidebar ── */}
        <aside className="fc-sidebar">

          {/* Avatar + follow */}
          <div className="fc-avatar-wrap">
            <div className="fc-avatar">SS</div>
            <div className="fc-avatar-plus">+</div>
          </div>

          {/* Like */}
          <button
            className={`fc-action ${liked ? 'fc-action--liked' : ''}`}
            onClick={handleLike}
            aria-label="Like"
          >
            <HeartIcon filled={liked} />
            <span className="fc-count">{fmt(likeCount)}</span>
          </button>

          {/* Comment → Ask Gemma */}
          <button
            className="fc-action"
            onClick={() => setCommentOpen(true)}
            aria-label="Comment"
          >
            <CommentIcon />
            <span className="fc-count">{fmt(item.comments)}</span>
          </button>

          {/* Save / Bookmark */}
          <button
            className={`fc-action ${saved ? 'fc-action--saved' : ''}`}
            onClick={handleSave}
            aria-label="Save"
          >
            <BookmarkIcon filled={saved} />
            <span className="fc-count">{fmt(saveCount)}</span>
          </button>

          {/* Share */}
          <button className="fc-action" aria-label="Share">
            <ShareIcon />
            <span className="fc-count">{fmt(item.shares ?? 0)}</span>
          </button>

          {/* Spinning music disc */}
          <div className="fc-disc" aria-hidden>
            <MusicIcon />
          </div>
        </aside>

        {/* ── Bottom-left content info ── */}
        <div className="fc-info">

          {/* AI tag pill */}
          <div className="fc-topic-tag">
            <span className="fc-topic-dot" />
            AI Summary · {item.topic}
          </div>

          {/* Username + verified */}
          <div className="fc-username-row">
            <span className="fc-username">@smartscroll</span>
            <VerifiedIcon />
          </div>

          {/* Expandable caption */}
          <p className="fc-caption">
            {expanded || !isLong
              ? item.caption
              : item.caption.slice(0, captionLimit)}
            {isLong && !expanded && (
              <button className="fc-more-btn" onClick={() => setExpanded(true)}>
                …&nbsp;more
              </button>
            )}
          </p>

          {/* Hashtags */}
          <p className="fc-tags">{item.tags}</p>

          {/* Audio row */}
          <div className="fc-audio-row">
            <NoteIcon />
            <span className="fc-audio-text">Original narration · SmartScroll</span>
          </div>
        </div>

      </div>

      {/* Slide-up comment / Ask Gemma drawer */}
      {commentOpen && (
        <CommentDrawer
          topic={item.topic}
          onClose={() => setCommentOpen(false)}
        />
      )}
    </>
  )
}

/* ── SVG icon components ── */

function HeartIcon({ filled }) {
  return (
    <svg className="fc-icon" viewBox="0 0 24 24" fill={filled ? '#ee1d52' : 'none'} stroke={filled ? '#ee1d52' : '#fff'} strokeWidth="1.8">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  )
}

function CommentIcon() {
  return (
    <svg className="fc-icon" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <circle cx="8.5" cy="11" r="0.8" fill="#fff" stroke="none" />
      <circle cx="12"  cy="11" r="0.8" fill="#fff" stroke="none" />
      <circle cx="15.5" cy="11" r="0.8" fill="#fff" stroke="none" />
    </svg>
  )
}

function BookmarkIcon({ filled }) {
  return (
    <svg className="fc-icon" viewBox="0 0 24 24" fill={filled ? '#fff' : 'none'} stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function ShareIcon() {
  return (
    <svg className="fc-icon" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
      <polyline points="16 6 12 2 8 6" />
      <line x1="12" y1="2" x2="12" y2="15" />
    </svg>
  )
}

function VerifiedIcon() {
  return (
    <svg className="fc-verified" viewBox="0 0 24 24" fill="#20d5ec">
      <path d="M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" stroke="#20d5ec" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
    </svg>
  )
}

function MusicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="#fff" width="18" height="18">
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  )
}

function NoteIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" width="13" height="13">
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" fill="#fff" stroke="none"/>
      <circle cx="18" cy="16" r="3" fill="#fff" stroke="none"/>
    </svg>
  )
}
