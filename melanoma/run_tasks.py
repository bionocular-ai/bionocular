#!/usr/bin/env python3
"""
Simple task runner for Melanoma project.

Usage:
    python run_tasks.py <task>

Available tasks:
    - install: Install dependencies
    - test: Run tests (pytest with coverage, same as CI)
    - quality: Run all quality checks (ruff, black, mypy, pytest)
    - ci: Run quality checks then build (full CI locally)
    - build: Build project
    - run: Run application
    - clean: Clean project
    - help: Show this help
"""

import subprocess
import sys


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True
        )
        if result.stdout:
            print(result.stdout)
        print(f"✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        if e.stderr:
            print(e.stderr)
        return False


def install():
    """Install project dependencies."""
    return run_command("poetry install", "Installing dependencies")


def test():
    """Run tests (same as CI: tests/ with coverage)."""
    return run_command(
        "poetry run pytest tests/ --cov=src --cov-report=xml --cov-report=html",
        "Running tests",
    )


def quality():
    """Run all quality checks (same order as CI)."""
    checks = [
        ("poetry run ruff check src/ tests/", "Lint (ruff)"),
        ("poetry run black --check src/ tests/", "Format (black)"),
        ("poetry run mypy src/", "Type check (mypy)"),
        (
            "poetry run pytest tests/ --cov=src --cov-report=xml --cov-report=html",
            "Tests with coverage",
        ),
    ]

    all_passed = True
    for cmd, desc in checks:
        if not run_command(cmd, desc):
            all_passed = False

    if all_passed:
        print("🎉 All quality checks passed!")
    else:
        print("❌ Some quality checks failed!")

    return all_passed


def build():
    """Build the project."""
    return run_command("poetry build", "Building project")


def run():
    """Run the application."""
    return run_command("poetry run python run_ingestion.py", "Starting application")


def clean():
    """Clean build artifacts."""
    return run_command("poetry run python -m scripts.dev clean", "Cleaning project")


def help():
    """Show help information."""
    print(__doc__)
    return True


def main():
    """Main task runner."""
    if len(sys.argv) < 2:
        print("❌ Please specify a task to run.")
        help()
        sys.exit(1)

    task = sys.argv[1].lower()

    tasks = {
        "install": install,
        "test": test,
        "quality": quality,
        "build": build,
        "run": run,
        "clean": clean,
        "help": help,
        "ci": lambda: quality() and build(),
    }

    if task not in tasks:
        print(f"❌ Unknown task: {task}")
        help()
        sys.exit(1)

    success = tasks[task]()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
