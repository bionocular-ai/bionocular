#!/usr/bin/env python3
"""
Project Generator for Bionocular Organization

This script creates new cancer type projects following the established structure.
"""

import os
import shutil
import argparse
import re
from pathlib import Path
from string import Template


class ProjectGenerator:
    def __init__(self, organization_root: str):
        self.organization_root = Path(organization_root)
        self.template_dir = self.organization_root / "shared" / "templates"
        self.projects_dir = self.organization_root
        
    def create_project(self, project_name: str, description: str) -> bool:
        """Create a new cancer type project."""
        try:
            # Validate project name
            if not re.match(r'^[a-z][a-z0-9-]*$', project_name):
                raise ValueError("Project name must be lowercase, start with letter, and contain only letters, numbers, and hyphens")
            
            project_dir = self.projects_dir / project_name
            
            if project_dir.exists():
                raise ValueError(f"Project directory {project_dir} already exists")
            
            print(f"Creating project: {project_name}")
            print(f"Description: {description}")
            
            # Create project structure
            self._create_directory_structure(project_dir, project_name)
            self._copy_template_files(project_dir, project_name, description)
            self._create_pyproject_toml(project_dir, project_name, description)
            self._create_readme(project_dir, project_name, description)
            self._create_env_example(project_dir)
            self._create_init_files(project_dir, project_name)
            
            print(f"✅ Project '{project_name}' created successfully!")
            print(f"📁 Location: {project_dir}")
            print(f"🚀 Next steps:")
            print(f"   1. cd {project_name}")
            print(f"   2. poetry install")
            print(f"   3. cp env.example .env")
            print(f"   4. Edit .env with your settings")
            print(f"   5. python run_ingestion.py")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating project: {e}")
            return False
    
    def _create_directory_structure(self, project_dir: Path, project_name: str):
        """Create the project directory structure."""
        directories = [
            f"src/domain",                    # Simplified structure
            f"src/infrastructure",            # No more main/project-name nesting
            f"src/app",                       # Direct src/ structure
            "data/abstracts",
            "data/publications",
            "data/processed",
            "scripts",
            "resources",
            "tests",
            "alembic"
        ]
        
        for directory in directories:
            (project_dir / directory).mkdir(parents=True, exist_ok=True)
    
    def _copy_template_files(self, project_dir: Path, project_name: str, description: str):
        """Copy and customize template files from shared templates."""
        # Copy from melanoma project as template
        melanoma_dir = self.organization_root / "melanoma"
        
        if melanoma_dir.exists():
            # Copy source files
            self._copy_and_customize_source_files(melanoma_dir, project_dir, project_name)
            
            # Copy other files
            files_to_copy = [
                "run_ingestion.py",
                "requirements.txt", 
                "alembic.ini"
            ]
            
            for file_name in files_to_copy:
                src_file = melanoma_dir / file_name
                dst_file = project_dir / file_name
                if src_file.exists():
                    shutil.copy2(src_file, dst_file)
            
            # Copy alembic directory
            alembic_src = melanoma_dir / "alembic"
            alembic_dst = project_dir / "alembic"
            if alembic_src.exists():
                shutil.copytree(alembic_src, alembic_dst, dirs_exist_ok=True)
    
    def _copy_and_customize_source_files(self, melanoma_dir: Path, project_dir: Path, project_name: str):
        """Copy and customize source code files."""
        src_src = melanoma_dir / "src"                    # Simplified path
        src_dst = project_dir / "src"                     # Direct src/ structure
        
        if src_src.exists():
            shutil.copytree(src_src, src_dst, dirs_exist_ok=True)
            
            # Customize __init__.py files
            self._customize_init_files(src_dst, project_name)
    
    def _customize_init_files(self, src_dir: Path, project_name: str):
        """Customize __init__.py files with project-specific content."""
        init_files = [
            src_dir / "__init__.py",
            src_dir / "domain" / "__init__.py",
            src_dir / "infrastructure" / "__init__.py",
            src_dir / "app" / "__init__.py"
        ]
        
        for init_file in init_files:
            if init_file.exists():
                content = init_file.read_text()
                content = content.replace("melanoma", project_name)
                content = content.replace("Melanoma", project_name.title())
                init_file.write_text(content)
    
    def _create_pyproject_toml(self, project_dir: Path, project_name: str, description: str):
        """Create pyproject.toml for the new project."""
        pyproject_content = f'''[tool.poetry]
name = "{project_name}"
version = "0.1.0"
description = "{description} for Bionocular organization"
authors = ["Bionocular Team <team@bionocular.com>"]
readme = "README.md"
packages = [{{include = "src"}}]

[tool.poetry.dependencies]
python = "^3.9"
fastapi = "^0.104.1"
uvicorn = {{extras = ["standard"], version = "^0.24.0"}}
pydantic = "^2.5.0"
sqlalchemy = "^2.0.23"
psycopg2-binary = "^2.9.9"
pypdf2 = "^3.0.1"
pdfplumber = "^0.10.3"
python-multipart = "^0.0.6"
python-dotenv = "^1.0.0"
alembic = "^1.12.1"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.3"
pytest-asyncio = "^0.21.1"
pytest-cov = "^4.1.0"
black = "^23.11.0"
ruff = "^0.1.6"
mypy = "^1.7.1"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.black]
line-length = 88
target-version = ['py39']

[tool.ruff]
target-version = "py39"
line-length = 88

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
'''
        
        (project_dir / "pyproject.toml").write_text(pyproject_content)
    
    def _create_readme(self, project_dir: Path, project_name: str, description: str):
        """Create README.md for the new project."""
        readme_content = f'''# {project_name.title()} Project

## Overview
The {project_name.title()} project is part of the Bionocular organization, focusing on {description.lower()}.

## Project Structure
```
{project_name}/
├── src/main/{project_name}/     # Source code
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
cd {project_name}
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
'''
        
        (project_dir / "README.md").write_text(readme_content)
    
    def _create_env_example(self, project_dir: Path):
        """Create .env.example file."""
        env_content = '''# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/melanoma_db

# Storage Configuration
STORAGE_DIR=./data
MAX_FILE_SIZE=10485760  # 10MB in bytes

# API Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log

# Processing Configuration
BATCH_SIZE=100
MAX_WORKERS=4
'''
        
        (project_dir / "env.example").write_text(env_content)
    
    def _create_init_files(self, project_dir: Path, project_name: str):
        """Create __init__.py files in appropriate directories."""
        init_dirs = [
            project_dir / "src",
            project_dir / "src" / "domain",
            project_dir / "src" / "infrastructure",
            project_dir / "src" / "app",
            project_dir / "tests"
        ]
        
        for init_dir in init_dirs:
            init_file = init_dir / "__init__.py"
            if not init_file.exists():
                init_file.write_text(f'"""Package initialization for {project_name}."""\n')


def main():
    parser = argparse.ArgumentParser(description="Create a new cancer type project")
    parser.add_argument("project_name", help="Name of the new project (e.g., lung-cancer)")
    parser.add_argument("description", help="Description of the project")
    parser.add_argument("--org-root", default=".", help="Path to organization root directory")
    
    args = parser.parse_args()
    
    generator = ProjectGenerator(args.org_root)
    success = generator.create_project(args.project_name, args.description)
    
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
