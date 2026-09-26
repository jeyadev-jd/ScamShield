"""Explanations for one message (contribution C3).

    token_contributions  leave-one-word-out occlusion: how much the scam
                         probability drops when each word is removed.
                         Model-agnostic, so it works for NB, LR, SVM and BERT.
    kill_chain           hook / urgency / credibility / ask phrases
    advice               category-specific next steps

``report(text, ...)`` assembles the full API response (see project plan §9).
"""
from __future__ import annotations

import re

import numpy as np

from ml.category import rule_category
from ml.normalizer import normalize
from ml.url_forensics import BRANDS, analyze_text

# ---------------------------------------------------------------- tokens

TOKEN_RE = re.compile(r"\S+")


def scam_proba(model, texts: list[str]) -> np.ndarray:
    """P(not ham) for a binary (0/1) or multi-class (ham/spam/smishing) model."""
    p = model.predict_proba(texts)
    classes = [str(c) for c in model.classes_]
    ham = classes.index("0") if "0" in classes else classes.index("ham")
    return 1.0 - p[:, ham]


def scam_margin(model, texts: list[str]) -> np.ndarray | None:
    """Uncalibrated scam-vs-ham margin, averaged over the calibration folds.

    Calibration squashes scores through a sigmoid fitted on training folds;
    when the base model is very confident (NB often returns exactly 1.0), every
    input maps to the same calibrated value and occlusion sees no change. The
    raw margin (decision function, or joint log-likelihood difference for NB)
    does not saturate. Returns None for models without this structure.
    """
    try:
        vec, clf = model.named_steps["vec"], model.named_steps["clf"]
        folds = clf.calibrated_classifiers_
    except (AttributeError, KeyError):
        return None
    classes = [str(c) for c in clf.classes_]
    if len(classes) != 2:
        return None
    X = vec.transform(texts)
    scores = []
    for cc in folds:
        est = cc.estimator
        if hasattr(est, "decision_function"):
            scores.append(est.decision_function(X))
        elif hasattr(est, "predict_joint_log_proba"):
            j = est.predict_joint_log_proba(X)
            scores.append(j[:, 1] - j[:, 0])
        else:
            return None
    return np.mean(scores, axis=0)


def token_contributions(model, text: str, max_tokens: int = 80) -> list[dict]:
    """Occlusion: weight(token) = logit P(scam | text) - logit P(scam | text without token).

    Positive weight = the word pushes toward scam; negative = toward legitimate.
    Tokens are the original, un-normalized words, so the UI can shade exactly
    what the user pasted.
    """
    spans = [(m.start(), m.end()) for m in TOKEN_RE.finditer(text)][:max_tokens]
    if not spans:
        return []
    variants = [text] + [text[:a] + text[b:] for a, b in spans]
    score = scam_margin(model, variants)
    if score is None:
        # Log-odds, not probability: at P=0.99 removing one word barely moves the
        # probability even when it carries real evidence (saturation).
        p = np.clip(scam_proba(model, variants), 1e-9, 1 - 1e-9)
        score = np.log(p / (1 - p))
    return [{"token": text[a:b], "start": a, "end": b, "weight": round(float(score[0] - score[i + 1]), 4)}
            for i, (a, b) in enumerate(spans)]


# ---------------------------------------------------------------- kill-chain

STAGES = {
    "hook": r"(kyc|account|a/c|card|parcel|courier|prize|lottery|won|job|task|refund|cashback|electricity|bill|aadhaar|pan|narcotics|order)"
            r"[^.!?]{0,30}?(expired?|blocked|suspended|held|pending|won|selected|approved|disconnected|registered|failed|due)",
    "urgency": r"\b(urgent(ly)?|immediately|right now|now|today|tonight|within \d+ ?(hours?|hrs?|mins?|minutes|days?)|last (chance|day)|final (notice|warning)|expires? (today|soon)|asap)\b",
    "ask": r"\b(verify|update|share|click|call|pay|send|download|install|scan|accept|reply|confirm|login|log in|submit|contact)\b[^.!?]{0,25}",
}
STAGE_RX = {k: re.compile(v, re.I) for k, v in STAGES.items()}
AUTHORITY_RX = re.compile(r"\b(rbi|cbi|police|court|income ?tax|customs|trai|government|govt|cyber ?cell|narcotics)\b", re.I)


def kill_chain(text: str) -> dict[str, str]:
    t = normalize(text).text
    chain = {}
    for stage in ("hook", "urgency"):
        m = STAGE_RX[stage].search(t)
        if m:
            chain[stage] = m.group().strip()
    brand = next((b for b in BRANDS if len(b) >= 3 and re.search(rf"\b{b}\b", t, re.I)), None)
    auth = AUTHORITY_RX.search(t)
    if auth or brand:
        chain["credibility"] = (auth.group() if auth else brand).upper() if (auth or brand) else ""
    m = STAGE_RX["ask"].search(t)
    if m:
        chain["ask"] = m.group().strip()
    return chain


