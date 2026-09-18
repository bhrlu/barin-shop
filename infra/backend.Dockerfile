# syntax=docker/dockerfile:1
# SÂNDÉ backend — FastAPI + uvicorn (dev-friendly: --reload + bind mount).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# curl is used for the container healthcheck (/health)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached layer), then the app itself.
COPY backend/pyproject.toml ./pyproject.toml
RUN pip install .

COPY backend/app ./app

EXPOSE 8000

# Dev default: auto-reload. When you bind-mount the source (see compose),
# the local ./app directory shadows the pip-installed copy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
