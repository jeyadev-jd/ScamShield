import { useMemo, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Section from '../components/Section.jsx'
import { listCases, formatIST, formatConfidence } from '../lib/cases.js'

const RISK = { HIGH: 'text-high border-high', MEDIUM: 'text-med border-med', LOW: 'text-low border-low' }
const DATES = [['all', 'Any time'], ['1', 'Last 24 hours'], ['7', 'Last 7 days'], ['30', 'Last 30 days']]

function Select({ label, value, onChange, options }) {
  return (
    <label className="block">
      <span className="block text-xs uppercase tracking-wider text-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 border-b border-ink/60 bg-transparent py-1 pr-6 font-mono text-sm outline-none focus:border-ink"
      >
        {options.map(([v, l]) => <option key={v} value={v} className="bg-paper">{l}</option>)}
      </select>
    </label>
  )
}

export default function Cases() {
  const cases = useMemo(() => listCases(), [])
  const [risk, setRisk] = useState('all')
  const [category, setCategory] = useState('all')
  const [days, setDays] = useState('all')
  const navigate = useNavigate()

  const categories = [...new Set(cases.map((c) => c.result.category))].sort()
  const rows = cases.filter((c) =>
    (risk === 'all' || c.result.risk_level === risk) &&
    (category === 'all' || c.result.category === category) &&
    (days === 'all' || Date.now() - new Date(c.createdAt) < days * 864e5))

  return (
    <Section title="Case register" aside={`${rows.length} of ${cases.length} cases · stored on this device`}>
      <div className="mb-5 flex flex-wrap gap-x-8 gap-y-3">
        <Select label="Risk" value={risk} onChange={setRisk}
          options={[['all', 'All'], ['HIGH', 'High'], ['MEDIUM', 'Medium'], ['LOW', 'Low']]} />
        <Select label="Category" value={category} onChange={setCategory}
          options={[['all', 'All'], ...categories.map((c) => [c, c])]} />
        <Select label="Date" value={days} onChange={setDays} options={DATES} />
      </div>

      {!cases.length ? (
        <p className="text-sm text-muted">No cases yet. <Link to="/" className="text-stamp underline">Analyze a message</Link> to open the first one.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-ink/60 text-left text-xs uppercase tracking-wider text-muted">
                {['Case #', 'Time', 'Message', 'Verdict', 'Category', 'Risk', 'Conf.'].map((h, i) => (
                  <th key={h} className={`py-2 pr-4 font-medium ${i >= 5 ? 'text-right' : ''}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => navigate(`/case/${c.id}`)}
                  className="cursor-pointer border-b border-rule hover:bg-sheet"
                >
                  <td className="py-2 pr-4 font-mono">
                    <Link to={`/case/${c.id}`} onClick={(e) => e.stopPropagation()}>#{c.id.split('-').pop()}</Link>
                  </td>
                  <td className="whitespace-nowrap py-2 pr-4 font-mono text-xs text-muted">{formatIST(c.createdAt)}</td>
                  <td className="max-w-[22rem] truncate py-2 pr-4 font-mono">
                    {c.message.length > 60 ? `${c.message.slice(0, 60)}…` : c.message}
                  </td>
                  <td className="py-2 pr-4">
                    <span className={`inline-block border px-1.5 font-mono text-xs tracking-wider ${c.result.uncertain ? RISK.MEDIUM : RISK[c.result.risk_level]}`}>
                      {c.result.uncertain ? 'REVIEW' : c.result.risk_level}
                    </span>
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs">{c.result.category}</td>
                  <td className="py-2 pr-4 text-right font-mono">{c.result.risk_score}</td>
                  <td className="py-2 text-right font-mono">{formatConfidence(c.result.probability)}</td>
                </tr>
              ))}
              {!rows.length && (
                <tr><td colSpan={7} className="py-4 text-muted">No cases match these filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}
