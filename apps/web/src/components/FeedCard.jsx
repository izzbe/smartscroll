import { useState } from 'react'
import './FeedCard.css'

export default function FeedCard({ item, index }) {
  const [liked, setLiked] = useState(false)
  const [likeCount, setLikeCount] = useState(item.likes)

  function handleLike() {
    setLiked((prev) => !prev)
    setLikeCount((c) => liked ? c - 1 : c + 1)
  }

  return (
    <div className="feed-card" style={{ background: item.gradient }}>
      {/* Background overlay */}
      <div className="card-overlay" />

      {/* Subtitle — center stage */}
      <div className="card-subtitle-wrap">
        <p className="card-subtitle">{item.subtitle}</p>
      </div>

      {/* Right action bar */}
      <div className="action-bar">
        <div className="action-item">
          <div className="avatar-wrap">
            <div className="avatar">SS</div>
            <div className="avatar-plus">+</div>
          </div>
        </div>

        <button className={`action-item action-btn ${liked ? 'liked' : ''}`} onClick={handleLike}>
          <span className="action-icon">{liked ? '❤️' : '🤍'}</span>
          <span className="action-label">{likeCount.toLocaleString()}</span>
        </button>

        <button className="action-item action-btn">
          <span className="action-icon">💬</span>
          <span className="action-label">{item.comments}</span>
        </button>

        <button className="action-item action-btn">
          <span className="action-icon">↗️</span>
          <span className="action-label">Share</span>
        </button>

        <button className="action-item action-btn">
          <span className="action-icon">🔖</span>
          <span className="action-label">Save</span>
        </button>
      </div>

      {/* Bottom-left content info */}
      <div className="card-info">
        <p className="card-username">@smartscroll</p>
        <p className="card-caption">{item.caption}</p>
        <p className="card-tags">{item.tags}</p>
        <div className="card-audio">
          <span className="audio-icon">🎵</span>
          <span className="audio-label">Original narration · SmartScroll</span>
        </div>
      </div>
    </div>
  )
}
