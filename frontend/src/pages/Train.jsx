import { useEffect, useMemo, useState } from 'react'
import { Check, X, RotateCcw } from 'lucide-react'
import Section from '../components/Section.jsx'
import SmsBubble from '../components/SmsBubble.jsx'
import TokenHeatmap, { alignToOriginal } from '../components/TokenHeatmap.jsx'
import { analyze } from '../lib/api.js'
import { drawQuiz } from '../lib/quiz.js'

const CATEGORY = {
  otp_account: 'OTP / account takeover', kyc: 'KYC update fraud', upi_payment: 'UPI payment fraud',
  prize_lottery: 'prize / lottery', job_task: 'job / task scams', courier: 'courier / customs fee',
  digital_arrest: 'digital arrest', phishing: 'phishing', promotional: 'promotional', legit: 'legitimate messages',
}
const LEVEL = { HIGH: 'text-high', MEDIUM: 'text-med', LOW: 'text-low' }

export default function Train() {
  const [round, setRound] = useState(0)
  const items = useMemo(() => drawQuiz(10), [round])
  const [i, setI] = useState(0)
  const [answers, setAnswers] = useState([])

  const done = answers.length === items.length && i >= items.length
  const q = items[Math.min(i, items.length - 1)]
  const answered = answers.length > i
  const [result, setResult] = useState(null)
  const [modelError, setModelError] = useState('')
  useEffect(() => {
    let live = true
    setResult(null)
    setModelError('')
    analyze(q.text, q.sender).then((r) => live && setResult(r)).catch((e) => live && setModelError(e.message))
    return () => { live = false }
  }, [q])

  function answer(saidScam) { if (!answered) setAnswers([...answers, saidScam]) }
  function restart() { setRound(round + 1); setI(0); setAnswers([]) }

  if (done) {
    const score = answers.filter((a, k) => a === items[k].scam).length
    const missed = items.filter((it, k) => answers[k] !== it.scam)
    return (
      <Section title="Awareness drill: result" className="max-w-2xl">
        <p className="font-serif text-5xl">{score}<span className="text-muted">/{items.length}</span></p>
        <p className="mt-3 text-sm text-muted">
          {score === items.length ? 'No mistakes.' : `You misjudged ${missed.length} message${missed.length > 1 ? 's' : ''}.`}
        </p>
        {!!missed.length && (
          <table className="mt-6 w-full text-sm">
            <thead>
              <tr className="border-b border-ink/60 text-left text-xs uppercase tracking-wider text-muted">
                <th className="py-1.5 font-medium">Missed</th><th className="py-1.5 font-medium">Type</th><th className="py-1.5 text-right font-medium">Truth</th>
              </tr>
            </thead>
            <tbody>
              {missed.map((m, k) => (
                <tr key={k} className="border-b border-rule">
                  <td className="max-w-[16rem] truncate py-1.5 pr-3 font-mono">{m.text}</td>
                  <td className="py-1.5 pr-3">{CATEGORY[m.category]}</td>
                  <td className={`py-1.5 text-right font-mono ${m.scam ? 'text-high' : 'text-low'}`}>{m.scam ? 'SCAM' : 'LEGIT'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <button onClick={restart} className="mt-8 inline-flex items-center gap-2 rounded-sm bg-stamp px-5 py-2.5 text-sm font-medium text-paper hover:opacity-90">
          <RotateCcw size={15} strokeWidth={1.5} /> New drill
        </button>
      </Section>
    )
  }

  const correct = answered && answers[i] === q.scam
  return (
    <div className="grid gap-10 lg:grid-cols-12">
      <div className="lg:col-span-5">
        <Section title="Awareness drill" aside={`Message ${i + 1} of ${items.length}`}>
          <div className="mb-5 flex gap-1" aria-hidden>
            {items.map((it, k) => (
              <span key={k} className={`h-1 flex-1 ${k < answers.length ? (answers[k] === it.scam ? 'bg-ink' : 'bg-high') : 'bg-rule'}`} />
            ))}
          </div>
          <SmsBubble sender={q.sender} time={q.time} text={q.text} />
          <div className="mx-auto mt-5 grid max-w-sm grid-cols-2 gap-3">
            {[[false, 'Legitimate'], [true, 'Scam']].map(([v, l]) => {
              const picked = answered && answers[i] === v
              return (
                <button
                  key={l}
                  onClick={() => answer(v)}
                  disabled={answered}
                  className={`rounded-sm border px-4 py-2.5 text-sm font-medium ${picked ? 'border-ink bg-ink text-paper' : 'border-ink/60 hover:bg-sheet'} disabled:cursor-default ${answered && !picked ? 'opacity-40' : ''}`}
                >{l}</button>
              )
            })}
          </div>
        </Section>
      </div>

      <div className="lg:col-span-7">
        {answered ? (
          <Section title="Reveal">
            <p className={`flex items-center gap-2 font-serif text-2xl ${correct ? '' : 'text-high'}`}>
              {correct ? <Check size={22} strokeWidth={1.5} /> : <X size={22} strokeWidth={1.5} />}
              {correct ? 'Correct' : 'Not quite'}: this is {q.scam ? 'a scam' : 'legitimate'}.
            </p>

            <h3 className="mt-6 text-xs font-semibold uppercase tracking-[0.14em]">What gave it away</h3>
            <p className="mt-1.5 max-w-prose">{q.tell}</p>

            {modelError && <p className="mt-6 text-sm text-muted">Model verdict unavailable: {modelError}</p>}
            {!result && !modelError && <p className="mt-6 text-sm text-muted">Asking the model…</p>}
            {result && <>
              <h3 className="mt-6 text-xs font-semibold uppercase tracking-[0.14em]">
                Model verdict: <span className={`font-mono ${LEVEL[result.risk_level]}`}>{result.risk_level} {result.risk_score}/100</span>
                {(result.risk_level !== 'LOW') !== q.scam && <span className="ml-2 font-normal normal-case tracking-normal text-med">(the model got this one wrong)</span>}
              </h3>
              <div className="mt-2 border border-rule bg-sheet p-3">
                <TokenHeatmap key={i} tokens={alignToOriginal(q.text, result.token_contributions)} />
              </div>
              <ul className="mt-3 space-y-1 text-sm">
                {result.indicators.slice(0, 3).map((ind, k) => (
                  <li key={k} className="flex justify-between border-b border-rule py-1">
                    <span>{ind.label}</span>
                    <span className={`font-mono ${ind.weight < 0 ? 'text-low' : ''}`}>{ind.weight > 0 ? '+' : ''}{ind.weight.toFixed(2)}</span>
                  </li>
                ))}
              </ul>
            </>}

            <button onClick={() => setI(i + 1)} className="mt-6 rounded-sm bg-stamp px-5 py-2.5 text-sm font-medium text-paper hover:opacity-90">
              {i + 1 < items.length ? 'Next message' : 'See result'}
            </button>
          </Section>
        ) : (
          <Section title="Reveal">
            <p className="text-sm text-muted">Decide first. The model's reading and the giveaway appear after you answer.</p>
          </Section>
        )}
      </div>
    </div>
  )
}
