#!/usr/bin/env python3
"""
Simple task runner for Melanoma project.

Usage:
    python run_tasks.py <task>
    
Available tasks:
    - install: Install dependencies
    - test: Run tests
    - quality: Run all quality checks
    - build: Build project
    - run: Run application
    - clean: Clean project
    - help: Show this help
"""

import sys
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
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
    """Run tests."""
    return run_command("poetry run pytest", "Running tests")


def quality():
    """Run all quality checks."""
    checks = [
        ("poetry run black --check src/ tests/", "Code formatting check"),
        ("poetry run ruff check src/ tests/", "Linting"),
        ("poetry run mypy src/", "Type checking"),
        ("poetry run pytest --cov=src --cov-report=term-missing", "Tests with coverage"),
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
        'install': install,
        'test': test,
        'quality': quality,
        'build': build,
        'run': run,
        'clean': clean,
        'help': help,
    }
    
    if task not in tasks:
        print(f"❌ Unknown task: {task}")
        help()
        sys.exit(1)
    
    success = tasks[task]()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
