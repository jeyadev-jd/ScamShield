// Scores the rule-based mock on labeled messages.
//   node scripts/eval-mock.mjs            # summary + misses
//   node scripts/eval-mock.mjs --all      # every message
import { mockAnalyze } from '../src/lib/mockAnalyze.js'
import { TUNE, HOLDOUT } from './mock-cases.js'

const all = process.argv.includes('--all')

function score(name, cases) {
  let tp = 0, fp = 0, fn = 0, tn = 0
  const lines = []
  for (const [text, scam, sender = ''] of cases) {
    const r = mockAnalyze(text, sender)
    const flagged = r.risk_level !== 'LOW'
    if (flagged && scam) tp++; else if (flagged) fp++; else if (scam) fn++; else tn++
    const ok = flagged === scam
    if (!ok || all) lines.push(`  ${ok ? 'ok ' : 'MISS'} ${scam ? 'scam' : 'legit'} -> ${r.risk_level.padEnd(6)} ${String(r.risk_score).padStart(3)}  ${text.slice(0, 70)}`)
  }
  const n = cases.length
  console.log(`${name}: ${tp + tn}/${n} correct · scam recall ${(tp / (tp + fn)).toFixed(2)} · false alarms ${fp}/${fp + tn}`)
  lines.forEach((l) => console.log(l))
  return fn + fp
}

const bad = score('TUNE', TUNE) + score('HOLDOUT', HOLDOUT)
process.exitCode = bad ? 1 : 0
