.PHONY: install fetch stage test lint format

PY_DIRS := core pipeline

install:
	uv sync

# Download every dataset in config/datasets.yaml into data/raw/ (Price Paid alone is 5.5 GB)
fetch:
	uv run lix fetch --all

# Stage every downloaded dataset to data/staged/*.parquet; nspl runs first (price_paid needs it)
stage:
	uv run lix stage --all

test:
	uv run pytest

lint:
	uv run ruff check $(PY_DIRS)
	uv run ruff format --check $(PY_DIRS)

format:
	uv run ruff format $(PY_DIRS)
	uv run ruff check --fix $(PY_DIRS)
