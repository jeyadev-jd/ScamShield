"""Hand-engineered features, used next to TF-IDF and by the risk-score model.

    from ml.features import extract, FeatureExtractor
    extract("URGENT! Verify 0TP at sbi-kyc.xyz")["url_lookalike_score"]  # 1.0
"""
from __future__ import annotations

import re

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

from ml.normalizer import normalize
from ml.preprocess import MONEY_RE, PHONE_RE
from ml.url_forensics import analyze_text

URGENT = r"urgent|immediately|asap|now|today|tonight|within \d+|expire[sd]?|last chance|final notice|hurry|limited time|blocked|suspend\w*|deactivat\w*"
MONEY = r"rs\.?|inr|₹|cash|money|pay\w*|refund|loan|credit|debit|fee|charges?|amount|balance|lakh|crore|£"
PRIZE = r"won|win|winner|prize|lottery|reward|cashback|gift|voucher|bonus|congrat\w*|selected|lucky|claim|free"
PERSONAL = r"otp|pin|cvv|password|passcode|card (?:no|number|details)|account (?:no|number|details)|aadhaar|pan (?:card|no|number)|kyc|login|credentials|bank details"
INDIAN = r"upi|kyc|aadhaar|aadhar|pan card|courier|parcel|customs|arrest|cbi|narcotics|police|digital arrest|telegram|task|part time|electricity|yono|paytm|phonepe"

PATTERNS = {name: re.compile(rf"\b(?:{p})\b", re.I) for name, p in [
    ("urgent_words", URGENT), ("money_keywords", MONEY), ("prize_keywords", PRIZE),
    ("personal_info_request", PERSONAL), ("indian_scam_keywords", INDIAN),
]}

FEATURE_NAMES = [
    "message_length", "word_count", "has_url", "has_phone", "urgent_words", "money_keywords",
    "prize_keywords", "personal_info_request", "special_char_count", "exclamation_count",
    "uppercase_ratio", "obfuscation_count", "url_lookalike_score", "url_shortener",
    "suspicious_tld", "indian_scam_keywords",
]


def extract(text: str) -> dict[str, float]:
    norm = normalize(text)
    clean = norm.text
    urls = analyze_text(text)
    letters = [c for c in text if c.isalpha()]
    f = {
        "message_length": len(text),
        "word_count": len(text.split()),
        "has_url": int(bool(urls)),
        "has_phone": int(bool(PHONE_RE.search(clean))),
        "special_char_count": sum(not c.isalnum() and not c.isspace() for c in text),
        "exclamation_count": text.count("!"),
        "uppercase_ratio": (sum(c.isupper() for c in letters) / len(letters)) if letters else 0.0,
        "obfuscation_count": norm.count,
        "url_lookalike_score": max((1.0 if u["lookalike_of"] else 0.0 for u in urls), default=0.0),
        "url_shortener": int(any(u["shortener"] for u in urls)),
        "suspicious_tld": int(any(u["suspicious_tld"] for u in urls)),
    }
    for name, rx in PATTERNS.items():
        f[name] = len(rx.findall(clean))
    f["money_keywords"] += len(MONEY_RE.findall(clean))
    return {k: float(f[k]) for k in FEATURE_NAMES}


def extract_matrix(texts) -> np.ndarray:
    return np.array([[row[k] for k in FEATURE_NAMES] for row in map(extract, texts)], dtype=float)


class FeatureExtractor(BaseEstimator, TransformerMixin):
    """sklearn transformer: raw texts -> engineered features scaled to [0, 1].

    Scaling uses a log1p transform and the max seen during fit (clipped), which
    keeps every value non-negative so MultinomialNB can use the features too.
    """

    def fit(self, X, y=None):
        m = np.log1p(extract_matrix(X))
        self.max_ = np.where(m.max(axis=0) > 0, m.max(axis=0), 1.0)
        return self

    def transform(self, X):
        return np.clip(np.log1p(extract_matrix(X)) / self.max_, 0, 1)

    def get_feature_names_out(self, input_features=None):
        return np.array([f"feat__{n}" for n in FEATURE_NAMES])
