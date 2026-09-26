"""Explainer, category, risk and evaluate smoke tests."""
import argparse
import json

import joblib
import pytest

import ml.evaluate as E
import ml.train as T
from ml.category import rule_category
from ml.explain import kill_chain, report, token_contributions

SCAM = "URGENT! Your SBI KYC exp1red. Verify 0TP at sbi-kyc.xyz"
HAM = "reached home, dinner at 9"


@pytest.fixture
def trained(data_dir):
    args = argparse.Namespace(exp=["e3"], models=["lr"], no_char=False, no_features=False,
                              no_normalizer=False, save=True, tag="")
    T.run(args)
    m = data_dir / "models"
    # category.joblib is only trained with >= 50 labeled Indian messages; rules are used otherwise.
    return {k: joblib.load(m / f"{k}.joblib") if (m / f"{k}.joblib").exists() else None
            for k in ("scam_binary", "scam_multi", "risk", "category")}


@pytest.mark.parametrize("text, cat", [
    ("CBI officer: arrest warrant issued on your Aadhaar", "digital_arrest"),
    ("Your KYC is pending, update now", "kyc"),
    ("Accept the collect request on UPI to receive refund", "upi_payment"),
    ("Your account will be blocked, share OTP", "otp_account"),
    ("Parcel held at customs, pay fee", "courier"),
    ("You w0n a lottery prize", "prize_lottery"),
    ("Part time job, earn Rs 3000 daily", "job_task"),
])
def test_rule_category(text, cat):
    assert rule_category(text, True) == cat


def test_rule_category_respects_ham_verdict():
    assert rule_category("482913 is your OTP. Do not share.", False) == "legit"
    assert rule_category("Flat 50% off sale", False) == "promotional"


def test_kill_chain():
    c = kill_chain(SCAM)
    assert "expired" in c["hook"].lower()
    assert c["urgency"].lower() == "urgent"
    assert c["credibility"] == "SBI"
    assert c["ask"].lower().startswith("verify otp")
    assert kill_chain(HAM) == {}


def test_occlusion_weights_point_the_right_way(trained):
    toks = token_contributions(trained["scam_binary"], SCAM)
    assert [t["token"] for t in toks] == SCAM.split()
    w = {t["token"]: t["weight"] for t in toks}
    # "OTP" also appears in the synthetic HAM templates, so only scam-exclusive tokens are checked.
    assert w["URGENT!"] > 0 and w["KYC"] > 0 and w["sbi-kyc.xyz"] > 0
    assert SCAM[toks[3]["start"]:toks[3]["end"]] == toks[3]["token"]


def test_report_matches_api_schema(trained):
    r = report(SCAM, trained["scam_binary"], trained["scam_multi"], trained["category"], trained["risk"], sender="+91 9876543210")
    for k in ["label", "probability", "uncertain", "risk_score", "risk_level", "category", "normalized_text",
              "obfuscation_detected", "token_contributions", "url_analysis", "kill_chain", "indicators", "advice"]:
        assert k in r, k
    assert r["label"] == "smishing" and r["risk_level"] == "HIGH"
    assert r["url_analysis"]["lookalike_of"] == "sbi.co.in"
    assert {o["from"] for o in r["obfuscation_detected"]} == {"exp1red", "0TP"}
    assert any(i["feature"] == "sender_personal" for i in r["indicators"])
    json.dumps(r)  # must be serializable for the API

    h = report(HAM, trained["scam_binary"], trained["scam_multi"], trained["category"], trained["risk"], sender="VM-SBIINB")
    assert h["label"] == "ham" and h["risk_level"] == "LOW" and h["category"] == "legit" and h["kill_chain"] == {}


def test_evaluate_all(data_dir, trained):
    rob = E.robustness("lr", "test_indian")
    assert set(rob.attack) == set(E.ATTACKS) and rob.config.nunique() == 4
    E.plot_robustness(rob)
    # The fixture's dev split has < 50 rows, so only the rule baseline is scored.
    assert E.categories(False, "").method.tolist() == ["rules"]
    cal = E.calibration("test_indian")
    assert set(cal) == {"nb", "lr", "svm"} and "raw" not in cal["svm"]
    res = data_dir / "results"
    for f in ["robustness.csv", "category.csv", "calibration.json", "fig2_robustness.png", "fig3_calibration.png"]:
        assert (res / f).exists(), f


def test_occlusion_not_flat_for_saturated_nb(data_dir):
    # Calibrated NB can map every input to one probability; weights must still vary.
    T.run(argparse.Namespace(exp=["e3"], models=["nb"], no_char=False, no_features=False,
                             no_normalizer=False, save=True, tag=""))
    nb = joblib.load(data_dir / "models" / "scam_binary.joblib")
    w = [t["weight"] for t in token_contributions(nb, SCAM)]
    assert len(set(w)) > 3 and max(w) > 0
