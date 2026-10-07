.PHONY: up down up-demo data-pack data-unpack install resolve fetch stage indicators score tiles build-data validate demo-data docs schemas api web-install web web-test e2e dev test lint format

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
	uv run lix validate serve

# Small dataset (Leeds + Brighton) cut from a full build, for CI end-to-end tests
demo-data:
	uv run lix demo-data --lad E08000035 E06000043 --out fixtures/demo

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

# Docker: everything at http://localhost:3000 (data from ./data/serve)
up:
	docker compose up -d --build --wait

# The same on the small committed demo dataset (Leeds + Brighton)
up-demo:
	LIX_SERVE_DIR=./fixtures/demo/serve docker compose up -d --build --wait

down:
	docker compose down

# Snapshot of a built data/serve (about 120 MB) so another machine can skip the 14 GB
# raw download: `make data-pack`, copy dist/lix-serve-*.tar.gz, then
# `make data-unpack PACK=dist/lix-serve-YYYYMMDD.tar.gz`
PACK_NAME := lix-serve-$(shell date +%Y%m%d)
data-pack:
	uv run lix validate serve
	mkdir -p dist
	tar -C data -czf dist/$(PACK_NAME).tar.gz serve
	cd dist && shasum -a 256 $(PACK_NAME).tar.gz > $(PACK_NAME).tar.gz.sha256
	@echo "Wrote dist/$(PACK_NAME).tar.gz"

data-unpack:
	@test -n "$(PACK)" || (echo "Usage: make data-unpack PACK=dist/lix-serve-YYYYMMDD.tar.gz" && exit 1)
	cd $(dir $(PACK)) && shasum -a 256 -c $(notdir $(PACK)).sha256
	mkdir -p data
	tar -C data -xzf $(PACK)
	uv run lix validate serve

