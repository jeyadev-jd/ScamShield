import numpy as np
import pytest

from ml.features import FEATURE_NAMES, FeatureExtractor, extract
from ml.preprocess import preprocess
from ml.url_forensics import analyze_url, extract_urls

SCAM = "URGENT! Your SBI KYC exp1red. Verify 0TP at sbi-kyc.xyz or call 9876543210"
HAM = "Dear Customer, your A/c XX4521 is debited by Rs 1,250.00. Not you? Call 1800111109. -SBI"


def test_all_features_present_and_numeric():
    f = extract(SCAM)
    assert list(f) == FEATURE_NAMES
    assert all(isinstance(v, float) for v in f.values())


def test_scam_signals():
    f = extract(SCAM)
    assert f["has_url"] == 1 and f["has_phone"] == 1
    assert f["url_lookalike_score"] == 1 and f["suspicious_tld"] == 1
    assert f["obfuscation_count"] == 2          # exp1red, 0TP
    assert f["personal_info_request"] >= 2      # kyc, otp (after normalization)
    assert f["urgent_words"] >= 2               # urgent, expired


def test_ham_is_quieter():
    s, h = extract(SCAM), extract(HAM)
    assert h["has_url"] == 0 and h["obfuscation_count"] == 0 and h["personal_info_request"] == 0
    assert h["money_keywords"] >= 1
    assert s["urgent_words"] > h["urgent_words"]


def test_transformer_scaled_nonnegative():
    fe = FeatureExtractor().fit([SCAM, HAM, "ok see you"])
    X = fe.transform([SCAM, HAM, "x" * 5000])
    assert X.shape == (3, len(FEATURE_NAMES))
    assert np.all(X >= 0) and np.all(X <= 1)


def test_preprocess_masks_volatile_values():
    t = preprocess("Pay Rs 49 at bit.ly/x1 or call +91 98765 43210, OTP 482913")
    assert t == "pay moneytoken at urltoken or call phonetoken otp numtoken"
    assert preprocess("V e r i f y 0TP") == "verify otp"


@pytest.mark.parametrize("url, lookalike, flags", [
    ("sbi-kyc.xyz", "sbi.co.in", {"suspicious_tld"}),
    ("http://hdfcbank-secure.top/login", "hdfcbank.com", {"suspicious_tld"}),
    ("paytrn.com", "paytm.com", set()),
    ("bit.ly/ip-redel", None, {"shortener"}),
    ("http://192.168.4.20/sbi", None, {"ip_host"}),
    ("https://www.onlinesbi.sbi", None, set()),
    ("https://sbi.co.in/web/yono", None, set()),
])
def test_url_forensics(url, lookalike, flags):
    r = analyze_url(url)
    assert r["lookalike_of"] == lookalike
    for k in ("suspicious_tld", "shortener", "ip_host"):
        assert r[k] == (k in flags), k


def test_official_domain_scores_zero():
    assert analyze_url("https://sbi.co.in")["score"] == 0
    assert analyze_url("sbi-kyc.xyz")["score"] > 0.5


def test_extract_urls():
    assert extract_urls("Go to sbi-kyc.xyz. Or www.x.com/a, then bit.ly/q!") == ["sbi-kyc.xyz", "www.x.com/a", "bit.ly/q"]
