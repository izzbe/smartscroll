import './TopTabs.css'

const TABS = ['Upload', 'Smart Feed']

export default function TopTabs({ activeTab, onTabChange }) {
  return (
    <div className="tt-bar">
      <div className="tt-tabs">
        {TABS.map((label, i) => (
          <button
            key={label}
            className={`tt-tab ${activeTab === i ? 'tt-tab--active' : ''}`}
            onClick={() => onTabChange(i)}
          >
            {label}
          </button>
        ))}

        {/* Sliding underline indicator */}
        <div
          className="tt-indicator"
          style={{ left: `${activeTab * 50}%` }}
        />
      </div>
    </div>
  )
}
