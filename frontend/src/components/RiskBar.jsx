const COLOR = { HIGH: 'bg-high', MEDIUM: 'bg-med', LOW: 'bg-low' }

export default function RiskBar({ score, level }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 whitespace-nowrap font-mono text-sm">Risk {score}/100</span>
      <div className="relative h-3 flex-1 border border-ink/60" role="meter" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100}>
        <div className={`h-full ${COLOR[level]}`} style={{ width: `${score}%` }} />
        {[50, 70].map((t) => ( // band edges, see ml/explain.py risk_level
          <span key={t} className="absolute top-[-4px] h-[18px] w-px bg-ink/50" style={{ left: `${t}%` }} />
        ))}
      </div>
    </div>
  )
}
