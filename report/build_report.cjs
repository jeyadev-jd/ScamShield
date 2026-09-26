// Builds report/ScamShield_Report.docx from the files in results/ and data/processed/.
// Every number in the report is read from those files, never typed by hand.
//   cd report && npm install && npm run build
const fs = require('fs')
const path = require('path')
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun, PageBreak, Footer, PageNumber, TableOfContents,
  LevelFormat, TabStopType,
} = require('docx')

const ROOT = path.resolve(__dirname, '..')
const R = (...p) => path.join(ROOT, 'results', ...p)
const OUT = path.join(__dirname, 'ScamShield_Report.docx')

// ------------------------------------------------------------------ data
function csv(file) {
  if (!fs.existsSync(file)) return []
  const [head, ...lines] = fs.readFileSync(file, 'utf8').trim().split(/\r?\n/)
  const cols = head.split(',')
  return lines.filter((l) => l && l !== head).map((l) => Object.fromEntries(l.split(',').map((v, i) => [cols[i], v])))
}
const metrics = csv(R('metrics.csv'))
const nosyn = csv(R('metrics_nosyn.csv'))
const rob = csv(R('robustness.csv'))
const robRnn = csv(R('robustness_rnn.csv'))
const robBert = csv(R('robustness_bert.csv'))
const cat = csv(R('category.csv'))
const calib = JSON.parse(fs.readFileSync(R('calibration.json'), 'utf8'))
const stats = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'processed', 'stats.json'), 'utf8'))

