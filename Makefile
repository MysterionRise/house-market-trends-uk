.PHONY: install download process test lint

install:
	uv sync

download:
	uv run python -m src.download

process:
	uv run python -m src.clean && uv run python -m src.geocode

test:
	uv run pytest tests/

lint:
	uv run ruff check src/ tests/
