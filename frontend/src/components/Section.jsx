export default function Section({ n, title, aside, children, className = '' }) {
  return (
    <section className={`border-t border-rule pt-4 ${className}`}>
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h2 className="font-sans text-xs font-semibold uppercase tracking-[0.14em]">
          {n && <span className="mr-2 font-serif text-muted">§{n}</span>}
          {title}
        </h2>
        {aside && <span className="text-xs text-muted">{aside}</span>}
      </div>
      {children}
    </section>
  )
}
