# Pre-commit Hooks Implementation Summary

## Overview

Added comprehensive pre-commit hooks to automate testing and quality checks locally before commits and pushes. This provides fast feedback and catches issues before they reach CI/CD.

**Commit**: `16c5d49` - feat: Add pre-commit hooks for automated local testing and quality checks  
**Pull Request**: [#14](https://github.com/Matthew-Booth-Py/data-labeller/pull/14)  

## What Was Added

### Configuration Files

1. **`.pre-commit-config.yaml`** - Main configuration with 15+ hooks
2. **`.secrets.baseline`** - Baseline for detect-secrets
3. **`.github/workflows/pre-commit-ci.yml`** - CI validation workflow
4. **`docs/PRE_COMMIT_SETUP.md`** - Comprehensive setup guide
5. **`docs/CICD_SUMMARY.md`** - Overall CI/CD implementation summary

### Updated Files

- **`backend/pyproject.toml`** - Added pre-commit and dev dependencies
- **`CONTRIBUTING.md`** - Updated with pre-commit workflow
- **`README.md`** - Added installation instructions
- **`docs/CICD.md`** - Integrated pre-commit documentation

## Hook Configuration

### Stage 1: On Commit (Fast ~10-30s)

**General File Checks**:
- ✅ Remove trailing whitespace
- ✅ Fix end-of-file
- ✅ Validate YAML, JSON, TOML
- ✅ Check for large files (>1MB)
- ✅ Detect merge conflicts
- ✅ Detect private keys
- ✅ Normalize line endings

**Backend (Python)**:
- ✅ **Ruff linting** - Auto-fix code style issues
- ✅ **Ruff formatting** - Format Python code
- ✅ **mypy** - Type checking
- ✅ **Bandit** - Security scanning

**Frontend (TypeScript/JavaScript)**:
- ✅ **Prettier** - Format code
- ✅ **ESLint** - Lint and auto-fix

**Docker**:
- ✅ **Hadolint** - Lint Dockerfiles
- ✅ **docker-compose validation** - Validate compose files

**Security**:
- ✅ **detect-secrets** - Prevent committing secrets

**Commit Message**:
- ✅ **Conventional commits** - Validate format

### Stage 2: On Push (Comprehensive ~2-5min)

**Backend Tests**:
- 🧪 Full pytest suite
- 📊 Coverage check (70% minimum)

**Frontend Tests**:
- 🧪 Test suite (if configured)
- 🔍 Complete type checking

## Installation

### Quick Setup

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
cd /path/to/data-labeller
pre-commit install
pre-commit install --hook-type pre-push
pre-commit install --hook-type commit-msg

# Verify installation
pre-commit run --all-files
```

### First Run

The first run will:
1. Download and cache hook environments (~1-2 minutes)
2. Run all hooks on all files
3. Auto-fix issues where possible
4. Report any remaining issues

Subsequent runs are much faster due to caching.

## Usage

### Normal Workflow

```bash
# Make changes
vim backend/src/uu_backend/services/my_service.py

# Stage changes
git add backend/src/uu_backend/services/my_service.py

# Commit (hooks run automatically)
git commit -m "feat(backend): Add new service"
# Output shows:
# - Ruff linting... ✅ Passed (auto-fixed 3 issues)
# - Ruff formatting... ✅ Passed
# - mypy... ✅ Passed
# - Bandit... ✅ Passed
# ... etc

# Push (test hooks run automatically)
git push
# Output shows:
# - Backend tests... ✅ Passed (2.3s)
# - Backend coverage... ✅ Passed (70.5% coverage)
# - Frontend type check... ✅ Passed
```

### Manual Execution

```bash
# Run all hooks manually
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files

# Run only commit-stage hooks
pre-commit run --hook-stage commit

# Run only push-stage hooks
pre-commit run --hook-stage push
```

## Benefits

### 🚀 Fast Feedback

| Check | Without Pre-commit | With Pre-commit |
|-------|-------------------|-----------------|
| Linting issues | 5-8 min (CI) | 5-15 sec (local) |
| Test failures | 5-8 min (CI) | 2-3 min (local) |
| Format issues | 5-8 min (CI) | 5-10 sec (local) |
| Security issues | 8-12 min (CI) | 10-20 sec (local) |

### ✨ Developer Experience

- **Auto-fixing**: Many issues fixed automatically
- **Early Detection**: Catch issues before pushing
- **Consistent Quality**: Same checks for all developers
- **Reduced CI Load**: Fewer failed CI runs
- **Better Commits**: Enforced conventional commit format

### 📊 Impact Metrics

**Expected Improvements**:
- ⬇️ 60-80% reduction in failed CI runs
- ⚡ 10x faster feedback on code quality issues
- ✅ 100% commit message format compliance
- 🔒 Zero secrets committed (with detect-secrets)
- 📈 Improved code coverage (enforced locally)

## Hook Details

### Auto-fixing Hooks

These hooks automatically fix issues:

| Hook | What It Fixes | Example |
|------|--------------|---------|
| ruff | Import sorting, unused imports | `import os, sys` → sorted |
| ruff-format | Code formatting | Indentation, line length |
| prettier | JS/TS/CSS formatting | Quotes, semicolons, spacing |
| eslint | JS/TS issues | Unused vars, missing types |
| trailing-whitespace | Extra spaces | `code   ` → `code` |
| end-of-file-fixer | Missing newlines | Adds `\n` at EOF |
| mixed-line-ending | Line endings | CRLF → LF |

### Validation Hooks

These hooks report issues (no auto-fix):

| Hook | What It Checks | Action Required |
|------|---------------|-----------------|
| mypy | Type hints | Add/fix type annotations |
| bandit | Security issues | Fix security vulnerabilities |
| backend-tests | Test failures | Fix failing tests |
| backend-coverage | Coverage < 70% | Add more tests |
| detect-secrets | Exposed secrets | Remove secrets, use env vars |
| conventional-pre-commit | Commit format | Fix commit message |

## CI Integration

### Pre-commit CI Workflow

Added `.github/workflows/pre-commit-ci.yml`:

**Purpose**: Validate that pre-commit hooks pass in CI

**Runs on**:
- All pushes to main branches
- All pull requests

**Benefits**:
- Ensures hooks are properly configured
- Catches issues if developers skip hooks
- Faster than running full CI workflows
- Provides consistent feedback

**Duration**: ~2-3 minutes (faster than full CI)

## Configuration

### Customization

Edit `.pre-commit-config.yaml` to customize:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix, --select, E,F,I]  # Customize rules
```

### Skipping Hooks

**Temporarily skip** (use sparingly):

```bash
# Skip all hooks
git commit --no-verify -m "emergency fix"

# Skip specific hooks
SKIP=ruff,mypy git commit -m "feat: Add feature"
```

**Permanently skip** (add to config):

```yaml
hooks:
  - id: mypy
    exclude: ^tests/  # Skip mypy for tests
```

### Updating Hooks

Keep hooks up to date:

```bash
# Update to latest versions
pre-commit autoupdate

# Commit the updates
git add .pre-commit-config.yaml
git commit -m "chore: Update pre-commit hooks"
```

## Troubleshooting

### Common Issues

**1. Hook fails on first run**

```bash
# Solution: Install dependencies
cd backend && uv sync --all-extras
cd frontend && npm install
```

**2. Hooks are slow**

- First run is slow (downloads environments)
- Subsequent runs are cached and fast
- Only changed files are checked

**3. False positive from detect-secrets**

```bash
# Update baseline
detect-secrets scan > .secrets.baseline
git add .secrets.baseline
```

**4. ESLint not configured**

```bash
# Install ESLint
cd frontend
npm install --save-dev eslint @typescript-eslint/parser
```

### Getting Help

```bash
# Show installed hooks
pre-commit run --all-files --verbose

# Validate configuration
pre-commit validate-config

# Clean cache and reinstall
pre-commit clean
pre-commit install --install-hooks
```

## Comparison: Pre-commit vs CI/CD

| Aspect | Pre-commit | CI/CD | Best Practice |
|--------|-----------|-------|---------------|
| **Speed** | Seconds to minutes | Minutes | Use both |
| **Scope** | Changed files | All files | Pre-commit first |
| **Auto-fix** | Yes | No | Pre-commit fixes |
| **Enforcement** | Optional (can skip) | Required | CI enforces |
| **Feedback** | Immediate | Delayed | Pre-commit faster |
| **Coverage** | Local changes | Full codebase | Both needed |

**Recommended Workflow**:
1. ✅ Pre-commit catches issues locally (fast)
2. ✅ CI/CD validates everything (comprehensive)
3. ✅ Both provide defense in depth

## Adoption Strategy

### For New Projects

1. Install pre-commit from day one
2. Run `pre-commit install` in setup docs
3. All developers use hooks from start

### For Existing Projects (This Project)

1. ✅ Add configuration files
2. ✅ Update documentation
3. ✅ Add CI validation
4. 📢 Announce to team
5. 🎓 Provide training/support
6. 📊 Monitor adoption

### Team Rollout

**Week 1**: Optional adoption
- Share documentation
- Help with installation
- Gather feedback

**Week 2**: Encouraged adoption
- Show benefits (faster feedback)
- Address issues
- Update configuration

**Week 3+**: Standard practice
- Expected for all commits
- CI enforces same checks
- Part of onboarding

## Maintenance

### Weekly

- Review hook execution times
- Check for hook failures
- Update documentation as needed

### Monthly

- Run `pre-commit autoupdate`
- Review and adjust hook configuration
- Check for new useful hooks

### Quarterly

- Audit hook effectiveness
- Review skip patterns
- Update baseline files
- Team feedback session

## Metrics to Track

### Adoption

- % of commits with hooks enabled
- % of developers using hooks
- Hook skip frequency

### Impact

- Failed CI runs (before vs after)
- Average time to fix issues
- Number of auto-fixed issues
- Security issues caught locally

### Performance

- Average hook execution time
- Cache hit rate
- Developer satisfaction

## Resources

- **Setup Guide**: [docs/PRE_COMMIT_SETUP.md](PRE_COMMIT_SETUP.md)
- **CI/CD Guide**: [docs/CICD.md](CICD.md)
- **Contributing**: [CONTRIBUTING.md](../CONTRIBUTING.md)
- **Official Docs**: https://pre-commit.com/

## Next Steps

1. **Install pre-commit** on your local machine
2. **Run first check** with `pre-commit run --all-files`
3. **Test workflow** by making a small change
4. **Share with team** and help with adoption
5. **Monitor impact** and gather feedback

---

**Implementation Date**: February 25, 2026  
**Status**: ✅ Complete - Ready for Use  
**Pull Request**: [#14](https://github.com/Matthew-Booth-Py/data-labeller/pull/14)
