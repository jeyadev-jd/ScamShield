"""Loads the trained artifacts once and turns a message into an API response."""
from __future__ import annotations

import json
import os
from functools import cached_property
from pathlib import Path

import joblib
import pandas as pd

from ml.explain import report

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = Path(os.environ.get("SCAMSHIELD_MODELS", ROOT / "backend" / "models"))
RESULTS_DIR = Path(os.environ.get("SCAMSHIELD_RESULTS", ROOT / "results"))
DATA_DIR = Path(os.environ.get("SCAMSHIELD_DATA", ROOT / "data" / "processed"))

REQUIRED = ["scam_binary.joblib"]
OPTIONAL = ["scam_multi.joblib", "category.joblib", "risk.joblib"]


class ModelsMissing(RuntimeError):
    pass


class Analyzer:
    def __init__(self, models_dir: Path = MODELS_DIR):
        self.dir = Path(models_dir)
        missing = [f for f in REQUIRED if not (self.dir / f).exists()]
        if missing:
            raise ModelsMissing(f"missing {missing} in {self.dir}; run python -m ml.train")
        self.binary = joblib.load(self.dir / "scam_binary.joblib")
        opt = {f: joblib.load(self.dir / f) if (self.dir / f).exists() else None for f in OPTIONAL}
        self.multi, self.category, self.risk = opt["scam_multi.joblib"], opt["category.joblib"], opt["risk.joblib"]
        meta = self.dir / "meta.json"
        self.meta = json.loads(meta.read_text()) if meta.exists() else {}

    def analyze(self, text: str, sender: str = "") -> dict:
        return report(text, self.binary, self.multi, self.category, self.risk, sender=sender)


def research() -> dict | None:
    f = RESULTS_DIR / "research.json"
    return json.loads(f.read_text()) if f.exists() else None


class Dataset:
    """Summary + specimen messages for the Dataset page. Only the Indian set is
    served as specimens; it is already anonymized by build_dataset."""

    @cached_property
    def payload(self) -> dict | None:
        stats = DATA_DIR / "stats.json"
        if not stats.exists():
            return None
        out = {"stats": json.loads(stats.read_text())}
        frames = [pd.read_csv(DATA_DIR / f, keep_default_na=False)
                  for f in ("test_indian.csv", "dev_indian.csv") if (DATA_DIR / f).exists()]
        if frames:
            df = pd.concat(frames, ignore_index=True)
            out["specimens"] = df[["text", "label", "category", "source", "is_synthetic"]].to_dict("records")
        return out