# ---------------------------------------------------------------- advice

ADVICE = {
    "otp_account": ["Never share an OTP, PIN or CVV. No bank employee will ever ask for one."],
    "kyc": ["Banks do not update KYC through SMS links. Visit the branch or use the official app."],
    "upi_payment": ["You never need to enter your UPI PIN or accept a collect request to receive money."],
    "prize_lottery": ["You cannot win a lottery you never entered. Never pay a fee to claim a prize."],
    "job_task": ["Real employers never ask you to pay or deposit money to earn."],
    "courier": ["Couriers and India Post do not collect customs fees through SMS links."],
    "digital_arrest": ["Police, CBI and courts never arrest or question anyone over a video call. Hang up."],
    "phishing": ["Do not enter details on a site you reached from an SMS link. Type the official address yourself."],
    "promotional": ["Likely marketing. Unsubscribe via the official app, or register on DND (dial 1909)."],
}


def advice(category: str, risk_level: str, brand: str | None = None) -> list[str]:
    if risk_level == "LOW":
        return ["No strong scam signals found.", "If unsure, check through the official app instead of replying."]
    out = ["Do not open the link, call back, or reply to the sender."]
    out += ADVICE.get(category, [])
    if brand and brand in BRANDS and BRANDS[brand]:
        out.append(f"Check with {brand.upper()} directly through {BRANDS[brand]} or the number on your card.")
    out.append("Report it at cybercrime.gov.in or call 1930. Forward the SMS to 7726 (spam).")
    return out


# ---------------------------------------------------------------- full report

def risk_level(score: int) -> str:
    # LOW ends at 50, where the calibrated classifier switches from ham to scam,
    # so a "legitimate" label never comes with a MEDIUM risk.
    return "HIGH" if score >= 70 else "MEDIUM" if score >= 50 else "LOW"


def report(text: str, binary_model, multi_model=None, category_model=None, risk_model=None,
           sender: str = "", uncertain_band: tuple[float, float] = (0.35, 0.65)) -> dict:
    """Assemble the API response for one message."""
    norm = normalize(text)
    p_scam = float(scam_proba(binary_model, [text])[0])

    label = "smishing" if p_scam >= 0.5 else "ham"
    # Confidence in the label that is shown, not in "is it ham?".
    confidence = 1 - p_scam if label == "ham" else p_scam
    if multi_model is not None and p_scam >= 0.5:
        probs = multi_model.predict_proba([text])[0]
        cls = [str(c) for c in multi_model.classes_]
        ranked = sorted((c for c in cls if c != "ham"), key=lambda c: -probs[cls.index(c)])
        label = ranked[0]
        # P(label) = P(not ham) [calibrated binary] x P(label | not ham) [multi-class].
        non_ham = sum(probs[cls.index(c)] for c in cls if c != "ham")
        confidence = p_scam * (probs[cls.index(label)] / non_ham if non_ham > 0 else 1.0)

    # The score is the calibrated classifier probability (the model evaluated in
    # E1-E6). The risk model only supplies indicator weights that explain it;
    # letting it set the score made verdicts contradict the classifier.
    score = int(round(100 * p_scam))
    indicators = risk_model.score(text, p_scam, sender)[1] if risk_model is not None else []
    # Spam (unwanted marketing) is not fraud: cap it below HIGH.
    if label == "spam":
        score = min(score, 69)
    level = risk_level(score)

    is_scam = p_scam >= 0.5
    if category_model is not None:
        category = str(category_model.predict([text])[0]) if is_scam else rule_category(text, False)
    else:
        category = rule_category(text, is_scam)

    urls = analyze_text(text)
    url = max(urls, key=lambda u: u["score"]) if urls else None
    brand = next((b for b in BRANDS if len(b) >= 3 and re.search(rf"\b{b}\b", norm.text, re.I)), None)

    return {
        "label": label,
        "probability": round(confidence, 4),
        "p_scam": round(p_scam, 4),
        "uncertain": uncertain_band[0] < p_scam < uncertain_band[1],
        "risk_score": score,
        "risk_level": level,
        "category": category,
        "normalized_text": norm.text,
        "obfuscation_detected": [{"from": c.original, "to": c.normalized, "kind": c.kind} for c in norm.changes],
        "token_contributions": token_contributions(binary_model, text),
        "url_analysis": url,
        "kill_chain": kill_chain(text) if level != "LOW" else {},
        "indicators": indicators,
        "advice": advice(category, level, brand),
    }
