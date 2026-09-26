import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import Section from '../components/Section.jsx'
import { Figure, ChartTooltip } from '../components/Figure.jsx'
import { getResearch } from '../lib/api.js'
import { useTheme, RAMP, RAMP_DARK } from '../lib/theme.js'

const MODEL = { nb: 'Naive Bayes', lr: 'Logistic regression', svm: 'Linear SVM', rnn: 'Simple RNN', rnn_attn: 'RNN + attention', lstm: 'BiLSTM', lstm_attn: 'BiLSTM + attention', distilbert: 'DistilBERT' }
const SHORT = { nb: 'NB', lr: 'LR', svm: 'SVM', rnn: 'RNN', rnn_attn: 'RNN+att', lstm: 'LSTM', lstm_attn: 'LSTM+att', distilbert: 'BERT' }
const MODEL_ORDER = ['nb', 'lr', 'svm', 'rnn', 'rnn_attn', 'lstm', 'lstm_attn', 'distilbert']
const byModel = (a, b) => MODEL_ORDER.indexOf(a.model) - MODEL_ORDER.indexOf(b.model)
const TICKS = [0, 0.25, 0.5, 0.75, 1]
const CONFIGS = ['Word only', 'Word + normalizer', 'Word + char', 'Word + char + normalizer']
const f2 = (v) => (v == null ? '—' : Number(v).toFixed(3))
const pct = (v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`

function axisProps(t) {
  return { stroke: t.muted, tick: { fill: t.muted, fontSize: 11, fontFamily: 'IBM Plex Mono' }, tickLine: false }
}

function MetricsTable({ rows, caption }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-y border-ink text-left text-xs uppercase tracking-wider text-muted">
            {['Model', 'Test set', 'Accuracy', 'Precision', 'Recall', 'F1 (macro)', 'Scam recall', 'ROC-AUC', 'ECE'].map((h, i) => (
              <th key={h} className={`py-1.5 pr-3 font-medium ${i > 1 ? 'text-right' : ''}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono">
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-rule last:border-ink">
              <td className="py-1.5 pr-3 font-sans">{MODEL[r.model] || r.model}</td>
              <td className="py-1.5 pr-3 text-muted">{r.test.replace('test_', '')}</td>
              {['accuracy', 'precision_macro', 'recall_macro', 'f1_macro', 'scam_recall', 'roc_auc', 'ece'].map((k) => (
                <td key={k} className="py-1.5 pr-3 text-right">{f2(r[k])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {caption}
    </div>
  )
}

// Dumbbell chart: one row per model, UCI accuracy (grey) -> Indian accuracy (accent).
// A slope chart overprints its labels once there are more than a few models.
function DomainShift({ shift }) {
  const models = [...MODEL_ORDER.filter((m) => shift[m]), ...Object.keys(shift).filter((m) => !MODEL_ORDER.includes(m))]
  const lo = Math.max(0, Math.floor((Math.min(...models.map((m) => shift[m].indian)) - 0.02) * 10) / 10)
  const x = (v) => `${((v - lo) / (1 - lo)) * 100}%`
  const ticks = Array.from({ length: Math.round((1 - lo) * 10) + 1 }, (_, i) => +(lo + i / 10).toFixed(1))
  return (
    <div>
      <div className="mb-3 flex gap-5 text-xs">
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-muted" />UCI test</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-stamp" />Indian test</span>
      </div>
      <div className="grid grid-cols-[6.5rem_1fr_auto] items-center gap-y-2.5 sm:grid-cols-[10rem_1fr_auto]">
        {models.map((m) => {
          const { uci, indian, drop_pct: d } = shift[m]
          return [
            <span key={m + 'l'} className="pr-3 text-right text-xs text-muted sm:text-sm">{MODEL[m] || m}</span>,
            <div key={m} className="relative h-5" title={`${MODEL[m] || m}: UCI ${f2(uci)} → Indian ${f2(indian)} (${pct(d)})`}>
              <div className="absolute top-1/2 h-[3px] -translate-y-1/2 bg-rule" style={{ left: x(indian), right: `calc(100% - ${x(uci)})` }} />
              <div className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-muted" style={{ left: x(uci) }} />
              <div className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-stamp" style={{ left: x(indian) }} />
            </div>,
            <span key={m + 'v'} className="whitespace-nowrap pl-3 text-right font-mono text-[11px]">{f2(indian)} ({pct(d)})</span>,
          ]
        })}
        <span />
        <div className="relative mt-1 h-4 border-t border-muted/60 font-mono text-[10px] text-muted">
          {ticks.map((v) => <span key={v} className="absolute -translate-x-1/2 pt-0.5" style={{ left: x(v) }}>{v.toFixed(1)}</span>)}
        </div>
        <span />
      </div>
    </div>
  )
}

function Robustness({ rows, t, dark }) {
  const attacks = [...new Set(rows.map((r) => r.attack))]
  const data = attacks.map((a) => ({
    attack: a.replace('_', '-'),
    ...Object.fromEntries(CONFIGS.map((c) => [c, rows.find((r) => r.attack === a && r.config === c)?.scam_recall])),
  }))
  const ramp = dark ? RAMP_DARK : RAMP
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} barGap={2} barCategoryGap="18%" margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={t.rule} vertical={false} />
        <XAxis dataKey="attack" {...axisProps(t)} />
        <YAxis domain={[0, 1]} ticks={TICKS} {...axisProps(t)} tickFormatter={(v) => v.toFixed(2)} label={{ value: 'Scam recall', angle: -90, position: 'insideLeft', fill: t.muted, fontSize: 11 }} />
        <Tooltip content={<ChartTooltip fmt={f2} />} cursor={{ fill: t.rule, opacity: 0.4 }} />
        <Legend content={() => (
          <ul className="mt-2 flex flex-wrap justify-center gap-x-5 gap-y-1 text-xs">
            {CONFIGS.map((c, i) => (
              <li key={c} className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 border border-rule" style={{ background: ramp[i] }} />{c}
              </li>
            ))}
          </ul>
        )} />
        {CONFIGS.map((c, i) => (
          <Bar key={c} dataKey={c} fill={ramp[i]} radius={[2, 2, 0, 0]} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

function Calibration({ cal, t }) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {Object.entries(cal).map(([m, arms]) => {
        const pts = (arm) => (arms[arm]?.bins || []).filter((b) => b.n).map((b) => ({ x: +b.confidence.toFixed(3), [arm]: b.accuracy }))
        const data = [...pts('raw'), ...pts('calibrated')].sort((a, b) => a.x - b.x)
        return (
          <div key={m}>
            <div className="mb-1 text-sm">{MODEL[m]}</div>
            <div className="mb-2 font-mono text-[11px] text-muted">
              {arms.raw && <>raw ECE {f2(arms.raw.ece)} · </>}calibrated ECE {f2(arms.calibrated.ece)}
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={data} margin={{ top: 5, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid stroke={t.rule} />
                <XAxis type="number" dataKey="x" domain={[0.5, 1]} ticks={[0.5, 0.75, 1]} {...axisProps(t)} tickFormatter={(v) => v.toFixed(2)} />
                <YAxis domain={[0, 1]} ticks={TICKS} {...axisProps(t)} tickFormatter={(v) => v.toFixed(2)} />
                <ReferenceLine segment={[{ x: 0.5, y: 0.5 }, { x: 1, y: 1 }]} stroke={t.muted} strokeDasharray="3 3" />
                <Tooltip content={<ChartTooltip fmt={f2} />} labelFormatter={(v) => `confidence ${v}`} />
                {arms.raw && <Line dataKey="raw" name="Raw" stroke={t.muted} strokeDasharray="4 3" strokeWidth={2} dot={{ r: 3 }} connectNulls isAnimationActive={false} />}
                <Line dataKey="calibrated" name="Calibrated" stroke={t.stamp} strokeWidth={2} dot={{ r: 3 }} connectNulls isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )
      })}
    </div>
  )
}

function Confusion({ rec }) {
  return (
    <table className="font-mono text-sm">
      <thead>
        <tr><th /><th colSpan={rec.labels.length} className="pb-1 text-left text-xs font-normal text-muted">predicted →</th></tr>
        <tr>
          <th className="pr-3 text-left text-xs font-normal text-muted">true ↓</th>
          {rec.labels.map((l) => <th key={l} className="w-20 pb-1 text-center text-xs font-normal">{l}</th>)}
        </tr>
      </thead>
      <tbody>
        {rec.confusion.map((row, i) => {
          const tot = row.reduce((a, b) => a + b, 0) || 1
          return (
            <tr key={i}>
              <td className="pr-3 text-xs">{rec.labels[i]}</td>
              {row.map((v, j) => (
                <td key={j} title={`${v} of ${tot} (${((v / tot) * 100).toFixed(0)}%)`}
                  className="h-10 border border-paper text-center"
                  style={{ background: `color-mix(in srgb, var(--ink) ${Math.round((v / tot) * 85)}%, transparent)`, color: v / tot > 0.5 ? 'var(--paper)' : 'var(--ink)' }}>
                  {v}
                </td>
              ))}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export default function Research() {
  const [data, setData] = useState(undefined)
  const t = useTheme()
  const dark = typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
  useEffect(() => { getResearch().then(setData) }, [])

  if (data === undefined) return <p className="text-sm text-muted">Loading results…</p>
  if (!data) {
    return (
      <Section title="Results">
        <p className="max-w-prose text-sm text-muted">
          No experiment results are available yet. Train and evaluate the models, then start the API:
        </p>
        <pre className="mt-3 border border-rule bg-sheet p-3 font-mono text-xs">{`python -m ml.build_dataset
python -m ml.train
python -m ml.evaluate
uvicorn backend.main:app --port 8000`}</pre>
      </Section>
    )
  }

  const e1 = (data.metrics || []).filter((r) => r.exp === 'E1').sort(byModel)
  const e3 = (data.metrics || []).filter((r) => r.exp === 'E3' && r.task === 'binary' && r.test === 'test_indian').sort(byModel)
  const seedRows = (data.metrics || []).filter((r) => r.exp === 'E2' && r.e2_seed_std != null).sort(byModel)
  const neuralRob = [...(data.robustness_rnn || []), ...(data.robustness_bert || [])]
  const shift = data.domain_shift
  const avgDrop = shift ? Object.values(shift).reduce((a, s) => a + s.drop_pct, 0) / Object.keys(shift).length : null
  const rob = data.robustness || []
  const get = (config, attack) => rob.find((r) => r.config === config && r.attack === attack)?.scam_recall
  const conf = (data.experiments || []).filter((r) => r.exp === 'E3' && r.task === 'multi' && r.test === 'test_indian')
    .sort((a, b) => b.f1_macro - a.f1_macro)[0]
  let fig = 0

  return (
    <article className="space-y-12">
      <header className="border-b-2 border-ink pb-3">
        <h1 className="font-serif text-3xl">Results</h1>
        <p className="mt-1 max-w-prose text-sm text-muted">
          All numbers are produced by <code className="font-mono">ml/run_all.py</code> (TF-IDF models, RNN / BiLSTM, DistilBERT, then evaluation).
          Test sets are held out and de-duplicated against training data.
        </p>
      </header>

      {!!e1.length && (
        <Figure n={1} kind="Table" caption="Baseline performance, trained and tested on the UCI SMS Spam Collection (E1). Probabilities are sigmoid-calibrated.">
          <MetricsTable rows={e1} />
        </Figure>
      )}

      {shift && (
        <Figure n={++fig} caption="Domain shift (E2): the same UCI-trained models on UCI test messages vs the Indian test set."
          note={avgDrop != null && <>Accuracy changes by <strong className="font-mono">{pct(avgDrop)}</strong> on average when models trained on UK SMS meet Indian scams.</>}>
          <DomainShift shift={shift} />
          {!!seedRows.length && (
            <p className="mt-3 max-w-prose text-xs text-muted">
              Recurrent models trained from scratch vary strongly with the random seed out of domain. Indian-set accuracy over{' '}
              {seedRows[0].e2_seeds} seeds:{' '}
              {seedRows.map((r, i) => (
                <span key={r.model} className="font-mono text-ink">
                  {i ? ' · ' : ''}{SHORT[r.model] || r.model} {Number(r.e2_seed_mean).toFixed(2)} ± {Number(r.e2_seed_std).toFixed(2)}
                </span>
              ))}. The chart plots these seed means; the other models are deterministic or pretrained.
            </p>
          )}
        </Figure>
      )}

      {!!e3.length && (
        <Figure n={2} kind="Table" caption="Recovery via data (E3): trained on UCI + Mishra-Soni + the Indian dev split, tested on the held-out Indian set (ham vs scam).">
          <MetricsTable rows={e3} />
        </Figure>
      )}

      {!!rob.length && (
        <Figure n={++fig} caption="Robustness to obfuscation (E4, E7): scam recall on clean and attacked copies of the test set, by defense. Darker bars carry more defense."
          note={get('Word only', 'mixed') != null && <>
            Under the mixed attack, the normalizer moves scam recall from <strong className="font-mono">{f2(get('Word only', 'mixed'))}</strong> to{' '}
            <strong className="font-mono">{f2(get('Word + normalizer', 'mixed'))}</strong>; char n-grams alone reach{' '}
            <strong className="font-mono">{f2(get('Word + char', 'mixed'))}</strong>.
          </>}>
          <Robustness rows={rob} t={t} dark={dark} />
        </Figure>
      )}

      {!!neuralRob.length && (
        <Figure n={3} kind="Table" caption={`Neural models under the same obfuscation attacks (E4), scam recall on ${neuralRob[0].test.replace('test_', '')} test messages, with and without the normalizer. Compare with Figure 2.`}>
          <div className="overflow-x-auto">
            <table className="text-sm">
              <thead>
                <tr className="border-y border-ink text-left text-xs uppercase tracking-wider text-muted">
                  <th className="py-1.5 pr-6 font-medium">Model</th>
                  {[...new Set(neuralRob.map((r) => r.attack))].map((a) => (
                    <th key={a} className="py-1.5 pr-4 text-right font-medium">{a.replace('_', '-')}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {[...new Set(neuralRob.map((r) => r.config))].map((cfg) => (
                  <tr key={cfg} className="border-b border-rule last:border-ink">
                    <td className="py-1.5 pr-6 font-sans">{cfg}</td>
                    {neuralRob.filter((r) => r.config === cfg).map((r) => (
                      <td key={r.attack} className="py-1.5 pr-4 text-right">{f2(r.scam_recall)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Figure>
      )}

      {data.calibration && (
        <Figure n={++fig} caption="Reliability diagrams (E6). Points on the dashed diagonal are perfectly calibrated. Linear SVM has no raw probabilities, so only its calibrated curve is shown.">
          <Calibration cal={data.calibration} t={t} />
        </Figure>
      )}

      {conf && (
        <Figure n={++fig} caption={`Confusion matrix, ${MODEL[conf.model]}, ham / spam / smishing on the Indian test set (E3). Shading shows the share of each true class; hover a cell for the percentage.`}>
          <Confusion rec={conf} />
        </Figure>
      )}

      {!!data.category?.length && (
        <Figure n={4} kind="Table" caption={`Scam category (E5): keyword rules vs a model trained on the Indian dev split${data.category.some((r) => r.method === 'zero_shot') ? ' vs zero-shot NLI' : ''}, on the Indian test set. Indicative only: the public Indian categories were themselves assigned by keyword rules (see Method), so a hand-labelled set is needed for a fair comparison.`}>
          <table className="text-sm">
            <thead>
              <tr className="border-y border-ink text-left text-xs uppercase tracking-wider text-muted">
                <th className="py-1.5 pr-8 font-medium">Method</th><th className="py-1.5 pr-6 text-right font-medium">Accuracy</th><th className="py-1.5 text-right font-medium">F1 (macro)</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {data.category.map((r) => (
                <tr key={r.method} className="border-b border-rule last:border-ink">
                  <td className="py-1.5 pr-8 font-sans">{r.method.replace('_', '-')}</td>
                  <td className="py-1.5 pr-6 text-right">{f2(r.accuracy)}</td>
                  <td className="py-1.5 text-right">{f2(r.f1_macro)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Figure>
      )}
    </article>
  )
}
