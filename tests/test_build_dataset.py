import json
import shutil
from pathlib import Path

import pandas as pd

from ml.build_dataset import anonymize, build, dedup_key

ROOT = Path(__file__).resolve().parents[1]


def _fake_raw(tmp: Path) -> Path:
    raw = tmp / "raw"
    (raw / "uci").mkdir(parents=True)
    (raw / "mishra_soni").mkdir()
    ham = [f"hey are we meeting at {i} pm near gate {i % 7}" for i in range(40)]
    spam = [f"WINNER you have won a {i} prize call now to claim offer code {chr(65 + i % 26)}{chr(66 + i % 20)}" for i in range(20)]
    lines = [f"ham\t{t}" for t in ham] + [f"spam\t{t}" for t in spam]
    (raw / "uci" / "SMSSpamCollection").write_text("\n".join(lines), encoding="utf-8")
    ms = pd.DataFrame({
        # First 10 rows copy UCI messages to check cross-source leakage handling.
        "LABEL": ["ham"] * 10 + ["ham"] * 20 + ["spam"] * 10 + ["Smishing"] * 20,
        "TEXT": ham[:10] + [f"lunch at home on day {i} with family {chr(97 + i)}" for i in range(20)]
        + [f"sale ends {i} sunday big discount on shoes {chr(97 + i)}" for i in range(10)]
        + [f"your account {chr(97 + i)} is blocked verify at bit.ly/x{i}" for i in range(20)],
        "URL": "", "EMAIL": "", "PHONE": "",
    })
    ms.to_csv(raw / "mishra_soni" / "Dataset_5971.csv", index=False)
    shutil.copy(ROOT / "data" / "raw" / "indian_raw.csv", raw / "indian_raw.csv")
    return raw


def test_build_end_to_end(tmp_path):
    raw = _fake_raw(tmp_path)
    out = tmp_path / "processed"
    stats = build(raw, out, seed=1)

    for f in ["train", "test_uci", "test_ms", "test_indian", "dev_indian"]:
        assert (out / f"{f}.csv").exists()
    train = pd.read_csv(out / "train.csv")
    assert set(train["label"]) <= {"ham", "spam", "smishing"}
    assert "smishing" in set(train["label"])
    assert not train["source"].str.startswith("indian").any()

    # No test message may also appear in train.
    keys = set(train["text"].map(dedup_key))
    for f in ["test_uci", "test_ms", "test_indian"]:
        t = pd.read_csv(out / f"{f}.csv")
        assert not t["text"].map(dedup_key).isin(keys).any(), f

    indian = pd.concat([pd.read_csv(out / "test_indian.csv"), pd.read_csv(out / "dev_indian.csv")])
    assert len(indian) == len(pd.read_csv(raw / "indian_raw.csv"))
    assert json.loads((out / "stats.json").read_text())["train"]["n"] == len(train)


def test_indian_in_train_flag(tmp_path):
    raw = _fake_raw(tmp_path)
    build(raw, tmp_path / "p", seed=1, indian_in_train=True)
    train = pd.read_csv(tmp_path / "p" / "train.csv")
    assert train["source"].str.startswith("indian").any()


def test_anonymize():
    s = anonymize("Call 9876543210 or +91 98765 43210, Aadhaar 1234 5678 9012, PAN ABCDE1234F, A/c 123456789, mail a.b@gmail.com")
    for secret in ["9876543210", "98765 43210", "1234 5678 9012", "ABCDE1234F", "123456789", "a.b@gmail.com"]:
        assert secret not in s, secret


def test_dedup_key_ignores_amounts_and_obfuscation():
    assert dedup_key("Pay Rs 49 now to verify 0TP") == dedup_key("pay rs 99 now to verify OTP")
