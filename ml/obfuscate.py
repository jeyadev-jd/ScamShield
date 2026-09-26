"""Obfuscation attack generator (attack side of contribution C2).

Creates adversarial copies of test messages using the tricks scammers use to
slip past keyword and word-level filters. Used for experiments E4 and E7:

    python -m ml.obfuscate data/processed/test_indian.csv data/processed/test_obf.csv

Attacks:
    leet        o->0, i->1, e->3, a->@, s->$     "verify otp" -> "v3rify 0tp"
    homoglyph   Latin -> Cyrillic/Greek look-alike "pay" -> "раy"
    spacing     letters split by spaces          "verify" -> "v e r i f y"
    dots        letters split by dots            "bank" -> "b.a.n.k"
    zero_width  invisible U+200B inside words    "otp" -> "o​tp"
    mixed       one random attack per word

Only scam-bearing keywords are attacked by default (that is what scammers
do); ``--rate`` also hits a fraction of the other words. URLs, numbers and
e-mail addresses are left intact so link forensics still has input.
Everything is seeded so the benchmark is reproducible.
"""
from __future__ import annotations

import argparse
import random
import sys
import re
from pathlib import Path

from ml.normalizer import URL_RE, EMAIL_RE

ATTACKS = ("leet", "homoglyph", "spacing", "dots", "zero_width", "mixed")

# Words scammers actually disguise. Kept lower-case.
KEYWORDS = {
    "otp", "pin", "cvv", "password", "verify", "verification", "kyc", "update", "bank", "account",
    "blocked", "suspended", "expired", "urgent", "immediately", "click", "link", "pay", "payment",
    "upi", "refund", "prize", "winner", "won", "lottery", "cash", "cashback", "reward", "free",
    "offer", "claim", "loan", "credit", "debit", "card", "customs", "parcel", "courier", "arrest",
    "police", "cbi", "aadhaar", "pan", "job", "income", "earn", "task", "telegram", "whatsapp",
    "sbi", "hdfc", "icici", "axis", "paytm", "phonepe", "amazon", "call", "txt", "text", "reply",
    "mobile", "guaranteed", "selected", "congratulations", "congrats", "gift", "voucher",
}

# "l"->"1" is left out on purpose: it collides with "i"->"1" and cannot be
# inverted without a dictionary. Char n-grams (E7) are the answer to that case.
LEET_MAP = {"o": "0", "i": "1", "e": "3", "a": "@", "s": "$", "t": "7"}
HOMOGLYPH_MAP = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "y": "у", "i": "і", "s": "ѕ",
                 "A": "А", "B": "В", "E": "Е", "K": "К", "M": "М", "O": "О", "P": "Р", "C": "С", "T": "Т"}

WORD_RE = re.compile(r"[A-Za-z]{2,}")


def _leet(w: str, rng: random.Random) -> str:
    idx = [i for i, ch in enumerate(w) if ch.lower() in LEET_MAP]
    if not idx:
        return w
    k = max(1, round(len(idx) * rng.uniform(0.4, 1.0)))
    chosen = set(rng.sample(idx, k))
    return "".join(LEET_MAP[ch.lower()] if i in chosen else ch for i, ch in enumerate(w))


def _homoglyph(w: str, rng: random.Random) -> str:
    idx = [i for i, ch in enumerate(w) if ch in HOMOGLYPH_MAP]
    if not idx:
        return w
    chosen = set(rng.sample(idx, max(1, len(idx) // 2)))
    return "".join(HOMOGLYPH_MAP[ch] if i in chosen else ch for i, ch in enumerate(w))


def _spacing(w: str, rng: random.Random) -> str:
    # Padded with extra spaces so two spaced words in a row ("b a n k  a c c o u n t")
    # stay separable. Without the padding, word boundaries are lost for good.
    return f" {' '.join(w)} " if len(w) >= 3 else w


def _dots(w: str, rng: random.Random) -> str:
    return ".".join(w) if len(w) >= 3 else w


def _zero_width(w: str, rng: random.Random) -> str:
    if len(w) < 2:
        return w
    i = rng.randrange(1, len(w))
    return w[:i] + "​" + w[i:]


FUNCS = {"leet": _leet, "homoglyph": _homoglyph, "spacing": _spacing, "dots": _dots, "zero_width": _zero_width}


def obfuscate(text: str, attack: str = "mixed", rate: float = 0.0, seed: int | None = 0) -> str:
    """Obfuscate keywords in ``text`` (plus a ``rate`` fraction of other words)."""
    if attack not in ATTACKS:
        raise ValueError(f"unknown attack {attack!r}; choose from {ATTACKS}")
    rng = random.Random(seed)

    protected = [(m.start(), m.end()) for r in (URL_RE, EMAIL_RE) for m in r.finditer(text)]

    def repl(m: re.Match) -> str:
        if any(a <= m.start() < b for a, b in protected):
            return m.group()
        w = m.group()
        if w.lower() not in KEYWORDS and rng.random() >= rate:
            return w
        name = rng.choice(list(FUNCS)) if attack == "mixed" else attack
        return FUNCS[name](w, rng)

    return WORD_RE.sub(repl, text)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    import pandas as pd

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path, help="CSV with a 'text' column")
    ap.add_argument("dst", type=Path)
    ap.add_argument("--attacks", nargs="+", default=list(ATTACKS), choices=ATTACKS)
    ap.add_argument("--rate", type=float, default=0.0, help="fraction of non-keyword words to also attack")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = pd.read_csv(args.src)
    frames = []
    for attack in args.attacks:
        out = df.copy()
        out["text_clean"] = df["text"]
        out["text"] = [obfuscate(t, attack, args.rate, seed=args.seed + i) for i, t in enumerate(df["text"])]
        out["attack"] = attack
        frames.append(out)
    res = pd.concat(frames, ignore_index=True)
    args.dst.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(args.dst, index=False, encoding="utf-8")
    changed = (res["text"] != res["text_clean"]).mean()
    print(f"wrote {len(res)} rows ({len(df)} x {len(args.attacks)} attacks) to {args.dst}; {changed:.0%} of rows altered")


if __name__ == "__main__":
    main()
