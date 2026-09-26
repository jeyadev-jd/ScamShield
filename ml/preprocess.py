"""Text preprocessing for the TF-IDF vectorizers.

    normalize (optional) -> lowercase -> mask URLs / phones / money / numbers
    -> strip punctuation -> collapse whitespace

Masking replaces volatile values with stable placeholder tokens so the model
learns "message contains a link" rather than memorizing one scam domain.
No lemmatization: on SMS text it barely changes scores, and the char n-gram
vectorizer already shares evidence between "verify" / "verified" / "verification".
"""
from __future__ import annotations

import re

from ml.normalizer import normalize_text
from ml.url_forensics import URL_RE

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s-]{8,}\d|1800\d{6,7})(?!\w)")
MONEY_RE = re.compile(r"(?:rs\.?|inr|₹|£|\$)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:rs|inr|/-|lakh|lac|crore|cr)\b", re.I)
NUM_RE = re.compile(r"\d+")
NONWORD_RE = re.compile(r"[^a-z_ ]+")


def preprocess(text: str, use_normalizer: bool = True) -> str:
    if use_normalizer:
        text = normalize_text(text)
    t = text.lower()
    t = URL_RE.sub(" urltoken ", t)
    t = EMAIL_RE.sub(" emailtoken ", t)
    t = MONEY_RE.sub(" moneytoken ", t)
    t = PHONE_RE.sub(" phonetoken ", t)
    t = NUM_RE.sub(" numtoken ", t)
    t = NONWORD_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def preprocess_raw(text: str) -> str:
    """Same pipeline without the normalizer (the undefended baseline for E4)."""
    return preprocess(text, use_normalizer=False)
