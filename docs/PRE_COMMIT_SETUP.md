# Pre-commit Hooks Setup Guide

This project uses [pre-commit](https://pre-commit.com/) to run automated checks before commits and pushes, catching issues early in the development process.

## Quick Start

### Installation

1. **Install pre-commit** (if not already installed):

   ```bash
   # Using pip
   pip install pre-commit

   # Using pipx (recommended)
   pipx install pre-commit

   # Using homebrew (macOS)
   brew install pre-commit
   ```

2. **Install the git hooks**:

   ```bash
   cd /path/to/data-labeller
   pre-commit install
   pre-commit install --hook-type pre-push
   pre-commit install --hook-type commit-msg
   ```

3. **Verify installation**:

   ```bash
   pre-commit --version
   ```

### First Run

Run all hooks on all files to ensure everything works:

```bash
pre-commit run --all-files
```

This may take a few minutes on the first run as it downloads and sets up all the hooks.

## What Gets Checked

### On Every Commit (Fast Checks)

These run automatically when you `git commit`:

#### General File Checks
- ✅ Trailing whitespace removal
- ✅ End-of-file fixer
- ✅ YAML/JSON/TOML validation
- ✅ Large file detection (>1MB)
- ✅ Merge conflict detection
- ✅ Private key detection
- ✅ Line ending normalization

#### Backend (Python)
- ✅ **Ruff linting** - Auto-fixes code style issues
- ✅ **Ruff formatting** - Formats Python code
- ✅ **mypy type checking** - Validates type hints
- ✅ **Bandit security** - Scans for security issues

#### Frontend (TypeScript/JavaScript)
- ✅ **Prettier formatting** - Formats JS/TS/CSS/JSON
- ✅ **ESLint** - Lints and auto-fixes code issues

#### Docker
- ✅ **Hadolint** - Lints Dockerfiles
- ✅ **Docker Compose validation** - Validates compose files

#### Security
- ✅ **Secrets detection** - Prevents committing secrets

#### Commit Message
- ✅ **Conventional commits** - Validates commit message format

### On Every Push (Slower Checks)

**Note**: Push-stage hooks are currently disabled for Windows compatibility. These checks run in CI instead:

#### Backend Tests (Runs in CI)
- 🧪 **Full test suite** - Runs all pytest tests
- 📊 **Coverage check** - Ensures 70% minimum coverage

#### Frontend Tests (Runs in CI)
- 🧪 **Test suite** - Runs frontend tests (if configured)
- 🔍 **Type checking** - Full TypeScript validation

**Why disabled locally?**
- Bash commands in pre-commit don't work reliably on Windows
- Tests run faster in CI with proper service containers
- CI provides comprehensive validation anyway

## Usage Examples

### Normal Workflow

```bash
# Make changes to code
vim backend/src/uu_backend/services/my_service.py

# Stage changes
git add backend/src/uu_backend/services/my_service.py

# Commit (pre-commit hooks run automatically)
git commit -m "feat(backend): Add new service"

# Push (test hooks run automatically)
git push
```

### Skip Hooks (Emergency Only)

```bash
# Skip all pre-commit hooks (NOT RECOMMENDED)
git commit --no-verify -m "emergency fix"

# Skip pre-push hooks
git push --no-verify
```

⚠️ **Warning**: Skipping hooks means your code won't be checked locally and may fail CI/CD pipelines.

### Run Specific Hooks

```bash
# Run only Python linting
pre-commit run ruff --all-files

# Run only formatting
pre-commit run ruff-format --all-files

# Run only tests
pre-commit run backend-tests --hook-stage push

# Run only type checking
pre-commit run mypy --all-files
```

### Run Hooks on Specific Files

```bash
# Run hooks on specific file
pre-commit run --files backend/src/uu_backend/services/my_service.py

# Run hooks on all Python files
pre-commit run --files backend/src/**/*.py
```

## Hook Stages

Pre-commit runs different hooks at different stages:

| Stage | When | What Runs | Duration |
|-------|------|-----------|----------|
| `commit` | `git commit` | Linting, formatting, quick checks | ~10-30s |
| `push` | `git push` | Tests, coverage, type checking | ~2-5min |
| `commit-msg` | `git commit` | Commit message validation | <1s |

## Configuration

### Customizing Hooks

Edit `.pre-commit-config.yaml` to customize:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix, --select, E,F,I]  # Customize rules
```

### Skipping Specific Hooks

Add to your commit message:

```bash
git commit -m "feat: Add feature" -m "SKIP=ruff,mypy"
```

Or set environment variable:

```bash
SKIP=ruff,mypy git commit -m "feat: Add feature"
```

### Updating Hooks

Update to latest versions:

```bash
pre-commit autoupdate
```

## Troubleshooting

### Hook Fails on First Run

**Problem**: Hook fails with "command not found" or similar error.

**Solution**: Install dependencies:

```bash
# Backend dependencies
cd backend
uv sync --all-extras

# Frontend dependencies
cd frontend
npm install
```

### Hooks Are Slow

**Problem**: Pre-commit hooks take too long.

**Solution**:
1. Hooks cache results - they'll be faster on subsequent runs
2. Only changed files are checked (not all files)
3. Consider moving slow checks to `pre-push` stage:

```yaml
hooks:
  - id: my-slow-hook
    stages: [push]  # Only run on push, not commit
