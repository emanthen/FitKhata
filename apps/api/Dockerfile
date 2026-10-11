# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Dev stage: full dev deps, source bind-mounted by docker-compose.dev.yml for hot reload.
FROM base AS dev
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
RUN useradd -m appuser
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Runtime stage: prod image, gunicorn + uvicorn workers, non-root.
FROM base AS runtime
COPY --from=deps /app/.venv /app/.venv
COPY . .
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# Shell form (not exec-form array) so $GUNICORN_WORKERS actually expands --
# without --workers, gunicorn defaults to exactly 1, which was silently
# the case here (H2 hardening: "tune gunicorn workers (2 x CPU + 1)").
# Default of 3 fits staging-1 (2 vCPU); prod-1 (4 vCPU) should set
# GUNICORN_WORKERS=9 in its own env.
CMD gunicorn config.wsgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3}
