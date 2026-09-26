"""Experiments E4-E7 plus the report figures.

    python -m ml.evaluate                 # everything available
    python -m ml.evaluate --only e4e7 e6  # subsets
    python -m ml.evaluate --zero-shot     # include the (slow, ~1.6 GB) NLI model in E5

    E4  robustness: clean vs obfuscated test set, with / without the normalizer
    E5  category: rules vs trained vs zero-shot, on the Indian test set
    E6  calibration: reliability diagrams, raw vs calibrated
    E7  char n-grams as a defense: word vs word+char TF-IDF on obfuscated text
        (E4 and E7 share one 2x2 grid: normalizer on/off x char n-grams on/off)

Also redraws the E1-E3 figures from results/metrics.csv (run ml.train first).
Writes results/*.csv, results/fig*.png and results/research.json (for the
frontend Research page).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from ml.category import CATEGORIES, ZeroShot, make_trained, rule_category
from ml.metrics import evaluate, expected_calibration_error, reliability_bins
from ml.obfuscate import obfuscate
from ml.train import DATA, RESULTS, load, make_pipeline

ATTACKS = ["clean", "leet", "homoglyph", "spacing", "dots", "zero_width", "mixed"]
GRID = [  # (label, char n-grams, normalizer) - ordered weakest to strongest defense
    ("Word only", False, False),
    ("Word + normalizer", False, True),
    ("Word + char", True, False),
    ("Word + char + normalizer", True, True),
]

# Palette: ink + one accent, following the UI plan. The E4/E7 grid is an
# ordered series (more defense = darker), so it uses a single-hue ramp.
INK, MUTED, RULE, PAPER = "#1A1A1A", "#5F5B52", "#D9D4C7", "#F4F1EA"
ACCENT, ALERT = "#1E3A8A", "#C8102E"
RAMP = ["#C9D3EE", "#8FA3D6", "#4F6BB5", "#1E3A8A"]


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor": PAPER, "axes.facecolor": PAPER, "savefig.facecolor": PAPER,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
        "text.color": INK, "font.family": "serif", "font.size": 10, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.color": RULE, "grid.linewidth": 0.6,
        "axes.axisbelow": True, "legend.frameon": False, "figure.dpi": 150,
    })
    return plt


def _test_set(name: str | None) -> tuple[str, pd.DataFrame]:
    for n in ([name] if name else ["test_indian", "test_ms", "test_uci"]):
        df = load(n)
        if df is not None and len(df):
            return n, df
    sys.exit("no test set found in data/processed. Run ml.build_dataset first.")


def _train_full() -> pd.DataFrame:
    train, dev = load("train"), load("dev_indian")
    if train is None:
        sys.exit("data/processed/train.csv not found. Run: python -m ml.build_dataset")
    return pd.concat([train, dev], ignore_index=True) if dev is not None else train


# ---------------------------------------------------------------- E4 + E7

def robustness(model: str, test_name: str | None, seed: int = 42) -> pd.DataFrame:
    full = _train_full()
    tn, test = _test_set(test_name)
    print(f"\nE4/E7: {model}, train {len(full)}, test {tn} ({len(test)})")
    variants = {a: test["text"].tolist() if a == "clean"
                else [obfuscate(t, a, seed=seed + i) for i, t in enumerate(test["text"])] for a in ATTACKS}
    rows = []
    for label, char, norm in GRID:
        # Engineered features are off here: they always normalize internally,
        # which would leak the defense into the "no normalizer" arms.
        pipe = make_pipeline(model, char=char, features=False, normalizer=norm)
        pipe.fit(full["text"].tolist(), full["binary"].tolist())
        for attack, texts in variants.items():
            m = evaluate(pipe, texts, test["binary"].tolist())
            rows.append({"config": label, "char": char, "normalizer": norm, "attack": attack,
                         "accuracy": m["accuracy"], "f1_macro": m["f1_macro"], "scam_recall": m.get("scam_recall")})
        print(f"  {label:<26} " + "  ".join(f"{r['attack']}={r['scam_recall']:.2f}" for r in rows[-len(ATTACKS):]))
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "robustness.csv", index=False)
    return df


def plot_robustness(df: pd.DataFrame, metric: str = "scam_recall"):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(9, 3.8))
    n = len(GRID)
    w = 0.8 / n
    x = np.arange(len(ATTACKS))
    for k, (label, _, _) in enumerate(GRID):
        vals = [df[(df.config == label) & (df.attack == a)][metric].iloc[0] for a in ATTACKS]
        # 2px surface gap between adjacent bars.
        bars = ax.bar(x + (k - (n - 1) / 2) * w, vals, w * 0.92, color=RAMP[k], label=label, edgecolor=PAPER, linewidth=1)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=6.5, color=MUTED)
    ax.set_xticks(x, [a.replace("_", "-") for a in ATTACKS])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Scam recall" if metric == "scam_recall" else metric)
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS / "fig2_robustness.png")
    plt.close(fig)


# ---------------------------------------------------------------- E5

def categories(zero_shot: bool, zs_model: str) -> pd.DataFrame | None:
    dev, test = load("dev_indian"), load("test_indian")
    if test is None or dev is None or not len(test):
        print("\nE5 skipped: needs dev_indian.csv and test_indian.csv")
        return None
    test = test[test["category"].isin(CATEGORIES)]
    y = test["category"].tolist()
    preds = {"rules": [rule_category(t, bool(b)) for t, b in zip(test["text"], test["binary"])]}
    if len(dev) >= 50 and dev["category"].nunique() >= 2:  # same threshold as ml.train
        preds["trained"] = make_trained().fit(dev["text"].tolist(), dev["category"].tolist()).predict(test["text"].tolist()).tolist()
    if zero_shot:
        try:
            preds["zero_shot"] = ZeroShot(zs_model).predict(test["text"].tolist())
        except ImportError:
            print("  zero-shot skipped: pip install transformers torch")
    rows, conf = [], {}
    print(f"\nE5: categories on test_indian ({len(test)} rows; trained on dev_indian, {len(dev)} rows)")
    for name, p in preds.items():
        labels = [c for c in CATEGORIES if c in set(y) | set(p)]
        rows.append({"method": name, "accuracy": round(accuracy_score(y, p), 4),
                     "f1_macro": round(f1_score(y, p, labels=sorted(set(y)), average="macro", zero_division=0), 4)})
        conf[name] = {"labels": labels, "matrix": confusion_matrix(y, p, labels=labels).tolist()}
        print(f"  {name:<10} acc={rows[-1]['accuracy']:.3f} f1={rows[-1]['f1_macro']:.3f}")
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "category.csv", index=False)
    (RESULTS / "category_confusion.json").write_text(json.dumps(conf, indent=2))
    best = max(rows, key=lambda r: r["f1_macro"])["method"]
    plot_confusion(conf[best]["matrix"], conf[best]["labels"], f"fig5_category_{best}.png")
    return df


def plot_confusion(matrix, labels, fname):
    plt = _plt()
    m = np.asarray(matrix, dtype=float)
    norm = m / np.maximum(m.sum(axis=1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(1 + 0.55 * len(labels), 0.8 + 0.5 * len(labels)))
    from matplotlib.colors import LinearSegmentedColormap

    ax.imshow(norm, cmap=LinearSegmentedColormap.from_list("ink", [PAPER, INK]), vmin=0, vmax=1)
    for i in range(len(labels)):
        for j in range(len(labels)):
            if m[i, j]:
                ax.text(j, i, int(m[i, j]), ha="center", va="center", fontsize=8,
                        color=PAPER if norm[i, j] > 0.5 else INK)
    short = [l.replace("_", " ") for l in labels]
    ax.set_xticks(range(len(labels)), short, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)), short, fontsize=8)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.grid(False)
    fig.tight_layout()
    fig.savefig(RESULTS / fname)
    plt.close(fig)


# ---------------------------------------------------------------- E6

class _Raw:
    """Uncalibrated counterpart of a pipeline: same features, plain classifier."""

    @staticmethod
    def make(model: str):
        pipe = make_pipeline(model)
        base = pipe.named_steps["clf"].estimator
        pipe.steps[-1] = ("clf", base)
        return pipe


def calibration(test_name: str | None) -> dict:
    full = _train_full()
    tn, test = _test_set(test_name)
    print(f"\nE6: reliability on {tn} ({len(test)})")
    out = {}
    for model in ("nb", "lr", "svm"):
        arms = {"calibrated": make_pipeline(model)}
        if model != "svm":  # LinearSVC has no probabilities before calibration
            arms["raw"] = _Raw.make(model)
        out[model] = {}
        for arm, pipe in arms.items():
            pipe.fit(full["text"].tolist(), full["binary"].tolist())
            p = pipe.predict_proba(test["text"].tolist())
            cls = list(pipe.classes_)
            y = test["binary"].to_numpy()
            out[model][arm] = {"ece": round(expected_calibration_error(y, p, cls), 4),
                               "bins": reliability_bins(y, p, cls)}
            print(f"  {model:<4} {arm:<10} ece={out[model][arm]['ece']:.4f}")
    (RESULTS / "calibration.json").write_text(json.dumps(out, indent=2))
    plot_calibration(out)
    return out


def plot_calibration(cal: dict):
    plt = _plt()
    fig, axes = plt.subplots(1, len(cal), figsize=(3.2 * len(cal), 3.2), sharey=True)
    names = {"nb": "Naive Bayes", "lr": "Logistic regression", "svm": "Linear SVM"}
    for ax, (model, arms) in zip(np.atleast_1d(axes), cal.items()):
        ax.plot([0, 1], [0, 1], color=RULE, lw=1, ls="--")
        for arm, style in (("raw", dict(color=MUTED, ls=":", marker="o", ms=4)),
                           ("calibrated", dict(color=ACCENT, ls="-", marker="o", ms=4))):
            if arm not in arms:
                continue
            b = [x for x in arms[arm]["bins"] if x["n"]]
            ax.plot([x["confidence"] for x in b], [x["accuracy"] for x in b], lw=2,
                    label=f"{arm} (ECE {arms[arm]['ece']:.3f})", **style)
        ax.set_title(names[model], fontsize=10)
        ax.set_xlim(0.45, 1.01)
        ax.set_ylim(0.0, 1.02)
        ax.set_xlabel("Predicted confidence")
        ax.legend(fontsize=7, loc="lower right")
    np.atleast_1d(axes)[0].set_ylabel("Observed accuracy")
    fig.tight_layout()
    fig.savefig(RESULTS / "fig3_calibration.png")
    plt.close(fig)


# ---------------------------------------------------------------- E1-E3 figures

def plot_domain_shift() -> dict | None:
    f = RESULTS / "metrics.csv"
    if not f.exists():
        print("\nE1-E3 figures skipped: run python -m ml.train first")
        return None
    df = pd.read_csv(f)
    e1, e2 = df[df.exp == "E1"].set_index("model"), df[df.exp == "E2"].set_index("model")
    if e1.empty or e2.empty:
        return None
    order = ["nb", "lr", "svm", "rnn", "rnn_attn", "lstm", "lstm_attn", "distilbert"]
    names = {"nb": "Naive Bayes", "lr": "Logistic regression", "svm": "Linear SVM", "rnn": "Simple RNN",
             "rnn_attn": "RNN + attention", "lstm": "BiLSTM", "lstm_attn": "BiLSTM + attention", "distilbert": "DistilBERT"}
    shift = {}
    for m in e1.index.intersection(e2.index):
        a, b = e1.loc[m, "accuracy"], e2.loc[m, "accuracy"]
        # Seed-sensitive models (ml.train_rnn --e2-seeds) are plotted at their seed mean.
        if "e2_seed_mean" in e2.columns and pd.notna(e2.loc[m, "e2_seed_mean"]):
            b = float(e2.loc[m, "e2_seed_mean"])
        shift[m] = {"uci": a, "indian": b, "drop_pct": round((b - a) / a * 100, 1)}

    # Dumbbell chart: one row per model, UCI accuracy (grey) -> Indian accuracy (accent).
    # Scales to many models without overlapping labels, unlike a slope chart.
    models = [m for m in order if m in shift] + [m for m in shift if m not in order]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 0.42 * len(models) + 1.1))
    for i, m in enumerate(reversed(models)):
        a, b = shift[m]["uci"], shift[m]["indian"]
        ax.plot([b, a], [i, i], color=RULE, lw=3, solid_capstyle="round", zorder=1)
        ax.scatter([a], [i], s=46, color=MUTED, zorder=2, label="UCI test" if i == 0 else None)
        ax.scatter([b], [i], s=46, color=ACCENT, zorder=3, label="Indian test" if i == 0 else None)
        ax.annotate(f"{b:.2f} ({shift[m]['drop_pct']:+.0f}%)", (b, i), xytext=(-8, 0), textcoords="offset points",
                    ha="right", va="center", fontsize=8, color=INK)
    ax.set_yticks(range(len(models)), [names.get(m, m) for m in reversed(models)], fontsize=9)
    lo = min(v["indian"] for v in shift.values())
    ax.set_xlim(max(0, lo - 0.18), 1.01)
    ax.set_xlabel("Accuracy")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS / "fig1_domain_shift.png")
    plt.close(fig)

    e3 = df[(df.exp == "E3") & (df.test == "test_indian") & (df.task == "multi")]
    if not e3.empty:
        row = e3.sort_values("f1_macro").iloc[-1]
        rec = next(r for r in json.loads((RESULTS / "experiments.json").read_text())
                   if r["exp"] == "E3" and r["task"] == "multi" and r["test"] == "test_indian" and r["model"] == row["model"])
        plot_confusion(rec["confusion"], rec["labels"], "fig4_confusion_e3.png")
    return shift


# ---------------------------------------------------------------- main

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=["e4e7", "e5", "e6", "figs"], default=["e4e7", "e5", "e6", "figs"])
    ap.add_argument("--model", default="lr", choices=["nb", "lr", "svm"], help="model for E4/E7")
    ap.add_argument("--test", default=None, help="test set for E4/E6 (default: test_indian, else test_ms / test_uci)")
    ap.add_argument("--zero-shot", action="store_true")
    ap.add_argument("--zs-model", default="facebook/bart-large-mnli")
    a = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)

    research = {}
    if "figs" in a.only:
        research["domain_shift"] = plot_domain_shift()
        f = RESULTS / "metrics.csv"
        if f.exists():
            research["metrics"] = pd.read_csv(f).replace({np.nan: None}).to_dict("records")
        ex = RESULTS / "experiments.json"
        if ex.exists():  # includes confusion matrices, which metrics.csv drops
            research["experiments"] = json.loads(ex.read_text())
    if "e4e7" in a.only:
        df = robustness(a.model, a.test)
        plot_robustness(df)
        research["robustness"] = df.to_dict("records")
    if "e5" in a.only:
        df = categories(a.zero_shot, a.zs_model)
        research["category"] = None if df is None else df.to_dict("records")
    if "e6" in a.only:
        research["calibration"] = calibration(a.test)

    path = RESULTS / "research.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    path.write_text(json.dumps({**old, **{k: v for k, v in research.items() if v is not None}}, indent=2, default=float))
    print(f"\nwrote {path} and figures in {RESULTS}")


if __name__ == "__main__":
    main()
