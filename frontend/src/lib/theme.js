import { useEffect, useState } from 'react'

// SVG presentation attributes cannot read CSS variables, so charts resolve
// the palette tokens once and re-resolve when the colour scheme changes.
const NAMES = ['paper', 'sheet', 'ink', 'muted', 'rule', 'high', 'med', 'low', 'stamp']

function read() {
  const cs = getComputedStyle(document.documentElement)
  return Object.fromEntries(NAMES.map((n) => [n, cs.getPropertyValue(`--${n}`).trim()]))
}

export function useTheme() {
  const [t, setT] = useState(read)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const on = () => setT(read())
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return t
}

// Ordered defense configs (E4/E7): one hue, light -> dark = weaker -> stronger.
export const RAMP = ['#C9D3EE', '#8FA3D6', '#4F6BB5', '#1E3A8A']
export const RAMP_DARK = ['#3A4A73', '#5A6FA6', '#7D93D1', '#B3C2EC']
