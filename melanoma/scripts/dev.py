#!/usr/bin/env python3
"""
Development task scripts for Poetry.

Usage:
    poetry run dev:install
    poetry run dev:test
    poetry run dev:quality
    etc.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command."""
    print(f"🔄 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result


def install_dependencies():
    """Install project dependencies."""
    print("📦 Installing dependencies...")
    try:
        run_command(["poetry", "install"])
        print("✅ Dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        sys.exit(1)


def run_tests():
    """Run all tests."""
    print("🧪 Running tests...")
    try:
        run_command(["poetry", "run", "pytest"])
        print("✅ Tests completed!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Tests failed: {e}")
        sys.exit(1)


def run_tests_with_coverage():
    """Run tests with coverage report."""
    print("📊 Running tests with coverage...")
    try:
        run_command(
            [
                "poetry",
                "run",
                "pytest",
                "--cov=src",
                "--cov-report=html",
                "--cov-report=term-missing",
            ]
        )
        print("✅ Coverage report generated!")
        print("📁 Open htmlcov/index.html to view detailed coverage")
    except subprocess.CalledProcessError as e:
        print(f"❌ Coverage generation failed: {e}")
        sys.exit(1)


def run_linting():
    """Run code linting."""
    print("🔍 Running linting...")
    try:
        run_command(["poetry", "run", "ruff", "check", "src/", "tests/"])
        print("✅ Linting completed!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Linting failed: {e}")
        sys.exit(1)


def format_code():
    """Format code with Black."""
    print("🎨 Formatting code...")
    try:
        run_command(["poetry", "run", "black", "src/", "tests/"])
        print("✅ Code formatting completed!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Code formatting failed: {e}")
        sys.exit(1)


def run_type_checking():
    """Run type checking with MyPy."""
    print("🔍 Running type checking...")
    try:
        run_command(["poetry", "run", "mypy", "src/"])
        print("✅ Type checking completed!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Type checking failed: {e}")
        sys.exit(1)


def run_all_quality_checks():
    """Run all quality checks."""
    print("🚀 Running all quality checks...")

    checks = [
        ("Code Formatting", format_code),
        ("Linting", run_linting),
        ("Type Checking", run_type_checking),
        ("Tests", run_tests),
    ]

    failed_checks = []

    for check_name, check_func in checks:
        try:
            print(f"\n--- {check_name} ---")
            check_func()
        except SystemExit:
            failed_checks.append(check_name)
        except Exception as e:
            print(f"❌ {check_name} failed with error: {e}")
            failed_checks.append(check_name)

    if failed_checks:
        print(f"\n❌ Failed checks: {', '.join(failed_checks)}")
        sys.exit(1)
    else:
        print("\n🎉 All quality checks passed!")


def build_project():
    """Build the project package."""
    print("🏗️ Building project...")
    try:
        run_command(["poetry", "build"])
        print("✅ Project built successfully!")
        print("📦 Check dist/ directory for build artifacts")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        sys.exit(1)


def run_application():
    """Run the application."""
    print("🚀 Starting application...")
    try:
        run_command(["poetry", "run", "python", "run_ingestion.py"])
    except subprocess.CalledProcessError as e:
        print(f"❌ Application failed to start: {e}")
        sys.exit(1)


def initialize_database():
    """Initialize the database."""
    print("🗄️ Initializing database...")
    try:
        run_command(["poetry", "run", "alembic", "upgrade", "head"])
        print("✅ Database initialized successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1)


def clean_project():
    """Clean build artifacts and cache."""
    print("🧹 Cleaning project...")

    # Remove build artifacts
    build_dirs = ["dist/", "build/", "__pycache__/", "*.egg-info/"]
    for pattern in build_dirs:
        for path in Path(".").glob(pattern):
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
                print(f"🗑️ Removed: {path}")
            else:
                path.unlink()
                print(f"🗑️ Removed: {path}")

    # Remove test artifacts
    test_dirs = ["htmlcov/", ".coverage", ".pytest_cache/"]
    for pattern in test_dirs:
        for path in Path(".").glob(pattern):
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
                print(f"🗑️ Removed: {path}")
            else:
                path.unlink()
                print(f"🗑️ Removed: {path}")

    print("✅ Project cleaned successfully!")


if __name__ == "__main__":
    print("This module is designed to be run through Poetry scripts.")
    print("Use: poetry run dev:<task>")
    sys.exit(1)
