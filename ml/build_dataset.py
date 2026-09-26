"""Merge, clean, anonymize and split the raw datasets.

    python -m ml.build_dataset            # reads data/raw, writes data/processed

Inputs (see data/raw/README.md for where to get them):
    data/raw/uci/SMSSpamCollection          tab-separated: label<TAB>text
    data/raw/mishra_soni/*.csv              columns LABEL, TEXT (ham / spam / smishing)
    data/raw/indian_raw.csv                 text, label, category, source, is_synthetic

Outputs in data/processed/:
    train.csv          UCI-train + Mishra-Soni-train (+ Indian dev split with --indian-in-train)
    test_uci.csv       held-out UCI (E1)
    test_ms.csv        held-out Mishra-Soni
    test_indian.csv    held-out Indian set, never used for training (E2, E3, E5)
    dev_indian.csv     Indian slice that E3 may add to training
    stats.json         counts per split / label / category, overlap checks

Unified schema: text, label (ham|spam|smishing), binary (0 ham / 1 scam),
category, source, is_synthetic.

Leakage control:
    1. Exact and near-duplicates are removed inside each source.
    2. Any test message whose normalized form also appears in train is
       dropped from the test split (cross-source duplicates are common:
       Mishra-Soni reuses many UCI messages).
    3. Splits are stratified and seeded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from ml.normalizer import normalize_text

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

LABELS = {"ham", "spam", "smishing"}
CATEGORIES = {
    "phishing", "otp_account", "upi_payment", "kyc", "prize_lottery", "job_task",
    "courier", "digital_arrest", "promotional", "legit",
}
COLUMNS = ["text", "label", "binary", "category", "source", "is_synthetic"]


# ---------------------------------------------------------------- cleaning

PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
ACCOUNT_RE = re.compile(r"\b(?:a/?c|acct?|account)\s*(?:no\.?|number)?\s*[:#]?\s*[x*]*\d{3,}", re.IGNORECASE)
AADHAAR_RE = re.compile(r"(?<!\d)\d{4}\s\d{4}\s\d{4}(?!\d)")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def anonymize(text: str) -> str:
    """Mask personal identifiers in the Indian set. Keeps the *shape* of the
    message (a phone number is still a phone number) so features still fire."""
    text = PHONE_RE.sub(lambda m: m.group()[:-8] + "XXXXXXXX" if len(m.group()) > 8 else "XXXXXXXXXX", text)
    text = AADHAAR_RE.sub("XXXX XXXX XXXX", text)
    text = PAN_RE.sub("XXXXX0000X", text)
    text = ACCOUNT_RE.sub(lambda m: re.sub(r"\d(?=\d{2})", "X", m.group()), text)
    text = EMAIL_RE.sub("user@example.com", text)
    return text


def clean(text: str) -> str:
    text = str(text).replace("\r", " ").replace("\n", " ")
    # Mishra-Soni ships U+FFFD (lost characters) and C1 control codes where
    # Windows smart quotes / dashes were mis-encoded.
    text = text.translate({0x91: "'", 0x92: "'", 0x93: '"', 0x94: '"', 0x96: "-", 0x97: "-", 0xFFFD: " "})
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    return re.sub(r"\s+", " ", text).strip()


def dedup_key(text: str) -> str:
    """Key for near-duplicate detection: normalized, lower-case, letters only,
    digits collapsed (so the same template with a different amount collides)."""
    t = normalize_text(text).lower()
    t = re.sub(r"\d+", "0", t)
    t = re.sub(r"[^a-z0 ]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return hashlib.md5(t.encode()).hexdigest()


def dedup(df: pd.DataFrame) -> pd.DataFrame:
    df = df.assign(_k=df["text"].map(dedup_key))
    # If duplicates disagree on label, keep the more severe one.
    severity = {"ham": 0, "spam": 1, "smishing": 2}
    # Stable sort: among equal labels the earlier row (earlier source) is kept.
    df = df.assign(_s=df["label"].map(severity)).sort_values("_s", ascending=False, kind="stable")
    return df.drop_duplicates("_k").drop(columns=["_k", "_s"]).sort_index()


# ---------------------------------------------------------------- loaders

def _finalize(df: pd.DataFrame, source: str, synthetic: int = 0) -> pd.DataFrame:
    df = df.copy()
    df["text"] = df["text"].map(clean)
    df = df[df["text"].str.len() > 0]
    df["label"] = df["label"].str.strip().str.lower()
    bad = ~df["label"].isin(LABELS)
    if bad.any():
        print(f"  [{source}] dropping {bad.sum()} rows with unknown labels: {sorted(df.loc[bad, 'label'].unique())[:5]}")
        df = df[~bad]
    df["binary"] = (df["label"] != "ham").astype(int)
    if "category" not in df:
        df["category"] = ""
    df["category"] = df["category"].fillna("").astype(str).str.strip().str.lower()
    df.loc[(df["category"] == "") & (df["label"] == "ham"), "category"] = "legit"
    if "source" in df:  # keep where the message was collected (rbi, cybercrime, personal, ...)
        df["source"] = source + ":" + df["source"].fillna("unknown").astype(str).str.strip()
    else:
        df["source"] = source
    if "is_synthetic" not in df:
        df["is_synthetic"] = synthetic
    df["is_synthetic"] = df["is_synthetic"].fillna(0).astype(int)
    return df[COLUMNS].reset_index(drop=True)


def load_uci(path: Path) -> pd.DataFrame | None:
    f = path / "SMSSpamCollection" if path.is_dir() else path
    if not f.exists():
        return None
    df = pd.read_csv(f, sep="\t", header=None, names=["label", "text"], quoting=3, encoding="utf-8")
    return _finalize(df, "uci")


def load_mishra_soni(path: Path) -> pd.DataFrame | None:
    files = sorted(path.glob("*.csv")) if path.is_dir() else [path]
    files = [f for f in files if f.exists()]
    if not files:
        return None
    df = pd.read_csv(files[0], encoding="utf-8", encoding_errors="replace")
    cols = {c.lower().strip(): c for c in df.columns}
    if "label" not in cols or "text" not in cols:
        sys.exit(f"{files[0]}: expected LABEL and TEXT columns, got {list(df.columns)}")
    df = df.rename(columns={cols["label"]: "label", cols["text"]: "text"})[["label", "text"]]
    return _finalize(df, "mishra_soni")


def load_indian(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, encoding="utf-8")
    missing = {"text", "label", "category"} - set(df.columns)
    if missing:
        sys.exit(f"{path}: missing columns {missing}")
    unknown = set(df["category"].dropna().str.strip().str.lower()) - CATEGORIES
    if unknown:
        sys.exit(f"{path}: unknown categories {unknown}; allowed {sorted(CATEGORIES)}")
    df["text"] = df["text"].map(anonymize)
    return _finalize(df, "indian")


# ---------------------------------------------------------------- splitting

def split(df: pd.DataFrame, test_size: float, seed: int, stratify: str = "label"):
    strat = df[stratify] if df[stratify].value_counts().min() >= 2 else None
    return train_test_split(df, test_size=test_size, random_state=seed, stratify=strat)


def drop_overlap(test: pd.DataFrame, train: pd.DataFrame, name: str, stats: dict) -> pd.DataFrame:
    train_keys = set(train["text"].map(dedup_key))
    mask = test["text"].map(dedup_key).isin(train_keys)
    stats.setdefault("overlap_removed", {})[name] = int(mask.sum())
    return test[~mask]


def summarize(df: pd.DataFrame) -> dict:
    return {
        "n": len(df),
        "label": df["label"].value_counts().to_dict(),
        "category": df["category"].value_counts().to_dict(),
        "source": df["source"].value_counts().to_dict(),
        "synthetic": int(df["is_synthetic"].sum()),
    }


def build(raw: Path, out: Path, seed: int = 42, test_size: float = 0.2,
          indian_dev: float = 0.3, indian_in_train: bool = False,
          use_synthetic: bool = True) -> dict:
    uci = load_uci(raw / "uci")
    ms = load_mishra_soni(raw / "mishra_soni")
    # Own collection + public Indian datasets (ml.import_public), both tested as "Indian".
    ind_parts = [d for d in (load_indian(raw / "indian_raw.csv"), load_indian(raw / "indian_public.csv")) if d is not None]
    ind = pd.concat(ind_parts, ignore_index=True) if ind_parts else None

    for name, df in [("uci", uci), ("mishra_soni", ms), ("indian", ind)]:
        print(f"{name:<12} {'missing' if df is None else f'{len(df)} rows'}")
    if uci is None and ms is None:
        sys.exit("No training data found. Download UCI and/or Mishra-Soni first (see data/raw/README.md).")

    stats: dict = {"seed": seed, "dedup_removed": {}}
    train_parts, tests = [], {}

    # De-duplicate the public sources jointly *before* splitting: Mishra-Soni
    # reuses most UCI messages, so per-source splits would leak test messages
    # into training via the other source. Each message is kept once, under
    # the source listed first (UCI), with the more severe label on conflict.
    public = pd.concat([d for d in (uci, ms) if d is not None], ignore_index=True)
    before = len(public)
    public = dedup(public)
    stats["dedup_removed"]["public"] = before - len(public)
    stats["public_after_dedup"] = public["source"].value_counts().to_dict()

    for name, src in [("uci", "uci"), ("ms", "mishra_soni")]:
        df = public[public["source"] == src]
        if df.empty:
            continue
        tr, te = split(df, test_size, seed)
        train_parts.append(tr)
        tests[f"test_{name}"] = te

    if ind is not None:
        before = len(ind)
        ind = dedup(ind)
        stats["dedup_removed"]["indian"] = before - len(ind)
        dev, te = split(ind, 1 - indian_dev, seed, stratify="category")
        tests["test_indian"] = te
        tests["dev_indian"] = dev
        if indian_in_train:
            train_parts.append(dev)

    train = dedup(pd.concat(train_parts, ignore_index=True))
    for name in list(tests):
        if name != "dev_indian":
            tests[name] = drop_overlap(tests[name], train, name, stats)

    # Synthetic augmentation goes into TRAIN ONLY. Rows that collide with any
    # test message are dropped from the synthetic side, never from the tests.
    syn_path = raw / "synthetic_train.csv"
    if use_synthetic and syn_path.exists():
        syn = pd.read_csv(syn_path, encoding="utf-8")
        syn = _finalize(syn.drop(columns=["source"], errors="ignore"), "synthetic", synthetic=1)
        test_keys = set().union(*(set(t["text"].map(dedup_key)) for t in tests.values()))
        clash = syn["text"].map(dedup_key).isin(test_keys)
        stats["synthetic"] = {"rows": int((~clash).sum()), "dropped_test_clash": int(clash.sum())}
        train = dedup(pd.concat([train, syn[~clash]], ignore_index=True))
        print(f"synthetic    {int((~clash).sum())} rows added to train ({int(clash.sum())} dropped: clash with a test message)")

    out.mkdir(parents=True, exist_ok=True)
    train.to_csv(out / "train.csv", index=False, encoding="utf-8")
    stats["train"] = summarize(train)
    for name, df in tests.items():
        df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8")
        stats[name] = summarize(df)
    (out / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"\ntrain        {len(train)} rows  {stats['train']['label']}")
    for name, df in tests.items():
        print(f"{name:<12} {len(df)} rows  {df['label'].value_counts().to_dict()}")
    print(f"overlap removed from tests: {stats.get('overlap_removed', {})}")
    print(f"wrote {out}")
    return stats


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=RAW)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--indian-dev", type=float, default=0.3, help="fraction of the Indian set reserved as dev (E3)")
    ap.add_argument("--no-synthetic", action="store_true", help="skip data/raw/synthetic_train.csv (from ml.synth)")
    ap.add_argument("--indian-in-train", action="store_true", help="add the Indian dev split to train.csv (E3)")
    a = ap.parse_args()
    build(a.raw, a.out, a.seed, a.test_size, a.indian_dev, a.indian_in_train, not a.no_synthetic)


if __name__ == "__main__":
    main()
