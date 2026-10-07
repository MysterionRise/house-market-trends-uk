.PHONY: install download process test lint format

install:
	uv sync

download:
	uv run python -m src.download

# Cleans every dataset that has been downloaded; nspl runs first (price_paid needs it)
process:
	uv run python -m src.clean --all

test:
	uv run pytest tests/

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/
