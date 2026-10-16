ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

# Optional PyPI mirror for servers where pypi.org is slow or blocked (see DEPLOY.md).
ARG PIP_INDEX_URL=

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FORWARDED_ALLOW_IPS=*

RUN useradd --create-home --uid 10001 appuser
COPY requirements.txt .
RUN if [ -n "$PIP_INDEX_URL" ]; then export PIP_INDEX_URL; else unset PIP_INDEX_URL; fi \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .
RUN rm -f projectverse.db
USER appuser
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# --proxy-headers: the API is reachable only through the shared Caddy, which sets X-Forwarded-For.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
