import { mockAnalyze } from './mockAnalyze.js'

// Empty in dev (Vite proxies /api to :8000); set VITE_API_URL for a deployed backend.
const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
// The rule-based mock is opt-in only (VITE_ALLOW_MOCK=1), for UI work without a backend.
const ALLOW_MOCK = import.meta.env.VITE_ALLOW_MOCK === '1'

export class ApiError extends Error {}

async function getJSON(path) {
  try {
    const r = await fetch(`${BASE}${path}`)
    return r.ok ? await r.json() : null
  } catch {
    return null
  }
}

// Analyze with the trained model. Throws ApiError with a readable message if
// the backend is unreachable or has no model, instead of silently guessing.
export async function analyze(text, sender) {
  let r
  try {
    r = await fetch(`${BASE}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, sender }),
    })
  } catch {
    if (ALLOW_MOCK) return { ...mockAnalyze(text, sender), source: 'mock' }
    throw new ApiError('Cannot reach the ScamShield API. Start it with: uvicorn backend.main:app --port 8000')
  }
  if (r.ok) return { ...(await r.json()), source: 'api' }
  if (ALLOW_MOCK) return { ...mockAnalyze(text, sender), source: 'mock' }
  const detail = await r.json().then((j) => j.detail).catch(() => null)
  throw new ApiError(r.status === 503 ? 'The model is not trained yet. Run: python -m ml.train'
    : r.status === 502 || r.status === 504 ? 'Cannot reach the ScamShield API. Start it with: uvicorn backend.main:app --port 8000'
      : typeof detail === 'string' ? detail : `Analysis failed (HTTP ${r.status}).`)
}

export const getResearch = () => getJSON('/api/research')
export const getDataset = () => getJSON('/api/dataset')
