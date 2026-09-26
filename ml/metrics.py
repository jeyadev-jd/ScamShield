"""Evaluation metrics shared by train.py and evaluate.py."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)


def expected_calibration_error(y_true, proba, classes, n_bins: int = 10) -> float:
    """ECE on the top-class confidence (Guo et al., 2017)."""
    y_true = np.asarray(y_true)
    conf = proba.max(axis=1)
    pred = np.asarray(classes)[proba.argmax(axis=1)]
    correct = (pred == y_true).astype(float)
    edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def reliability_bins(y_true, proba, classes, n_bins: int = 10) -> list[dict]:
    """Per-bin confidence vs accuracy, for the reliability diagram (E6)."""
    y_true = np.asarray(y_true)
    conf = proba.max(axis=1)
    correct = (np.asarray(classes)[proba.argmax(axis=1)] == y_true)
    out = []
    edges = np.linspace(0, 1, n_bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        out.append({"lo": float(lo), "hi": float(hi), "n": int(m.sum()),
                    "confidence": float(conf[m].mean()) if m.any() else None,
                    "accuracy": float(correct[m].mean()) if m.any() else None})
    return out


def evaluate(model, texts, y_true) -> dict:
    y_true = np.asarray(y_true)
    classes = list(model.classes_)
    proba = model.predict_proba(texts)
    pred = np.asarray(classes)[proba.argmax(axis=1)]
    labels = sorted(set(classes) | set(y_true.tolist()), key=str)
    present = sorted(set(y_true.tolist()), key=str)

    m = {
        "n": int(len(y_true)),
        "accuracy": accuracy_score(y_true, pred),
        "precision_macro": precision_score(y_true, pred, labels=present, average="macro", zero_division=0),
        "recall_macro": recall_score(y_true, pred, labels=present, average="macro", zero_division=0),
        "f1_macro": f1_score(y_true, pred, labels=present, average="macro", zero_division=0),
        "ece": expected_calibration_error(y_true, proba, classes),
        "labels": [str(l) for l in labels],
        "confusion": confusion_matrix(y_true, pred, labels=labels).tolist(),
    }
    # Scam recall = share of non-ham messages flagged as non-ham. The number
    # that matters most here: a missed scam costs more than a false alarm.
    scam_true = np.array([str(v) not in ("0", "ham") for v in y_true])
    scam_pred = np.array([str(v) not in ("0", "ham") for v in pred])
    if scam_true.any():
        m["scam_recall"] = float((scam_pred & scam_true).sum() / scam_true.sum())
    if (~scam_true).any():
        m["false_alarm_rate"] = float((scam_pred & ~scam_true).sum() / (~scam_true).sum())

    try:
        if len(classes) == 2 and len(present) == 2:
            m["roc_auc"] = roc_auc_score(y_true, proba[:, 1])
        elif len(present) > 2 and set(present) <= set(classes):
            cols = [classes.index(c) for c in present]
            p = proba[:, cols] / proba[:, cols].sum(axis=1, keepdims=True)
            m["roc_auc"] = roc_auc_score(y_true, p, multi_class="ovr", labels=present)
    except ValueError:
        pass
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()}
