import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Printer, RotateCw } from 'lucide-react'
import Section from '../components/Section.jsx'
import VerdictStamp from '../components/VerdictStamp.jsx'
import RiskBar from '../components/RiskBar.jsx'
import TokenHeatmap, { alignToOriginal, normalizedView } from '../components/TokenHeatmap.jsx'
import { ObfuscationTable, UrlForensicsCard, KillChain, IndicatorTable, AdviceList } from '../components/Evidence.jsx'
import { getCase, updateCase, formatIST, formatConfidence } from '../lib/cases.js'
import { analyze } from '../lib/api.js'

const LABEL = { smishing: 'Smishing', spam: 'Spam', ham: 'Legitimate' }
const CATEGORY = {
  otp_account: 'OTP / account takeover', kyc: 'KYC update fraud', upi_payment: 'UPI payment fraud',
  prize_lottery: 'Prize / lottery', job_task: 'Job / task scam', courier: 'Courier / customs fee',
  digital_arrest: 'Digital arrest', phishing: 'Phishing', promotional: 'Promotional', legit: 'Legitimate',
}

export default function CaseReport() {
  const { id } = useParams()
  const [c, setC] = useState(() => getCase(id))
  const [view, setView] = useState('original')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { setC(getCase(id)) }, [id])

  async function reanalyze() {
    setBusy(true)
    setError('')
    try {
      setC(updateCase(c.id, await analyze(c.message, c.sender || '')))
    } catch (e) {
      setError(e.message)
    }
    setBusy(false)
  }

  if (!c) {
    return (
      <p className="text-muted">
        Case {id} not found on this device. <Link to="/" className="text-stamp underline">Analyze a message</Link>
      </p>
    )
  }
  const r = c.result
  const tokens = view === 'original'
    ? alignToOriginal(c.message, r.token_contributions)
    : normalizedView(c.message, r.token_contributions)

  return (
    <article className="space-y-8 overflow-x-clip">
      <header className="flex flex-wrap items-baseline justify-between gap-3 border-b-2 border-ink pb-3">
        <h1 className="font-mono text-lg tracking-wide">CASE #{c.id}</h1>
        <div className="flex items-center gap-5 text-sm text-muted">
          <time dateTime={c.createdAt} className="font-mono">{formatIST(c.createdAt)}</time>
          <button onClick={reanalyze} disabled={busy} title="Run this message through the current analyzer again"
            className="inline-flex items-center gap-1.5 text-stamp hover:underline disabled:opacity-50 print:hidden">
            <RotateCw size={14} strokeWidth={1.5} className={busy ? 'animate-spin' : ''} /> Re-analyze
          </button>
          <button onClick={() => window.print()} className="inline-flex items-center gap-1.5 text-stamp hover:underline print:hidden">
            <Printer size={15} strokeWidth={1.5} /> Export PDF
          </button>
        </div>
      </header>
      {error && <p role="alert" className="border-l-2 border-high pl-3 text-sm"><span className="font-medium text-high">Re-analysis failed.</span> {error}</p>}

      <Section n={1} title="Verdict" aside={r.source === 'mock' ? 'rule-based preview (model not connected)' : null}>
        <div className="flex flex-col-reverse gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex-1 space-y-3">
            <p className="font-serif text-2xl">
              {LABEL[r.label]}
              {r.category !== 'legit' && <> <span className="text-muted">·</span> {CATEGORY[r.category] || r.category}</>}
            </p>
            <div className="max-w-xl"><RiskBar score={r.risk_score} level={r.risk_level} /></div>
            <p className="font-mono text-sm text-muted">
              Confidence it is {LABEL[r.label]?.toLowerCase() || r.label}: {formatConfidence(r.probability)} {r.source === 'mock' ? '(heuristic, not calibrated)' : '(calibrated)'}
              {r.uncertain && <span className="text-med"> — inside the uncertainty zone, review manually</span>}
            </p>
            {c.sender && <p className="font-mono text-sm text-muted">Sender {c.sender}</p>}
          </div>
          <div className="sm:pr-4 sm:pt-2"><VerdictStamp key={c.reanalyzedAt || 'first'} level={r.risk_level} uncertain={r.uncertain} /></div>
        </div>
      </Section>

      <Section
        n={2}
        title="Evidence: message as submitted"
        aside={
          <span className="inline-flex border border-rule text-xs">
            {['original', 'normalized'].map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-2.5 py-1 capitalize ${view === v ? 'bg-ink text-paper' : 'hover:text-ink'}`}
              >{v}</button>
            ))}
          </span>
        }
      >
        <div className="border border-rule bg-sheet p-4">
          <TokenHeatmap key={view + (c.reanalyzedAt || '')} tokens={tokens} />
        </div>
        <p className="mt-2 text-xs text-muted">Shading shows how much each word pushed the verdict. Hover a word for its weight.</p>
      </Section>

      <div className="grid gap-8 md:grid-cols-2">
        <Section n={3} title="Obfuscation found"><ObfuscationTable items={r.obfuscation_detected} /></Section>
        <Section n={4} title="Link forensics" aside="not visited"><UrlForensicsCard url={r.url_analysis} /></Section>
      </div>

      <Section n={5} title="Attack pattern (kill-chain)"><KillChain chain={r.kill_chain} /></Section>

      <div className="grid gap-8 md:grid-cols-2">
        <Section n={6} title="Indicators"><IndicatorTable items={r.indicators} /></Section>
        <Section n={7} title="What to do"><AdviceList items={r.advice} /></Section>
      </div>
    </article>
  )
}
