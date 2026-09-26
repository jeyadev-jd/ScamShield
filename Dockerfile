# ScamShield API. Works on Render (reads $PORT) and Hugging Face Spaces (port 7860).
# Build after training so backend/models/ and results/ exist:
#   python -m ml.build_dataset && python -m ml.train && python -m ml.evaluate
#   docker build -t scamshield-api . && docker run -p 7860:7860 scamshield-api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860
WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY ml/ ml/
COPY backend/ backend/
COPY results/ results/
# Only the anonymized Indian split and stats are shipped, for the Dataset page.
COPY data/processed/stats.json data/processed/test_indian.csv data/processed/dev_indian.csv data/processed/

RUN useradd -m app && chown -R app /app
USER app
EXPOSE 7860
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
