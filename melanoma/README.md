# Melanoma backend and data pipelines

Clinical-trial ingestion, LLM-assisted extraction and validation (Gemini on Vertex AI), scheduled Supabase syncs, and a local FastAPI service. See `AGENTS.md` for the architecture, pipelines and development commands.

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

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd melanoma
poetry install
```

### 2. Set Environment Variables
```bash
export DATABASE_URL="postgresql://user:password@localhost/melanoma"
```

### 3. Initialize Database
```bash
alembic upgrade head
```

### 4. Run the Application
```bash
# Start the API server
python -m uvicorn src.app.api:app --reload --host 0.0.0.0 --port 8000

# Or run the ingestion service
python run_ingestion.py
```

## 📊 API Endpoints

### **Document Ingestion**
- `POST /ingest` - Upload single PDF
- `POST /ingest/batch` - Upload batch PDF
- `POST /ingest/local` - Process local PDF file
- `POST /ingest/local/batch` - Process local batch PDF
- `POST /ingest/directory` - Process entire directory
- `GET /health` - System health check
- `GET /stats` - System statistics
- `GET /documents` - List all documents
- `GET /documents/{id}` - Get specific document

## 🧪 Development

### **Running Tests**
```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html
```

### **Code Quality**
```bash
# Format code
poetry run black src/ tests/

# Lint code
poetry run ruff check src/ tests/

# Type checking
poetry run mypy src/

# Security check
poetry run bandit -r src/
```

### **Development Setup**
```bash
# Install development dependencies
poetry install --with dev

# Set up pre-commit hooks
poetry run pre-commit install

# Run database migrations
alembic upgrade head

# Start development server
poetry run uvicorn src.app.api:app --reload
```

## 🤝 Contributing

This project follows the Bionocular organization's development standards and clean architecture principles:

- **Clean Architecture**: Clear separation of concerns
- **SOLID Principles**: Maintainable and extensible code
- **Type Safety**: Full type annotations with mypy
- **Testing**: Comprehensive test coverage
- **Documentation**: Clear and up-to-date documentation
- **Code Quality**: Automated formatting and linting

## 📄 License

This project is part of the Bionocular organization and follows the organization's licensing terms.
