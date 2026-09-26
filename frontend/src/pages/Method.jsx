import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

const EXAMPLE = 'URGENT! Your $BI KYC exp1red. V e r i f y 0TP at sbi-kyc.xyz'

// Each example is real output of the corresponding module for EXAMPLE.
const STEPS = [
  {
    name: 'Normalize', file: 'ml/normalizer.py',
    what: 'Undo obfuscation: leet digits and symbols, Cyrillic and Greek look-alikes, spaced or dotted letters, invisible characters. URLs, amounts and phone numbers are left alone.',
    example: [['in', EXAMPLE], ['out', 'URGENT! Your SBI KYC expired. Verify OTP at sbi-kyc.xyz'], ['log', 'Verify (spacing) · $BI→SBI · exp1red→expired · 0TP→OTP (leet)']],
  },
  {
    name: 'Clean', file: 'ml/preprocess.py',
    what: 'Lower-case and replace volatile values with placeholder tokens, so the model learns "has a link" rather than one scam domain.',
    example: [['out', 'urgent your sbi kyc expired verify otp at urltoken']],
  },
  {
    name: 'Vectorize', file: 'ml/train.py',
    what: 'Word TF-IDF (1–2 grams) plus character TF-IDF (2–5 grams, within word boundaries) plus 16 engineered features. Character n-grams still match "v3rify" to "verify" through shared pieces such as "rify".',
    example: [['word', 'urgent · sbi kyc · verify otp · urltoken …'], ['char', '" ve" · "ver" · "rify" · "otp " …'], ['feat', 'has_url 1 · obfuscation_count 4 · url_lookalike_score 1 · personal_info_request 3 …']],
  },
  {
    name: 'Classify', file: 'ml/train.py · train_rnn.py · train_bert.py',
    what: 'Eight models are compared: Naive Bayes, logistic regression and linear SVM on TF-IDF; a simple RNN and a BiLSTM with embeddings learned from scratch, each with and without additive attention pooling; and fine-tuned DistilBERT. The deployed model is the one with the best cross-validated macro F1 on training data among the fast TF-IDF models (linear SVM); test sets are never used to choose. The neural models are reported in the experiments only.',
    example: [['out', 'ham / spam / smishing, and a binary ham vs scam model'], ['why', 'SVM matches DistilBERT on Indian messages at a fraction of the cost, and needs no GPU to serve']],
  },
  {
    name: 'Calibrate', file: 'ml/train.py',
    what: 'Platt (sigmoid) calibration with 5-fold cross-validation, so that "0.9" means right about 9 times in 10. Messages between 0.35 and 0.65 are marked "needs human review".',
    example: [['e.g.', 'P(scam) 0.97 → confidence 0.97, outside the review band (illustrative)']],
  },
  {
    name: 'Forensics', file: 'ml/url_forensics.py',
    what: 'Links are judged by their spelling only and are never opened: brand look-alikes, edit distance to official domains, shorteners, suspicious TLDs, raw IPs, "@" tricks.',
    example: [['url', 'sbi-kyc.xyz → imitates sbi.co.in · TLD .xyz flagged · shortener no']],
  },
  {
    name: 'Explain', file: 'ml/explain.py · ml/risk.py',
    what: 'Word weights come from occlusion: remove one word, measure the change in log-odds of scam. The risk score is a small logistic regression over the features and the classifier output, so it breaks down into named indicators.',
    example: [['heat', 'per-word weights depend on the trained model (see any Case Report)'], ['chain', 'hook "KYC expired" → urgency "URGENT" → authority "SBI" → ask "Verify OTP at sbi-kyc"']],
  },
]

const LIMITS = [
  'Most Indian messages come from two public datasets whose collection method is only partly documented, and about 62% of the Indian test set is promotional spam, which flatters accuracy.',
  'Spam vs smishing and all scam categories in the public Indian data were assigned by keyword rules (recorded per row as label_method), not by hand. E5 compares against those same rules, so it is indicative only.',
  'Training is augmented with templated synthetic messages (ml/synth.py). They never appear in a test set, and results with and without them are reported.',
  'Real bill reminders (telecom, insurance) are sometimes rated as spam, because the public Indian data labels many such reminders as spam.',
  'URL checks are lexical only. A fresh domain with an innocent name passes; nothing is fetched or looked up in a reputation service.',
  'The risk score is an indicator trained on dataset class balance, not the probability that a given message is fraud.',
  'English and romanized text only. Hindi, Tamil and other scripts, and code-mixed messages, are not handled.',
  'Sender checks are fixed rules; no public dataset includes sender IDs to learn from.',
  'Obfuscation seen in the wild evolves; the normalizer covers the six attack families in the benchmark and not novel ones.',
]

export default function Method() {
  const [open, setOpen] = useState(0)
  return (
    <article className="grid gap-12 lg:grid-cols-12">
      <div className="lg:col-span-8">
        <header className="mb-6 border-b-2 border-ink pb-3">
          <h1 className="font-serif text-3xl">Method</h1>
          <p className="mt-1 text-sm text-muted">One message, traced through every stage.</p>
          <p className="mt-3 border border-rule bg-sheet px-3 py-2 font-mono text-sm">{EXAMPLE}</p>
        </header>

        <ol className="relative">
          {STEPS.map((s, i) => (
            <li key={s.name} className="relative pb-2 pl-10">
              {i < STEPS.length - 1 && <span className="absolute bottom-0 left-[13px] top-7 w-px bg-rule" />}
              <span className={`absolute left-0 top-1 flex h-[27px] w-[27px] items-center justify-center border font-mono text-xs ${open === i ? 'border-ink bg-ink text-paper' : 'border-ink/60 bg-paper'}`}>
                {i + 1}
              </span>
              <button onClick={() => setOpen(open === i ? -1 : i)} aria-expanded={open === i}
                className="flex w-full items-baseline justify-between gap-4 py-1.5 text-left">
                <span className="font-serif text-lg">{s.name}</span>
                <span className="flex items-center gap-2 font-mono text-xs text-muted">
                  {s.file}
                  <ChevronDown size={14} strokeWidth={1.5} className={open === i ? 'rotate-180' : ''} />
                </span>
              </button>
              {open === i && (
                <div className="pb-4">
                  <p className="max-w-prose text-sm">{s.what}</p>
                  <dl className="mt-3 border-l-2 border-rule pl-3 font-mono text-[13px]">
                    {s.example.map(([k, v]) => (
                      <div key={k} className="grid grid-cols-[3.5rem_1fr] gap-2 py-0.5">
                        <dt className="text-muted">{k}</dt><dd className="break-words">{v}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>

      <aside className="lg:col-span-4">
        <h2 className="border-t border-rule pt-4 text-xs font-semibold uppercase tracking-[0.14em]">Limitations</h2>
        <ol className="mt-3 space-y-3 text-sm">
          {LIMITS.map((l, i) => (
            <li key={i} className="flex gap-3"><span className="font-mono text-muted">{i + 1}.</span><span>{l}</span></li>
          ))}
        </ol>
      </aside>
    </article>
  )
}
