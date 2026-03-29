# syntax=docker/dockerfile:1

# === Base image configuration ===
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VENV_PATH=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# === Builder stage ===
FROM base AS builder

WORKDIR /build

COPY requirements.txt ./
RUN python -m venv "$VENV_PATH" \
 && "$VENV_PATH/bin/pip" install --upgrade pip \
 && "$VENV_PATH/bin/pip" install -r requirements.txt


# === Runtime stage ===
FROM base AS runtime

LABEL maintainer="Ali Hassan <alihasanuos@gmail.com>" \
      description="ResMed File Sharing API"

WORKDIR /app

# Copy only what is required at runtime.
COPY --from=builder "$VENV_PATH" "$VENV_PATH"
COPY app/ ./app/

# Create a dedicated non-root user and writable app directories.
RUN groupadd --system --gid 10001 appgroup \
 && useradd --system --uid 10001 --gid appgroup --create-home --home-dir /home/appuser appuser \
 && mkdir -p /app/uploads /app/data \
 && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
