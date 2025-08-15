# Bionocular

A Python backend for processing scientific PDFs about melanoma treatments. This project provides a foundation for building a RAG (Retrieval-Augmented Generation) system that will extract and analyze medical research data.

## 🎯 Project Overview

Bionocular is designed to:
- Process scientific PDFs related to melanoma treatments
- Extract structured data (drugs, combinations, outcomes, ~180 attributes)
- Normalize and store extracted information
- Support retrieval and analytics for medical research

**Note**: This is currently a foundation project. The core PDF processing and entity extraction functionality will be implemented in future iterations.

## 🚀 Features

- **Clean Architecture**: Minimal, clean Python backend foundation
- **Code Quality**: Comprehensive linting, formatting, and type checking
- **Testing**: Full test coverage with pytest
- **CI/CD**: Automated testing and quality checks via GitHub Actions
- **Development Tools**: Pre-commit hooks for code quality

## 🛠️ Tech Stack

- **Python**: 3.11+
- **Package Management**: Poetry
- **Code Quality**: 
  - Black (formatting)
  - Ruff (linting)
  - MyPy (type checking)
  - Bandit (security)
- **Testing**: pytest with coverage
- **CI/CD**: GitHub Actions

## 📋 Prerequisites

- Python 3.11 or higher
- Poetry (will be installed automatically if not present)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd bionocular
```

### 2. Install Dependencies

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install
```

### 3. Activate the Virtual Environment

```bash
poetry shell
```

### 4. Run Tests

```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=app --cov-report=html

# Run specific test file
poetry run pytest tests/test_core.py -v
```

### 5. Code Quality Checks

```bash
# Format code
poetry run black app/ tests/

# Lint code
poetry run ruff check app/ tests/

# Type checking
poetry run mypy app/ tests/

# Security audit
poetry run bandit -r app/
```

## 🏗️ Project Structure

```
bionocular/
├── app/                    # Application package
│   ├── __init__.py        # Package initialization
│   └── core.py            # Core application logic
├── tests/                  # Test suite
│   ├── __init__.py        # Test package initialization
│   └── test_core.py       # Core functionality tests
├── .github/                # GitHub configuration
│   └── workflows/          # CI/CD workflows
│       └── ci.yml          # Main CI pipeline
├── .gitignore              # Git ignore rules
├── .pre-commit-config.yaml # Pre-commit hooks configuration
├── pyproject.toml          # Project configuration and dependencies
└── README.md               # This file
```

## 🧪 Testing

The project includes comprehensive testing:

- **Unit Tests**: Test individual components and functions
- **Integration Tests**: Test component interactions
- **Coverage**: 100% code coverage target
- **Quality**: All tests must pass before merging

Run tests with:
```bash
poetry run pytest tests/ -v
```

## 🔧 Development

### Pre-commit Hooks

Install pre-commit hooks to automatically check code quality:

```bash
poetry run pre-commit install
```

### Code Quality Tools

- **Black**: Automatic code formatting
- **Ruff**: Fast Python linter
- **MyPy**: Static type checking
- **Bandit**: Security vulnerability scanning

### Adding New Dependencies

```bash
# Add production dependency
poetry add package-name

# Add development dependency
poetry add --group dev package-name
```

## 📦 Building and Distribution

Build the package:
```bash
poetry build
```

This creates distribution files in the `dist/` directory.

## 🚀 CI/CD Pipeline

The GitHub Actions CI pipeline runs on every push and pull request:

1. **Code Quality**: Linting, formatting, and type checking
2. **Testing**: Run test suite with coverage reporting
3. **Security**: Security audit with Bandit
4. **Build**: Create distribution packages (on tags)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Ensure all tests pass (`poetry run pytest`)
5. Run code quality checks (`poetry run black`, `poetry run ruff`, `poetry run mypy`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔮 Future Roadmap

- [ ] PDF text extraction and processing
- [ ] Entity extraction for medical terms
- [ ] Data normalization and storage
- [ ] API endpoints for data retrieval
- [ ] Advanced analytics and reporting
- [ ] Machine learning model integration

## 📞 Support

For questions or support, please open an issue on GitHub.

---

**Note**: This project is in early development. The current focus is on establishing a solid foundation with proper tooling and structure.
# Test GPG signing
