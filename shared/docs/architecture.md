# Bionocular Organization Architecture

## Overview
This document describes the architectural patterns and standards used across all projects in the Bionocular organization.

## 🏗️ Clean Architecture Principles

### Core Principles
1. **Dependency Rule**: Dependencies point inward. Outer layers depend on inner layers, never the reverse.
2. **Separation of Concerns**: Each layer has a specific responsibility.
3. **Testability**: Business logic is independent of frameworks and external concerns.
4. **Framework Independence**: Core business logic doesn't depend on specific frameworks.

### Layer Structure
```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│                    (API, CLI, Web UI)                      │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                        │
│                (Use Cases, Orchestration)                  │
├─────────────────────────────────────────────────────────────┤
│                    Domain Layer                             │
│              (Entities, Business Rules, Interfaces)        │
├─────────────────────────────────────────────────────────────┤
│                  Infrastructure Layer                        │
│            (Database, External Services, File I/O)         │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure Standards

### Standard Directory Layout
```
project-name/
├── src/main/project-name/     # Source code root
│   ├── domain/                # Domain layer
│   │   ├── __init__.py
│   │   ├── models.py          # Domain entities
│   │   └── interfaces.py      # Abstract interfaces
│   ├── infrastructure/        # Infrastructure layer
│   │   ├── __init__.py
│   │   ├── database.py        # Database configuration
│   │   ├── storage.py         # File storage
│   │   ├── repository.py      # Data access
│   │   └── pdf_processor.py   # PDF processing
│   └── app/                   # Application layer
│       ├── __init__.py
│       ├── api.py             # API endpoints
│       ├── services.py        # Business logic
│       └── cli.py             # Command line interface
├── data/                      # Data storage
│   ├── abstracts/             # Abstract documents
│   ├── publications/          # Publication documents
│   └── processed/             # Processed documents
├── tests/                     # Test suite
├── resources/                 # Configuration files
├── scripts/                   # Utility scripts
├── alembic/                   # Database migrations
├── pyproject.toml             # Project configuration
└── README.md                  # Project documentation
```

## 🔧 Technology Stack Standards

### Core Dependencies (Required)
- **Python**: 3.9+
- **FastAPI**: Web framework for APIs
- **SQLAlchemy**: ORM for database operations
- **Pydantic**: Data validation and serialization
- **Alembic**: Database migrations
- **Poetry**: Dependency management

### Development Dependencies (Required)
- **pytest**: Testing framework
- **Black**: Code formatting
- **Ruff**: Linting
- **MyPy**: Type checking

### Optional Dependencies
- **uvicorn**: ASGI server (included with FastAPI)
- **psycopg2-binary**: PostgreSQL adapter
- **PyPDF2/pdfplumber**: PDF processing

## 📊 Data Model Standards

### Document Model
All projects must implement a standard document model:

```python
class Document(BaseModel):
    id: UUID
    original_filename: str
    storage_path: str
    type: DocumentType
    upload_date: datetime
    hash: str
    status: DocumentStatus
    metadata: dict[str, Any]
```

### Required Enums
```python
class DocumentType(str, Enum):
    ABSTRACT = "abstract"
    PUBLICATION = "publication"

class DocumentStatus(str, Enum):
    INGESTED = "ingested"
    PROCESSING_FAILED = "processing_failed"
```

## 🚀 API Standards

### Required Endpoints
All projects must implement these standard endpoints:

- `POST /ingest` - Single document ingestion
- `POST /ingest/batch` - Batch document ingestion
- `POST /ingest/local` - Local file processing
- `GET /health` - Health check
- `GET /stats` - System statistics
- `GET /documents` - List documents
- `GET /documents/{id}` - Get specific document

### Response Format
```python
class StandardResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
```

## 🧪 Testing Standards

### Test Structure
```
tests/
├── unit/                      # Unit tests
├── integration/               # Integration tests
└── fixtures/                  # Test data and fixtures
```

### Coverage Requirements
- **Minimum Coverage**: 90%
- **Critical Paths**: 100% coverage
- **New Features**: Must include tests

## 📝 Code Quality Standards

### Formatting
- **Line Length**: 88 characters (Black default)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings

### Linting Rules
- **E**: Pycodestyle errors
- **W**: Pycodestyle warnings
- **F**: Pyflakes
- **I**: Import sorting
- **B**: Bug detection
- **C4**: Comprehension improvements

### Type Checking
- **Strict Mode**: Enabled by default
- **No Implicit Any**: Required
- **Return Type Annotations**: Required for public functions

## 🔄 Migration Standards

### Database Migrations
- **Tool**: Alembic
- **Naming**: `{version}_{description}.py`
- **Rollback**: All migrations must be reversible
- **Testing**: Test migrations in development environment

## 🚀 Deployment Standards

### Environment Configuration
```bash
# Required Environment Variables
DATABASE_URL=postgresql://user:pass@host:port/db
STORAGE_DIR=./data
LOG_LEVEL=INFO
DEBUG=false
```

## 📚 Documentation Standards

### Required Documentation
1. **README.md**: Project overview and quick start
2. **API Documentation**: OpenAPI/Swagger documentation
3. **Architecture**: System design and patterns
4. **Deployment**: Setup and deployment instructions

---

*This architecture guide ensures consistency and quality across all Bionocular projects.* 🏥🔬
