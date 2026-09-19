# Enterprise HR Compliance Bot (RAG) - container image
# Build:  docker build -t hr-compliance-bot .
# Run:    docker run --rm -p 8000:8000 --env-file .env hr-compliance-bot

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and the SAMPLE documents.
COPY app ./app
COPY scripts ./scripts
COPY data/documents ./data/documents

# Persistent vector store directory + non-root user.
RUN mkdir -p /app/data/chroma_db && useradd -m appuser && chown -R appuser:appuser /app/data
USER appuser

EXPOSE 8000

# Index the sample documents on startup (ignore failure so the API still
# serves /health and /documents), then launch the API.
#MD ["sh", "-c", "python scripts/ingest.py || echo '[warn] ingestion failed - starting API anyway'; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
CMD ["sh", "-c", "python scripts/init_db.py && (python scripts/ingest.py || echo '[warn] ingestion failed - starting API anyway'); exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]