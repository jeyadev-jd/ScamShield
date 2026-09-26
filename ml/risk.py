"""Learned risk score (0-100) with per-indicator contributions.

A small logistic regression on top of the engineered features plus the text
classifier's out-of-fold scam probability. Its coefficients are readable, so
every score decomposes into "+0.41 personal info request, +0.19 suspicious
URL, ..." for the Indicators table.

The score is an *indicator*, not a fraud probability: it is trained on the
dataset's class balance, which does not match real inbox base rates.
"""
from __future__ import annotations

import re

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict

from ml.features import FEATURE_NAMES, FeatureExtractor

LABELS = {
    "message_length": "Message length", "word_count": "Word count", "has_url": "Contains a link",
    "has_phone": "Contains a phone number", "urgent_words": "Urgency language",
    "money_keywords": "Money language", "prize_keywords": "Prize / reward language",
    "personal_info_request": "Asks for OTP / PIN / personal details", "special_char_count": "Special characters",
    "exclamation_count": "Exclamation marks", "uppercase_ratio": "Shouting (uppercase)",
    "obfuscation_count": "Disguised words (obfuscation)", "url_lookalike_score": "Link imitates a brand",
    "url_shortener": "Shortened link hides destination", "suspicious_tld": "Suspicious link ending",
    "indian_scam_keywords": "Known Indian scam terms", "text_model": "Text classifier",
    "sender_header": "Registered sender header", "sender_personal": "Sent from a personal number",
}


HIDDEN = {"message_length", "word_count", "special_char_count"}


def sender_features(sender: str) -> tuple[float, float]:
    s = (sender or "").replace(" ", "")
    header = bool(re.fullmatch(r"[A-Z]{2}-[A-Z0-9]{5,6}(-[A-Z])?", s, re.I))
    personal = bool(re.fullmatch(r"\+?\d{10,13}", s.replace("X", "0").replace("x", "0")))
    return float(header), float(personal)


class RiskModel:
    def __init__(self, C: float = 1.0):
        self.fe = FeatureExtractor()
        # No class_weight="balanced": it shifts the intercept so a message the
        # text model rates P(scam)=0.4 came out as "HIGH 72". Unweighted, the
        # score stays consistent with the calibrated classifier.
        self.lr = LogisticRegression(C=C, max_iter=2000)
        self.names = FEATURE_NAMES + ["text_model"]

    def _X(self, texts, p_scam):
        return np.hstack([self.fe.transform(texts), np.asarray(p_scam, dtype=float).reshape(-1, 1)])

    def fit(self, texts, y, text_model):
        """Fit on out-of-fold text-model probabilities so the risk layer does not
        learn to trust an overfit classifier."""
        from ml.explain import scam_proba  # local import avoids a cycle

        texts = list(texts)
        y = np.asarray(y)
        oof = cross_val_predict(text_model, texts, y, cv=3, method="predict_proba")
        classes = sorted(set(y.tolist()), key=str)
        ham = classes.index(0) if 0 in classes else classes.index("ham")
        p = 1 - oof[:, ham]
        self.fe.fit(texts)
        self.lr.fit(self._X(texts, p), (y != classes[ham]).astype(int))
        return self

    def score(self, text: str, p_scam: float, sender: str = "") -> tuple[int, list[dict]]:
        x = self._X([text], [p_scam])[0]
        contrib = self.lr.coef_[0] * x
        logit = self.lr.intercept_[0] + contrib.sum()
        header, personal = sender_features(sender)
        # Sender is a rule-based adjustment: no public dataset carries sender IDs.
        adj = []
        if header:
            adj.append(("sender_header", -0.6))
        if personal:
            adj.append(("sender_personal", 0.6))
        logit += sum(w for _, w in adj)
        score = int(round(100 / (1 + np.exp(-logit))))

        # Length and punctuation counts help the model but are not reasons a
        # person can act on ("message length +6"), so they are not listed.
        items = [(n, float(c)) for n, c in zip(self.names, contrib)
                 if n not in HIDDEN and abs(c) >= 0.05 and x[self.names.index(n)] > 0]
        items += adj
        items.sort(key=lambda t: -abs(t[1]))
        return score, [{"feature": n, "label": LABELS.get(n, n), "weight": round(w, 2)} for n, w in items[:8]]
