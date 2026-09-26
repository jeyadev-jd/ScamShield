import { useEffect, useMemo, useState } from 'react'
import { Download } from 'lucide-react'
import Section from '../components/Section.jsx'
import { getDataset } from '../lib/api.js'

const SPLITS = ['train', 'test_uci', 'test_ms', 'test_indian', 'dev_indian']
// Source strings come from build_dataset: "uci", "mishra_soni", "synthetic" (train-only
// augmentation from ml.synth) and "indian:<origin>" for everything in the Indian set.
const isPublicIndian = (s) => /^indian:(india_spam_github|scamshield_hf)/.test(s)
const isIllustrative = (s) => /^indian:(synthetic|published_example)$/.test(s)
const GROUPS = [
  ['UCI', (s) => s === 'uci', 'bg-muted'],
  ['Mishra-Soni', (s) => s === 'mishra_soni', 'bg-ink'],
  ['Indian public datasets', isPublicIndian, 'bg-stamp'],
  ['Indian reported (news, PIB)', (s) => s.startsWith('indian:') && !isPublicIndian(s) && !isIllustrative(s), 'bg-high'],
  ['Indian illustrative', isIllustrative, 'bg-stamp/40'],
  ['Synthetic (train only)', (s) => s === 'synthetic', 'bg-rule'],
]
const LABEL = { ham: 'text-low border-low', spam: 'text-med border-med', smishing: 'text-high border-high' }

