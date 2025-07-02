.PHONY: all install dev test lint format clean help validate benchmark security

all: dev lint test

help:
	@echo "MVP Policy Decision Backend - Available targets:"
	@echo "Run 'make <target>' - Use 'all' for full setup"
	@echo "Full target list: install dev test lint format clean validate benchmark security"

install:
	uv sync

dev:
	uv sync --dev
	uv run pre-commit install

test:
	uv run pytest

test-cov:
	uv run pytest --cov=src --cov-report=html --cov-report=term

lint:
	uv run flake8 src tests
	uv run mypy src

format:
	uv run black src tests
	uv run isort src tests

format-check:
	uv run black --check src tests
	uv run isort --check-only src tests

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

validate: validate-pydantic validate-performance validate-master-ruleset
	@echo "✅ All validation checks passed!"

validate-pydantic:
	@echo "🔍 Validating Pydantic model compliance..."
	@bash scripts/validate-pydantic-compliance.sh

validate-performance:
	@echo "⚡ Validating performance gates..."
	@bash scripts/validate-performance-gates.sh

validate-master-ruleset:
	@echo "📋 Validating master ruleset compliance..."
	@bash scripts/validate-master-ruleset.sh

benchmark:
	@echo "🚀 Running performance benchmarks..."
	@bash scripts/run_benchmarks.sh

security:
	@echo "🔒 Running security checks..."
	uv run bandit -r src/
	uv run safety check
	uv run pip-audit

check-db:
	@echo "🗄️ Checking database connectivity..."
	uv run python scripts/check_db.py

check-redis:
	@echo "🔴 Checking Redis connectivity..."
	uv run python scripts/check_redis.py
