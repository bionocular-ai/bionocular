#!/usr/bin/env python3
"""
CI/CD task scripts for Poetry.

Usage:
    poetry run ci:test
    poetry run ci:build
    poetry run ci:deploy
"""

import subprocess
import sys


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command."""
    print(f"🔄 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result


def run_ci_tests():
    """Run tests for CI pipeline."""
    print("🧪 Running CI tests...")

    # Run all quality checks
    checks = [
        (
            "Code Formatting Check",
            ["poetry", "run", "black", "--check", "src/", "tests/"],
        ),
        ("Linting", ["poetry", "run", "ruff", "check", "src/", "tests/"]),
        ("Type Checking", ["poetry", "run", "mypy", "src/"]),
        (
            "Tests with Coverage",
            [
                "poetry",
                "run",
                "pytest",
                "--cov=src",
                "--cov-report=xml",
                "--cov-report=term-missing",
            ],
        ),
    ]

    failed_checks = []

    for check_name, cmd in checks:
        try:
            print(f"\n--- {check_name} ---")
            run_command(cmd)
            print(f"✅ {check_name} passed")
        except subprocess.CalledProcessError:
            print(f"❌ {check_name} failed")
            failed_checks.append(check_name)

    if failed_checks:
        print(f"\n❌ CI checks failed: {', '.join(failed_checks)}")
        sys.exit(1)
    else:
        print("\n🎉 All CI checks passed!")


def build_for_ci():
    """Build project for CI pipeline."""
    print("🏗️ Building project for CI...")

    try:
        # Clean previous builds
        print("🧹 Cleaning previous builds...")
        run_command(
            ["poetry", "run", "python", "-m", "scripts.dev", "clean"], check=False
        )

        # Install dependencies
        print("📦 Installing dependencies...")
        run_command(["poetry", "install"])

        # Run tests
        print("🧪 Running tests...")
        run_command(["poetry", "run", "pytest", "--cov=src", "--cov-report=xml"])

        # Build package
        print("🏗️ Building package...")
        run_command(["poetry", "build"])

        print("✅ CI build completed successfully!")

    except subprocess.CalledProcessError as e:
        print(f"❌ CI build failed: {e}")
        sys.exit(1)


def deploy_project():
    """Deploy the project (placeholder for actual deployment logic)."""
    print("🚀 Deploying project...")

    # This is a placeholder - implement actual deployment logic
    print("⚠️  Deployment not implemented yet")
    print("📝 Add your deployment logic here")

    # Example deployment steps:
    # 1. Build project
    # 2. Run tests
    # 3. Upload to package registry
    # 4. Deploy to production

    print("✅ Deployment completed (placeholder)")


if __name__ == "__main__":
    print("This module is designed to be run through Poetry scripts.")
    print("Use: poetry run ci:<task>")
    sys.exit(1)