function toCSV(rows) {
  const esc = (v) => `"${String(v).replace(/"/g, '""')}"`
  const cols = ['text', 'label', 'category', 'source', 'is_synthetic']
  return [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n')
}

export default function Dataset() {
  const [data, setData] = useState(undefined)
  const [cat, setCat] = useState('all')
  useEffect(() => { getDataset().then(setData) }, [])

  const specimens = data?.specimens || []
  const byCategory = useMemo(() => {
    const m = {}
    for (const s of specimens) {
      m[s.category] ??= { ham: 0, spam: 0, smishing: 0, synthetic: 0 }
      m[s.category][s.label]++
      m[s.category].synthetic += Number(s.is_synthetic)
    }
    return Object.entries(m).sort((a, b) => a[0].localeCompare(b[0]))
  }, [specimens])

  if (data === undefined) return <p className="text-sm text-muted">Loading dataset…</p>
  if (!data) {
    return (
      <Section title="Dataset">
        <p className="max-w-prose text-sm text-muted">No processed dataset is available. Build it and start the API:</p>
        <pre className="mt-3 border border-rule bg-sheet p-3 font-mono text-xs">{`python -m ml.build_dataset
uvicorn backend.main:app --port 8000`}</pre>
      </Section>
    )
  }

  const st = data.stats
  const totals = GROUPS.map(([name, match, cls]) => [name, cls, SPLITS.reduce((a, sp) =>
    a + Object.entries(st[sp]?.source || {}).filter(([s]) => match(s)).reduce((x, [, n]) => x + n, 0), 0)])
  const total = totals.reduce((a, [, , n]) => a + n, 0) || 1
  const shown = specimens.filter((s) => cat === 'all' || s.category === cat)

  function download() {
    const url = URL.createObjectURL(new Blob([toCSV(specimens)], { type: 'text/csv' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: 'scamshield_indian_set.csv' })
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <article className="space-y-10">
      <header className="border-b-2 border-ink pb-3">
        <h1 className="font-serif text-3xl">Dataset</h1>
        <p className="mt-1 text-sm text-muted">{total.toLocaleString('en-IN')} messages after cleaning and de-duplication.</p>
      </header>

      <Section n={1} title="Composition">
        <div className="flex h-6 w-full gap-[2px]" role="img" aria-label="Messages by source">
          {totals.filter(([, , n]) => n).map(([name, cls, n]) => (
            <div key={name} className={`${cls} h-full`} style={{ width: `${(n / total) * 100}%` }} title={`${name}: ${n}`} />
          ))}
        </div>
        <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
          {totals.map(([name, cls, n]) => (
            <li key={name} className="flex items-center gap-2">
              <span className={`inline-block h-2.5 w-2.5 ${cls}`} />{name}
              <span className="font-mono text-muted">{n.toLocaleString('en-IN')} ({((n / total) * 100).toFixed(1)}%)</span>
            </li>
          ))}
        </ul>

        <table className="mt-6 w-full max-w-2xl text-sm">
          <thead>
            <tr className="border-y border-ink text-left text-xs uppercase tracking-wider text-muted">
              <th className="py-1.5 font-medium">Split</th>
              {['ham', 'spam', 'smishing', 'total'].map((h) => <th key={h} className="py-1.5 text-right font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody className="font-mono">
            {SPLITS.filter((s) => st[s]).map((s) => (
              <tr key={s} className="border-b border-rule last:border-ink">
                <td className="py-1.5">{s}</td>
                {['ham', 'spam', 'smishing'].map((l) => <td key={l} className="py-1.5 text-right">{st[s].label[l] || 0}</td>)}
                <td className="py-1.5 text-right">{st[s].n}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {st.overlap_removed && (
          <p className="mt-2 text-xs text-muted">
            Removed from test sets because a near-duplicate appears in training:{' '}
            <span className="font-mono">{Object.entries(st.overlap_removed).map(([k, v]) => `${k} ${v}`).join(' · ')}</span>
          </p>
        )}
      </Section>

      {!!byCategory.length && (
        <Section n={2} title="Indian set by category">
          <table className="w-full max-w-2xl text-sm">
            <thead>
              <tr className="border-y border-ink text-left text-xs uppercase tracking-wider text-muted">
                <th className="py-1.5 font-medium">Category</th>
                {['ham', 'spam', 'smishing', 'synthetic'].map((h) => <th key={h} className="py-1.5 text-right font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody className="font-mono">
              {byCategory.map(([c, v]) => (
                <tr key={c} className="border-b border-rule last:border-ink">
                  <td className="py-1.5">{c}</td>
                  {['ham', 'spam', 'smishing', 'synthetic'].map((k) => <td key={k} className="py-1.5 text-right">{v[k] || '·'}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {!!specimens.length && (
        <Section n={3} title="Specimens" aside={
          <button onClick={download} className="inline-flex items-center gap-1.5 text-stamp hover:underline">
            <Download size={14} strokeWidth={1.5} /> Download Indian set (CSV)
          </button>
        }>
          <label className="mb-4 block text-xs uppercase tracking-wider text-muted">
            Category{' '}
            <select value={cat} onChange={(e) => setCat(e.target.value)}
              className="ml-2 border-b border-ink/60 bg-transparent py-1 font-mono text-sm normal-case tracking-normal text-ink outline-none">
              <option value="all" className="bg-paper">all ({specimens.length})</option>
              {byCategory.map(([c]) => <option key={c} value={c} className="bg-paper">{c}</option>)}
            </select>
          </label>
          <ul className="divide-y divide-rule border-y border-rule">
            {shown.slice(0, 60).map((s, i) => (
              <li key={i} className="grid gap-2 py-2.5 sm:grid-cols-[1fr_auto]">
                <p className="font-mono text-sm">{s.text}</p>
                <div className="flex items-start gap-2 text-xs">
                  <span className={`border px-1.5 font-mono ${LABEL[s.label]}`}>{s.label}</span>
                  <span className="font-mono text-muted">{s.category}</span>
                  {Number(s.is_synthetic) === 1 && <span className="font-mono text-muted">· synthetic</span>}
                </div>
              </li>
            ))}
          </ul>
          {shown.length > 60 && <p className="mt-2 text-xs text-muted">Showing 60 of {shown.length}.</p>}
        </Section>
      )}

      <Section n={4} title="Ethics and anonymization">
        <div className="max-w-prose space-y-2 text-sm">
          <p>Personal messages were shared with consent. Phone numbers, Aadhaar and PAN numbers, account numbers and e-mail addresses are masked
            automatically (<code className="font-mono">build_dataset.anonymize</code>) and then checked by hand.</p>
          <p>Messages written or adapted by the authors carry <code className="font-mono">is_synthetic = 1</code> and are reported separately,
            so results can be checked on real messages alone.</p>
          <p>The Indian set is used only for testing, apart from the dev split that experiment E3 adds to training.
            Public datasets are used under their original licenses.</p>
        </div>
      </Section>
    </article>
  )
}
