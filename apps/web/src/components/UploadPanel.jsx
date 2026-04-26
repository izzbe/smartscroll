import { useState, useRef } from 'react'
import { uploadPdf, getPdf, generateFromTopic, getTopicStatus } from '../api/client'
import './UploadPanel.css'

export default function UploadPanel({ onGenerate }) {
  const [mode, setMode] = useState('pdf')
  const [pdfFile, setPdfFile] = useState(null)
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingMsg, setLoadingMsg] = useState('')
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  const isValid = mode === 'pdf' ? pdfFile !== null : text.trim().length > 0

  function handleFileChange(e) {
    const file = e.target.files[0]
    if (file?.type === 'application/pdf') { setPdfFile(file); setError(null) }
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file?.type === 'application/pdf') { setPdfFile(file); setError(null) }
  }

  async function handleGenerate() {
    if (!isValid || loading) return
    setError(null)
    setLoading(true)

    if (mode === 'pdf') {
      try {
        setLoadingMsg('Uploading…')
        const { pdf_id } = await uploadPdf(pdfFile)

        setLoadingMsg('Processing your PDF… this may take a minute')
        const deadline = Date.now() + 300_000
        while (Date.now() < deadline) {
          await new Promise(r => setTimeout(r, 3000))
          const pdf = await getPdf(pdf_id)
          if (pdf.status === 'ready') { onGenerate(pdf_id); return }
          if (pdf.status === 'failed') throw new Error(pdf.error_message || 'Processing failed')
        }
        throw new Error('Processing timed out — check back soon')
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
        setLoadingMsg('')
      }
    } else {
      try {
        setLoadingMsg('Researching your topic…')
        const { topic_id } = await generateFromTopic(text.trim())

        setLoadingMsg('Building your video… this may take a minute')
        const deadline = Date.now() + 300_000
        while (Date.now() < deadline) {
          await new Promise(r => setTimeout(r, 3000))
          const status = await getTopicStatus(topic_id)
          if (status.status === 'ready') { onGenerate(topic_id); return }
          if (status.status === 'failed') throw new Error(status.error_message || 'Processing failed')
        }
        throw new Error('Processing timed out — check back soon')
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
        setLoadingMsg('')
      }
    }
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
          <PdfIcon />
          <span className="up-mode-label">PDF</span>
        </button>
        <button
          className={`up-mode-card ${mode === 'text' ? 'up-mode-card--active' : ''}`}
          onClick={() => setMode('text')}
        >
          <TextIcon />
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
            placeholder="What do you want to learn about? (e.g., What is Redis?)"
          />
          <span className="up-char-count">{text.length.toLocaleString()} chars</span>
        </div>
      )}

      {/* Error message */}
      {error && <p className="up-error">{error}</p>}

      {/* Generate button */}
      <div className="up-generate-wrap">
        <button
          className={`up-generate ${isValid ? 'up-generate--active' : ''}`}
          onClick={handleGenerate}
          disabled={!isValid || loading}
        >
          {loading ? (
            <span className="up-btn-loading">
              <span className="up-spinner" />
              {loadingMsg || 'Generating…'}
            </span>
          ) : (
            'Generate Smart Feed'
          )}
        </button>
      </div>

    </div>
  )
}

function UploadArrow() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 19V5" />
      <path d="M5 12l7-7 7 7" />
    </svg>
  )
}

function PdfIcon() {
  return (
    <svg className="up-mode-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="13" y2="17" />
    </svg>
  )
}

function TextIcon() {
  return (
    <svg className="up-mode-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  )
}
