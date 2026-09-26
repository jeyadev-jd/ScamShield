// Rule-based stand-in for POST /api/analyze. Returns the same schema as the
// planned FastAPI response so the UI can be built before the model exists.

const LEET = { '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's' }
const HOMOGLYPH = { 'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'х': 'x', 'і': 'i', 'ѕ': 's' }

const BRANDS = {
  sbi: 'sbi.co.in', hdfc: 'hdfcbank.com', icici: 'icicibank.com', axis: 'axisbank.com',
  paytm: 'paytm.com', phonepe: 'phonepe.com', amazon: 'amazon.in', indiapost: 'indiapost.gov.in',
  fedex: 'fedex.com', dhl: 'dhl.com', npci: 'npci.org.in', uidai: 'uidai.gov.in', incometax: 'incometax.gov.in',
}
const SHORTENERS = ['bit.ly', 'tinyurl.com', 'cutt.ly', 'is.gd', 't.ly', 'rb.gy', 'shorturl.at']
const BAD_TLDS = ['xyz', 'top', 'club', 'online', 'site', 'info', 'live', 'icu', 'buzz', 'cc', 'tk']

// [pattern, weight, indicator label, kill-chain stage]
const SECRET = '(otp|one time password|pin|cvv|password|verification code|' +
  '(bank|banking|card|debit card|credit card|account|payment|personal|login|kyc|upi)\\s+(details|information|info|credentials|number))'
const RULES = [
  // Asking for a secret is the strongest single signal; merely mentioning one is weak
  // (real alerts say "incorrect PIN", "do not share this OTP").
  [new RegExp(`\\b(share|send|tell|give|provide|enter|confirm|verify|submit|update)\\b[^.!?]{0,25}\\b${SECRET}\\b`), 0.45, 'Asks for OTP / PIN / credentials', 'ask'],
  [new RegExp(`\\b${SECRET}\\b`), 0.12, 'Mentions OTP / PIN / credentials', null],
  [/\bkyc\b/, 0.24, 'KYC pretext', 'hook'],
  [/\b(blocked|suspended|expired?|deactivated|frozen|terminated|locked|closed|on hold|losing access|lose access|suspicious activity)\b/, 0.2, 'Account threat', 'hook'],
  [/\b(urgent\w*|immediately|within \d+ ?(hours?|hrs?|mins?|minutes)|today only|last chance|now|before midnight|midnight|tonight|expires?|hurry|limited (time|seats|offer))\b/, 0.14, 'Urgency language', 'urgency'],
  [/\b(verify|update|click|call|pay|share)\b/, 0.12, 'Action demand', 'ask'],
  [/\bpress \d\b/, 0.22, 'Automated call menu (press a key)', 'ask'],
  [/\b(won|winner|prize|lottery|lucky|jackpot|cashback|reward|congratulations|congrats|selected)\b/, 0.3, 'Prize bait', 'hook'],
  [/\b(claim|redeem|reserved for you|collect your)\b/, 0.22, 'Claim demand', 'ask'],
  [/(₹|\brs\.?|\binr)\s?\d{1,3}(,\d{2,3})+/, 0.1, 'Large sum of money', null],
  [/\b(customs|parcel|courier|shipment|delivery failed|incomplete address|redelivery)\b/, 0.16, 'Courier pretext', 'hook'],
  // Digital-arrest scripts keep the victim isolated and on camera.
  [/\b(do not (tell|inform|disconnect)|don't (tell|disconnect)|stay on (the )?(video )?call|video call|under digital arrest|keep this confidential)\b/, 0.35, 'Isolation tactic (keep quiet, stay on call)', 'urgency'],
  [/\b(arrest|cbi|police|narcotics|drugs?|court|warrant|illegal|money laundering|trai|digital arrest)\b/, 0.3, 'Legal intimidation', 'urgency'],
  [/\b(part[- ]time|work from home|daily income|tasks?|telegram|per (day|review|task|like)|task deposit|prepaid)\b/, 0.2, 'Job/task lure', 'hook'],
  [/\b(guaranteed returns?|\d+% returns?|stock tips|trading tips|double your money|investment plan)\b/, 0.4, 'Investment promise', 'hook'],
  [/\b(my new number|new number|lost my phone|dropped my phone|changed my number)\b/, 0.3, 'Impersonates someone you know', 'hook'],
  [/\bsend (me )?(rs|₹|money|\d)/, 0.2, 'Asks you to send money', 'ask'],
  // Banks publish toll-free numbers (1800...); scams give a personal mobile.
  [/\b(call|whatsapp|contact|message|reach)\b[^.]{0,30}(\+91[\s-]?)?\b[6-9][\dx]{9}\b/, 0.25, 'Asks you to contact a personal mobile number', 'ask'],
  [/\b(contact|message|chat|join|dm)\b[^.]{0,20}\b(on|via) (telegram|whatsapp)\b|\bt\.me\//, 0.2, 'Moves the conversation to Telegram / WhatsApp', 'ask'],
  [/\b(deposit|prepaid|registration fee|processing fee|security fee)\b/, 0.3, 'Asks for an upfront fee or deposit', 'ask'],
  [/\b(upi|scan)\b/, 0.12, 'UPI payment', 'ask'],
  [/\b(accept the (collect )?request|collect request|by mistake|sent by mistake)\b/, 0.3, 'UPI reversal trick', 'hook'],
  [/\b(disconnected|disconnection|power cut|will be cut)\b/, 0.3, 'Utility disconnection threat', 'hook'],
  // Failed-payment / refund bait: a problem that only "your details" can fix.
  [/\b(could not be processed|couldn't be processed|payment (has )?failed|transaction (has )?failed|unable to process|pending refund|receive (your|the) refund|refund (is )?(pending|approved|initiated))\b/, 0.3, 'Refund / failed-payment bait', 'hook'],
  [/\b(tonight|officer)\b/, 0.12, 'Pressure / fake official', 'urgency'],
  [/\b(earn|rs \d+ daily|per day)\b/, 0.18, 'Easy-money promise', 'hook'],
  [/\b(aadhaar|pan)\b/, 0.15, 'ID document mention', 'ask'],
]
// Function words inside matched phrases are not shaded in the heatmap.
const STOP = new Set(['a', 'an', 'the', 'to', 'of', 'for', 'on', 'in', 'at', 'by', 'is', 'be', 'has', 'have', 'been',
  'your', 'you', 'my', 'me', 'our', 'we', 'it', 'this', 'that', 'not', 'will', 'can', 'could', 'and', 'or', 'with', 'via', 'us'])

const SAFE = [
  [/\b(do not share|never share|don't share)\b/, -0.45],
  // A delivered OTP contains the code itself; a scam asks you to hand one over.
  [/\b(otp|code)\b[^.]{0,25}\b\d{4,8}\b|\b\d{4,8} is (your|the) (otp|code)\b/, -0.4],
  [/\b(debited|credited)\b.*\b(a\/c|ac|account)\b/, -0.35],
  [/\bnot you\?/, -0.1],
]

const CATEGORY_RULES = [
  ['digital_arrest', /\b(arrest|cbi|narcotics|drugs?|warrant|money laundering|illegal items|police|trai)\b/],
  ['kyc', /\bkyc\b/],
  ['courier', /\b(customs|parcel|courier|shipment|delivery failed|dhl|fedex|india ?post)\b/],
  ['otp_account', /\b(otp|blocked|suspended|deactivated|locked|frozen|on hold|netbanking|debit card|credit card|verification code)\b/],
  ['prize_lottery', /\b(won|prize|lottery|winner|lucky|jackpot|reward|selected for)\b/],
  ['job_task', /\b(part[- ]time|tasks?|daily income|work from home|per day|guaranteed returns?|stock tips)\b/],
  ['upi_payment', /\b(upi|collect request|accept the request|paytm|phonepe|google pay|gpay|qr code)\b/],
  ['phishing', /\b(electricity|disconnected|refund|new number|update|click|link)\b/],
]
// A flagged message that fits no category is phishing unless it reads as marketing.
const PROMO = /\b(sale|% off|discount|offer|shop|recharge|t&c|membership)\b/

export function normalize(text) {
  const found = []
  let out = text.replace(/\b(?:[a-z] ){3,}[a-z]\b/gi, (m) => {
    const j = m.replace(/ /g, ''); found.push({ from: m, to: j.toLowerCase(), kind: 'spacing' }); return j
  })
  out = out.replace(/\b(?:[a-z]\.){3,}[a-z]?\b/gi, (m) => {
    const j = m.replace(/\./g, ''); found.push({ from: m, to: j.toLowerCase(), kind: 'dots' }); return j
  })
  out = out.split(/(\s+)/).map((tok) => {
    if (/^https?:|\.[a-z]{2,}(\/|$)/i.test(tok)) return tok
    const core = tok.replace(/^[^\w$@]+|[^\w$@]+$/g, '')
    if (!/[a-zа-я]/i.test(core)) return tok
    let fixed = core, kind = null
    for (const [h, a] of Object.entries(HOMOGLYPH)) if (fixed.includes(h)) { fixed = fixed.split(h).join(a); kind = 'homoglyph' }
    if (/[013457@$]/.test(fixed) && /[a-z]{2}/i.test(fixed)) {
      fixed = fixed.replace(/[013457@$]/g, (c) => LEET[c]); kind = kind || 'leet'
    }
    if (kind) { found.push({ from: core, to: fixed.toLowerCase(), kind }); return tok.replace(core, fixed) }
    return tok
  }).join('')
  return { text: out.toLowerCase(), found }
}

function levenshtein(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)])
  for (let j = 1; j <= b.length; j++) d[0][j] = j
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
  return d[a.length][b.length]
}

export function findUrl(text) {
  return text.match(/\b((?:https?:\/\/)?(?:[a-z0-9-]+\.)+[a-z]{2,})(\/\S*)?/i)
}

function analyzeUrl(text) {
  const m = findUrl(text)
  if (!m) return null
  const domain = m[1].replace(/^https?:\/\//i, '').toLowerCase()
  const tld = domain.split('.').pop()
  let lookalike_of = null
  if (!Object.values(BRANDS).includes(domain)) {
    const bare = domain.replace(/[^a-z]/g, '')
    for (const [k, v] of Object.entries(BRANDS)) if (bare.includes(k)) { lookalike_of = v; break }
  }
  return {
    domain,
    lookalike_of,
    distance: lookalike_of ? levenshtein(domain, lookalike_of) : null,
    shortener: SHORTENERS.includes(domain),
    suspicious_tld: BAD_TLDS.includes(tld),
    ip_host: /^\d+\.\d+\.\d+\.\d+$/.test(domain),
    https: /^https:/i.test(m[0]) ? true : null,
  }
}

export function mockAnalyze(message, sender = '') {
  const { text, found } = normalize(message)
  const url = analyzeUrl(message)
  const indicators = []
  const killChain = {}
  const tokenW = {}
  let score = -0.6

  for (const [re, w, label, stage] of RULES) {
    const m = text.match(re)
    if (!m) continue
    score += w
    indicators.push({ label: `${label} ("${m[0]}")`, weight: w })
    for (const mm of text.matchAll(new RegExp(re.source, 'g')))
      // Phrase matches ("reserved for you") only weight their content words,
      // so "for" and "you" elsewhere in the message stay unshaded.
      for (const word of mm[0].split(' ').filter((x, _, a) => a.length === 1 || !STOP.has(x)))
        tokenW[word] = Math.max(tokenW[word] || 0, w)
    if (stage && !killChain[stage]) killChain[stage] = m[0]
  }
  // The scam pattern is the combination: a hook (threat or bait), pressure,
  // and a demand. Single words are weak evidence; the full chain is strong.
  const stages = ['hook', 'urgency', 'ask'].filter((s) => killChain[s]).length
  if (stages >= 2) {
    const w = stages === 3 ? 0.4 : 0.15
    score += w
    indicators.push({ label: `Scam pattern: ${stages} of 3 stages (hook, urgency, demand)`, weight: w })
  }
  for (const [re, w] of SAFE) if (re.test(text)) { score += w; indicators.push({ label: 'Standard bank-alert phrasing', weight: w }) }

  const brand = Object.keys(BRANDS).find((b) => new RegExp(`\\b${b}\\b`).test(text))
  if (brand) { killChain.credibility = brand.toUpperCase(); tokenW[brand] = 0.1 }
  // Claimed authority: police, CBI, RBI, TRAI, income tax, customs, courts.
  const auth = text.match(/\b(cbi|police|cyber cell|rbi|trai|income tax|customs|court|narcotics bureau|government)\b/)
  if (auth && !killChain.credibility) killChain.credibility = auth[0].toUpperCase()
  if (url) {
    let w = 0.08
    if (url.lookalike_of) w += 0.2
    if (url.suspicious_tld) w += 0.12
    if (url.shortener) w += 0.1
    score += w
    indicators.push({ label: `Suspicious URL (${url.domain})`, weight: +w.toFixed(2) })
  }
  if (found.length) {
    const w = +(0.1 * found.length).toFixed(2)
    score += w
    indicators.push({ label: `Obfuscation (${found.length} token${found.length > 1 ? 's' : ''})`, weight: w })
  }
  const s = sender.replace(/\s/g, '')
  if (/^[A-Z]{2}-[A-Z0-9]{5,6}$/i.test(s)) { score -= 0.1; indicators.push({ label: `Registered sender header (${sender})`, weight: -0.1 }) }
  else if (/^\+?\d{10,}/.test(s.replace(/X/gi, '0'))) { score += 0.12; indicators.push({ label: 'Sender is a personal number', weight: 0.12 }) }

  const p = 1 / (1 + Math.exp(-4 * score))
  const risk_score = Math.round(p * 100)
  // The opt-in mock keeps its own tuned 40 cut; the real model uses 50 (ml/explain.py).
  const risk_level = risk_score >= 70 ? 'HIGH' : risk_score >= 40 ? 'MEDIUM' : 'LOW'
  const label = risk_score >= 70 ? 'smishing' : risk_score >= 40 ? 'spam' : 'ham'
  const category = risk_level === 'LOW' ? 'legit'
    : (CATEGORY_RULES.find(([, re]) => re.test(text)) || [PROMO.test(text) && risk_level !== 'HIGH' ? 'promotional' : 'phishing'])[0]

  const urlParts = url ? url.domain.split(/[.-]/) : []
  const token_contributions = text.split(/(\s+)/).map((t) => {
    const k = t.replace(/^[^\w]+|[^\w]+$/g, '')
    const w = tokenW[k] ?? (urlParts.includes(k) || (url && t.includes(url.domain)) ? 0.19 : 0)
    return { token: t, weight: /^\s+$/.test(t) ? 0 : w }
  })

  return {
    label,
    probability: +Math.max(p, 1 - p).toFixed(2),
    uncertain: p > 0.4 && p < 0.6,
    risk_score,
    risk_level,
    category,
    normalized_text: text,
    obfuscation_detected: found,
    token_contributions,
    url_analysis: url,
    kill_chain: risk_level === 'LOW' ? {} : killChain,
    indicators: indicators.sort((a, b) => b.weight - a.weight),
    advice: adviceFor(category, brand, risk_level, !!url),
  }
}

function adviceFor(category, brand, level, hasUrl) {
  if (level === 'LOW') return ['No strong scam signals found.', 'If unsure, check through the official app instead of replying.']
  const a = [hasUrl ? 'Do not open the link or reply to the sender.' : 'Do not reply, call back, or send money or codes.']
  if (['otp_account', 'kyc'].includes(category)) a.push(`${brand ? brand.toUpperCase() : 'Banks'} never ask for OTP or KYC updates over SMS.`)
  if (category === 'digital_arrest') a.push('Police and CBI never arrest or investigate anyone over a video call.')
  if (category === 'courier') a.push('Couriers do not collect customs fees through SMS links.')
  if (category === 'job_task') a.push('Real jobs never ask you to pay to earn.')
  if (category === 'prize_lottery') a.push('You cannot win a lottery you never entered.')
  a.push('Report at cybercrime.gov.in or call 1930.')
  return a
}
