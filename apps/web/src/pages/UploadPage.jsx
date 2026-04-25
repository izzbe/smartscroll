import { useState, useRef } from 'react'
import TopTabs from '../components/TopTabs'
import UploadPanel from '../components/UploadPanel'
import SmartFeedPlaceholder from '../components/SmartFeedPlaceholder'
import BottomBar from '../components/BottomBar'
import './UploadPage.css'

export default function UploadPage() {
  const [activeTab, setActiveTab] = useState(0) // 0 = Upload, 1 = Smart Feed
  const pointerStartX = useRef(null)

  function onPointerDown(e) {
    // record where the drag/touch started
    pointerStartX.current = e.clientX ?? e.touches?.[0]?.clientX ?? null
  }

  function onPointerUp(e) {
    if (pointerStartX.current === null) return
    const endX = e.clientX ?? e.changedTouches?.[0]?.clientX ?? pointerStartX.current
    const delta = endX - pointerStartX.current
    pointerStartX.current = null

    // only register as swipe if moved more than 60px horizontally
    if (Math.abs(delta) < 60) return
    if (delta < 0 && activeTab === 0) setActiveTab(1) // swipe left → Smart Feed
    if (delta > 0 && activeTab === 1) setActiveTab(0) // swipe right → Upload
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
              <UploadPanel onGenerate={() => setActiveTab(1)} />
            </div>
            <div className="shell-slide">
              <SmartFeedPlaceholder onGoUpload={() => setActiveTab(0)} />
            </div>
          </div>
        </div>

        {/* Bottom navigation bar */}
        <BottomBar onCreateClick={() => setActiveTab(0)} />
      </div>
    </div>
  )
}
