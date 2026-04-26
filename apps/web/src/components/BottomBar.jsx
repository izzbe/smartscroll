import './BottomBar.css'

export default function BottomBar({ onCreateClick, onDiscoverClick, onInboxClick, activeBar, unreadCount = 0 }) {
  return (
    <nav className="bbar">
      <button className={`bbar-item ${activeBar === 'home' ? 'bbar-item--active' : ''}`} onClick={onCreateClick}>
        <HomeIcon />
        <span className="bbar-label">Home</span>
      </button>

      <button className={`bbar-item ${activeBar === 'discover' ? 'bbar-item--active' : ''}`} onClick={onDiscoverClick}>
        <DiscoverIcon />
        <span className="bbar-label">Discover</span>
      </button>

      <button className="bbar-create" onClick={onCreateClick} aria-label="Create">
        <div className="bbar-create-face">
          <PlusIcon />
        </div>
      </button>

      <button className={`bbar-item ${activeBar === 'inbox' ? 'bbar-item--active' : ''}`} onClick={onInboxClick} style={{ position: 'relative' }}>
        <InboxIcon />
        {unreadCount > 0 && (
          <span className="bbar-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
        <span className="bbar-label">Inbox</span>
      </button>

      <button className="bbar-item">
        <MeIcon />
        <span className="bbar-label">Me</span>
      </button>
    </nav>
  )
}

function PlusIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#111" strokeWidth="2.8" strokeLinecap="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5"  y1="12" x2="19" y2="12" />
    </svg>
  )
}

function HomeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
      <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
    </svg>
  )
}

function DiscoverIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/>
      <path d="m21 21-4.35-4.35"/>
    </svg>
  )
}

function InboxIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
      <polyline points="22,6 12,13 2,6"/>
    </svg>
  )
}

function MeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  )
}
