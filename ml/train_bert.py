"""DistilBERT baseline for experiments E1-E4 (not deployed; the app serves the SVM).

    python -m ml.train_bert                       # E1, E2, E3, E4 with defaults
    python -m ml.train_bert --exp e4 --limit 3000 # quicker CPU run on a subsample
    python -m ml.train_bert --epochs 3 --device cuda

Needs:  pip install torch transformers   (CPU torch is fine; a GPU is ~10x faster)
First run downloads distilbert-base-uncased (~260 MB) from Hugging Face.

    E1  train UCI                 -> test UCI
    E2  same model                -> test Indian           (domain shift)
    E3  train all (+ Indian dev)  -> test UCI / MS / Indian
    E4  E3 model on clean vs obfuscated Indian test, with / without the normalizer.
        Subword tokenizers split "0TP" / "v e r i f y" into unfamiliar pieces, so
        transformers are expected to be more fragile than char n-grams here.

Results are merged into results/metrics.csv and results/experiments.json with
model "distilbert" (earlier DistilBERT rows are replaced), robustness goes to
results/robustness_bert.csv, and results/research.json is refreshed, so the
Research page shows DistilBERT next to NB / LR / SVM.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time

import numpy as np
import pandas as pd

from ml.metrics import evaluate
from ml.normalizer import normalize_text
from ml.obfuscate import obfuscate
from ml.train import RESULTS, load

ATTACKS = ["clean", "leet", "homoglyph", "spacing", "dots", "zero_width", "mixed"]


class BertClassifier:
    """sklearn-style wrapper: fit / predict_proba / classes_, so ml.metrics.evaluate works."""

    def __init__(self, model_name="distilbert-base-uncased", epochs=2, batch_size=32, max_len=96,
                 lr=5e-5, device="auto", normalizer=False, seed=42):
        self.model_name, self.epochs, self.batch_size, self.max_len = model_name, epochs, batch_size, max_len
        self.lr, self.normalizer, self.seed = lr, normalizer, seed
        import torch

        self.torch = torch
        self.device = ("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else device

    def _prep(self, texts):
        return [normalize_text(t) if self.normalizer else t for t in texts]

    def fit(self, texts, y):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        torch = self.torch
        torch.manual_seed(self.seed)
        random.seed(self.seed)
        np.random.seed(self.seed)
        self.classes_ = sorted(set(y))
        idx = {c: i for i, c in enumerate(self.classes_)}
        self.tok = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name, num_labels=len(self.classes_)).to(self.device)

        texts = self._prep(list(texts))
        labels = torch.tensor([idx[v] for v in y])
        # Class weights: scams are the minority and a missed scam costs more.
        counts = np.bincount(labels.numpy(), minlength=len(self.classes_))
        weights = torch.tensor(len(labels) / (len(counts) * np.maximum(counts, 1)), dtype=torch.float).to(self.device)
        loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
        opt = torch.optim.AdamW(self.model.parameters(), lr=self.lr)
        steps = self.epochs * ((len(texts) + self.batch_size - 1) // self.batch_size)
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: max(0.0, 1 - s / max(steps, 1)))

        self.model.train()
        order = list(range(len(texts)))
        step = 0
        for ep in range(self.epochs):
            random.shuffle(order)
            t0, total = time.time(), 0.0
            for b in range(0, len(order), self.batch_size):
                ids = order[b:b + self.batch_size]
                enc = self.tok([texts[i] for i in ids], truncation=True, max_length=self.max_len,
                               padding=True, return_tensors="pt").to(self.device)
                out = self.model(**enc)
                loss = loss_fn(out.logits, labels[ids].to(self.device))
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                opt.step(); sched.step(); opt.zero_grad()
                total += loss.item()
                step += 1
                if step % 50 == 0:
                    print(f"    epoch {ep + 1} step {step}/{steps} loss {total / ((b // self.batch_size) + 1):.4f}", flush=True)
            print(f"    epoch {ep + 1} done in {time.time() - t0:.0f}s, mean loss {total / max(1, len(order) // self.batch_size):.4f}")
        return self

    def predict_proba(self, texts):
        torch = self.torch
        texts = self._prep(list(texts))
        self.model.eval()
        out = []
        with torch.no_grad():
            for b in range(0, len(texts), 64):
                enc = self.tok(texts[b:b + 64], truncation=True, max_length=self.max_len,
                               padding=True, return_tensors="pt").to(self.device)
                out.append(torch.softmax(self.model(**enc).logits, dim=-1).cpu().numpy())
        return np.vstack(out)


def _subsample(df, limit, seed):
    if not limit or len(df) <= limit:
        return df
    # Stratified: keep the class balance of the full set.
    return df.groupby("binary").sample(frac=limit / len(df), random_state=seed)


def run(args) -> tuple[list[dict], list[dict]]:
    train, dev = load("train"), load("dev_indian")
    if train is None:
        sys.exit("data/processed/train.csv not found. Run: python -m ml.build_dataset")
    tests = {n: load(n) for n in ("test_uci", "test_ms", "test_indian")}
    rows, rob = [], []
    kw = dict(model_name=args.model, epochs=args.epochs, batch_size=args.batch, max_len=args.max_len, device=args.device)

    def record(exp, name, df, m, secs):
        r = evaluate(m, df["text"].tolist(), df["binary"].tolist())
        rows.append({"exp": exp, "model": "distilbert", "task": "binary", "test": name, "train_secs": round(secs, 1),
                     "char": False, "features": False, "normalizer": m.normalizer, **r})
        print(f"  {exp} distilbert {name:<12} n={r['n']:<5} acc={r['accuracy']:.3f} f1={r['f1_macro']:.3f} "
              f"recall={r.get('scam_recall', float('nan')):.3f} ece={r['ece']:.3f}")

    if {"e1", "e2"} & set(args.exp):
        uci = _subsample(train[train["source"] == "uci"], args.limit, args.seed)
        print(f"\nE1/E2: DistilBERT on UCI ({len(uci)} rows), device {BertClassifier(**kw).device}")
        t0 = time.time()
        m = BertClassifier(**kw).fit(uci["text"].tolist(), uci["binary"].tolist())
        secs = time.time() - t0
        if "e1" in args.exp and tests["test_uci"] is not None:
            record("E1", "test_uci", tests["test_uci"], m, secs)
        if "e2" in args.exp and tests["test_indian"] is not None:
            record("E2", "test_indian", tests["test_indian"], m, secs)

    if {"e3", "e4"} & set(args.exp):
        full = pd.concat([train, dev], ignore_index=True) if dev is not None else train
        full = _subsample(full, args.limit, args.seed)
        for norm in ([False, True] if "e4" in args.exp else [False]):
            label = "DistilBERT + normalizer" if norm else "DistilBERT"
            print(f"\nE3/E4: {label}, train {len(full)} rows")
            t0 = time.time()
            m = BertClassifier(normalizer=norm, **kw).fit(full["text"].tolist(), full["binary"].tolist())
            secs = time.time() - t0
            if "e3" in args.exp and not norm:
                for n, df in tests.items():
                    if df is not None and len(df):
                        record("E3", n, df, m, secs)
            if "e4" in args.exp:
                tn = "test_indian" if tests["test_indian"] is not None and len(tests["test_indian"]) >= 100 else "test_ms"
                test = tests[tn]
                for attack in ATTACKS:
                    texts = test["text"].tolist() if attack == "clean" else \
                        [obfuscate(t, attack, seed=args.seed + i) for i, t in enumerate(test["text"])]
                    r = evaluate(m, texts, test["binary"].tolist())
                    rob.append({"config": label, "normalizer": norm, "attack": attack, "test": tn,
                                "accuracy": r["accuracy"], "f1_macro": r["f1_macro"], "scam_recall": r.get("scam_recall")})
                print("  " + "  ".join(f"{x['attack']}={x['scam_recall']:.2f}" for x in rob[-len(ATTACKS):]))
    return rows, rob


def merge_results(rows, rob):
    RESULTS.mkdir(exist_ok=True)
    if rows:
        f = RESULTS / "metrics.csv"
        old = pd.read_csv(f) if f.exists() else pd.DataFrame()
        exps = {r["exp"] for r in rows}
        if not old.empty:
            old = old[~((old["model"] == "distilbert") & old["exp"].isin(exps))]
        new = pd.DataFrame(rows).drop(columns=["labels", "confusion"], errors="ignore")
        pd.concat([old, new], ignore_index=True).to_csv(f, index=False)
        fj = RESULTS / "experiments.json"
        ex = json.loads(fj.read_text()) if fj.exists() else []
        ex = [r for r in ex if not (r.get("model") == "distilbert" and r.get("exp") in exps)] + rows
        fj.write_text(json.dumps(ex, indent=2, default=float))
    if rob:
        pd.DataFrame(rob).to_csv(RESULTS / "robustness_bert.csv", index=False)
    # Refresh research.json so the Research page picks everything up.
    fr = RESULTS / "research.json"
    research = json.loads(fr.read_text()) if fr.exists() else {}
    if rob:
        research["robustness_bert"] = rob
    fr.write_text(json.dumps(research, indent=2, default=float))
    print(f"\nmerged DistilBERT results into {RESULTS}. Run `python -m ml.evaluate --only figs` to redraw figures.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exp", nargs="+", default=["e1", "e2", "e3", "e4"], choices=["e1", "e2", "e3", "e4"])
    ap.add_argument("--model", default="distilbert-base-uncased")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-len", type=int, default=96, help="SMS are short; 96 tokens covers ~99%%")
    ap.add_argument("--limit", type=int, default=0, help="stratified subsample of training rows (for CPU runs)")
    ap.add_argument("--device", default="auto", help="auto | cpu | cuda")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        sys.exit("DistilBERT needs: pip install torch transformers")
    rows, rob = run(a)
    merge_results(rows, rob)


if __name__ == "__main__":
    main()
