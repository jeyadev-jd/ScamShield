"""Fine-grained scam category: three approaches compared in E5.

    rules      hand-written keyword rules, no training data needed
    trained    TF-IDF + logistic regression on the labeled Indian dev split
    zero_shot  NLI zero-shot classifier (optional, needs `transformers` + torch)

The public datasets carry no category labels, so only the Indian set can
train or evaluate this step. That is why the Indian set holds a dev split.
"""
from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from ml.normalizer import normalize_text
from ml.preprocess import preprocess

CATEGORIES = [
    "phishing", "otp_account", "upi_payment", "kyc", "prize_lottery", "job_task",
    "courier", "digital_arrest", "promotional", "legit",
]

# Checked in order; the first match wins. Specific, high-harm categories first.
RULES: list[tuple[str, re.Pattern]] = [(c, re.compile(p, re.I)) for c, p in [
    ("digital_arrest", r"\b(arrest|cbi|narcotics|drugs? parcel|warrant|money laundering|customs officer|cyber ?crime (branch|police)|trai)\b"),
    ("kyc", r"\b(kyc|re-?kyc|know your customer)\b"),
    ("upi_payment", r"\b(upi|collect request|scan (the )?qr|gpay|phonepe|paytm|bhim|sent .* by mistake)\b"),
    ("otp_account", r"\b(otp|account (will be |is )?(blocked|suspended|frozen|deactivated)|pin|cvv|net ?banking|yono)\b"),
    ("courier", r"\b(parcel|courier|customs|shipment|delivery (failed|attempt)|india ?post|fedex|dhl|bluedart)\b"),
    ("prize_lottery", r"\b(won|winner|lottery|prize|lucky draw|kbc|jackpot|claim your (reward|gift))\b"),
    ("job_task", r"\b(part[- ]?time|work from home|daily (income|salary|earn)|earn rs|task|telegram|hiring|like (youtube|videos))\b"),
    ("phishing", r"(https?://|www\.|\b[a-z0-9-]+\.(xyz|top|info|online|site|live|club|icu|in|com|ly)\b)|\b(electricity|disconnect|refund|verify|update)\b"),
    ("promotional", r"\b(offer|sale|discount|% off|cashback|shop|recharge|plan|coupon|t&c)\b"),
]]

NLI_LABELS = {
    "phishing": "a phishing link asking to verify or update details",
    "otp_account": "a request for an OTP or a threat that a bank account is blocked",
    "upi_payment": "a UPI payment or collect request trick",
    "kyc": "a KYC update request",
    "prize_lottery": "a prize, lottery or reward claim",
    "job_task": "a part-time job or online task offer",
    "courier": "a courier, parcel or customs fee notice",
    "digital_arrest": "a police, CBI or legal threat",
    "promotional": "a marketing promotion",
    "legit": "a normal personal or transactional message",
}


def rule_category(text: str, is_scam: bool | None = None) -> str:
    """Rule-based category. With ``is_scam=False`` a message is 'legit' unless it is
    clearly promotional; with no verdict given, only rules decide."""
    t = normalize_text(text)
    if is_scam is False:
        return "promotional" if RULES[-1][1].search(t) else "legit"
    for cat, rx in RULES:
        if rx.search(t):
            return cat
    return "legit" if is_scam is None else "phishing"


def make_trained() -> Pipeline:
    return Pipeline([
        ("vec", FeatureUnion([
            ("word", TfidfVectorizer(preprocessor=preprocess, ngram_range=(1, 2), sublinear_tf=True)),
            ("char", TfidfVectorizer(preprocessor=preprocess, analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
        ])),
        ("clf", LogisticRegression(C=5, max_iter=3000, class_weight="balanced")),
    ])


class ZeroShot:
    """Lazy wrapper around a Hugging Face zero-shot pipeline. Heavy: ~1.6 GB for bart-large-mnli."""

    def __init__(self, model: str = "facebook/bart-large-mnli"):
        from transformers import pipeline  # optional dependency

        self.pipe = pipeline("zero-shot-classification", model=model)
        self.inv = {v: k for k, v in NLI_LABELS.items()}

    def predict(self, texts: list[str]) -> list[str]:
        out = self.pipe([normalize_text(t) for t in texts], list(NLI_LABELS.values()),
                        hypothesis_template="This SMS is {}.")
        return [self.inv[r["labels"][0]] for r in (out if isinstance(out, list) else [out])]
