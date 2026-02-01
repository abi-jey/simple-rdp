# Makefile for simple-rdp development

.PHONY: help install install-dev test test-unit test-e2e coverage coverage-html lint format clean build-rust

PYTHON := poetry run python
PYTEST := poetry run pytest
VENV := .venv

help:
	@echo "Available targets:"
	@echo "  install       - Install project dependencies"
	@echo "  install-dev   - Install dev dependencies + build Rust extension"
	@echo "  test          - Run all unit tests"
	@echo "  test-unit     - Run unit tests only (no e2e)"
	@echo "  test-e2e      - Run e2e tests (requires .env with RDP credentials)"
	@echo "  coverage      - Run tests with coverage report"
	@echo "  coverage-html - Run tests with HTML coverage report"
	@echo "  lint          - Run linters"
	@echo "  format        - Format code"
	@echo "  build-rust    - Build Rust RLE extension"
	@echo "  clean         - Clean build artifacts"

# Installation
install:
	poetry install

install-dev: install build-rust
	@echo "Dev environment ready!"

# Rust extension
build-rust:
	cd rle-fast && poetry run maturin develop --release
	@echo "Rust RLE extension built and installed"

# Testing
test:
	$(PYTEST) tests/ -v --ignore=tests/e2e

test-unit:
	$(PYTEST) tests/ -v --ignore=tests/e2e -x

test-e2e:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Create it with RDP_HOST, RDP_USER, RDP_PASS"; \
		exit 1; \
	fi
	$(PYTHON) tests/e2e/test_connection.py

# Coverage
coverage:
	$(PYTEST) tests/ -v --ignore=tests/e2e --cov=src/simple_rdp --cov-report=term-missing

coverage-html:
	$(PYTEST) tests/ -v --ignore=tests/e2e --cov=src/simple_rdp --cov-report=html --cov-report=term
	@echo "Coverage report: htmlcov/index.html"

coverage-full: coverage-html
	@echo ""
	@echo "=== Coverage Summary ==="
	@$(PYTEST) tests/ -v --ignore=tests/e2e --cov=src/simple_rdp --cov-report=term-missing 2>/dev/null | tail -20

# Code quality
lint:
	poetry run ruff check src/ tests/

format:
	poetry run ruff format src/ tests/
	poetry run ruff check --fix src/ tests/

# Cleaning
clean:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf *.egg-info
	rm -rf rle-fast/target
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Development shortcuts
dev: install-dev
	@echo "Run 'make test' to run tests"

check: lint test
	@echo "All checks passed!"
