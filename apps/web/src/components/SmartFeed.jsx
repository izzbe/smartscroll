import { useState, useEffect, useRef } from 'react'
import FeedCard from './FeedCard'
import { getFeed } from '../api/client'
import './SmartFeed.css'

const THRESHOLD       = 72   // px to swipe between cards
const DRAG_DAMP       = 0.82
const BOUNDS_DAMP     = 0.14
const PULL_THRESHOLD  = 80   // px of downward pull to trigger refresh

export default function SmartFeed({ onGoUpload, creatorUid }) {
  const [videos,     setVideos]     = useState([])
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [pullY,      setPullY]      = useState(0)      // 0 → not pulling
  const [refreshing, setRefreshing] = useState(false)

  const scrollRef = useRef(null)
  const drag      = useRef({ active: false, startY: 0, startTop: 0, index: 0 })
  const pullRef   = useRef(0)  // mirrors pullY for use inside pointer handlers

  useEffect(() => {
    getFeed(undefined, creatorUid)
      .then(data => setVideos(data.videos ?? []))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [creatorUid])

  function cardH() {
    return scrollRef.current?.clientHeight ?? 0
  }

  function snapTo(i) {
    drag.current.index = i
    scrollRef.current?.scrollTo({ top: i * cardH(), behavior: 'smooth' })
  }

  async function doRefresh() {
    setRefreshing(true)
    snapTo(0)
    try {
      const data = await getFeed(undefined, creatorUid)
      setVideos(data.videos ?? [])
    } catch {
      // fail silently — existing feed stays visible
    } finally {
      setRefreshing(false)
    }
  }

  function onPointerDown(e) {
    if (e.target.closest('button, a, input, textarea')) return
    const h   = cardH()
    const top = scrollRef.current.scrollTop
    drag.current = {
      active: true,
      startY: e.clientY,
      startTop: top,
      index: Math.round(top / h),
    }
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  function onPointerMove(e) {
    const d = drag.current
    if (!d.active) return
    const dy      = e.clientY - d.startY
    const atTop   = d.index === 0 && dy > 0
    const atBtm   = d.index === videos.length - 1 && dy < 0

    scrollRef.current.scrollTop =
      d.startTop - (atTop || atBtm ? dy * BOUNDS_DAMP : dy * DRAG_DAMP)

    // Track pull distance at top card
    if (d.index === 0) {
      const pull = Math.max(0, Math.min(dy, PULL_THRESHOLD * 1.6))
      pullRef.current = pull
      setPullY(pull)
    }
  }

  function onPointerUp(e) {
    const d  = drag.current
    if (!d.active) return
    const dy = e.clientY - d.startY
    d.active = false

    const pull = pullRef.current
    pullRef.current = 0
    setPullY(0)

    if (pull >= PULL_THRESHOLD && !refreshing) {
      doRefresh()
      return
    }

    let next = d.index
    if (dy < -THRESHOLD && next < videos.length - 1) next++
    else if (dy > THRESHOLD && next > 0) next--
    snapTo(next)
  }

  function cancel() {
    if (!drag.current.active) return
    drag.current.active = false
    pullRef.current = 0
    setPullY(0)
    snapTo(drag.current.index)
  }

  // ── Loading / error / empty states ──────────────────────────────────────
  if (loading) {
    return (
      <div className="sf-scroll sf-center">
        <div className="sf-spinner" />
        <p className="sf-status-text">Loading your feed…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="sf-scroll sf-center">
        <p className="sf-status-text sf-status-text--error">Couldn't load feed</p>
        <p className="sf-status-sub">{error}</p>
      </div>
    )
  }

  if (videos.length === 0) {
    return (
      <div className="sf-scroll sf-center">
        <p className="sf-status-text">No videos yet</p>
        <p className="sf-status-sub">Upload a PDF to generate your first SmartScroll</p>
      </div>
    )
  }

  // Pull indicator visibility & position
  // At pullY=0 indicator sits at -PILL_TOP (hidden above fold).
  // At pullY=PULL_THRESHOLD it lands at PILL_SHOW (just inside the viewport).
  const PILL_TOP  = 44  // height of the pill
  const PILL_SHOW = 10  // how far below top edge when fully pulled
  const indicatorY = refreshing
    ? PILL_SHOW
    : (pullY / PULL_THRESHOLD) * (PILL_TOP + PILL_SHOW) - PILL_TOP
  const isReady = pullY >= PULL_THRESHOLD

  return (
    <div className="sf-wrapper">

      {/* Pull-to-refresh indicator */}
      {(pullY > 4 || refreshing) && (
        <div className="sf-pull-pill" style={{ top: `${indicatorY}px` }}>
          {refreshing ? (
            <div className="sf-pull-spinner" />
          ) : (
            <svg
              className={`sf-pull-arrow ${isReady ? 'sf-pull-arrow--ready' : ''}`}
              width="16" height="16" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2.5"
              strokeLinecap="round" strokeLinejoin="round"
            >
              <path d="M12 5v14M5 12l7 7 7-7" />
            </svg>
          )}
          <span className="sf-pull-label">
            {refreshing ? 'Refreshing…' : isReady ? 'Release to refresh' : 'Pull to refresh'}
          </span>
        </div>
      )}

      {/* Feed scroll container */}
      <div
        ref={scrollRef}
        className="sf-scroll"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={cancel}
      >
        {videos.map(item => (
          <FeedCard key={item.video_id} item={item} />
        ))}
      </div>

    </div>
  )
}
