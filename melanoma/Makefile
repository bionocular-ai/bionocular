# Makefile for Melanoma Project
# Provides additional task management alongside Poetry scripts

.PHONY: help install test test-cov lint format type-check quality build run clean db-init

# Default target
help:
	@echo "Melanoma Project - Available Commands:"
	@echo ""
	@echo "📦 Setup:"
	@echo "  install     Install dependencies"
	@echo "  db-init     Initialize database"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  test        Run all tests"
	@echo "  test-cov    Run tests with coverage"
	@echo ""
	@echo "🔍 Quality:"
	@echo "  lint        Run linting"
	@echo "  format      Format code"
	@echo "  type-check  Run type checking"
	@echo "  quality     Run all quality checks"
	@echo ""
	@echo "🏗️ Build:"
	@echo "  build       Build project package"
	@echo "  run         Run application"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  clean       Clean build artifacts"
	@echo ""
	@echo "💡 Poetry Commands (recommended):"
	@echo "  poetry run dev:install"
	@echo "  poetry run dev:test"
	@echo "  poetry run dev:quality"
	@echo "  poetry run dev:build"

# Setup tasks
install:
	@echo "📦 Installing dependencies..."
	poetry install

db-init:
	@echo "🗄️ Initializing database..."
	poetry run alembic upgrade head

# Testing tasks
test:
	@echo "🧪 Running tests..."
	poetry run pytest

test-cov:
	@echo "📊 Running tests with coverage..."
	poetry run pytest --cov=src --cov-report=html --cov-report=term-missing

# Quality tasks
lint:
	@echo "🔍 Running linting..."
	poetry run ruff check src/ tests/

format:
	@echo "🎨 Formatting code..."
	poetry run black src/ tests/

type-check:
	@echo "🔍 Running type checking..."
	poetry run mypy src/

quality: format lint type-check test
	@echo "🎉 All quality checks completed!"

# Build tasks
build:
	@echo "🏗️ Building project..."
	poetry build

run:
	@echo "🚀 Starting application..."
	poetry run python run_ingestion.py

# Maintenance tasks
clean:
	@echo "🧹 Cleaning project..."
	rm -rf dist/ build/ *.egg-info/ htmlcov/ .coverage .pytest_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# Quick development workflow
dev: install quality
	@echo "🚀 Development environment ready!"

# CI workflow
ci: quality build
	@echo "✅ CI workflow completed!"

# Show project info
info:
	@echo "📋 Project Information:"
	@echo "  Name: $(shell poetry run python -c "import toml; print(toml.load('pyproject.toml')['tool']['poetry']['name'])")"
	@echo "  Version: $(shell poetry run python -c "import toml; print(toml.load('pyproject.toml')['tool']['poetry']['version'])")"
	@echo "  Python: $(shell poetry run python --version)"
	@echo "  Poetry: $(shell poetry --version)"
