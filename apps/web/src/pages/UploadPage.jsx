import { useState, useRef } from 'react'
import TopTabs from '../components/TopTabs'
import UploadPanel from '../components/UploadPanel'
import SmartFeed from '../components/SmartFeed'
import BottomBar from '../components/BottomBar'
import './UploadPage.css'

export default function UploadPage() {
  const [activeTab, setActiveTab] = useState(0) // 0 = Upload, 1 = Smart Feed
  const [feedKey, setFeedKey] = useState(0)     // increment to force SmartFeed re-fetch
  const startX = useRef(null)
  const startY = useRef(null)

  function onPointerDown(e) {
    startX.current = e.clientX
    startY.current = e.clientY
  }

  function onPointerUp(e) {
    if (startX.current === null) return
    const dx = e.clientX - startX.current
    const dy = e.clientY - startY.current
    startX.current = null
    startY.current = null

    // Ignore if the gesture is more vertical than horizontal (feed scroll)
    if (Math.abs(dx) < 60) return
    if (Math.abs(dy) > Math.abs(dx)) return

    if (dx < 0 && activeTab === 0) setActiveTab(1) // swipe left → Smart Feed
    if (dx > 0 && activeTab === 1) setActiveTab(0) // swipe right → Upload
  }

  return (
    <div className="shell-outer">
      <div className="shell-frame">

        {/* Fake iOS-style status bar */}
        <div className="shell-status">
          <span className="shell-time">9:41</span>
          <div className="shell-status-right">
            <svg width="16" height="12" viewBox="0 0 16 12" fill="currentColor">
              <rect x="0" y="4" width="3" height="8" rx="1" opacity="0.4"/>
              <rect x="4.5" y="2.5" width="3" height="9.5" rx="1" opacity="0.6"/>
              <rect x="9" y="0.5" width="3" height="11.5" rx="1"/>
              <rect x="14" y="0" width="2" height="10" rx="1" opacity="0.3"/>
            </svg>
            <svg width="15" height="12" viewBox="0 0 15 12" fill="currentColor">
              <path d="M7.5 2.5 C10.5 2.5 13 4.5 13 7 C13 9.5 10.5 11.5 7.5 11.5 C4.5 11.5 2 9.5 2 7 C2 4.5 4.5 2.5 7.5 2.5Z" opacity="0.3"/>
              <path d="M7.5 4.5 C9.5 4.5 11 5.8 11 7.5 C11 9.2 9.5 10.5 7.5 10.5 C5.5 10.5 4 9.2 4 7.5 C4 5.8 5.5 4.5 7.5 4.5Z" opacity="0.6"/>
              <circle cx="7.5" cy="7.5" r="1.8"/>
            </svg>
            <svg width="25" height="12" viewBox="0 0 25 12" fill="currentColor">
              <rect x="0" y="1" width="22" height="10" rx="3" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.4"/>
              <rect x="22.5" y="3.5" width="2" height="5" rx="1" opacity="0.4"/>
              <rect x="1.5" y="2.5" width="16" height="7" rx="2"/>
            </svg>
          </div>
        </div>

        {/* Top tab switcher */}
        <TopTabs activeTab={activeTab} onTabChange={setActiveTab} />

        {/* Swipeable two-page carousel */}
        <div
          className="shell-slides-outer"
          onPointerDown={onPointerDown}
          onPointerUp={onPointerUp}
        >
          <div
            className="shell-slides-track"
            style={{ transform: `translateX(${activeTab * -50}%)` }}
          >
            <div className="shell-slide">
              <UploadPanel onGenerate={() => { setFeedKey(k => k + 1); setActiveTab(1) }} />
            </div>
            <div className="shell-slide shell-slide--feed">
              <SmartFeed key={feedKey} />
            </div>
          </div>
        </div>

        {/* Bottom navigation bar */}
        <BottomBar onCreateClick={() => setActiveTab(0)} />
      </div>
    </div>
  )
}
