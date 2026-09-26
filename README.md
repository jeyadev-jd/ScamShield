# ScamShield

An explainable, obfuscation-robust scam SMS detector for the Indian context.
Paste a message and get a case report: verdict, calibrated confidence, a word-level heatmap,
de-obfuscated text, lexical link forensics, the attack pattern, and what to do next.

![Case report for an obfuscated SBI KYC scam](docs/screenshots/02-case-report.png)

## Screenshots

| Analyze | Research results |
|---|---|
| ![Analyze page](docs/screenshots/01-analyze.png) | ![Research page](docs/screenshots/03-research.png) |
| **Dataset** | **Awareness quiz** |
| ![Dataset page](docs/screenshots/04-dataset.png) | ![Train quiz](docs/screenshots/06-train.png) |
| **Method** | **Phone** |
| ![Method page](docs/screenshots/05-method.png) | ![Mobile case report](docs/screenshots/07-mobile.png) |

## Project layout

```
frontend/   React (Vite + Tailwind): Analyze, Case Report, Cases, Research, Dataset, Train, Method; PWA share target
backend/    FastAPI: /api/analyze, /api/health, /api/research, /api/dataset (serves the linear SVM)
ml/         normalizer, obfuscation attacks, features, URL forensics, training (TF-IDF, RNN/LSTM, DistilBERT),
            evaluation, explanations, dataset import
data/raw/   datasets (see data/raw/README.md)
results/    metrics, figures and research.json (read by the Research page)
report/     project report draft with the real numbers
tests/      pytest suite (runs on small synthetic data, no downloads needed)
```

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # Windows; use .venv/bin/python on macOS/Linux
npm --prefix frontend install
```

Neural models (optional, experiments only): see `requirements-bert.txt`. On an NVIDIA GPU:

```bash
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/python -m pip install transformers
```

## Data

| Source | Messages used | Role |
|---|---|---|
| UCI SMS Spam Collection (CC BY 4.0) | 4,836 after de-duplication | train + UCI test |
| Mishra & Soni SMS Phishing, Mendeley (CC BY 4.0) | 1,053 not already in UCI | train + MS test |
| Indian Telecom SMS Spam Collection, GitHub/Kaggle (MIT) | 1,854 | Indian test + dev |
| ScamShield dataset, Hugging Face (MIT), real rows only | 6,985 | Indian test + dev |
| News / PIB Fact Check reports + published examples | 28 | Indian test + dev |
| Templated synthetic messages (`ml/synth.py`) | 1,117 | train only, never tested |

Spam vs smishing and scam categories in the public Indian data were assigned by keyword rules
(`ml/import_public.py`, recorded per row as `label_method`). Public sources de-duplicate across each
other before splitting, so no test message appears in training.

## Pipeline

One command runs everything in the right order (about 20 minutes with a GPU):

```bash
.venv/Scripts/python -m ml.run_all                 # add --skip-neural to skip RNN/LSTM/DistilBERT
```

Individual steps:

```bash
.venv/Scripts/python -m ml.synth                   # synthetic Indian messages, TRAIN ONLY
.venv/Scripts/python -m ml.import_public           # public Indian datasets -> data/raw/indian_public.csv
.venv/Scripts/python -m ml.build_dataset           # clean, anonymize, de-duplicate, split (--no-synthetic)
.venv/Scripts/python -m ml.train                   # NB / LR / SVM, E1-E3, saves the deployed model
.venv/Scripts/python -m ml.train_rnn               # RNN, BiLSTM, each +/- attention, E1-E4
.venv/Scripts/python -m ml.train_bert              # DistilBERT, E1-E4
.venv/Scripts/python -m ml.evaluate                # E4-E7, figures, research.json
```

| Exp | What | Where |
|---|---|---|
| E1 | UCI → UCI baseline | `train.py`, `train_rnn.py`, `train_bert.py` |
| E2 | UCI-trained models on the Indian set (domain shift) | same |
| E3 | All sources + Indian dev → held-out Indian set | same |
| E4 | Clean vs obfuscated, ± normalizer | `evaluate.py`, `train_rnn.py`, `train_bert.py` |
| E5 | Category: rules vs trained (vs zero-shot) | `evaluate.py` |
| E6 | Reliability diagrams, raw vs calibrated | `evaluate.py` |
| E7 | Word vs word+char TF-IDF on obfuscated text | `evaluate.py` (same grid as E4) |

## Results (Indian test set: 6,061 messages)

| Model | E1 UCI F1 | E2 UCI→Indian accuracy | E3 Indian F1 |
|---|---|---|---|
| Naive Bayes | 0.932 | 0.615 | 0.940 |
| Logistic regression | 0.936 | 0.652 | 0.966 |
| **Linear SVM (deployed)** | 0.936 | 0.656 | **0.970** |
| Simple RNN | 0.889 | 0.46 ± 0.09 (5 seeds) | 0.927 |
| RNN + attention | 0.906 | 0.52 ± 0.10 | 0.943 |
| BiLSTM | 0.930 | 0.62 ± 0.11 | 0.946 |
| BiLSTM + attention | 0.889 | 0.62 ± 0.15 | 0.951 |
| DistilBERT | **0.963** | **0.952** | 0.968 |

- **Domain shift (E2):** models trained only on UK SMS lose 33–52% accuracy on Indian messages; pretrained
  DistilBERT loses 4%.
- **Robustness (E4/E7):** under letter-spacing attacks, word-level models drop (TF-IDF 0.94, RNN 0.80,
  BiLSTM 0.91, DistilBERT 0.96 scam recall); the normalizer restores all of them to 0.98–0.99.
- **Calibration (E6):** LR and SVM are well calibrated (ECE ≈ 0.01).
- E5 is indicative only: the public Indian categories were assigned by the same kind of keyword rules.

Full tables and figures: the app's Research page, `results/`, and `report/`.

## Run locally

```bash
.venv/Scripts/python -m uvicorn backend.main:app --port 8000
npm --prefix frontend run dev                  # http://localhost:5173, proxies /api to :8000
```

Verdicts always come from the trained model. If the API is down or untrained, the page says so
instead of guessing. For UI work without a backend, `VITE_ALLOW_MOCK=1 npm --prefix frontend run dev`
enables the rule-based mock (`frontend/src/lib/mockAnalyze.js`), labelled on every report;
`npm --prefix frontend run eval:mock` scores it.

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

## Deploy

**API (Render or Hugging Face Spaces, Docker).** Train first, so `backend/models/`, `results/` and
`data/processed/` exist, then build from the repo root. `requirements-api.txt` pins scikit-learn to the
training version, because pickled models only load reliably with the version that trained them.
The neural models are not deployed, so the image needs no torch.

```bash
docker build -t scamshield-api .
docker run -p 7860:7860 -e ALLOWED_ORIGINS=https://your-app.vercel.app scamshield-api
```

- Render: new Web Service from the repo, runtime Docker; Render sets `$PORT`. Add `ALLOWED_ORIGINS`.
- Hugging Face Spaces: new Space, SDK Docker; port 7860 is the default.
- If the host builds from git, commit `backend/models/`, `results/` and the three `data/processed/` files
  the Dockerfile copies (`data/processed/` is gitignored by default).

**Frontend (Vercel).** Import the repo, set the root directory to `frontend`, and set the environment
variable `VITE_API_URL` to the API URL (for example `https://your-space.hf.space`). `vercel.json`
routes all app paths to `index.html`.

**Share to check (Android).** Open the deployed site in Chrome, install it (menu → Install app), then
share any SMS to *ScamShield* from the messaging app's share sheet. The message opens pre-filled.
Share targets need HTTPS and an installed PWA; iOS does not support them.

## Privacy

Messages are analyzed in memory and never logged or stored by the API. Case history lives only in
the browser's local storage. Links are never opened: URL analysis is purely lexical.
