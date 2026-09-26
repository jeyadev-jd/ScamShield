import argparse
import json

import pytest
from fastapi.testclient import TestClient

import backend.main as M
import backend.pipeline as P
import ml.train as T


@pytest.fixture
def client(data_dir, monkeypatch):
    T.run(argparse.Namespace(exp=["e3"], models=["lr"], no_char=False, no_features=False,
                             no_normalizer=False, save=True, tag=""))
    monkeypatch.setattr(P, "MODELS_DIR", data_dir / "models")
    monkeypatch.setattr(P, "RESULTS_DIR", data_dir / "results")
    monkeypatch.setattr(P, "DATA_DIR", data_dir)
    monkeypatch.setattr(M, "_state", {"analyzer": P.Analyzer(data_dir / "models")})
    monkeypatch.setattr(M, "_dataset", P.Dataset())
    return TestClient(M.app)


def test_analyze(client):
    r = client.post("/api/analyze", json={"text": "URGENT! Your SBI KYC exp1red. Verify 0TP at sbi-kyc.xyz", "sender": "+91 9876543210"})
    assert r.status_code == 200
    d = r.json()
    assert d["risk_level"] == "HIGH" and d["url_analysis"]["lookalike_of"] == "sbi.co.in"
    assert d["token_contributions"][0]["token"] == "URGENT!"


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "   "}, {"text": "x" * 2001}, {}])
def test_analyze_rejects_bad_input(client, body):
    assert client.post("/api/analyze", json=body).status_code == 422


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_research_404_then_200(client, data_dir):
    assert client.get("/api/research").status_code == 404
    (data_dir / "results" / "research.json").write_text(json.dumps({"metrics": []}))
    assert client.get("/api/research").json() == {"metrics": []}


def test_dataset(client, data_dir):
    assert client.get("/api/dataset").status_code == 404
    (data_dir / "stats.json").write_text(json.dumps({"train": {"n": 1}}))
    M._dataset = P.Dataset()
    d = client.get("/api/dataset").json()
    assert d["stats"]["train"]["n"] == 1 and len(d["specimens"]) == 30


def test_no_models_returns_503(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(M, "_state", {})
    monkeypatch.setattr(P.Analyzer.__init__, "__defaults__", (tmp_path,))
    c = TestClient(M.app)
    assert c.post("/api/analyze", json={"text": "hi"}).status_code == 503
    assert c.get("/api/health").json()["status"] == "no_models"
