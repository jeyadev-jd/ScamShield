"""Smoke test: the full training pipeline runs end to end on a tiny synthetic
set, produces sane metrics and a loadable model. Not a quality benchmark."""
import argparse

import joblib
import numpy as np
import pytest

import ml.train as T
from ml.metrics import expected_calibration_error

def _args(**kw):
    base = dict(exp=["e1", "e2", "e3"], models=["nb", "lr", "svm"], no_char=False, no_features=False,
                no_normalizer=False, save=True, tag="")
    return argparse.Namespace(**{**base, **kw})


def test_all_experiments_run(data_dir):
    rows = T.run(_args())
    exps = {(r["exp"], r["model"], r["task"], r["test"]) for r in rows}
    assert ("E1", "lr", "binary", "test_uci") in exps
    assert ("E2", "svm", "binary", "test_indian") in exps
    assert ("E3", "nb", "multi", "test_indian") in exps
    for r in rows:
        assert 0 <= r["accuracy"] <= 1 and 0 <= r["ece"] <= 1
    # Easy synthetic data: the linear models should separate it almost perfectly.
    e1 = [r for r in rows if r["exp"] == "E1" and r["model"] in ("lr", "svm")]
    assert all(r["f1_macro"] > 0.9 for r in e1)


def test_saved_model_predicts(data_dir):
    T.run(_args(exp=["e3"], models=["lr"]))
    model = joblib.load(data_dir / "models" / "scam_multi.joblib")
    p = model.predict_proba(["URGENT verify your 0TP at sbi-kyc.xyz now", "reached home, see you tomorrow"])
    assert p.shape == (2, 3)
    assert np.allclose(p.sum(axis=1), 1)
    classes = list(model.classes_)
    assert p[0, classes.index("smishing")] > p[1, classes.index("smishing")]


def test_ablation_flags_build(data_dir):
    rows = T.run(_args(exp=["e1"], models=["nb"], no_char=True, no_features=True, no_normalizer=True))
    assert rows and rows[0]["char"] is False and rows[0]["normalizer"] is False


def test_ece_perfect_and_bad():
    y = np.array([0, 1, 1, 0])
    perfect = np.array([[1, 0], [0, 1], [0, 1], [1, 0]], dtype=float)
    assert expected_calibration_error(y, perfect, [0, 1]) == 0
    overconfident = np.array([[0.99, 0.01]] * 4)
    assert expected_calibration_error(y, overconfident, [0, 1]) == pytest.approx(0.49, abs=0.01)