```

### Type Checking Fails

**Problem**: mypy reports errors.

**Solution**:
```bash
# Install type stubs
cd backend
uv pip install types-python-dateutil types-PyYAML types-redis
```

### ESLint Not Found

**Problem**: ESLint hook fails.

**Solution**:
```bash
cd frontend
npm install --save-dev eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin
```

### Secrets Detected (False Positive)

**Problem**: detect-secrets flags a false positive.

**Solution**: Update baseline:

```bash
detect-secrets scan > .secrets.baseline
git add .secrets.baseline
git commit -m "chore: Update secrets baseline"
```

### Docker Hooks Fail

**Problem**: Docker-related hooks fail.

**Solution**: Ensure Docker is running:

```bash
docker --version
docker compose version
```

## CI/CD Integration

Pre-commit hooks complement (not replace) CI/CD:

| Check | Pre-commit | CI/CD | Why Both? |
|-------|-----------|-------|-----------|
| Linting | ✅ Fast local | ✅ Enforced | Catch early + enforce |
| Tests | ✅ On push | ✅ Full suite | Quick feedback + comprehensive |
| Security | ✅ Secrets | ✅ Full scan | Prevent + detect |
| Type check | ✅ Changed files | ✅ All files | Fast + complete |

### Pre-commit.ci (Optional)

Enable automatic hook updates and fixes on PRs:

1. Visit https://pre-commit.ci
2. Enable for your repository
3. Hooks will auto-update weekly
4. Auto-fix commits on PRs

## Best Practices

### ✅ Do

- Run `pre-commit run --all-files` before creating a PR
- Keep hooks fast (move slow checks to `pre-push`)
- Update hooks regularly with `pre-commit autoupdate`
- Fix issues locally rather than in CI/CD
- Use meaningful commit messages (conventional commits)

### ❌ Don't

- Skip hooks regularly (defeats the purpose)
- Commit large files (>1MB) - use Git LFS
- Ignore security warnings from Bandit or detect-secrets
- Commit with failing tests
- Use `--no-verify` except in emergencies

## Hook Reference

### Backend Hooks

| Hook | Purpose | Stage | Auto-fix |
|------|---------|-------|----------|
| ruff | Linting | commit | ✅ |
| ruff-format | Formatting | commit | ✅ |
| mypy | Type checking | commit | ❌ |
| bandit | Security | commit | ❌ |
| backend-tests | Tests | push | ❌ |
| backend-coverage | Coverage | push | ❌ |

### Frontend Hooks

| Hook | Purpose | Stage | Auto-fix |
|------|---------|-------|----------|
| prettier | Formatting | commit | ✅ |
| eslint | Linting | commit | ✅ |
| frontend-typecheck | Type checking | push | ❌ |
| frontend-tests | Tests | push | ❌ |

### General Hooks

| Hook | Purpose | Stage | Auto-fix |
|------|---------|-------|----------|
| trailing-whitespace | Remove trailing spaces | commit | ✅ |
| end-of-file-fixer | Ensure newline at EOF | commit | ✅ |
| check-yaml | Validate YAML | commit | ❌ |
| check-json | Validate JSON | commit | ❌ |
| detect-private-key | Find SSH keys | commit | ❌ |
| detect-secrets | Find secrets | commit | ❌ |
| hadolint-docker | Lint Dockerfiles | commit | ❌ |
| docker-compose-check | Validate compose | commit | ❌ |
| conventional-pre-commit | Commit message | commit-msg | ❌ |

## Performance Tips

### Speed Up Hooks

1. **Use file filters**: Hooks only run on relevant files
2. **Cache dependencies**: Pre-commit caches virtual environments
3. **Parallel execution**: Some hooks run in parallel
4. **Skip unchanged files**: Only modified files are checked

### Typical Execution Times

| Stage | First Run | Subsequent Runs |
|-------|-----------|-----------------|
| Pre-commit | 30-60s | 5-15s |
| Pre-push | 3-5min | 2-3min |

## Getting Help

### Check Hook Status

```bash
# Show installed hooks
pre-commit run --all-files --verbose

# Show hook configuration
cat .pre-commit-config.yaml
```

### Debug Hook Failures

```bash
# Run with verbose output
pre-commit run --verbose --all-files

# Run specific hook with debug
pre-commit run ruff --verbose --all-files
```

### Common Commands

```bash
# Install hooks
pre-commit install --install-hooks

# Uninstall hooks
pre-commit uninstall

# Update hooks to latest versions
pre-commit autoupdate

# Run all hooks manually
pre-commit run --all-files

# Clean hook cache
pre-commit clean

# Validate config
pre-commit validate-config
```

## Resources

- [Pre-commit Documentation](https://pre-commit.com/)
- [Supported Hooks](https://pre-commit.com/hooks.html)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Conventional Commits](https://www.conventionalcommits.org/)

## Support

For issues with pre-commit hooks:
1. Check this documentation
2. Run `pre-commit run --verbose --all-files`
3. Check [CONTRIBUTING.md](../CONTRIBUTING.md)
4. Open an issue with the `ci/cd` label
