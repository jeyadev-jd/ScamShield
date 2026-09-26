const KEY = 'scamshield.cases'

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)) || [] } catch { return [] }
}

export function listCases() { return load() }
export function getCase(id) { return load().find((c) => c.id === id) }

export function saveCase(message, sender, result) {
  const cases = load()
  const year = new Date().getFullYear()
  const n = (cases.length ? Math.max(...cases.map((c) => +c.id.split('-').pop())) : 411) + 1
  const c = { id: `SS-${year}-${String(n).padStart(4, '0')}`, createdAt: new Date().toISOString(), message, sender, result }
  try { localStorage.setItem(KEY, JSON.stringify([c, ...cases].slice(0, 200))) } catch { /* storage blocked */ }
  return c
}

// Cases are snapshots; this replaces a case's result after the analyzer changes.
export function updateCase(id, result) {
  const cases = load().map((c) => (c.id === id ? { ...c, result, reanalyzedAt: new Date().toISOString() } : c))
  try { localStorage.setItem(KEY, JSON.stringify(cases)) } catch { /* storage blocked */ }
  return cases.find((c) => c.id === id)
}

// A calibrated probability is never truly 0 or 1; don't display it as such.
export function formatConfidence(p) {
  if (p >= 0.995) return '> 0.99'
  if (p <= 0.005) return '< 0.01'
  return p.toFixed(2)
}

export function formatIST(iso) {
  return new Date(iso).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }) + ' IST'
}
