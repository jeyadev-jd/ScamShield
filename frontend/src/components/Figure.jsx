export function Figure({ n, kind = 'Figure', caption, children, note }) {
  return (
    <figure className="border-t border-rule pt-4">
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-9">{children}</div>
        {note && (
          <aside className="border-l-2 border-stamp pl-3 text-sm lg:col-span-3 lg:self-start">
            <div className="mb-1 text-[11px] uppercase tracking-wider text-muted">Key finding</div>
            {note}
          </aside>
        )}
      </div>
      <figcaption className="mt-3 max-w-prose font-serif text-sm italic text-muted">
        <span className="not-italic font-semibold text-ink">{kind} {n}.</span> {caption}
      </figcaption>
    </figure>
  )
}

export function ChartTooltip({ active, payload, label, fmt = (v) => v }) {
  if (!active || !payload?.length) return null
  return (
    <div className="border border-rule bg-sheet px-2.5 py-1.5 font-mono text-xs shadow-none">
      {label !== undefined && <div className="mb-1 text-muted">{label}</div>}
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="inline-block h-2 w-2" style={{ background: p.color || p.stroke || p.fill }} />
          <span>{p.name}</span>
          <span className="ml-auto pl-3">{fmt(p.value)}</span>
        </div>
      ))}
    </div>
  )
}
