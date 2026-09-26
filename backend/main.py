"""ScamShield API.

    uvicorn backend.main:app --reload --port 8000

Endpoints
    POST /api/analyze   {"text": "...", "sender": "VM-SBIINB"} -> case report
    GET  /api/health    model status
    GET  /api/research  experiment results (results/research.json)
    GET  /api/dataset   dataset summary + Indian specimens

Privacy: submitted messages are processed in memory and never logged or
stored. Links inside them are never fetched.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.pipeline import Analyzer, Dataset, ModelsMissing, research

log = logging.getLogger("scamshield")

app = FastAPI(title="ScamShield API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_state: dict = {}
_dataset = Dataset()


def analyzer() -> Analyzer:
    if "analyzer" not in _state:
        try:
            _state["analyzer"] = Analyzer()
        except ModelsMissing as e:
            log.warning(str(e))
            raise HTTPException(503, "Models are not trained yet. Run: python -m ml.train") from e
    return _state["analyzer"]


class AnalyzeIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    sender: str = Field("", max_length=40)


@app.post("/api/analyze")
def analyze(body: AnalyzeIn) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Message is empty")
    return analyzer().analyze(text, body.sender.strip())


@app.get("/api/health")
def health() -> dict:
    try:
        a = analyzer()
        return {"status": "ok", "models": a.meta}
    except HTTPException:
        return {"status": "no_models", "models": None}


@app.get("/api/research")
def get_research() -> dict:
    r = research()
    if r is None:
        raise HTTPException(404, "No results yet. Run: python -m ml.train && python -m ml.evaluate")
    return r


@app.get("/api/dataset")
def get_dataset() -> dict:
    d = _dataset.payload
    if d is None:
        raise HTTPException(404, "No processed dataset yet. Run: python -m ml.build_dataset")
    return d
