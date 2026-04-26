import { useState } from 'react'
import { createPortal } from 'react-dom'
import './QuizOverlay.css'

export default function QuizOverlay({ questions, onClose }) {
  const [step,     setStep]     = useState(0)   // which question (0-2) or 'score'
  const [selected, setSelected] = useState(null) // index user tapped
  const [correct,  setCorrect]  = useState(0)   // running count

  if (!questions || questions.length === 0) return null

  const isScore = step === 'score'
  const q = isScore ? null : questions[step]

  function choose(idx) {
    if (selected !== null) return  // already answered
    setSelected(idx)
    if (idx === q.correct_index) setCorrect(c => c + 1)
  }

  function next() {
    const nextStep = step + 1
    if (nextStep >= questions.length) {
      setStep('score')
    } else {
      setStep(nextStep)
      setSelected(null)
    }
  }

  const overlay = (
    <div className="qo-backdrop" onPointerDown={e => e.stopPropagation()}>
      <div className="qo-panel">

        {isScore ? (
          /* ── Score screen ── */
          <div className="qo-score-screen">
            <div className="qo-score-circle">
              <span className="qo-score-num">{correct}</span>
              <span className="qo-score-denom">/ {questions.length}</span>
            </div>
            <p className="qo-score-label">
              {correct === questions.length
                ? 'Perfect score!'
                : correct >= Math.ceil(questions.length / 2)
                ? 'Nice work!'
                : 'Keep learning!'}
            </p>
            <button className="qo-btn qo-btn--primary" onClick={onClose}>
              Continue
            </button>
          </div>

        ) : (
          /* ── Question screen ── */
          <>
            <div className="qo-header">
              <span className="qo-progress">{step + 1} / {questions.length}</span>
              <button className="qo-skip" onClick={onClose}>Skip</button>
            </div>

            <p className="qo-question">{q.question}</p>

            <div className="qo-choices">
              {q.choices.map((choice, idx) => {
                let cls = 'qo-choice'
                if (selected !== null) {
                  if (idx === q.correct_index)       cls += ' qo-choice--correct'
                  else if (idx === selected)          cls += ' qo-choice--wrong'
                  else                               cls += ' qo-choice--dim'
                }
                return (
                  <button key={idx} className={cls} onClick={() => choose(idx)}>
                    {choice}
                  </button>
                )
              })}
            </div>

            {selected !== null && (
              <button className="qo-btn qo-btn--primary" onClick={next}>
                {step + 1 < questions.length ? 'Next' : 'See score'}
              </button>
            )}
          </>
        )}

      </div>
    </div>
  )

  return createPortal(overlay, document.body)
}
