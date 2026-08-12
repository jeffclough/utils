# Makefile for jc-handy-utils
# Target Python version: 3.12

# 1. Detect versioned binary name (e.g., 'python3.12' from 'Python 3.12.x')
DETECTED_PYTHON := $(shell python3 --version 2>/dev/null | sed -E 's/^Python ([0-9]+\.[0-9]+)\..*/python\1/')
# 2. Check if that specific binary exists in PATH; if not, fall back to standard 'python3'
# 3. Use ?= so the user can still explicitly override it via CLI: `PYTHON=python3.11 make venv`
PYTHON ?= $(shell command -v $(DETECTED_PYTHON) 2>/dev/null || command -v python3)

VENV      := .venv
BIN       := $(VENV)/bin
DEVENV    := .devenv
DEVBIN    := $(DEVENV)/bin

.PHONY: help venv test lint format clean build publish-test publish dev-install install

.DEFAULT_GOAL := help

help: ## Display this help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

devenv: ## Create virtualenv and install project in editable mode with dev dependencies
	$(PYTHON) -m venv $(DEVENV)
	$(DEVBIN)/pip install --upgrade pip
	$(DEVBIN)/pip install -e .[dev]
	@echo "\nVirtual environment created in $(DEVENV). Run 'source $(DEVENV)/bin/activate' to enter."

venv: ## Create virtualenv and install project
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install .
	@echo "\nVirtual environment created in $(VENV). Run 'source $(VENV)/bin/activate' to enter."

test: ## Run unit tests with pytest
	$(BIN)/pytest tests/ -v

lint: ## Run static type checking and linting
	$(BIN)/mypy src/
	$(BIN)/ruff check src/ tests/

format: ## Automatically format source code
	$(BIN)/ruff format src/ tests/

clean: ## Remove build artifacts, cache files, and byte code
	rm -rf build/ dist/ src/*.egg-info .eggs/
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete

build: clean ## Build source distribution and wheel packages
	$(BIN)/python -m build

publish-test: build ## Upload package to TestPyPI
	$(BIN)/twine upload --repository testpypi dist/*

publish: build ## Upload package to official PyPI
	$(BIN)/twine upload dist/*

dev-install: ## Install or force-refresh the editable package in pipx
	pipx install --editable --force .

install: ## Install or force-refresh the editable package in pipx
	pipx install --force .
