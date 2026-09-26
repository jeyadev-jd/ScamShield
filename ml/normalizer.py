"""Obfuscation normalizer (defense side of contribution C2).

Maps adversarially obfuscated SMS text back to a canonical form before it
reaches the vectorizer:

    "URGENT! Verify y0ur 0TP at $BI"  ->  "URGENT! Verify your OTP at SBI"
    "v e r i f y"                      ->  "verify"
    "b.a.n.k"                          ->  "bank"
    "раy" (Cyrillic р, а)              ->  "pay"

Every rewrite is recorded, so the API can report ``obfuscation_detected`` and
the feature extractor can use the count as ``obfuscation_count``.

Design rules:
- URLs, e-mail addresses, pure numbers (amounts, OTPs, phone numbers) and
  sender IDs are never touched. Only word-like tokens that mix letters with
  look-alike symbols are rewritten.
- Case is preserved where possible; lower-casing is the preprocessor's job.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Look-alike characters from other scripts. NFKC already folds full-width and
# most compatibility forms; these are the confusables it leaves alone.
HOMOGLYPHS: dict[str, str] = {
    # Cyrillic
    "а": "a", "в": "b", "е": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p",
    "с": "c", "т": "t", "у": "y", "х": "x", "ѕ": "s", "і": "i", "ј": "j", "ԁ": "d",
    "ԛ": "q", "ԝ": "w", "ɡ": "g",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "У": "Y", "Х": "X", "Ѕ": "S", "І": "I", "Ј": "J",
    # Greek
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "ι": "i", "κ": "k", "τ": "t", "υ": "u",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M",
    "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
    # Latin look-alikes
    "ı": "i", "ℓ": "l",
}

# "8" is left out: in SMS it is almost always slang ("gr8", "l8r"), not a "b".
LEET: dict[str, str] = {
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
    "@": "a", "$": "s", "!": "i", "|": "l", "€": "e", "£": "l",
}

UNIT_RE = re.compile(
    r"\d+(?:am|pm|gb|mb|kb|g|th|st|nd|rd|x|k|l|lac|lakh|cr|hrs?|mins?|days?|yrs?|km|kg|rs|w|mp|mah)",
    re.IGNORECASE,
)

ZERO_WIDTH = re.compile("[​‌‍⁠﻿­]")

URL_RE = re.compile(
    r"(?:https?://|www\.)\S+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|in|org|net|xyz|top|info|co|ly|me|io|gd|at|live|site|online|club|icu|cc|tk|gov|app)\b(?:/\S*)?",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# Single letters separated by spaces/dashes (3+ letters, "O T P", "v e r i f y")
# or by dots (3+ letters, "b.a.n.k"). Trailing punctuation is allowed.
SPACED_RE = re.compile(r"(?<!\S)(?:[^\W\d_][ \-_*]){2,}[^\W\d_](?=$|[\s.,!?;:])")
DOTTED_RE = re.compile(r"(?<![\w.])(?:[^\W\d_][.·•]){2,}[^\W\d_](?![\w])")

# Leading/trailing punctuation around a token (kept aside, not normalized).
EDGE_RE = re.compile(r"^([\"'(\[{<]*)(.*?)([\"')\]}>.,;:?]*)$", re.DOTALL)


@dataclass
class Change:
    original: str
    normalized: str
    kind: str  # "homoglyph" | "leet" | "spacing" | "dots" | "zero_width" | "unicode"

    def __str__(self) -> str:
        return f"{self.original}→{self.normalized}"


@dataclass
class NormalizeResult:
    text: str
    changes: list[Change] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.changes)


def _is_protected(token: str) -> bool:
    return bool(URL_RE.fullmatch(token) or EMAIL_RE.fullmatch(token))


def _fix_token(core: str) -> tuple[str, str | None]:
    """Normalize one word-like token. Returns (fixed, kind or None)."""
    kind = None
    fixed = core

    if any(ch in HOMOGLYPHS for ch in fixed):
        fixed = "".join(HOMOGLYPHS.get(ch, ch) for ch in fixed)
        kind = "homoglyph"

    letters = sum(ch.isalpha() for ch in fixed)
    leet = sum(ch in LEET for ch in fixed)
    # Only rewrite tokens of 3+ chars made of letters plus look-alike symbols:
    # "0TP", "07P", "b@nk", "v3rify", "$BI". Leaves "2,999", "5000", "A/c",
    # texting slang ("b4", "4u") and number+unit tokens ("7pm", "21st", "10k") alone.
    if (leet and letters >= 1 and letters + leet == len(fixed) and leet <= letters + 1
            and len(fixed) >= 3 and not UNIT_RE.fullmatch(fixed)):
        # Trailing "!" is punctuation, not a leet "i" ("URGENT!!").
        stripped = fixed.rstrip("!")
        tail = fixed[len(stripped):]
        if any(ch in LEET for ch in stripped) and len(stripped) >= 2:
            upper = all(ch.isupper() for ch in stripped if ch.isalpha())
            fixed = "".join(
                (LEET[ch].upper() if upper else LEET[ch]) if ch in LEET else ch for ch in stripped
            ) + tail
            kind = kind or "leet"

    return fixed, kind


def normalize(text: str) -> NormalizeResult:
    """Return canonical text plus the list of rewrites applied."""
    changes: list[Change] = []

    # 1. Zero-width characters and soft hyphens.
    if ZERO_WIDTH.search(text):
        for m in re.finditer(r"\S*[​‌‍⁠﻿­]\S*", text):
            changes.append(Change(m.group(), ZERO_WIDTH.sub("", m.group()), "zero_width"))
        text = ZERO_WIDTH.sub("", text)

    # 2. Unicode compatibility folding (full-width letters, ligatures, circled chars).
    folded = unicodedata.normalize("NFKC", text)
    if folded != text:
        for a, b in zip(text.split(), folded.split()):
            if a != b:
                changes.append(Change(a, b, "unicode"))
        text = folded

    # 3. Letter spacing and dot separation.
    def join_spaced(m: re.Match) -> str:
        joined = re.sub(r"[\s\-_*]", "", m.group())
        changes.append(Change(m.group(), joined, "spacing"))
        return joined

    def join_dotted(m: re.Match) -> str:
        joined = re.sub(r"[.·•]", "", m.group())
        changes.append(Change(m.group(), joined, "dots"))
        return joined

    text = SPACED_RE.sub(join_spaced, text)
    text = DOTTED_RE.sub(join_dotted, text)

    # 4. Token-level homoglyph and leet repair.
    out: list[str] = []
    for part in re.split(r"(\s+)", text):
        if not part or part.isspace() or _is_protected(part):
            out.append(part)
            continue
        lead, core, trail = EDGE_RE.match(part).groups()
        if not core:
            out.append(part)
            continue
        fixed, kind = _fix_token(core)
        if kind:
            changes.append(Change(core, fixed, kind))
        out.append(lead + fixed + trail)

    return NormalizeResult("".join(out), changes)


def normalize_text(text: str) -> str:
    """Convenience wrapper for use inside sklearn pipelines."""
    return normalize(text).text


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    sample = " ".join(sys.argv[1:]) or "URGENT!! Your $BI KYC exp1red. V e r i f y 0TP at sbi-kyc.xyz or pay Rs 2,999"
    r = normalize(sample)
    print(r.text)
    for c in r.changes:
        print(f"  {c.kind:<10} {c}")