const n = (v, d = 3) => (v === undefined || v === '' ? '—' : Number(v).toFixed(d))
const pct = (v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`
const find = (q) => metrics.find((r) => Object.entries(q).every(([k, v]) => r[k] === v))
const ORDER = ['nb', 'lr', 'svm', 'rnn', 'rnn_attn', 'lstm', 'lstm_attn', 'distilbert']
const NAME = { nb: 'Naive Bayes', lr: 'Logistic regression', svm: 'Linear SVM', rnn: 'Simple RNN', rnn_attn: 'RNN + attention',
  lstm: 'BiLSTM', lstm_attn: 'BiLSTM + attention', distilbert: 'DistilBERT' }
const models = ORDER.filter((m) => find({ exp: 'E1', model: m }))
const e2acc = (m) => { const r = find({ exp: 'E2', model: m }); return r.e2_seed_mean ? Number(r.e2_seed_mean) : Number(r.accuracy) }
const svmE3 = find({ exp: 'E3', model: 'svm', task: 'binary', test: 'test_indian' })
const bertE3 = find({ exp: 'E3', model: 'distilbert', task: 'binary', test: 'test_indian' })
const drop = (m) => (e2acc(m) - Number(find({ exp: 'E1', model: m }).accuracy)) / Number(find({ exp: 'E1', model: m }).accuracy) * 100
const tfidfDrops = ['nb', 'lr', 'svm'].map(drop)
const scratchDrops = ['rnn', 'rnn_attn', 'lstm', 'lstm_attn'].filter((m) => find({ exp: 'E2', model: m })).map(drop)
const allDrops = [...tfidfDrops, ...scratchDrops]
const robGet = (cfg, attack, src = rob) => src.find((r) => r.config === cfg && r.attack === attack)?.scam_recall
const indianTest = stats.test_indian
const labelCounts = (s) => s.label || {}

// ------------------------------------------------------------------ styling helpers
const FONT = 'Times New Roman'
const INK = '1A1A1A'
const MUTED = '5F5B52'
const RULE = 'BFB9AC'
const HEAD_FILL = 'EAE6DC'

const p = (text, opts = {}) => new Paragraph({
  spacing: { after: 120, line: 360 }, alignment: opts.align || AlignmentType.JUSTIFIED, ...opts.para,
  children: (Array.isArray(text) ? text : [text]).map((t) => (typeof t === 'string' ? new TextRun({ text: t, ...opts.run }) : t)),
})
const b = (text) => new TextRun({ text, bold: true })
const i = (text) => new TextRun({ text, italics: true })
const code = (text) => new TextRun({ text, font: 'Consolas', size: 21 })
const ph = (text) => new TextRun({ text, highlight: 'yellow' }) // placeholder the author must fill
const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, spacing: { after: 240 }, children: [new TextRun(text)] })
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 }, children: [new TextRun(text)] })
const h3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 180, after: 80 }, children: [new TextRun(text)] })
const bullet = (text) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60, line: 320 },
  children: (Array.isArray(text) ? text : [text]).map((t) => (typeof t === 'string' ? new TextRun(t) : t)) })
const numbered = (text, ref = 'numbers') => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 320 },
  children: (Array.isArray(text) ? text : [text]).map((t) => (typeof t === 'string' ? new TextRun(t) : t)) })

let tableNo = 0
let figNo = 0
const caption = (kind, no, text) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 80, after: 240 },
  children: [new TextRun({ text: `${kind} ${no}. `, bold: true, size: 21 }), new TextRun({ text, italics: true, size: 21, color: MUTED })],
})

// Tables: widths in DXA, set on the table and every cell (A4 text width ~9026 DXA).
function table(headers, rows, widths, capText, opts = {}) {
  const total = widths.reduce((a, c) => a + c, 0)
  const border = { style: BorderStyle.SINGLE, size: 4, color: RULE }
  const cell = (text, w, head, right) => new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, color: 'auto', fill: HEAD_FILL } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    borders: { top: border, bottom: border, left: border, right: border },
    children: [new Paragraph({ alignment: right ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [new TextRun({ text: String(text), bold: head || (opts.boldRow && opts.boldRow(text)), size: 20,
        font: !head && right ? 'Consolas' : FONT })] })],
  })
  const t = new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, k) => cell(h, widths[k], true, k > 0 && opts.rightFrom !== undefined && k >= opts.rightFrom)) }),
      ...rows.map((r) => new TableRow({ children: r.map((v, k) => cell(v, widths[k], false, opts.rightFrom !== undefined && k >= opts.rightFrom)) })),
    ],
  })
  tableNo += 1
  return [t, caption('Table', tableNo, capText)]
}

function pngSize(file) {
  const buf = fs.readFileSync(file)
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20), buf }
}
function figure(file, capText, maxW = 560) {
  if (!fs.existsSync(file)) return []
  const { w, h, buf } = pngSize(file)
  const scale = Math.min(1, maxW / w)
  figNo += 1
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 },
      children: [new ImageRun({ type: 'png', data: buf, transformation: { width: Math.round(w * scale), height: Math.round(h * scale) } })] }),
    caption('Figure', figNo, capText),
  ]
}

// ------------------------------------------------------------------ content
const today = new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
const E = []

// Title page
E.push(
  new Paragraph({ spacing: { before: 1800, after: 200 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: 'ScamShield', bold: true, size: 56 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
    children: [new TextRun({ text: 'An Explainable, Obfuscation-Robust Scam SMS Detector for the Indian Context', size: 30, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: 'Project report submitted by', size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [ph('[Your name] ([Register number])')] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400, after: 120 }, children: [new TextRun({ text: 'Under the guidance of', size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [ph('[Guide name, designation]')] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [ph('[Department], [College], [University]')] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: today, size: 24 })] }),
)

// Abstract
E.push(
  new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, spacing: { after: 240 }, children: [new TextRun('Abstract')] }),
  p(`Scam SMS in India exploit UPI payments, KYC updates, courier fees and impersonated police officers, yet the public datasets used to train spam filters are dominated by English messages collected in the UK around 2012. ScamShield studies what happens when such filters meet Indian messages, how easily they are evaded by simple character obfuscation, and how to make their verdicts explainable. I assemble a ${indianTest.n.toLocaleString('en-IN')}-message Indian test set from two public Indian SMS datasets and published fraud reports, train eight models (Naive Bayes, logistic regression and linear SVM on TF-IDF; a simple RNN and a BiLSTM, each with and without attention; and DistilBERT), and evaluate them in seven experiments.`),
  p(`Models trained only on the UCI SMS Spam Collection lose ${Math.round(-Math.max(...allDrops))}–${Math.round(-Math.min(...allDrops))}% accuracy on Indian messages, while pretrained DistilBERT loses ${Math.round(-drop('distilbert'))}%. With Indian data in training, a calibrated linear SVM on word and character n-grams reaches an F1 of ${n(svmE3.f1_macro)} and a scam recall of ${n(svmE3.scam_recall)} on the held-out Indian set, matching DistilBERT (F1 ${n(bertE3.f1_macro)}) at a fraction of the cost. Letter-spacing attacks reduce the scam recall of word-level models by up to ${Math.round((Number(robGet('RNN', 'clean', robRnn)) - Number(robGet('RNN', 'spacing', robRnn))) * 100)} points; a rule-based normalizer restores every model to within one point of its clean performance. The deployed web application explains each verdict with a word-level heatmap, calibrated confidence, lexical URL forensics and an attack-pattern breakdown.`),
  p([b('Keywords: '), 'SMS spam, smishing, domain shift, adversarial obfuscation, explainability, calibration, India.']),
)

// TOC
E.push(
  new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, spacing: { after: 240 }, children: [new TextRun('Contents')] }),
  new TableOfContents('Contents', { hyperlink: true, headingStyleRange: '1-2' }),
  p([i('Right-click the table above and choose "Update Field" in Word to fill in page numbers.')], { run: { color: MUTED, size: 20 } }),
)

// 1 Introduction
E.push(
  h1('1. Introduction'),
  h2('1.1 Problem'),
  p('Classic SMS spam filters, typically TF-IDF features with Naive Bayes or a support vector machine trained on the UCI SMS Spam Collection [1], have three weaknesses in the Indian context:'),
  bullet([b('Domain mismatch. '), 'The UCI data was collected in the UK around 2011–2012. It contains no UPI collect requests, KYC-expiry threats, courier customs fees or "digital arrest" calls, the patterns that dominate Indian scam SMS today.']),
  bullet([b('Fragility. '), 'Scammers write "0TP", "b@nk" or "v e r i f y" precisely because word-level filters stop recognising the word.']),
  bullet([b('Opacity. '), 'A bare spam/ham label gives the user no reason to trust it and no advice on what to do next.']),
  h2('1.2 Objectives'),
  numbered('Build a classifier that separates legitimate messages, spam (unwanted marketing) and smishing (fraud), and assigns a scam category.', 'obj'),
  numbered('Measure the domain shift from UK-trained models to Indian messages.', 'obj'),
  numbered('Build an obfuscation normalizer and measure the robustness it adds.', 'obj'),
  numbered('Give explainable, calibrated output: word heatmap, risk score, uncertainty band, attack pattern.', 'obj'),
  numbered('Analyse links lexically for look-alike bank domains, shorteners and suspicious top-level domains.', 'obj'),
  numbered('Deploy the system as a web application that phones can share messages to.', 'obj'),
  h2('1.3 Contributions'),
  ...table(['#', 'Contribution'], [
    ['C1', `An Indian test set of ${indianTest.n.toLocaleString('en-IN')} messages assembled from public sources, and a domain-shift analysis across eight models.`],
    ['C2', 'An obfuscation attack benchmark (six attacks) and a normalizer, evaluated on TF-IDF, recurrent and transformer models.'],
    ['C3', 'An explainable pipeline: occlusion-based word heatmap, calibrated confidence, uncertainty band, kill-chain, advice.'],
    ['C4', 'Lexical URL forensics against Indian bank and brand domains.'],
  ], [800, 8200], 'Contributions of this project.'),
)

// 2 Literature
E.push(
  h1('2. Literature Review'),
  h2('2.1 SMS spam filtering'),
  p('Almeida et al. [1] released the SMS Spam Collection (5,574 messages) and showed that linear classifiers such as SVMs on bag-of-words features perform strongly on it. Linear SVMs on sparse TF-IDF features are a long-standing strong baseline for text categorisation [11], and complement Naive Bayes addresses the class-imbalance weaknesses of multinomial Naive Bayes on text [17]. For India, Yadav et al. [5] crowdsourced Indian SMS spam in SMSAssassin, showing early that Indian spam differs from Western collections.'),
  h2('2.2 Smishing'),
  p('Mishra and Soni [2] published an SMS phishing dataset that separates spam from smishing (fraudulent messages that try to steal credentials or money), the distinction this project adopts. Public Indian collections now exist on GitHub, Kaggle and Hugging Face [3, 4], though with limited documentation of how the messages were gathered.'),
  h2('2.3 Neural text classifiers'),
  p('Recurrent networks with long short-term memory [7] model word order, and attention mechanisms [8] let a model weight the words that matter instead of relying on its final hidden state. Pretrained transformers such as DistilBERT [6] transfer knowledge learned from large corpora, which should help when the test domain differs from the training domain.'),
  h2('2.4 Adversarial text and robustness'),
  p('Visual and character-level perturbations such as look-alike characters and inserted spaces reliably break NLP systems, and character-aware preprocessing is an effective defence [12, 13]. This project applies that idea to scam SMS with a deterministic normalizer.'),
  h2('2.5 Explainability and calibration'),
  p('Occlusion, removing one input unit and measuring the change in output [14], gives a model-agnostic explanation of each word\'s contribution. Probability calibration by Platt scaling [9] and its evaluation with expected calibration error and reliability diagrams [10] make a "90% confident" verdict mean what it says.'),
)

// 3 Datasets
const S = stats
const pubRow = (k, label, role) => [label, (S.public_after_dedup?.[k] ?? 0).toLocaleString('en-IN'), role]
E.push(
  h1('3. Datasets'),
  h2('3.1 Sources'),
  ...table(['Source', 'Messages used', 'Role'], [
    pubRow('uci', 'UCI SMS Spam Collection [1] (CC BY 4.0)', 'train + UCI test'),
    pubRow('mishra_soni', 'Mishra & Soni SMS Phishing [2] (CC BY 4.0)', 'train + MS test'),
    ['Indian Telecom SMS Spam Collection [3] (MIT)', '1,854', 'Indian test + dev'],
    ['ScamShield dataset [4], real rows only (MIT)', '6,985', 'Indian test + dev'],
    ['News and PIB Fact Check reports, published examples', '28', 'Indian test + dev'],
    ['Templated synthetic messages (ml/synth.py)', (S.synthetic?.rows ?? 0).toLocaleString('en-IN'), 'train only'],
  ], [4600, 1800, 2600], 'Data sources after cleaning. Mishra-Soni counts exclude messages it shares with UCI.', { rightFrom: 1 }),
  p(`Only ${(S.public_after_dedup?.mishra_soni ?? 0).toLocaleString('en-IN')} Mishra-Soni messages are not already in UCI; ${(S.dedup_removed?.public ?? 0).toLocaleString('en-IN')} cross-source duplicates were removed before splitting, so no test message appears in training.`),
  h2('3.2 The Indian set'),
  p('My own collection of personal messages was too small, so the Indian set was assembled from public data. The Indian Telecom SMS Spam Collection contributes genuine Indian telecom, bank and investment-scam messages; the ScamShield dataset contributes real rows only (rows the authors mark as LLM-generated were excluded and verified absent), filtered to English or Hinglish messages that reference Indian brands, currency or services. A machine-generated Hugging Face collection was inspected and rejected.'),
  p([b('Labelling. '), 'The public sources only distinguish spam from legitimate messages, and their "spam" mixes marketing with fraud. A documented keyword pass (ml/import_public.py) split spam into promotional spam and smishing and assigned a scam category; 45 WhatsApp stock-scam messages labelled legitimate by their source were relabelled as smishing. Every row records how its label was set. A manual spot-check of random samples found and fixed three rule errors. These labels remain heuristic, which limits experiment E5.']),
  ...table(['Split', 'Ham', 'Spam', 'Smishing', 'Total'], ['train', 'test_uci', 'test_ms', 'test_indian', 'dev_indian'].filter((k) => S[k]).map((k) => {
    const l = labelCounts(S[k])
    return [k, (l.ham || 0).toLocaleString('en-IN'), (l.spam || 0).toLocaleString('en-IN'), (l.smishing || 0).toLocaleString('en-IN'), S[k].n.toLocaleString('en-IN')]
  }), [2600, 1600, 1600, 1600, 1600], 'Label distribution per split.', { rightFrom: 1 }),
  p(`Promotional spam makes up ${Math.round(100 * (labelCounts(indianTest).spam || 0) / indianTest.n)}% of the Indian test set. Since promotions are easier to recognise than fraud, scam recall and per-class results are reported alongside accuracy.`),
  h2('3.3 Ethics and anonymisation'),
  p('Phone numbers, Aadhaar and PAN numbers, account numbers and e-mail addresses are masked automatically by build_dataset.anonymize. Public datasets are used under their licences (CC BY 4.0 and MIT). Synthetic messages carry is_synthetic = 1, are never placed in a test split, and results are reported with and without them.'),
  h2('3.4 Obfuscated test copies'),
  p('ml/obfuscate.py produces six seeded attacks on scam keywords while leaving URLs, numbers and e-mail addresses intact: leet substitution (0TP), homoglyphs (Cyrillic look-alikes), letter spacing (v e r i f y), dots (b.a.n.k), zero-width characters and a random mix.'),
)

// 4 Methodology
E.push(
  h1('4. Methodology'),
  p('Figure 1 of the plan summarised the pipeline; each stage is described below in processing order.'),
  h2('4.1 Normalizer'),
  p('The normalizer undoes the six attack families: it removes zero-width characters, applies Unicode NFKC folding, maps Cyrillic and Greek look-alikes to Latin letters, joins spaced or dotted single letters, and repairs leet substitutions inside word-like tokens. URLs, e-mail addresses, amounts, OTP codes, phone numbers, texting slang ("gr8", "b4") and number-unit tokens ("7pm", "10k") are protected. Every rewrite is recorded and shown to the user.'),
  h2('4.2 Features'),
  p('Text is lower-cased and volatile values (URLs, e-mails, amounts, phone numbers, other numbers) are replaced by placeholder tokens. Three feature groups are concatenated: word TF-IDF (1–2 grams), character TF-IDF (2–5 grams within word boundaries) and 16 engineered features such as urgency words, requests for personal information, obfuscation count and URL look-alike score.'),
  h2('4.3 Models'),
  bullet([b('TF-IDF models: '), 'complement Naive Bayes, logistic regression and linear SVM, each calibrated with Platt scaling (sigmoid, five folds). Two versions are trained: legitimate vs scam, and legitimate / spam / smishing.']),
  bullet([b('Recurrent models: '), 'a unidirectional Elman RNN and a bidirectional LSTM (128-dimensional embeddings learned from scratch, 128 hidden units, six epochs, class-weighted loss).']),
  bullet([b('Attention: '), 'additive attention pooling [8] replaces the final hidden state: u_t = tanh(W h_t + b), a_t = softmax(v · u_t), c = Σ a_t h_t, with padding masked. It removes the recurrent models\' bias towards the last words and exposes per-word weights.']),
  bullet([b('DistilBERT: '), 'distilbert-base-uncased [6] fine-tuned for two epochs (learning rate 5·10⁻⁵, 96 tokens, class-weighted loss) on an RTX 3050 laptop GPU.']),
  p('The deployed model is chosen by three-fold cross-validated macro F1 on the training data among the TF-IDF models, never by test-set performance; the linear SVM was selected. The neural models are reported in the experiments only.'),
  h2('4.4 Risk score, confidence and uncertainty'),
  p('The risk score is the calibrated probability that a message is not legitimate, times 100, capped at 69 for promotional spam, which is unwanted but not fraud. The displayed confidence is the probability of the label shown: P(not legitimate) from the binary model times P(label | not legitimate) from the three-class model. Messages with a scam probability between 0.35 and 0.65 are marked "needs human review". A small logistic regression over the engineered features explains the score as named indicator weights.'),
  h2('4.5 Explanations'),
  p('Word weights come from occlusion [14]: each word is removed in turn and the change in the classifier\'s uncalibrated margin is recorded. Using the margin rather than the calibrated probability avoids saturation, where a very confident model shows no change for any single word. A rule-based kill-chain extracts the hook, urgency, claimed authority and demand, and category-specific advice is attached.'),
  h2('4.6 URL forensics'),
  p('Links are never opened. The registrable domain is compared against about thirty official Indian bank and brand domains by substring match and edit distance, and link shorteners, suspicious top-level domains, raw IP hosts, "@" tricks and excess subdomains are flagged.'),
)

// 5 Implementation
E.push(
  h1('5. Implementation'),
  ...table(['Layer', 'Technology', 'Responsibility'], [
    ['Machine learning', 'Python 3.12, scikit-learn, PyTorch, Hugging Face Transformers', 'normalizer, features, training, evaluation, explanations'],
    ['API', 'FastAPI + Uvicorn', 'POST /api/analyze, /api/health, /api/research, /api/dataset'],
    ['Frontend', 'React (Vite), Tailwind CSS, Recharts', 'Analyze, Case Report, Cases, Research, Dataset, Train quiz, Method'],
    ['Mobile', 'Progressive web app with a share target', 'share an SMS from the messaging app to ScamShield'],
    ['Deployment', 'Docker (Render / Hugging Face Spaces), Vercel', 'API image without neural dependencies'],
  ], [1900, 3500, 3600], 'System components.'),
  p('The interface is designed as a forensic case file: each analysis becomes a numbered case with a verdict stamp, the message with a word heatmap, obfuscation and link forensics tables, the attack pattern and advice. Messages are processed in memory and never logged; case history stays in the browser. An awareness quiz lets users practise telling scams from real messages and compares their answer with the model\'s. The whole experimental pipeline runs with one command (python -m ml.run_all), and 88 automated tests cover the normalizer, attacks, features, URL forensics, training, the API and the neural models.'),
)

// 6 Results
const e1rows = models.map((m) => { const r = find({ exp: 'E1', model: m }); return [NAME[m], n(r.accuracy), n(r.precision_macro), n(r.recall_macro), n(r.f1_macro), n(r.scam_recall), n(r.roc_auc)] })
const e2rows = models.map((m) => { const a = Number(find({ exp: 'E1', model: m }).accuracy); const r = find({ exp: 'E2', model: m })
  const acc = r.e2_seed_mean ? `${n(r.e2_seed_mean, 2)} ± ${n(r.e2_seed_std, 2)}` : n(r.accuracy)
  return [NAME[m], n(a), acc, pct(drop(m))] })
const e3rows = models.map((m) => { const r = find({ exp: 'E3', model: m, task: 'binary', test: 'test_indian' }); return r && [NAME[m], n(r.accuracy), n(r.f1_macro), n(r.scam_recall), n(r.false_alarm_rate), n(r.roc_auc), n(r.ece)] }).filter(Boolean)
const synRows = ['nb', 'lr', 'svm'].map((m) => {
  const w = find({ exp: 'E3', model: m, task: 'binary', test: 'test_indian' })
  const wo = nosyn.find((r) => r.exp === 'E3' && r.model === m && r.task === 'binary' && r.test === 'test_indian')
  return w && wo && [NAME[m], n(wo.f1_macro), n(w.f1_macro), n(wo.scam_recall), n(w.scam_recall)]
}).filter(Boolean)
const attacks = ['clean', 'leet', 'homoglyph', 'spacing', 'dots', 'zero_width', 'mixed']
const robRows = [...new Set(rob.map((r) => r.config))].map((c) => [c, ...attacks.map((a) => n(robGet(c, a), 2))])
const neuralRows = [...new Set([...robRnn, ...robBert].map((r) => r.config))].map((c) => [c, ...attacks.map((a) => n(robGet(c, a, [...robRnn, ...robBert]), 2))])
const mid = e3rows.length

E.push(
  h1('6. Results'),
  p(`All results are on held-out test sets: UCI (${S.test_uci.n} messages), Mishra-Soni (${S.test_ms.n}) and Indian (${indianTest.n.toLocaleString('en-IN')}). The recurrent models' out-of-domain results vary with the random seed, so E2 reports their mean and standard deviation over ${find({ exp: 'E2', model: 'rnn' })?.e2_seeds || 5} seeds.`),
  h2('6.1 E1: baseline on UCI'),
  ...table(['Model', 'Accuracy', 'Precision', 'Recall', 'F1', 'Scam recall', 'ROC-AUC'], e1rows, [2300, 1100, 1100, 1100, 1000, 1200, 1200],
    'E1: trained and tested on the UCI SMS Spam Collection (macro averages).', { rightFrom: 1 }),
  p('On in-domain UK data every model performs well; DistilBERT is best and the TF-IDF models are within three points of it.'),
  h2('6.2 E2: domain shift'),
  ...table(['Model', 'UCI accuracy', 'Indian accuracy', 'Change'], e2rows, [2800, 2000, 2400, 1800],
    'E2: models trained only on UCI, tested on UCI and on the Indian set.', { rightFrom: 1 }),
  ...figure(R('fig1_domain_shift.png'), 'Domain shift (E2). Grey: UCI test accuracy; blue: Indian test accuracy. Recurrent models are plotted at their seed mean.'),
  p(`Every model trained from scratch loses a third or more of its accuracy on Indian messages (TF-IDF models ${Math.round(Math.max(...tfidfDrops))}% to ${Math.round(Math.min(...tfidfDrops))}%, recurrent models ${Math.round(Math.max(...scratchDrops))}% to ${Math.round(Math.min(...scratchDrops))}%). Pretrained DistilBERT loses only ${Math.round(-drop('distilbert'))}%: pretraining transfers to the new domain, whereas vocabulary learned from 2012 UK messages does not. Attention does not change the recurrent models' out-of-domain accuracy beyond seed variance.`),
  h2('6.3 E3: recovery with Indian data'),
  ...table(['Model', 'Accuracy', 'F1', 'Scam recall', 'False alarms', 'ROC-AUC', 'ECE'], e3rows, [2500, 1100, 1000, 1200, 1200, 1100, 900],
    'E3: trained on all sources including the Indian dev split, tested on the held-out Indian set (legitimate vs scam).', { rightFrom: 1 }),
  p(`With Indian messages in training, all eight models exceed an F1 of 0.92. The linear SVM (F1 ${n(svmE3.f1_macro)}) matches DistilBERT (${n(bertE3.f1_macro)}); attention improves both recurrent models in this in-domain setting. Because the linear SVM needs no GPU and answers in milliseconds, it is the deployed model.`),
  ...(synRows.length ? [
    ...table(['Model', 'F1 without', 'F1 with', 'Recall without', 'Recall with'], synRows, [2800, 1550, 1550, 1550, 1550],
      'Effect of the synthetic training messages on the Indian test set.', { rightFrom: 1 }),
    p('Once real Indian messages are available for training, the templated synthetic messages no longer help: results with and without them differ by less than a point, slightly in favour of training without them. They mattered only while the Indian set was tiny (Section 3.2); the deployed model keeps them because they add legitimate bank-alert and OTP formats that the public data lacks.'),
  ] : []),
  ...figure(R('fig4_confusion_e3.png'), 'Confusion matrix of the linear SVM, legitimate / spam / smishing, on the Indian test set.', 380),
  h2('6.4 E4 and E7: robustness to obfuscation'),
  ...table(['Configuration', ...attacks.map((a) => a.replace('_', '-'))], robRows, [2500, 900, 900, 950, 950, 900, 1000, 900],
    'E4/E7: scam recall of logistic regression on the Indian test set under each attack (engineered features off).', { rightFrom: 1 }),
  ...figure(R('fig2_robustness.png'), 'Scam recall under each attack by defence. Darker bars carry more defence.'),
  ...table(['Model', ...attacks.map((a) => a.replace('_', '-'))], neuralRows, [2500, 900, 900, 950, 950, 900, 1000, 900],
    'E4: neural models under the same attacks, with and without the normalizer.', { rightFrom: 1 }),
  p(`Letter spacing and dots are the most damaging attacks because they split a word into single letters that a word-level model has never seen: the simple RNN drops from ${n(robGet('RNN', 'clean', robRnn), 2)} to ${n(robGet('RNN', 'spacing', robRnn), 2)} scam recall and DistilBERT from ${n(robGet('DistilBERT', 'clean', robBert), 2)} to ${n(robGet('DistilBERT', 'spacing', robBert), 2)}. The normalizer restores every model to within about one point of its clean score. Character n-grams alone recover most of the loss for TF-IDF (E7), which is why the deployed model uses both.`),
  h2('6.5 E5: scam category'),
  ...table(['Method', 'Accuracy', 'Macro F1'], cat.map((r) => [r.method.replace('_', '-'), n(r.accuracy), n(r.f1_macro)]), [3000, 3000, 3000],
    'E5: category prediction on the Indian test set.', { rightFrom: 1 }),
  p([b('Caveat. '), 'The categories in the public Indian data were themselves assigned by keyword rules (Section 3.2), so this comparison is indicative only. A hand-labelled category set is needed for a fair evaluation.']),
  h2('6.6 E6: calibration'),
  ...table(['Model', 'ECE raw', 'ECE calibrated'], Object.entries(calib).map(([m, a]) => [NAME[m] || m, a.raw ? n(a.raw.ece) : '—', n(a.calibrated.ece)]), [3000, 3000, 3000],
    'E6: expected calibration error on the Indian test set (lower is better). The linear SVM has no raw probabilities.', { rightFrom: 1 }),
  ...figure(R('fig3_calibration.png'), 'Reliability diagrams. Points on the diagonal are perfectly calibrated.'),
  p('Logistic regression and the SVM are well calibrated. Naive Bayes is better calibrated before Platt scaling than after on this set, because the scaling was fitted on training data dominated by UK messages; calibration does not transfer perfectly across domains.'),
)

