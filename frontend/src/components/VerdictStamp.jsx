import { motion } from 'framer-motion'

const STYLE = {
  HIGH: ['HIGH RISK', 'text-high border-high'],
  MEDIUM: ['MEDIUM RISK', 'text-med border-med'],
  LOW: ['LOW RISK', 'text-low border-low'],
  REVIEW: ['NEEDS HUMAN REVIEW', 'text-med border-med'],
}

export default function VerdictStamp({ level, uncertain }) {
  const [text, cls] = STYLE[uncertain ? 'REVIEW' : level]
  return (
    <motion.div
      initial={{ scale: 1.8, opacity: 0, rotate: -4 }}
      animate={{ scale: 1, opacity: 1, rotate: -4 }}
      transition={{ type: 'spring', stiffness: 420, damping: 18, delay: 0.15 }}
      className={`inline-block select-none border-[3px] px-4 py-2 text-center font-mono text-xl font-medium tracking-[0.18em] ${cls}`}
      style={{ outline: '1px solid currentColor', outlineOffset: '3px' }}
      aria-label={`Verdict: ${text}`}
    >
      {text}
    </motion.div>
  )
}
