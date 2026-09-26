"""Train NB / LR / SVM with calibration and run experiments E1-E3.

    python -m ml.train                  # all experiments, all models
    python -m ml.train --exp e1 e2      # just the UCI baseline and domain shift
    python -m ml.train --no-char        # word TF-IDF only (ablation for E7)

Experiments
    E1  train UCI                           -> test UCI         (baseline)
    E2  same models                         -> test Indian      (domain-shift drop)
    E3  train UCI + Mishra-Soni + Indian dev -> test Indian, test MS, test UCI (recovery)

The best E3 model (chosen by cross-validated macro F1 on its own training
data, never on a test set) is saved to backend/models/ for the API, in two
versions: binary (ham vs scam) and multi-class (ham / spam / smishing).

Outputs: results/metrics.csv, results/experiments.json, backend/models/*.joblib
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from ml.category import make_trained
from ml.features import FeatureExtractor
from ml.risk import RiskModel
from ml.metrics import evaluate
from ml.preprocess import preprocess, preprocess_raw

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
MODELS = ROOT / "backend" / "models"

MODEL_NAMES = ("nb", "lr", "svm")


def make_base(name: str):
    if name == "nb":
        return ComplementNB(alpha=0.3)
    if name == "lr":
        return LogisticRegression(C=10, max_iter=3000, class_weight="balanced")
    if name == "svm":
        return LinearSVC(C=0.5, class_weight="balanced")
    raise ValueError(name)


def _char_prep_raw(t: str) -> str:
    return t.lower()


def make_pipeline(name: str, char: bool = True, features: bool = True, normalizer: bool = True,
                  cv: int = 5) -> Pipeline:
    prep = preprocess if normalizer else preprocess_raw
    parts = [("word", TfidfVectorizer(preprocessor=prep, ngram_range=(1, 2), min_df=2,
                                      sublinear_tf=True, token_pattern=r"(?u)\b\w+\b"))]
    if char:
        # char_wb n-grams survive partial obfuscation: "v3rify" still shares
        # "rify", "ify " with "verify" even when the normalizer misses it.
        parts.append(("char", TfidfVectorizer(preprocessor=prep if normalizer else _char_prep_raw,
                                              analyzer="char_wb", ngram_range=(2, 5), min_df=2,
                                              sublinear_tf=True, max_features=150_000)))
    if features:
        parts.append(("feat", FeatureExtractor()))
    # Sigmoid (Platt) calibration: isotonic overfits on the small Indian slice.
    clf = CalibratedClassifierCV(make_base(name), method="sigmoid", cv=cv)
    return Pipeline([("vec", FeatureUnion(parts)), ("clf", clf)])


def load(name: str) -> pd.DataFrame | None:
    f = DATA / f"{name}.csv"
    return pd.read_csv(f, keep_default_na=False) if f.exists() else None


def fit(name, train, target, args, cv=5):
    t0 = time.time()
    pipe = make_pipeline(name, char=not args.no_char, features=not args.no_features,
                         normalizer=not args.no_normalizer, cv=cv)
    pipe.fit(train["text"].tolist(), train[target].tolist())
    return pipe, time.time() - t0


def run(args) -> list[dict]:
    train = load("train")
    if train is None:
        sys.exit("data/processed/train.csv not found. Run: python -m ml.build_dataset")
    tests = {n: load(n) for n in ("test_uci", "test_ms", "test_indian")}
    dev = load("dev_indian")
    rows: list[dict] = []
    tag = {"char": not args.no_char, "features": not args.no_features, "normalizer": not args.no_normalizer}

    def record(exp, model, task, test_name, df, pipe, target, secs):
        m = evaluate(pipe, df["text"].tolist(), df[target].tolist())
        rows.append({"exp": exp, "model": model, "task": task, "test": test_name, "train_secs": round(secs, 1), **tag, **m})
        print(f"  {exp} {model:<4} {task:<6} {test_name:<12} n={m['n']:<5} acc={m['accuracy']:.3f} "
              f"f1={m['f1_macro']:.3f} recall={m.get('scam_recall', float('nan')):.3f} ece={m['ece']:.3f}")

    # E1 / E2 ------------------------------------------------------------
    if {"e1", "e2"} & set(args.exp):
        uci = train[train["source"] == "uci"]
        if uci.empty:
            print("E1/E2 skipped: no UCI rows in train.csv")
        else:
            print(f"\nE1/E2: train on UCI ({len(uci)} rows), binary")
            for name in args.models:
                pipe, secs = fit(name, uci, "binary", args)
                if "e1" in args.exp and tests["test_uci"] is not None:
                    record("E1", name, "binary", "test_uci", tests["test_uci"], pipe, "binary", secs)
                if "e2" in args.exp and tests["test_indian"] is not None:
                    record("E2", name, "binary", "test_indian", tests["test_indian"], pipe, "binary", secs)
                elif "e2" in args.exp:
                    print("  E2 skipped: no test_indian.csv")

    # E3 -----------------------------------------------------------------
    if "e3" in args.exp:
        full = pd.concat([train, dev], ignore_index=True) if dev is not None and not dev.empty else train
        print(f"\nE3: train on all sources ({len(full)} rows, {len(full) - len(train)} Indian dev)")
        best: dict[str, tuple[float, str]] = {}
        for task, target in (("binary", "binary"), ("multi", "label")):
            if full[target].nunique() < 2:
                continue
            for name in args.models:
                pipe, secs = fit(name, full, target, args)
                for tn, df in tests.items():
                    if df is not None and not df.empty:
                        record("E3", name, task, tn, df, pipe, target, secs)
                if args.save:
                    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=0)
                    score = cross_val_score(make_pipeline(name, not args.no_char, not args.no_features,
                                                          not args.no_normalizer, cv=3),
                                            full["text"].tolist(), full[target].tolist(),
                                            cv=cv, scoring="f1_macro").mean()
                    print(f"    cv f1_macro {name}/{task}: {score:.4f}")
                    if score > best.get(task, (-1, ""))[0]:
                        best[task] = (score, name)
                        MODELS.mkdir(parents=True, exist_ok=True)
                        joblib.dump(pipe, MODELS / f"scam_{task}.joblib")
        if args.save and best:
            meta = {task: {"model": n, "cv_f1_macro": round(s, 4), **tag, "trained_rows": len(full)}
                    for task, (s, n) in best.items()}
            if "binary" in best:
                name = best["binary"][1]
                risk = RiskModel().fit(full["text"].tolist(), full["binary"].tolist(),
                                       make_pipeline(name, not args.no_char, not args.no_features, not args.no_normalizer, cv=3))
                joblib.dump(risk, MODELS / "risk.joblib")
                meta["risk"] = {"text_model": name}
            # Too few labeled Indian messages -> a trained category model is noise;
            # the API falls back to keyword rules (ml.category.rule_category).
            (MODELS / "category.joblib").unlink(missing_ok=True)
            if dev is not None and len(dev) >= 50 and dev["category"].nunique() >= 2:
                cat = make_trained().fit(dev["text"].tolist(), dev["category"].tolist())
                joblib.dump(cat, MODELS / "category.joblib")
                meta["category"] = {"trained_rows": len(dev), "classes": sorted(dev["category"].unique().tolist())}
            (MODELS / "meta.json").write_text(json.dumps(meta, indent=2))
            print(f"\nsaved best models to {MODELS}: {meta}")
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exp", nargs="+", default=["e1", "e2", "e3"], choices=["e1", "e2", "e3"])
    ap.add_argument("--models", nargs="+", default=list(MODEL_NAMES), choices=MODEL_NAMES)
    ap.add_argument("--no-char", action="store_true", help="drop char n-gram TF-IDF")
    ap.add_argument("--no-features", action="store_true", help="drop engineered features")
    ap.add_argument("--no-normalizer", action="store_true", help="skip the obfuscation normalizer")
    ap.add_argument("--no-save", dest="save", action="store_false", help="do not write backend/models")
    ap.add_argument("--tag", default="", help="suffix for result files, e.g. 'nochar'")
    args = ap.parse_args()

    rows = run(args)
    if not rows:
        return
    RESULTS.mkdir(exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    df = pd.DataFrame(rows)
    cols = ["exp", "model", "task", "test", "n", "accuracy", "precision_macro", "recall_macro", "f1_macro",
            "scam_recall", "false_alarm_rate", "roc_auc", "ece", "train_secs", "char", "features", "normalizer"]
    df[[c for c in cols if c in df]].to_csv(RESULTS / f"metrics{suffix}.csv", index=False)
    (RESULTS / f"experiments{suffix}.json").write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {RESULTS / f'metrics{suffix}.csv'}")

    e1 = df[(df.exp == "E1")].set_index("model")["accuracy"]
    e2 = df[(df.exp == "E2")].set_index("model")["accuracy"]
    if not e1.empty and not e2.empty:
        print("\ndomain shift (accuracy UCI -> Indian):")
        for m in e1.index.intersection(e2.index):
            print(f"  {m:<4} {e1[m]:.3f} -> {e2[m]:.3f}  ({(e2[m] - e1[m]) / e1[m]:+.1%})")


if __name__ == "__main__":
    main()
