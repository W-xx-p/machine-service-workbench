# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements-docling.txt requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 10 -r requirements.txt
# Docling depends on PyTorch. This service only performs CPU-side document
# parsing, so prefer the official CPU wheels instead of pulling CUDA runtimes.
# The cache mount, extended timeout and retries make first-time builds resilient
# to the large CPU-only PyTorch download without bloating the final image layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 600 --retries 10 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements-docling.txt

COPY app ./app
COPY data ./seed_data
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker-entrypoint.sh ./
RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/data/uploads && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
