# Data pipeline (`lix`): fetch, stage, score and build tiles. GDAL ships inside the
# pyogrio wheel (with the PMTiles driver), so no system GDAL or tippecanoe is needed.
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock ./
COPY core/pyproject.toml core/
COPY pipeline/pyproject.toml pipeline/
COPY api/pyproject.toml api/
RUN uv sync --frozen --no-dev --package lix-pipeline --no-install-workspace

COPY core core
COPY pipeline pipeline
RUN uv sync --frozen --no-dev --package lix-pipeline

# config/ (registry, lockfile, indicators, weights) and data/ are mounted from the host
ENV LIX_ROOT=/app LIX_DATA_DIR=/data PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["lix"]
CMD ["--help"]
