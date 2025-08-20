# Project Creation Guide

## Overview
This guide explains how to create new cancer type projects within the Bionocular organization using the automated project generator.

## 🚀 Quick Start

### 1. Basic Project Creation
```bash
# Navigate to organization root
cd bionocular

# Create a new project
python tools/project-generator/create_project.py lung-cancer "Lung cancer research system"
```

### 2. What Gets Created
The generator automatically creates:
- Complete project directory structure
- Source code templates
- Configuration files
- Documentation templates
- Test structure
- Database migration setup

## 📋 Project Naming Conventions

### Valid Project Names
- **Format**: lowercase with hyphens
- **Examples**:
  - `lung-cancer`
  - `breast-cancer`
  - `prostate-cancer`

### Invalid Project Names
- ❌ `LungCancer` (uppercase)
- ❌ `lung_cancer` (underscores)
- ❌ `lung cancer` (spaces)
- ❌ `1st-cancer` (starts with number)

## 🏗️ Generated Project Structure

```
new-project/
├── src/main/new-project/      # Source code
│   ├── domain/                # Domain layer
│   │   ├── __init__.py
│   │   ├── models.py          # Document models
│   │   └── interfaces.py      # Abstract interfaces
│   ├── infrastructure/        # Infrastructure layer
│   │   ├── __init__.py
│   │   ├── database.py        # Database setup
│   │   ├── storage.py         # File storage
│   │   ├── repository.py      # Data access
│   │   └── pdf_processor.py   # PDF processing
│   └── app/                   # Application layer
│       ├── __init__.py
│       ├── api.py             # REST API
│       ├── ingestion_service.py # Business logic
│       └── ingest_cli.py      # CLI interface
├── data/                      # Data directories
├── tests/                     # Test suite
├── resources/                 # Configuration
├── scripts/                   # Utility scripts
├── alembic/                   # Database migrations
├── pyproject.toml             # Project configuration
├── requirements.txt            # Dependencies
├── run_ingestion.py           # Startup script
├── env.example                # Environment template
└── README.md                  # Project documentation
```

## 🔧 Post-Generation Setup

### 1. Install Dependencies
```bash
cd new-project
poetry install
```

### 2. Environment Configuration
```bash
cp env.example .env
# Edit .env with your database and storage settings
```

### 3. Database Setup
```bash
# Initialize database
alembic upgrade head
```

### 4. Test the Setup
```bash
# Run tests
poetry run pytest

# Start the application
python run_ingestion.py
```

## 📚 Project-Specific Documentation

### 1. Update README.md
- Project-specific overview
- Cancer type description
- Special features or requirements
- Project-specific setup instructions

### 2. API Documentation
- Document all endpoints
- Include request/response examples
- Add project-specific parameters

## 🧪 Testing Strategy

### 1. Unit Tests
```bash
# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html
```

### 2. Code Quality
```bash
# Format code
poetry run black src/ tests/

# Lint code
poetry run ruff check src/ tests/

# Type checking
poetry run mypy src/
```

## 🔄 Maintenance and Updates

### 1. Dependency Updates
```bash
# Update dependencies
poetry update

# Check for security vulnerabilities
poetry audit
```

## 🚨 Common Issues and Solutions

### 1. Import Errors
**Problem**: Module import errors after generation
**Solution**: Ensure all `__init__.py` files are properly created

### 2. Database Connection
**Problem**: Database connection failures
**Solution**: Check `.env` file and database server status

### 3. File Permissions
**Problem**: Storage directory access issues
**Solution**: Ensure proper read/write permissions on data directories

---

*This guide ensures consistent project creation across the Bionocular organization.* 🏥🔬
