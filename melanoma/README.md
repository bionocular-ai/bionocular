# Melanoma Project

## Overview
The Melanoma project is part of the Bionocular organization, focusing on melanoma-specific document ingestion and processing systems.

## Project Structure
```
melanoma/
├── src/main/melanoma/         # Source code
│   ├── domain/                # Domain models and interfaces
│   ├── infrastructure/        # Database, storage, and external services
│   └── app/                   # Application layer and API
├── data/                      # Data storage
│   ├── abstracts/             # Abstract documents
│   ├── publications/          # Publication documents
│   └── processed/             # Processed documents
├── scripts/                    # Utility scripts
├── resources/                  # Configuration and documentation
├── tests/                      # Test suite
└── alembic/                    # Database migrations
```

## Quick Start

### 1. Install Dependencies
```bash
cd melanoma
poetry install
```

### 2. Set Environment Variables
```bash
cp env.example .env
# Edit .env with your database and storage settings
```

### 3. Initialize Database
```bash
alembic upgrade head
```

### 4. Run the Application
```bash
python run_ingestion.py
```

## Features
- PDF document ingestion (single and batch)
- Local file processing
- Duplicate detection using content hashing
- PostgreSQL metadata storage
- RESTful API endpoints
- Command-line interface
- Comprehensive testing

## API Endpoints
- `POST /ingest` - Upload single PDF
- `POST /ingest/batch` - Upload batch PDF
- `POST /ingest/local` - Process local PDF file
- `POST /ingest/local/batch` - Process local batch PDF
- `POST /ingest/directory` - Process entire directory
- `GET /health` - Health check
- `GET /stats` - System statistics
- `GET /documents` - List all documents
- `GET /documents/{id}` - Get specific document

## Development
```bash
# Run tests
poetry run pytest

# Format code
poetry run black src/ tests/

# Lint code
poetry run ruff check src/ tests/

# Type checking
poetry run mypy src/
```

## Contributing
This project follows the Bionocular organization's development standards and clean architecture principles.
