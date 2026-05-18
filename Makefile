.PHONY: install dev test lint format verify smoke compose-up compose-down clean

UV ?= uv

install:
	$(UV) sync --extra dev

dev:
	$(UV) run uvicorn aquadx.main:app --reload --host 0.0.0.0 --port 8000

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests
	$(UV) run mypy src

format:
	$(UV) run ruff format src tests
	$(UV) run ruff check --fix src tests

verify:
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests
	$(UV) run mypy src
	$(UV) run pytest --cov=src/aquadx --cov-fail-under=80

smoke:
	docker compose up -d --build
	./scripts/smoke.sh
	docker compose down

compose-up:
	docker compose up --build

compose-down:
	docker compose down

clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
