.PHONY: install resolve fetch stage indicators score tiles build-data validate docs schemas api web-install web web-test e2e dev test lint format

PY_DIRS := core pipeline api

install:
	uv sync

# Re-resolve every source to its current upstream file (updates config/datasets.lock.json)
resolve:
	uv run lix resolve --all

# Download every dataset pinned in the lockfile into data/raw/ (Price Paid alone is 5.5 GB)
fetch:
	uv run lix fetch --all

# Stage every downloaded dataset to data/staged/*.parquet; nspl runs first (price_paid needs it)
stage:
	uv run lix stage --all

# Build data/indicators/long.parquet from the staged tables
indicators:
	uv run lix indicators

# Write data/serve/ (features, browser scores, manifest) and the QA report
score:
	uv run lix score

# Vector map tiles (PMTiles) for the browser
tiles:
	uv run lix tiles

# Everything from download to scores and tiles
build-data: fetch stage indicators score tiles validate

# JSON Schema of the API models (contracts/schemas.json) for the front end's types
schemas:
	uv run python -m lix_api.schemas
	cd web && npm run types

# Run the API on :8000 (set LIX_MODEL, e.g. anthropic:claude-opus-5-5, or "test")
api:
	LIX_RELOAD=1 uv run lix-api

# Front end (Node 24, see .nvmrc) on :3000
web-install:
	cd web && npm ci

web:
	cd web && npm run dev

# Typecheck, lint and unit tests (incl. the scoring parity test against Python)
web-test:
	cd web && npm run typecheck && npm run lint && npm test

# Browser tests against the local build with the scripted assistant (needs make score tiles)
e2e:
	cd web && npx playwright test

# API (scripted assistant unless LIX_MODEL is set) and front end together
dev:
	(LIX_MODEL=$${LIX_MODEL:-test} uv run lix-api &) && cd web && npm run dev

validate:
	uv run lix validate geo

# Regenerate docs/data-sources.md and ATTRIBUTION.md from config/datasets.yaml
docs:
	uv run lix docs

test:
	uv run pytest

lint:
	uv run ruff check $(PY_DIRS)
	uv run ruff format --check $(PY_DIRS)

format:
	uv run ruff format $(PY_DIRS)
	uv run ruff check --fix $(PY_DIRS)
