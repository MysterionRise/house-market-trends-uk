.PHONY: install resolve fetch stage validate docs test lint format

PY_DIRS := core pipeline

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
