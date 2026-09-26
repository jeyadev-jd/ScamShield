// Small presentational blocks used on the Case Report page.

export function ObfuscationTable({ items }) {
  if (!items.length) return <p className="text-sm text-muted">No obfuscated tokens found.</p>
  return (
    <table className="w-full font-mono text-sm">
      <tbody>
        {items.map((o, i) => (
          <tr key={i} className="border-b border-rule last:border-0">
            <td className="py-1.5 pr-3">{o.from}</td>
            <td className="py-1.5 pr-3 text-muted">→</td>
            <td className="py-1.5 pr-3">{o.to}</td>
            <td className="py-1.5 text-right text-xs text-muted">{o.kind}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Flag({ on, children }) {
  return <span className={on ? 'text-high' : ''}>{children}</span>
}

export function UrlForensicsCard({ url }) {
  if (!url) return <p className="text-sm text-muted">No link in message.</p>
  const rows = [
    ['Domain', <span className="break-all">{url.domain}</span>],
    ['Imitates', url.lookalike_of ? <Flag on>{url.lookalike_of} <span className="text-muted">(distance {url.distance})</span></Flag> : 'none found'],
    ['TLD', <Flag on={url.suspicious_tld}>.{url.domain.split('.').pop()}{url.suspicious_tld ? ' — flagged' : ''}</Flag>],
    ['Shortener', <Flag on={url.shortener}>{url.shortener ? 'yes — real target hidden' : 'no'}</Flag>],
    ['IP host', url.ip_host ? <Flag on>yes</Flag> : 'no'],
    ['HTTPS', url.https ? 'yes' : 'unknown'],
  ]
  return (
    <table className="w-full font-mono text-sm">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k} className="border-b border-rule last:border-0">
            <td className="w-28 py-1.5 pr-3 font-sans text-xs uppercase tracking-wider text-muted">{k}</td>
            <td className="py-1.5">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const STAGES = [['hook', 'Hook'], ['urgency', 'Urgency'], ['credibility', 'Authority'], ['ask', 'Ask']]

export function KillChain({ chain }) {
  if (!Object.keys(chain).length) return <p className="text-sm text-muted">No attack pattern detected.</p>
  return (
    <ol className="grid grid-cols-2 gap-y-6 sm:grid-cols-4">
      {STAGES.map(([key, label], i) => {
        const hit = chain[key]
        return (
          <li key={key} className="relative pr-4">
            {i < 3 && <span className="absolute left-3 right-0 top-[5px] hidden h-px bg-rule sm:block" />}
            <span className={`relative block h-[11px] w-[11px] rounded-full border ${hit ? 'border-ink bg-ink' : 'border-muted bg-paper'}`} />
            <div className="mt-2 text-xs font-semibold uppercase tracking-[0.14em]">{label}</div>
            <div className={`mt-1 font-mono text-sm ${hit ? '' : 'text-muted'}`}>{hit ? `"${hit}"` : '—'}</div>
          </li>
        )
      })}
    </ol>
  )
}

export function IndicatorTable({ items }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-ink/60 text-left text-xs uppercase tracking-wider text-muted">
          <th className="py-1.5 font-medium">Indicator</th>
          <th className="py-1.5 text-right font-medium">Weight</th>
        </tr>
      </thead>
      <tbody>
        {items.map((it, i) => (
          <tr key={i} className="border-b border-rule last:border-0">
            <td className="py-1.5 pr-3">{it.label}</td>
            <td className={`py-1.5 text-right font-mono ${it.weight < 0 ? 'text-low' : ''}`}>
              {it.weight > 0 ? '+' : ''}{it.weight.toFixed(2)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function AdviceList({ items }) {
  return (
    <ol className="space-y-1.5">
      {items.map((a, i) => (
        <li key={i} className="flex gap-3">
          <span className="font-mono text-muted">{i + 1}.</span>
          <span>{a}</span>
        </li>
      ))}
    </ol>
  )
}
