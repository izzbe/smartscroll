import { useRef } from 'react'
import FeedCard from './FeedCard'
import { MOCK_FEED } from '../data/mockFeed'
import './SmartFeed.css'

const THRESHOLD   = 72
const DRAG_DAMP   = 0.82  // drag weight — cards resist your finger slightly
const BOUNDS_DAMP = 0.14  // strong resistance at first/last card

export default function SmartFeed({ onGoUpload }) {
  const scrollRef = useRef(null)
  const drag = useRef({ active: false, startY: 0, startTop: 0, index: 0 })

  function cardH() {
    return scrollRef.current?.clientHeight ?? 0
  }

  function snapTo(i) {
    drag.current.index = i
    scrollRef.current?.scrollTo({ top: i * cardH(), behavior: 'smooth' })
  }

  function onPointerDown(e) {
    if (e.target.closest('button, a, input, textarea')) return
    const h = cardH()
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
    const dy = e.clientY - d.startY
    const atTop    = d.index === 0 && dy > 0
    const atBottom = d.index === MOCK_FEED.length - 1 && dy < 0
    scrollRef.current.scrollTop =
      d.startTop - (atTop || atBottom ? dy * BOUNDS_DAMP : dy * DRAG_DAMP)
  }

  function onPointerUp(e) {
    const d = drag.current
    if (!d.active) return
    const dy = e.clientY - d.startY
    d.active = false
    let next = d.index
    if (dy < -THRESHOLD && next < MOCK_FEED.length - 1) next++
    else if (dy > THRESHOLD && next > 0) next--
    snapTo(next)
  }

  function cancel() {
    if (!drag.current.active) return
    drag.current.active = false
    snapTo(drag.current.index)
  }

  return (
    <div
      ref={scrollRef}
      className="sf-scroll"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={cancel}
    >
      {MOCK_FEED.map(item => (
        <FeedCard key={item.id} item={item} />
      ))}
    </div>
  )
}
