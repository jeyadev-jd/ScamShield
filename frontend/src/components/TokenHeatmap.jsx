import { motion } from 'framer-motion'
import { normalize } from '../lib/mockAnalyze.js'

// Shades each token by its contribution. High weights use the red accent;
// low ones use ink at low opacity so red stays reserved for the strongest signals.
// `r` is the weight relative to the strongest word in this message (-1..1),
// so mock weights and API log-odds weights shade on the same scale.
function shade(r) {
  if (r <= -0.25) return { background: `color-mix(in srgb, var(--low) ${Math.round(-r * 22)}%, transparent)` }
  if (r < 0.08) return {}
  if (r >= 0.6) return { background: 'color-mix(in srgb, var(--high) 28%, transparent)', borderBottom: '2px solid var(--high)' }
  return { background: `color-mix(in srgb, var(--med) ${Math.round(12 + r * 40)}%, transparent)`, borderBottom: '1px solid var(--med)' }
}

export default function TokenHeatmap({ tokens }) {
  const max = Math.max(1e-9, ...tokens.map((t) => Math.abs(t.weight)))
  return (
    <p className="font-mono text-[15px] leading-8 whitespace-pre-wrap break-words">
      {tokens.map((t, i) =>
        /^\s+$/.test(t.token) ? t.token : (
          <motion.span
            key={i}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.02 * i, duration: 0.15 }}
            style={shade(t.weight / max)}
            className="px-[1px]"
            title={t.weight ? `weight ${t.weight > 0 ? '+' : ''}${t.weight.toFixed(2)}` : undefined}
          >
            {t.token}
          </motion.span>
        ),
      )}
    </p>
  )
}

// Maps weights from normalized tokens back onto the original message:
// each original token is normalized on its own and looked up by its canonical form.
export function alignToOriginal(original, tokens) {
  // API tokens carry character spans into the original text: rebuild with the whitespace between them.
  if (tokens.length && tokens[0].start !== undefined) {
    const out = []
    let pos = 0
    for (const t of tokens) {
      if (t.start > pos) out.push({ token: original.slice(pos, t.start), weight: 0 })
      out.push({ token: original.slice(t.start, t.end), weight: t.weight })
      pos = t.end
    }
    if (pos < original.length) out.push({ token: original.slice(pos), weight: 0 })
    return out
  }
  const strip = (s) => s.replace(/^[^\w]+|[^\w]+$/g, '')
  const byWord = {}
  for (const t of tokens) if (t.weight) byWord[strip(t.token)] = t.weight
  return original.split(/(\s+)/).filter(Boolean).map((tok) => {
    if (/^\s+$/.test(tok)) return { token: tok, weight: 0 }
    const canon = strip(normalize(tok).text)
    return { token: tok, weight: byWord[canon] ?? byWord[strip(tok.toLowerCase())] ?? 0 }
  })
}

// Normalized view: API tokens are original words, so show each one normalized.
// Mock tokens are already normalized and are returned as-is.
export function normalizedView(original, tokens) {
  if (!tokens.length || tokens[0].start === undefined) return tokens
  return alignToOriginal(original, tokens).map((t) =>
    /^\s+$/.test(t.token) ? t : { ...t, token: normalize(t.token).text })
}
