"""Import public Indian SMS datasets into our schema.

    python -m ml.import_public          # writes data/raw/indian_public.csv

Sources (both MIT licensed, downloaded into data/raw/):
    india_spam/spam_ham_india.csv   Indian Telecom SMS Spam Collection
                                    (github.com/junioralive/india-spam-sms-classification);
                                    labels ham/spam; collection method undocumented.
    scamshield_hf/test.jsonl        sidzzz07/scamshield-dataset (Hugging Face), test split.
                                    Only rows marked real, English/Hinglish, and that look
                                    Indian are used; its own intent labels are noisy and ignored.

Relabeling. The sources only say ham vs spam, and their "spam" mixes marketing
with fraud. Our scheme separates spam (unwanted promotion) from smishing
(fraud). A keyword pass does the split and assigns a category; every row
records how its label was set in ``label_method``:

    source_ham         source said ham, kept as ham / legit
    rule_smishing      source said spam, fraud markers found -> smishing
    rule_spam          source said spam, no fraud markers    -> spam / promotional

These labels are heuristic. Spot-check a sample before reporting results
(``--sample 30`` prints one) and state the method in the report.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from ml.category import rule_category

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = RAW / "indian_public.csv"

# Fraud markers: a request for secrets or money under a pretext, fake prizes,
# investment / task scams, threats. Plain offers and recharges stay "spam".
FRAUD = re.compile(
    r"\b(kyc|re-?kyc|blocked|block(ed)? today|suspend\w*|deactivat\w*|verify|otp|cvv|pin\b|aadhaar|aadhar|pan card"
    r"|lottery|lucky draw|winner|won\b|jackpot|claim (your|the) (prize|reward|amount)"
    r"|guaranteed (return|profit)s?|\d+ ?% (weekly|daily|monthly) (return|profit)|stock (tips|market expert)|trading (group|tips)"
    r"|professor|vip group|part[- ]time|work from home|earn (rs|₹|\d)|daily (income|salary)|telegram|task"
    r"|customs|parcel (is )?(held|on hold)|arrest|cbi|narcotics|police"
    r"|electricity (will be )?disconnect\w*|disconnect\w* (tonight|today)|refund (is )?(pending|approved)"
    r"|(?<!nil )(?<!zero )(?<!no )processing fee|advance fee|registration fee|security deposit"
    r"|points? worth .{0,20}expir\w*|redeem (your )?(reward )?points?"
    r"|dear (customer|user),? your (account|a/c|card) (is|has been|will be))\b",
    re.I,
)
INDIAN = re.compile(
    r"(₹|\brs\.?\s?\d|\binr\b|\blakh|\bcrore|\bupi\b|\bpaytm|phonepe|gpay|google pay|\bkyc\b|aadhaar|aadhar|\bpan\b"
    r"|\bsbi\b|hdfc|icici|axis|kotak|\bpnb\b|yono|airtel|\bjio\b|\bvi\b|vodafone|\bidea\b|bsnl|flipkart|amazon\.in"
    r"|myntra|swiggy|zomato|irctc|india|mumbai|delhi|bengaluru|bangalore|chennai|kolkata|hyderabad)",
    re.I,
)


# Investment-scam group chatter that India Spam labels "ham" (WhatsApp stock
# "professor" groups). Overridden to smishing and recorded as such.
INVEST_SCAM = re.compile(
    r"\b(professor|recommend(ed)? (\w+ ){0,3}stocks?|strong stocks?|vip (group|member)|stock (group|analysis) group"
    r"|add more funds|guaranteed (return|profit)s?|trading (account|platform) (link|app)|join (our|the) (stock|trading))\b",
    re.I,
)


def fix_mojibake(t: str) -> str:
    """Repair UTF-8 text that was decoded as Latin-1 / cp1252 (possibly twice)."""
    for _ in range(2):
        if not re.search("[ÃÂâ€]", t):
            break
        fixed = None
        for enc in ("cp1252", "latin-1"):
            try:
                fixed = t.encode(enc).decode("utf-8")
                break
            except (UnicodeError, LookupError):
                continue
        if fixed is None:
            break
        t = fixed
    return re.sub(r"[ÃÂ][\x80-\xbf]?|â€\S?|�", "", t)


def relabel(text: str, source_label: str) -> tuple[str, str, str]:
    """-> (label, category, label_method)"""
    if source_label == "ham":
        if INVEST_SCAM.search(text):
            return "smishing", "job_task", "rule_override_ham"
        return "ham", "legit", "source_ham"
    if FRAUD.search(text):
        cat = rule_category(text, True)
        return "smishing", ("phishing" if cat in ("legit", "promotional") else cat), "rule_smishing"
    return "spam", "promotional", "rule_spam"


def load_india_spam() -> pd.DataFrame:
    f = RAW / "india_spam" / "spam_ham_india.csv"
    d = pd.read_csv(f, encoding="utf-8", encoding_errors="replace")
    d = d.rename(columns={"Msg": "text", "Label": "src_label"})
    d["src_label"] = d["src_label"].str.strip().str.lower()
    d["source"] = "india_spam_github"
    return d[["text", "src_label", "source"]]


def load_scamshield() -> pd.DataFrame:
    files = sorted((RAW / "scamshield_hf").glob("*.jsonl"))  # test / val / train, whichever are present
    if not files:
        raise FileNotFoundError(RAW / "scamshield_hf")
    rows = [json.loads(l) for f in files for l in f.open(encoding="utf-8")]
    d = pd.DataFrame(rows)
    keep = (
        d["split_group"].str.startswith("real_")
        & d["language"].isin(["English", "Hinglish"])
        & ~d["source_dataset"].isin(["UCI_SMS_Spam", "Indian_Telecom_SMS", "ysangam/Indian_Cyber_Scam_Hinglish"])
        & d["text"].map(lambda t: bool(INDIAN.search(t)))
    )
    d = d[keep].copy()
    d["src_label"] = d["is_scam"].map(lambda v: "spam" if v in (1, True, "1", "true", "True") else "ham")
    d["source"] = "scamshield_hf:" + d["source_dataset"].str.lower()
    return d[["text", "src_label", "source"]]


def build() -> pd.DataFrame:
    parts = []
    for loader in (load_india_spam, load_scamshield):
        try:
            parts.append(loader())
        except FileNotFoundError as e:
            print(f"skip: {e}")
    d = pd.concat(parts, ignore_index=True)
    # pandas 3 keeps NaN through astype(str); blank rows are dropped by the length filter below.
    d["text"] = d["text"].fillna("").astype(str).map(fix_mojibake).str.replace(r"\s+", " ", regex=True).str.strip()
    d = d[d["text"].str.len() >= 15]
    lab = d.apply(lambda r: relabel(r["text"], r["src_label"]), axis=1, result_type="expand")
    d[["label", "category", "label_method"]] = lab
    d["is_synthetic"] = 0
    return d.drop_duplicates("text")[["text", "label", "category", "source", "is_synthetic", "label_method"]]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", type=int, default=0, help="print N random rows for manual spot-checking")
    a = ap.parse_args()
    d = build()
    d.to_csv(OUT, index=False, encoding="utf-8")
    print(f"wrote {len(d)} rows to {OUT}")
    print(pd.crosstab(d["source"], d["label"]).to_string())
    print(d["category"].value_counts().to_string())
    if a.sample:
        for _, r in d.sample(a.sample, random_state=3).iterrows():
            print(f"[{r.label:<8} {r.category:<14} {r.label_method:<13}] {r.text[:110]}")


if __name__ == "__main__":
    main()
