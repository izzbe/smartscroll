import { useState, useRef } from 'react'
import './UploadPanel.css'

export default function UploadPanel({ onGenerate }) {
  const [mode, setMode] = useState('pdf')     // 'pdf' | 'text'
  const [pdfFile, setPdfFile] = useState(null)
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  const isValid = mode === 'pdf' ? pdfFile !== null : text.trim().length > 0

  function handleFileChange(e) {
    const file = e.target.files[0]
    if (file?.type === 'application/pdf') setPdfFile(file)
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file?.type === 'application/pdf') setPdfFile(file)
  }

  async function handleGenerate() {
    if (!isValid || loading) return
    setLoading(true)
    await new Promise((r) => setTimeout(r, 1000))
    setLoading(false)
    onGenerate()
  }

  return (
    <div className="up-panel">

      {/* Section header */}
      <div className="up-header">
        <p className="up-title">Create SmartScroll</p>
        <p className="up-sub">Upload notes. Generate your learning feed.</p>
      </div>

      {/* PDF / Text mode picker */}
      <div className="up-mode-row">
        <button
          className={`up-mode-card ${mode === 'pdf' ? 'up-mode-card--active' : ''}`}
          onClick={() => setMode('pdf')}
        >
          <span className="up-mode-icon">📄</span>
          <span className="up-mode-label">PDF</span>
        </button>
        <button
          className={`up-mode-card ${mode === 'text' ? 'up-mode-card--active' : ''}`}
          onClick={() => setMode('text')}
        >
          <span className="up-mode-icon">✏️</span>
          <span className="up-mode-label">Text</span>
        </button>
      </div>

      {/* Input area */}
      {mode === 'pdf' ? (
        <div
          className={`up-dropzone ${dragOver ? 'up-dropzone--over' : ''} ${pdfFile ? 'up-dropzone--filled' : ''}`}
          onClick={() => fileInputRef.current.click()}
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />

          {pdfFile ? (
            <div className="up-file-info">
              <div className="up-file-thumb">PDF</div>
              <p className="up-file-name">{pdfFile.name}</p>
              <p className="up-file-size">{(pdfFile.size / 1024 / 1024).toFixed(2)} MB</p>
              <button
                className="up-remove"
                onClick={(e) => { e.stopPropagation(); setPdfFile(null) }}
              >
                Remove
              </button>
            </div>
          ) : (
            <div className="up-drop-prompt">
              <div className="up-drop-icon">
                <UploadArrow />
              </div>
              <p className="up-drop-label">Upload PDF</p>
              <p className="up-drop-hint">
                Drop a study guide, lecture notes,<br />or textbook section.
              </p>
              <p className="up-drop-cta">Tap to browse files</p>
            </div>
          )}
        </div>
      ) : (
        <div className="up-text-wrap">
          <textarea
            className="up-textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste your notes here…"
          />
          <span className="up-char-count">{text.length.toLocaleString()} chars</span>
        </div>
      )}

      {/* Generate button — stays at the bottom */}
      <div className="up-generate-wrap">
        <button
          className={`up-generate ${isValid ? 'up-generate--active' : ''}`}
          onClick={handleGenerate}
          disabled={!isValid || loading}
        >
          {loading ? (
            <span className="up-btn-loading">
              <span className="up-spinner" />
              Generating…
            </span>
          ) : (
            'Generate Smart Feed'
          )}
        </button>
      </div>

    </div>
  )
}

/* Inline SVG so there's no external image dependency */
function UploadArrow() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 19V5" />
      <path d="M5 12l7-7 7 7" />
    </svg>
  )
}
