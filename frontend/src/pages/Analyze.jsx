import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronRight, Loader2 } from 'lucide-react'
import Section from '../components/Section.jsx'
import { analyze } from '../lib/api.js'
import { saveCase, listCases } from '../lib/cases.js'
import { SAMPLES } from '../lib/samples.js'
import { findUrl } from '../lib/mockAnalyze.js'

const PILL = { HIGH: 'text-high', MEDIUM: 'text-med', LOW: 'text-low' }

// The PWA share target opens "/?text=...&title=...&url=...". Messaging apps
// differ in which field they fill, so join whatever arrived.
function sharedText(params) {
  return ['title', 'text', 'url'].map((k) => params.get(k)).filter(Boolean)
    .filter((v, i, a) => !a.slice(0, i).some((p) => p.includes(v))).join(' ').trim()
}

export default function Analyze() {
  const [params, setParams] = useSearchParams()
  const [text, setText] = useState(() => sharedText(params))
  const [sender, setSender] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const shared = useMemo(() => !!sharedText(params), []) // eslint-disable-line react-hooks/exhaustive-deps
  const navigate = useNavigate()
  useEffect(() => { if (shared) setParams({}, { replace: true }) }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const recent = useMemo(() => listCases().slice(0, 6), [])

  const stats = useMemo(() => ({
    chars: text.length,
    urls: text.split(/\s+/).filter((w) => findUrl(w)).length,
    numbers: (text.match(/\d[\d,.]*/g) || []).length,
  }), [text])

  async function submit() {
    if (!text.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      const result = await analyze(text.trim(), sender.trim())
      const c = saveCase(text.trim(), sender.trim(), result)
      navigate(`/case/${c.id}`)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-10 lg:grid-cols-12">
      <div className="lg:col-span-8">
        <Section n={1} title="Submit message" aside={shared ? 'received from share sheet' : null}>
          <label htmlFor="msg" className="sr-only">SMS text</label>
          <textarea
            id="msg"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit() }}
            rows={7}
            placeholder="Paste the SMS here, exactly as received."
            className="lined w-full resize-y border border-rule bg-sheet px-3 pt-0 font-mono text-[15px] outline-none placeholder:text-muted focus:border-ink"
          />
          <div className="mt-1 font-mono text-xs text-muted">
            {stats.chars} chars · {stats.urls} URL{stats.urls === 1 ? '' : 's'} · {stats.numbers} number{stats.numbers === 1 ? '' : 's'}
          </div>

          <div className="mt-5 flex flex-wrap items-end gap-x-6 gap-y-4">
            <label className="block">
              <span className="block text-xs uppercase tracking-wider text-muted">Sender (optional)</span>
              <input
                value={sender}
                onChange={(e) => setSender(e.target.value)}
                placeholder="VM-SBIINB"
                className="mt-1 w-48 border-b border-ink/60 bg-transparent py-1 font-mono text-sm outline-none placeholder:text-muted/60 focus:border-ink"
              />
            </label>
            <button
              onClick={submit}
              disabled={!text.trim() || busy}
              className="inline-flex items-center gap-2 rounded-sm bg-stamp px-5 py-2.5 text-sm font-medium text-paper hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy && <Loader2 size={15} strokeWidth={1.5} className="animate-spin" />}
              Analyze message
            </button>
            <span className="font-mono text-xs text-muted">Ctrl+Enter</span>
          </div>
          {error && (
            <p role="alert" className="mt-4 border-l-2 border-high pl-3 text-sm">
              <span className="font-medium text-high">Not analyzed.</span> {error}
            </p>
          )}
        </Section>

        <p className="mt-10 max-w-prose border-l-2 border-rule pl-4 text-sm text-muted">
          Links in the message are never opened. ScamShield only inspects the text of the message and the
          spelling of any link. The risk score is an indicator, not a guarantee.
        </p>
      </div>

      <aside className="space-y-10 lg:col-span-4">
        <Section title="Recent cases" aside={recent.length ? <Link to="/cases" className="hover:text-ink">all</Link> : null}>
          {recent.length ? (
            <ul className="font-mono text-sm">
              {recent.map((c) => (
                <li key={c.id} className="border-b border-rule last:border-0">
                  <Link to={`/case/${c.id}`} className="grid grid-cols-[4.5rem_4.5rem_1fr] py-1.5 hover:bg-sheet">
                    <span>#{c.id.split('-').pop()}</span>
                    <span className={PILL[c.result.risk_level]}>{c.result.risk_level}</span>
                    <span className="truncate text-muted">{c.result.category}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-muted">No cases yet.</p>}
        </Section>

        <Section title="Sample messages">
          <ul className="text-sm">
            {SAMPLES.map((s) => (
              <li key={s.label}>
                <button
                  onClick={() => { setText(s.text); setSender(s.sender) }}
                  className="group flex w-full items-center gap-1.5 border-b border-rule py-1.5 text-left hover:text-stamp"
                >
                  <ChevronRight size={14} strokeWidth={1.5} className="text-muted group-hover:text-stamp" />
                  {s.label}
                </button>
              </li>
            ))}
          </ul>
        </Section>
      </aside>
    </div>
  )
}
