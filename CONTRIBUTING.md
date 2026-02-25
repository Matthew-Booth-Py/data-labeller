# Contributing to Document Extraction Platform

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [CI/CD Pipeline](#cicd-pipeline)
- [Pull Request Process](#pull-request-process)
- [Commit Message Guidelines](#commit-message-guidelines)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker and Docker Compose
- Git
- pre-commit (for automated checks)

### Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/data-labeller.git
   cd data-labeller
   ```

2. **Install pre-commit hooks** (recommended)
   ```bash
   pip install pre-commit
   pre-commit install
   pre-commit install --hook-type pre-push
   pre-commit install --hook-type commit-msg
   ```
   
   See [docs/PRE_COMMIT_SETUP.md](docs/PRE_COMMIT_SETUP.md) for detailed setup.

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start with Docker Compose**
   ```bash
   docker compose up -d
   ```

5. **Or run locally**
   
   Backend:
   ```bash
   cd backend
   uv sync --all-extras
   uv run python manage.py migrate
   uv run uvicorn uu_backend.asgi_dispatcher:application --reload
   ```
   
   Frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes**
   - Write clean, maintainable code
   - Follow coding standards
   - Add tests for new functionality
   - Update documentation as needed

3. **Pre-commit hooks run automatically**
   
   When you commit, pre-commit hooks will automatically:
   - Format your code (Ruff, Prettier)
   - Run linters (Ruff, ESLint)
   - Check types (mypy)
   - Scan for security issues (Bandit)
   - Detect secrets
   - Validate commit message format
   
   ```bash
   git add .
   git commit -m "feat: Add new feature"
   # Hooks run automatically and may auto-fix issues
   ```

4. **Tests run on push**
   
   When you push, additional hooks run:
   - Full test suite with coverage (70% minimum)
   - Complete type checking
   
   ```bash
   git push origin feat/your-feature-name
   # Tests run automatically before push completes
   ```

5. **Manual testing** (optional, if hooks are disabled)
   ```bash
   # Run all pre-commit hooks manually
   pre-commit run --all-files
   
   # Backend tests
   cd backend
   uv run pytest tests/
   
   # Frontend tests
   cd frontend
   npm test
   ```

## Coding Standards

### Python (Backend)

- **Style Guide**: Follow PEP 8
- **Linter**: Ruff (configured in `pyproject.toml`)
- **Type Hints**: Use type hints for all functions
- **Line Length**: 100 characters max

**Run linting:**
```bash
cd backend
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

**Example:**
```python
from typing import Optional

def process_document(
    document_id: str,
    options: Optional[dict] = None
) -> dict:
    """Process a document with given options.
    
    Args:
        document_id: Unique identifier for the document
        options: Optional processing configuration
        
    Returns:
        Processing result dictionary
    """
    # Implementation
    pass
```

### TypeScript (Frontend)

- **Style Guide**: Airbnb TypeScript Style Guide
- **Type Safety**: Strict TypeScript configuration
- **Components**: Functional components with hooks

**Run type checking:**
```bash
cd frontend
npm run check
```

**Example:**
```typescript
interface DocumentProps {
  id: string;
  title: string;
  onProcess?: (id: string) => void;
}

export const Document: React.FC<DocumentProps> = ({ 
  id, 
  title, 
  onProcess 
}) => {
  // Implementation
  return <div>{title}</div>;
};
```

### General Guidelines

- **DRY**: Don't Repeat Yourself
- **SOLID**: Follow SOLID principles
- **Comments**: Write self-documenting code; use comments for complex logic
- **Naming**: Use descriptive names for variables, functions, and classes
- **Error Handling**: Handle errors gracefully with appropriate messages

## Testing

### Automated Testing with Pre-commit

Tests run automatically on `git push` via pre-commit hooks:
- Backend: Full pytest suite with 70% coverage requirement
- Frontend: Test suite and type checking

### Backend Testing

**Framework**: pytest

**Run tests manually:**
```bash
cd backend
uv run pytest tests/ -v
uv run pytest tests/ --cov=src/uu_backend --cov-report=html
```

**Run via pre-commit:**
```bash
pre-commit run backend-tests --hook-stage push
pre-commit run backend-coverage --hook-stage push
```

**Test Structure:**
```python
def test_document_processing():
    """Test document processing functionality."""
    # Arrange
    document = create_test_document()
    
    # Act
    result = process_document(document.id)
    
    # Assert
    assert result["status"] == "success"
    assert "data" in result
```

**Coverage Target**: 70% minimum (enforced by pre-commit hooks)

### Frontend Testing

**Framework**: Vitest / Jest (if configured)

**Run tests:**
```bash
cd frontend
npm test
npm test -- --coverage
```

### Integration Testing

Test with Docker Compose:
```bash
docker compose up -d
# Run integration tests
docker compose down
```

## CI/CD Pipeline

Our CI/CD pipeline automatically runs on every push and pull request. See [docs/CICD.md](docs/CICD.md) for detailed information.

### Automated Checks

1. **Linting & Formatting**
   - Python: Ruff
   - TypeScript: ESLint (if configured)

2. **Type Checking**
   - Python: mypy
   - TypeScript: tsc

3. **Tests**
   - Unit tests with coverage
   - Integration tests

4. **Security Scans**
   - CodeQL static analysis
   - Dependency vulnerability scanning
   - Secret detection

5. **Docker Builds**
   - Multi-platform image builds
   - Vulnerability scanning with Trivy

### Required Checks

All of these must pass before merging:
- ✅ Backend CI - All Checks Passed
- ✅ Frontend CI - All Checks Passed
- ✅ Pull Request Checks - All PR Checks Passed
- ✅ No merge conflicts
- ✅ No secrets detected

## Pull Request Process

1. **Create PR from your feature branch**
   - Use the PR template
   - Fill out all relevant sections
   - Link related issues

2. **PR Title Format**
   ```
   <type>: <description>
   
   Types:
   - feat: New feature
   - fix: Bug fix
   - docs: Documentation changes
   - style: Code style changes (formatting)
   - refactor: Code refactoring
   - perf: Performance improvements
   - test: Test updates
   - build: Build system changes
   - ci: CI/CD changes
   - chore: Other changes
   ```

3. **PR Description**
   - Explain what and why
   - List main changes
   - Describe testing performed
   - Add screenshots if UI changes

4. **Review Process**
   - Wait for automated checks to pass
   - Address reviewer feedback
   - Keep PR up to date with base branch
   - Resolve merge conflicts promptly

5. **Merging**
   - Squash commits for cleaner history
   - Ensure all checks pass
   - Get required approvals
   - Maintainer will merge

### PR Size Guidelines

- **Small**: < 200 lines changed (preferred)
- **Medium**: 200-500 lines changed (acceptable)
- **Large**: 500-1000 lines changed (needs justification)
- **Too Large**: > 1000 lines (will fail automated check)

Break large changes into smaller, focused PRs when possible.

## Commit Message Guidelines

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `build`: Changes to build system or dependencies
- `ci`: Changes to CI configuration
- `chore`: Other changes that don't modify src or test files

### Scope (optional)

- `backend`: Backend changes
- `frontend`: Frontend changes
- `api`: API changes
- `ui`: UI changes
- `deps`: Dependency updates
- `docker`: Docker configuration

### Examples

```bash
feat(backend): Add document classification endpoint

Implement new REST API endpoint for automatic document classification
using LLM-based analysis.

Closes #123
```

```bash
fix(frontend): Resolve PDF rendering issue on mobile

- Fix viewport scaling for mobile devices
- Improve touch gesture handling
- Update react-pdf to v9.0.0

Fixes #456
```

```bash
docs: Update CI/CD documentation

Add comprehensive guide for GitHub Actions workflows and deployment process.
```

## Development Tips

### Backend

1. **Use UV for dependency management**
   ```bash
   uv add package-name
   uv sync
   ```

2. **Create migrations**
   ```bash
   uv run python manage.py makemigrations
   uv run python manage.py migrate
   ```

3. **Run Django shell**
   ```bash
   uv run python manage.py shell
   ```

### Frontend

1. **Add dependencies**
   ```bash
   npm install package-name
   ```

2. **Type checking during development**
   ```bash
   npm run check -- --watch
   ```

3. **Build for production**
   ```bash
   npm run build
   ```

### Docker

1. **Rebuild after dependency changes**
   ```bash
   docker compose build
   docker compose up -d
   ```

2. **View logs**
   ```bash
   docker compose logs -f backend
   docker compose logs -f frontend
   ```

3. **Clean up**
   ```bash
   docker compose down -v
   ```

## Questions or Issues?

- **Documentation**: Check [docs/](docs/) directory
- **CI/CD**: See [docs/CICD.md](docs/CICD.md)
- **Issues**: Open a GitHub issue
- **Discussions**: Use GitHub Discussions for questions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

Thank you for contributing to the Document Extraction Platform! 🎉
