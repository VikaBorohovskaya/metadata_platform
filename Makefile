.PHONY: install seed harvest report check test fmt

install:
	uv sync --extra dev

seed:
	uv run metadata-platform seed

harvest:
	uv run metadata-platform harvest

report:
	uv run metadata-platform report --output out

check:
	uv run metadata-platform check

test:
	uv run pytest
