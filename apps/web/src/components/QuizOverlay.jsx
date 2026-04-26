import { useState, useRef } from 'react'
import { createPortal } from 'react-dom'
import { judgeAnswer } from '../api/client'
import './QuizOverlay.css'

// step: 0|1|2 = MCQ index, 'fr' = free-response, 'grading' = loading, 'feedback' = results, 'score' = final
export default function QuizOverlay({ videoId, questions, freeResponseQuestion, onClose }) {
  const [step,       setStep]       = useState(0)
  const [selected,   setSelected]   = useState(null)
  const [mcqCorrect, setMcqCorrect] = useState(0)
  const [frAnswer,   setFrAnswer]   = useState('')
  const [frResult,   setFrResult]   = useState(null)   // {score, feedback}
  const [frError,    setFrError]    = useState(null)
  const textareaRef = useRef(null)

  const hasFr     = freeResponseQuestion?.question && freeResponseQuestion?.rubric?.length === 5
  const mcqCount  = questions?.length ?? 0
  const totalSteps = mcqCount + (hasFr ? 1 : 0)

  if (!questions || questions.length === 0) return null

  const isMcq     = typeof step === 'number'
  const q         = isMcq ? questions[step] : null

  /* ── MCQ interaction ── */
  function choose(idx) {
    if (selected !== null) return
    setSelected(idx)
    if (idx === q.correct_index) setMcqCorrect(c => c + 1)
  }

  function nextAfterMcq() {
    const nextStep = step + 1
    if (nextStep >= mcqCount) {
      if (hasFr) {
        setStep('fr')
      } else {
        setStep('score')
      }
    } else {
      setStep(nextStep)
      setSelected(null)
    }
  }

  /* ── Free-response submission ── */
  async function submitFr() {
    if (!frAnswer.trim()) return
    setStep('grading')
    setFrError(null)
    try {
      const result = await judgeAnswer(videoId, frAnswer.trim())
      setFrResult(result)
      setStep('feedback')
    } catch (err) {
      setFrError(err.message || 'Grading failed')
      setStep('fr')
    }
  }

  /* ── Progress label ── */
  function progressLabel() {
    if (step === 'fr')       return `${mcqCount + 1} / ${totalSteps}`
    if (step === 'grading')  return 'Grading…'
    if (step === 'feedback') return 'Feedback'
    if (step === 'score')    return 'Results'
    return `${step + 1} / ${totalSteps}`
  }

  const totalScore = mcqCorrect + (frResult?.score ?? 0)
  const maxScore   = mcqCount + (hasFr ? 5 : 0)

  const overlay = (
    <div className="qo-backdrop" onPointerDown={e => e.stopPropagation()}>
      <div className="qo-panel">

        {/* ── MCQ screen ── */}
        {isMcq && (
          <>
            <div className="qo-header">
              <span className="qo-progress">{progressLabel()}</span>
              <button className="qo-skip" onClick={onClose}>Skip</button>
            </div>
            <p className="qo-question">{q.question}</p>
            <div className="qo-choices">
              {q.choices.map((choice, idx) => {
                let cls = 'qo-choice'
                if (selected !== null) {
                  if (idx === q.correct_index)  cls += ' qo-choice--correct'
                  else if (idx === selected)    cls += ' qo-choice--wrong'
                  else                         cls += ' qo-choice--dim'
                }
                return (
                  <button key={idx} className={cls} onClick={() => choose(idx)}>
                    {choice}
                  </button>
                )
              })}
            </div>
            {selected !== null && (
              <button className="qo-btn qo-btn--primary" onClick={nextAfterMcq}>
                {step + 1 < mcqCount || hasFr ? 'Next' : 'See score'}
              </button>
            )}
          </>
        )}

        {/* ── Free-response screen ── */}
        {step === 'fr' && (
          <>
            <div className="qo-header">
              <span className="qo-progress">{progressLabel()}</span>
              <button className="qo-skip" onClick={onClose}>Skip</button>
            </div>
            <p className="qo-fr-label">Open-ended question</p>
            <p className="qo-question">{freeResponseQuestion.question}</p>
            {frError && <p className="qo-fr-error">{frError}</p>}
            <textarea
              ref={textareaRef}
              className="qo-textarea"
              placeholder="Write your answer here…"
              value={frAnswer}
              onChange={e => setFrAnswer(e.target.value)}
              rows={5}
            />
            <button
              className="qo-btn qo-btn--primary"
              onClick={submitFr}
              disabled={!frAnswer.trim()}
            >
              Submit for grading
            </button>
          </>
        )}

        {/* ── Grading spinner ── */}
        {step === 'grading' && (
          <div className="qo-grading-screen">
            <div className="qo-grading-spinner" />
            <p className="qo-grading-label">Grading your answer…</p>
            <p className="qo-grading-sub">Our AI is evaluating your response</p>
          </div>
        )}

        {/* ── Feedback screen ── */}
        {step === 'feedback' && frResult && (
          <>
            <div className="qo-header">
              <span className="qo-progress">Feedback</span>
              <span className="qo-fr-score-badge">{frResult.score}/5</span>
            </div>
            <p className="qo-question" style={{ fontSize: '0.88rem', color: 'rgba(255,255,255,0.7)', fontWeight: 600 }}>
              {freeResponseQuestion.question}
            </p>
            <div className="qo-feedback-list">
              {frResult.feedback.map((item, i) => (
                <div key={i} className={`qo-feedback-item ${item.hit ? 'qo-feedback-item--hit' : 'qo-feedback-item--miss'}`}>
                  <span className="qo-feedback-icon">{item.hit ? '✓' : '✗'}</span>
                  <div className="qo-feedback-text">
                    <p className="qo-feedback-criterion">{item.criterion}</p>
                    <p className="qo-feedback-comment">{item.comment}</p>
                  </div>
                </div>
              ))}
            </div>
            <button className="qo-btn qo-btn--primary" onClick={() => setStep('score')}>
              See total score
            </button>
          </>
        )}

        {/* ── Final score screen ── */}
        {step === 'score' && (
          <div className="qo-score-screen">
            <div className="qo-score-circle">
              <span className="qo-score-num">{totalScore}</span>
              <span className="qo-score-denom">/ {maxScore}</span>
            </div>
            <p className="qo-score-label">
              {totalScore === maxScore
                ? 'Perfect score!'
                : totalScore >= Math.ceil(maxScore * 0.6)
                ? 'Nice work!'
                : 'Keep learning!'}
            </p>
            {hasFr && (
              <div className="qo-score-breakdown">
                <span>Multiple choice</span><span>{mcqCorrect}/{mcqCount}</span>
                <span>Open question</span><span>{frResult?.score ?? 0}/5</span>
              </div>
            )}
            <button className="qo-btn qo-btn--primary" onClick={onClose}>
              Continue
            </button>
          </div>
        )}

      </div>
    </div>
  )

  return createPortal(overlay, document.body)
}
