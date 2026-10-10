# The learning website. Build from the repo root, so the lesson assets come in:
#   docker build -f site/Dockerfile -t learning-site .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv

WORKDIR /app
COPY site/pyproject.toml site/uv.lock ./site/
RUN cd site && uv sync --frozen --no-dev --no-install-project
COPY site/learnsite ./site/learnsite
COPY assets/base ./assets/base
RUN cd site && uv sync --frozen --no-dev

ENV PATH="/app/site/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LEARN_BASE_ASSETS=/app/assets/base

WORKDIR /app/site
EXPOSE 8080
CMD ["uvicorn", "learnsite.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