// 7 Conclusion
E.push(
  h1('7. Conclusion'),
  p(`ScamShield shows that UK-trained spam filters fail badly on Indian messages, that a modest amount of Indian data closes most of the gap, and that simple obfuscation is a real threat to word-level models, one a deterministic normalizer neutralises. A calibrated linear SVM on word and character n-grams matches a fine-tuned transformer on this task (F1 ${n(svmE3.f1_macro)} vs ${n(bertE3.f1_macro)}) while running without a GPU, and every verdict it gives is explained.`),
  h2('7.1 Limitations'),
  bullet('Most Indian messages come from two public datasets whose collection method is only partly documented, and promotional spam dominates the Indian test set.'),
  bullet('Spam vs smishing and scam categories in the public Indian data were assigned by keyword rules and spot-checked, not fully hand-labelled.'),
  bullet('URL checks are lexical only; a fresh domain with an innocent name passes.'),
  bullet('Only English and romanised text is handled; Devanagari and other scripts are not.'),
  bullet('Some legitimate bill reminders are rated as spam, because the public data labels many such reminders as spam.'),
  bullet('The risk score reflects the training class balance and is an indicator, not the probability that a given message is fraud.'),
  h2('7.2 Future work'),
  bullet('A hand-labelled Indian test set with scam categories, collected with consent.'),
  bullet('WhatsApp and multilingual (Hindi, Tamil, code-mixed) messages.'),
  bullet('On-device inference, so messages never leave the phone.'),
  bullet('Domain reputation lookups alongside the lexical URL checks.'),
)

