import './SmartFeedPlaceholder.css'

// Three fake card skeletons to show behind the CTA
const FAKE_CARDS = [
  { lines: ['60%', '90%', '75%'] },
  { lines: ['80%', '55%', '90%'] },
  { lines: ['70%', '85%', '60%'] },
]

export default function SmartFeedPlaceholder({ onGoUpload }) {
  return (
    <div className="sfp-wrap">

      {/* Faded skeleton cards in the background */}
      <div className="sfp-bg-cards" aria-hidden>
        {FAKE_CARDS.map((card, i) => (
          <div className="sfp-card" key={i}>
            <div className="sfp-card-thumb" />
            {card.lines.map((w, j) => (
              <div key={j} className="sfp-card-line" style={{ width: w }} />
            ))}
          </div>
        ))}
      </div>

      {/* Centered CTA */}
      <div className="sfp-content">
        <div className="sfp-icon">⚡</div>
        <h3 className="sfp-title">Your Smart Feed</h3>
        <p className="sfp-body">
          Generate from a PDF or text<br />to start scrolling
        </p>
        <button className="sfp-back-btn" onClick={onGoUpload}>
          ← Go to Upload
        </button>
      </div>

      {/* Fake "For You" tag at top */}
      <div className="sfp-for-you-tag">For You</div>
    </div>
  )
}
