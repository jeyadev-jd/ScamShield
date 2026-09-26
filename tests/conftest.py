"""Shared synthetic data for pipeline smoke tests. Not a quality benchmark."""
import random

import pandas as pd
import pytest

import ml.evaluate as E
import ml.train as T

HAM = ["hey are we meeting at {n} near the gate", "ok i will call you after class", "reached home, dinner at {n}",
       "Dear Customer, your A/c XX{n} is debited by Rs {n}. Not you? Call 1800111109 -SBI",
       "{n} is your OTP for HDFC transaction. Do not share it with anyone."]
SPAM = ["Flat {n}% off on shoes this weekend only. Shop at myntra.com", "WINNER! You won a {n} prize, call now to claim",
        "Free ringtones! Text TONE to {n} now"]
SMISH = ["URGENT your SBI KYC expired, verify 0TP at sbi-kyc{n}.xyz", "Your parcel is held at customs, pay Rs {n} at bit.ly/p{n}",
         "CBI: arrest warrant on your Aadhaar. Call {n} immediately", "Account blocked. Update PAN now at hdfc-{n}.top"]


def _rows(templates, label, n, src, rng, cat=""):
    return [{"text": rng.choice(templates).format(n=rng.randint(10, 99999)), "label": label,
             "binary": int(label != "ham"), "category": cat, "source": src, "is_synthetic": 1} for _ in range(n)]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    rng = random.Random(0)
    uci = _rows(HAM, "ham", 60, "uci", rng) + _rows(SPAM, "spam", 25, "uci", rng)
    ms = _rows(HAM, "ham", 40, "mishra_soni", rng) + _rows(SMISH, "smishing", 30, "mishra_soni", rng) + _rows(SPAM, "spam", 15, "mishra_soni", rng)
    pd.DataFrame(uci + ms).to_csv(tmp_path / "train.csv", index=False)
    pd.DataFrame(_rows(HAM, "ham", 20, "uci", rng) + _rows(SPAM, "spam", 10, "uci", rng)).to_csv(tmp_path / "test_uci.csv", index=False)
    ind = (_rows(HAM, "ham", 12, "indian", rng, "legit") + _rows(SMISH[:1], "smishing", 6, "indian", rng, "kyc")
           + _rows(SMISH[1:2], "smishing", 6, "indian", rng, "courier") + _rows(SPAM[:1], "spam", 6, "indian", rng, "promotional"))
    pd.DataFrame(ind[::2]).to_csv(tmp_path / "test_indian.csv", index=False)
    pd.DataFrame(ind[1::2]).to_csv(tmp_path / "dev_indian.csv", index=False)
    monkeypatch.setattr(T, "DATA", tmp_path)
    monkeypatch.setattr(T, "MODELS", tmp_path / "models")
    (tmp_path / "results").mkdir()
    monkeypatch.setattr(T, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(E, "RESULTS", tmp_path / "results")
    return tmp_path
