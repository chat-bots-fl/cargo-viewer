.PHONY: help install format lint check test clean all pre-commit-install pre-commit-run

# Default target
help:
	@echo "Available targets:"
	@echo "  make install          - Install dependencies"
	@echo "  make format           - Format code with black and isort"
	@echo "  make lint             - Run linters (flake8, mypy)"
	@echo "  make check            - Format and lint code"
	@echo "  make test             - Run tests with pytest"
	@echo "  make all              - Run format, lint and test"
	@echo "  make clean            - Clean cache and build artifacts"
	@echo "  make pre-commit-install - Install pre-commit hooks"
	@echo "  make pre-commit-run   - Run pre-commit hooks on all files"

# Install dependencies
install:
	pip install -r requirements.txt

# Format code with black and isort
format:
	@echo "Running black..."
	black --config .black .
	@echo "Running isort..."
	isort --settings-path .isort .
	@echo "Code formatted successfully!"

# Run linters (flake8 and mypy)
lint:
	@echo "Running flake8..."
	flake8 --config .flake8 .
	@echo "Running mypy..."
	mypy --config-file mypy.ini .
	@echo "Linting completed successfully!"

# Format and lint code
check: format lint
	@echo "Code check completed successfully!"

# Run tests
test:
	@echo "Running tests..."
	pytest --cov=apps --cov=config --cov-report=html --cov-report=term -v
	@echo "Tests completed!"

# Run all quality checks
all: format lint test
	@echo "All checks completed successfully!"

# Clean cache and build artifacts
clean:
	@echo "Cleaning cache and build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.pyd" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".tox" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean completed!"

# Install pre-commit hooks
pre-commit-install:
	@echo "Installing pre-commit hooks..."
	pre-commit install
	@echo "Pre-commit hooks installed successfully!"

# Run pre-commit hooks on all files
pre-commit-run:
	@echo "Running pre-commit hooks..."
	pre-commit run --all-files
	@echo "Pre-commit hooks completed!"
