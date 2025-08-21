# Development Tasks Guide

This document explains all the available development tasks for the Melanoma project.

## 🚀 **Poetry Scripts (Recommended)**

Poetry provides the most integrated experience. These scripts are defined in `pyproject.toml`.

### **Development Tasks**
```bash
# Setup
poetry run dev:install          # Install dependencies
poetry run dev:db-init          # Initialize database

# Testing
poetry run dev:test             # Run all tests
poetry run dev:test-cov         # Run tests with coverage

# Quality
poetry run dev:lint             # Run linting
poetry run dev:format           # Format code
poetry run dev:type-check       # Run type checking
poetry run dev:quality          # Run all quality checks

# Build & Run
poetry run dev:build            # Build project package
poetry run dev:run              # Run application

# Maintenance
poetry run dev:clean            # Clean build artifacts
```

### **CI/CD Tasks**
```bash
poetry run ci:test              # Run CI tests
poetry run ci:build             # Build for CI
poetry run ci:deploy            # Deploy project (placeholder)
```

---

## 🛠️ **Makefile Commands**

Traditional Makefile approach for those who prefer it.

### **Basic Commands**
```bash
make help                       # Show all available commands
make install                    # Install dependencies
make test                       # Run tests
make build                      # Build project
make run                        # Run application
make clean                      # Clean project
```

### **Quality Commands**
```bash
make lint                       # Run linting
make format                     # Format code
make type-check                 # Run type checking
make quality                    # Run all quality checks
make test-cov                   # Run tests with coverage
```

### **Workflow Commands**
```bash
make dev                        # Setup development environment
make ci                         # Run CI workflow
make info                       # Show project information
```

---

## 🐍 **Python Script Runner**

Simple Python script for running tasks.

```bash
python run_tasks.py <task>

# Available tasks:
python run_tasks.py install     # Install dependencies
python run_tasks.py test        # Run tests
python run_tasks.py quality     # Run all quality checks
python run_tasks.py build       # Build project
python run_tasks.py run         # Run application
python run_tasks.py clean       # Clean project
python run_tasks.py help        # Show help
```

---

## 📋 **Task Descriptions**

### **Setup Tasks**
- **`install`**: Install all project dependencies using Poetry
- **`db-init`**: Initialize PostgreSQL database using Alembic migrations

### **Testing Tasks**
- **`test`**: Run pytest test suite
- **`test-cov`**: Run tests with coverage reporting (HTML + terminal)

### **Quality Tasks**
- **`lint`**: Run Ruff linter to check code quality
- **`format`**: Format code using Black
- **`type-check`**: Run MyPy for static type checking
- **`quality`**: Run all quality checks in sequence

### **Build Tasks**
- **`build`**: Create distributable package (wheel + source)
- **`run`**: Start the FastAPI application server

### **Maintenance Tasks**
- **`clean`**: Remove build artifacts, cache files, and temporary files

---

## 🎯 **Recommended Workflows**

### **Daily Development**
```bash
# 1. Install dependencies (first time only)
poetry run dev:install

# 2. Activate environment
poetry shell

# 3. Run quality checks
poetry run dev:quality

# 4. Run tests
poetry run dev:test

# 5. Start development
poetry run dev:run
```

### **Before Committing**
```bash
# Run all quality checks
poetry run dev:quality

# Or use Makefile
make quality
```

### **CI/CD Pipeline**
```bash
# Run CI tests
poetry run ci:test

# Build for deployment
poetry run ci:build
```

---

## 🔧 **Customizing Tasks**

### **Adding New Poetry Scripts**
Edit `pyproject.toml`:
```toml
[tool.poetry.scripts]
dev:new-task = "scripts.dev:new_task_function"
```

### **Adding New Makefile Targets**
Edit `Makefile`:
```makefile
new-task:
	@echo "Running new task..."
	poetry run python -m scripts.dev new_task_function
```

### **Adding New Python Tasks**
Edit `run_tasks.py`:
```python
def new_task():
    return run_command("your command", "Task description")

# Add to tasks dictionary
tasks = {
    # ... existing tasks ...
    'new-task': new_task,
}
```

---

## 🚨 **Troubleshooting**

### **Common Issues**
1. **Poetry not found**: Install Poetry first
2. **Dependencies missing**: Run `poetry install`
3. **Database connection**: Check `.env` file and PostgreSQL
4. **Import errors**: Ensure you're in the right directory

### **Getting Help**
```bash
# Show all available tasks
make help
poetry run dev:help
python run_tasks.py help

# Check Poetry scripts
poetry run --help
```

---

## 📚 **Additional Resources**

- **Poetry Documentation**: https://python-poetry.org/docs/
- **Make Documentation**: https://www.gnu.org/software/make/
- **Project README**: `README.md`
- **Configuration**: `pyproject.toml`

---

*Choose the task runner that works best for your workflow!* 🎯
