# GitHub Actions Workflows

This directory contains all CI/CD workflow definitions for the Document Extraction Platform.

## Workflow Files

### Core CI Workflows

| Workflow | File | Triggers | Purpose |
|----------|------|----------|---------|
| Backend CI | `backend-ci.yml` | Push, PR (backend changes) | Lint, test, build backend |
| Frontend CI | `frontend-ci.yml` | Push, PR (frontend changes) | Lint, test, build frontend |
| Pull Request Checks | `pr-checks.yml` | PR events | Quality gates, metadata validation |

### Security & Quality

| Workflow | File | Triggers | Purpose |
|----------|------|----------|---------|
| CodeQL Analysis | `codeql.yml` | Push, PR, Weekly | Security scanning |
| Docker Publish | `docker-publish.yml` | Push to main, Releases | Build & publish images |

### Deployment & Maintenance

| Workflow | File | Triggers | Purpose |
|----------|------|----------|---------|
| Deploy | `deploy.yml` | Releases, Manual | Deploy to environments |
| Scheduled Maintenance | `scheduled-maintenance.yml` | Weekly | Dependency audits, cleanup |

## Quick Reference

### Running Workflows Locally

**Backend:**
```bash
cd backend
uv run ruff check src/ tests/
uv run pytest tests/ --cov=src/uu_backend
```

**Frontend:**
```bash
cd frontend
npm run check
npm test
npm run build
```

### Workflow Status

Check workflow status at: `https://github.com/YOUR_USERNAME/data-labeller/actions`

### Secrets Required

| Secret | Used By | Purpose |
|--------|---------|---------|
| `GITHUB_TOKEN` | All workflows | Auto-provided by GitHub |
| `CODECOV_TOKEN` | CI workflows | Upload coverage reports (optional) |

### Caching

All workflows use GitHub Actions caching:
- **Backend**: UV dependencies
- **Frontend**: npm dependencies
- **Docker**: BuildKit layer cache

### Concurrency

Workflows use concurrency groups to cancel outdated runs:
- Same workflow + branch = cancel previous
- Same PR = cancel previous

## Workflow Details

### Backend CI

**Duration**: ~5-8 minutes

**Steps:**
1. Lint & format check (Ruff)
2. Type checking (mypy)
3. Tests with PostgreSQL + Redis
4. Security scanning
5. Docker build validation

**Service Containers:**
- PostgreSQL 16
- Redis 7.4

### Frontend CI

**Duration**: ~3-5 minutes

**Steps:**
1. TypeScript type checking
2. ESLint (if configured)
3. Tests with coverage
4. Production build
5. Bundle size analysis
6. Docker build validation

### Docker Publish

**Duration**: ~10-15 minutes

**Platforms:**
- linux/amd64
- linux/arm64

**Outputs:**
- Container images in ghcr.io
- SBOM files (releases only)
- Trivy security reports

### CodeQL

**Duration**: ~8-12 minutes

**Languages:**
- Python (backend)
- JavaScript/TypeScript (frontend)

**Query Suites:**
- Security extended
- Security and quality

### PR Checks

**Duration**: ~2-3 minutes

**Validations:**
- Semantic PR title
- PR description exists
- PR size check
- Changed files detection
- Merge conflict detection
- Secret scanning
- Auto-labeling

## Maintenance

### Adding a New Workflow

1. Create `.yml` file in this directory
2. Define triggers and jobs
3. Test in a feature branch
4. Document in this README
5. Update [docs/CICD.md](../../docs/CICD.md)

### Modifying Existing Workflows

1. Test changes in a feature branch
2. Monitor workflow runs
3. Update documentation
4. Consider backward compatibility

### Debugging Workflows

1. Check workflow logs in Actions tab
2. Enable debug logging:
   ```yaml
   env:
     ACTIONS_STEP_DEBUG: true
     ACTIONS_RUNNER_DEBUG: true
   ```
3. Use `continue-on-error: true` for troubleshooting
4. Add echo statements for debugging

## Best Practices

1. **Use latest action versions**: Keep actions up to date
2. **Cache aggressively**: Speed up workflows
3. **Fail fast**: Put quick checks first
4. **Parallel execution**: Run independent jobs in parallel
5. **Path filters**: Skip unnecessary runs
6. **Concurrency groups**: Cancel outdated runs
7. **Secrets management**: Never log secrets
8. **Status checks**: Aggregate results properly

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [CI/CD Guide](../../docs/CICD.md)
- [Contributing Guide](../../CONTRIBUTING.md)