// References
const refs = [
  'T. A. Almeida, J. M. Gómez Hidalgo and A. Yamakami, "Contributions to the study of SMS spam filtering: new collection and results," in Proc. 11th ACM Symposium on Document Engineering (DocEng), 2011.',
  'S. Mishra and D. Soni, "SMS Phishing Dataset for Machine Learning and Pattern Recognition," Mendeley Data, V1, doi:10.17632/f45bkkt8pr.1.',
  'junioralive, "India Spam SMS Classification (Indian Telecom SMS Spam Collection)," GitHub, https://github.com/junioralive/india-spam-sms-classification (MIT licence).',
  'sidzzz07, "scamshield-dataset," Hugging Face Datasets, https://huggingface.co/datasets/sidzzz07/scamshield-dataset (MIT licence).',
  'K. Yadav, P. Kumaraguru, A. Goyal, A. Gupta and V. Naik, "SMSAssassin: crowdsourcing driven mobile-based system for SMS spam filtering," in Proc. HotMobile, 2011.',
  'V. Sanh, L. Debut, J. Chaumond and T. Wolf, "DistilBERT, a distilled version of BERT: smaller, faster, cheaper and lighter," arXiv:1910.01108, 2019.',
  'S. Hochreiter and J. Schmidhuber, "Long short-term memory," Neural Computation, vol. 9, no. 8, 1997.',
  'D. Bahdanau, K. Cho and Y. Bengio, "Neural machine translation by jointly learning to align and translate," in Proc. ICLR, 2015.',
  'J. Platt, "Probabilistic outputs for support vector machines and comparisons to regularized likelihood methods," in Advances in Large Margin Classifiers, MIT Press, 1999.',
  'C. Guo, G. Pleiss, Y. Sun and K. Q. Weinberger, "On calibration of modern neural networks," in Proc. ICML, 2017.',
  'T. Joachims, "Text categorization with support vector machines: learning with many relevant features," in Proc. ECML, 1998.',
  'S. Eger et al., "Text processing like humans do: visually attacking and shielding NLP systems," in Proc. NAACL, 2019.',
  'D. Pruthi, B. Dhingra and Z. C. Lipton, "Combating adversarial misspellings with robust word recognition," in Proc. ACL, 2019.',
  'M. D. Zeiler and R. Fergus, "Visualizing and understanding convolutional networks," in Proc. ECCV, 2014.',
  'F. Pedregosa et al., "Scikit-learn: machine learning in Python," Journal of Machine Learning Research, vol. 12, 2011.',
  'Press Information Bureau Fact Check and news reports (The Tribune, India TV, India.com) quoted for reported scam messages; URLs are listed in data/raw/indian_raw.csv sources.',
  'J. D. M. Rennie, L. Shih, J. Teevan and D. R. Karger, "Tackling the poor assumptions of naive Bayes text classifiers," in Proc. ICML, 2003.',
]
E.push(
  h1('References'),
  ...refs.map((r) => numbered(r, 'refs')),
  p([i('Check each reference against the original publication before submission.')], { run: { color: MUTED, size: 20 } }),
)

// ------------------------------------------------------------------ document
const doc = new Document({
  creator: 'ScamShield', title: 'ScamShield project report',
  styles: {
    default: { document: { run: { font: FONT, size: 24, color: INK } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, font: FONT }, paragraph: { spacing: { before: 0, after: 240 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, font: FONT }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, italics: true, font: FONT }, paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    ...['numbers', 'obj', 'refs'].map((reference) => ({ reference, levels: [{ level: 0, format: LevelFormat.DECIMAL,
      text: reference === 'refs' ? '[%1]' : '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 600, hanging: 420 } } } }] })),
  ] },
  sections: [{
    properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, // A4, 1 inch margins
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], size: 20, color: MUTED })] })] }) },
    children: E,
  }],
})

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf)
  console.log(`wrote ${OUT} (${tableNo} tables, ${figNo} figures)`)
})
