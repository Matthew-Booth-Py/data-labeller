# CI/CD Pipeline Documentation

This document describes the continuous integration and deployment pipelines for the Document Extraction Platform.

## Overview

Our CI/CD infrastructure follows modern 2026 best practices with:

- **Automated testing** on every push and pull request
- **Security scanning** with CodeQL, Trivy, and dependency audits
- **Quality gates** enforced before merging
- **Multi-platform Docker builds** with caching
- **Automated deployments** to staging and production
- **Dependency management** via Dependabot

## Workflows

### 1. Backend CI (`backend-ci.yml`)

**Triggers:**
- Push to `master`, `main`, or `develop` branches
- Pull requests targeting these branches
- Changes to `backend/**` or workflow file

**Jobs:**
- **Lint & Format Check**: Runs Ruff linting and format validation
- **Type Checking**: Runs mypy for static type analysis
- **Tests**: Executes pytest with coverage reporting (70% minimum)
  - Uses PostgreSQL 16 and Redis 7.4 service containers
  - Uploads coverage to Codecov
- **Security Scan**: Runs pip-audit and Bandit for vulnerability detection
- **Build**: Validates Docker image builds successfully
- **Status Check**: Aggregates all job results

**Environment:**
- Python 3.12
- UV package manager (0.5.11)
- PostgreSQL 16
- Redis 7.4

### 2. Frontend CI (`frontend-ci.yml`)

**Triggers:**
- Push to `master`, `main`, or `develop` branches
- Pull requests targeting these branches
- Changes to `frontend/**` or workflow file

**Jobs:**
- **Lint & Type Check**: TypeScript compilation and ESLint validation
- **Tests**: Runs test suite with coverage (if configured)
- **Build**: Production build validation
  - Uploads build artifacts (7-day retention)
- **Security Scan**: npm audit for vulnerability detection
- **Docker Build**: Validates Docker image builds
- **Bundle Analysis**: Analyzes bundle size and reports largest chunks
- **Status Check**: Aggregates all job results

**Environment:**
- Node.js 20
- npm with lock file caching

### 3. Docker Build & Publish (`docker-publish.yml`)

**Triggers:**
- Push to `master` or `main` branches
- Release publication
- Version tags (`v*.*.*`)
- Manual workflow dispatch

**Jobs:**
- **Build & Push Backend**: Multi-platform Docker image (amd64, arm64)
  - Publishes to GitHub Container Registry (ghcr.io)
  - Generates SBOM (Software Bill of Materials)
  - Tags: latest, version, SHA, branch
- **Build & Push Frontend**: Same as backend
- **Vulnerability Scan**: Trivy security scanning
  - Uploads results to GitHub Security tab
  - Scans for CRITICAL and HIGH vulnerabilities
- **Docker Compose Test**: Integration testing
  - Starts all services
  - Validates health endpoints

**Registry:** GitHub Container Registry (ghcr.io)

**Image Tags:**
- `latest` - Latest build from default branch
- `v1.2.3` - Semantic version tags
- `v1.2` - Major.minor version
- `v1` - Major version only
- `master-abc123` - Branch + SHA

### 4. CodeQL Security Analysis (`codeql.yml`)

**Triggers:**
- Push to `master`, `main`, or `develop`
- Pull requests
- Weekly schedule (Mondays at 2 AM UTC)
- Manual dispatch

**Languages Analyzed:**
- **Python**: Backend source code
  - Extended security queries
  - Excludes tests and migrations
- **JavaScript/TypeScript**: Frontend source code
  - Extended security queries
  - Excludes node_modules and test files

**Results:** Uploaded to GitHub Security tab

### 5. Pull Request Checks (`pr-checks.yml`)

**Triggers:**
- Pull request opened, synchronized, or reopened
- Only runs on non-draft PRs

**Jobs:**
- **PR Metadata Check**:
  - Validates semantic PR title format
  - Ensures PR has description
  - Checks PR size (warns >500 changes, fails >1000)
- **Changed Files Detection**: Identifies affected components
- **Backend/Frontend Quality Gates**: Waits for CI completion
- **Auto-labeling**: Adds labels based on changed files
- **Conflict Check**: Detects merge conflicts
- **Security Check**: Scans for secrets in diff (TruffleHog)
- **Comment Summary**: Posts analysis summary to PR

**PR Title Format:**
```
<type>: <description>

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
Example: feat: Add user authentication
```

### 6. Deployment (`deploy.yml`)

**Triggers:**
- Release publication (auto-deploys to production)
- Manual workflow dispatch

**Environments:**
- **Staging**: Pre-production testing environment
- **Production**: Live production environment

**Jobs:**
- **Prepare**: Determines environment and version
- **Deploy to Staging**: Deploys to staging environment
  - Runs smoke tests
  - Notifies deployment status
- **Deploy to Production**: Deploys to production
  - Requires manual approval (environment protection)
  - Pre-deployment checks
  - Smoke tests
  - Creates deployment record
- **Rollback**: Manual rollback on failure

**Deployment Commands:**
Replace placeholder commands with your actual deployment strategy:
- Kubernetes: `kubectl apply -f k8s/`
- Helm: `helm upgrade --install`
- Docker Swarm: `docker stack deploy`
- Cloud providers: AWS ECS, Azure Container Apps, Google Cloud Run

### 7. Scheduled Maintenance (`scheduled-maintenance.yml`)

**Schedule:** Every Sunday at 3 AM UTC

**Jobs:**
- **Dependency Audit**: Weekly security audit
  - Python dependencies (pip-audit)
  - npm dependencies (npm audit)
  - Uploads audit reports (30-day retention)
- **Docker Image Cleanup**: Removes old untagged images
  - Keeps last 10 versions
- **Stale Issues**: Marks inactive issues/PRs
  - 60 days before stale label
  - 7 days before auto-close
  - Exempts: pinned, security, bug labels
- **Performance Benchmarks**: Runs performance tests

## Dependabot Configuration

**File:** `.github/dependabot.yml`

**Update Schedule:** Weekly on Mondays at 9 AM UTC

**Managed Ecosystems:**
1. **Python (pip)** - Backend dependencies
   - Groups: django, openai, testing
   - Ignores major version updates for Django/DRF
2. **npm** - Frontend dependencies
   - Groups: react, radix-ui, tanstack, vite
   - Ignores major React updates
3. **GitHub Actions** - Workflow dependencies
4. **Docker** - Base image updates (backend & frontend)

**PR Limits:** 5-10 per ecosystem

**Labels:** Auto-applied based on ecosystem and component

## Security Features

### 1. Automated Scanning
- **CodeQL**: Static analysis for Python and TypeScript
- **Trivy**: Container vulnerability scanning
- **TruffleHog**: Secret detection in commits
- **pip-audit**: Python dependency vulnerabilities
- **npm audit**: JavaScript dependency vulnerabilities
- **Bandit**: Python security linter

### 2. Supply Chain Security
- **SBOM Generation**: Software Bill of Materials for releases
- **Provenance**: Build attestations for container images
- **Dependency Review**: Automated PR checks for new vulnerabilities

### 3. Security Policies
- Vulnerabilities reported to GitHub Security tab
- SARIF format for standardized reporting
- Automated security updates via Dependabot

## Quality Gates

### Required Checks for Merging
1. ✅ All CI tests pass (backend and frontend)
2. ✅ Code coverage meets minimum threshold (70%)
3. ✅ No merge conflicts
4. ✅ No secrets detected in changes
5. ✅ PR has valid title and description
6. ✅ Docker images build successfully

### Optional Checks (warnings only)
- Type checking (mypy)
- Security scans (may have false positives)
- Bundle size analysis

## Caching Strategy

### GitHub Actions Cache
- **Backend**: UV dependency cache
- **Frontend**: npm dependency cache
- **Docker**: BuildKit layer caching (GHA cache backend)

**Benefits:**
- Faster CI runs (2-5x speedup)
- Reduced network usage
- Cost savings

## Artifacts & Retention

| Artifact | Retention | Purpose |
|----------|-----------|---------|
| Build outputs | 7 days | Debugging failed builds |
| Test coverage | Permanent | Codecov integration |
| Security reports | 30 days | Audit trail |
| SBOM files | Permanent | Release artifacts |
| Audit reports | 30 days | Compliance tracking |

## Monitoring & Notifications

### Status Badges
README displays real-time status for:
- Backend CI
- Frontend CI
- Docker Publish
- CodeQL Security

### Notifications
- Failed workflows notify repository admins
- Deployment status posted to PRs
- Security findings appear in Security tab

## Best Practices

### 1. Branch Protection Rules
Configure on `master`/`main`:
```yaml
required_status_checks:
  - Backend CI / All Checks Passed
  - Frontend CI / All Checks Passed
  - Pull Request Checks / All PR Checks Passed
require_pull_request_reviews: true
dismiss_stale_reviews: true
require_code_owner_reviews: true
```

### 2. Environment Protection
**Production:**
- Require manual approval
- Limit to specific branches (main, master)
- Require deployment branch

**Staging:**
- Auto-deploy from develop branch
- No approval required

### 3. Secrets Management
Required secrets:
- `GITHUB_TOKEN` - Auto-provided by GitHub
- `CODECOV_TOKEN` - Optional, for coverage reporting
- Deployment credentials (varies by platform)

### 4. Performance Optimization
- Use concurrency groups to cancel outdated runs
- Cache dependencies aggressively
- Run jobs in parallel when possible
- Use path filters to skip unnecessary runs

## Troubleshooting

### Common Issues

**1. Docker build fails with "no space left on device"**
```yaml
# Add cleanup step before build
- name: Clean up Docker
  run: docker system prune -af
```

**2. Tests fail intermittently**
- Check service container health
- Increase health check timeouts
- Add retry logic for flaky tests

**3. Coverage upload fails**
```yaml
# Make coverage upload non-blocking
fail_ci_if_error: false
```

**4. Dependabot PRs fail CI**
- Review grouped updates
- Update test fixtures
- Check for breaking changes

## Migration Guide

### From No CI/CD
1. Merge this PR to add all workflows
2. Update README badges with your repository URL
3. Configure branch protection rules
4. Set up deployment environments
5. Add required secrets

### From Existing CI/CD
1. Review workflow files for conflicts
2. Migrate existing secrets
3. Update deployment commands
4. Test in a feature branch first
5. Gradually migrate workflows

## Maintenance

### Weekly Tasks
- Review Dependabot PRs
- Check security scan results
- Monitor workflow run times

### Monthly Tasks
- Review and update dependencies
- Optimize slow workflows
- Clean up old artifacts
- Update documentation

### Quarterly Tasks
- Review and update security policies
- Audit access controls
- Update CI/CD best practices
- Performance benchmarking

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [CodeQL Documentation](https://codeql.github.com/docs/)
- [Dependabot Configuration](https://docs.github.com/en/code-security/dependabot)

## Support

For issues with CI/CD pipelines:
1. Check workflow logs in Actions tab
2. Review this documentation
3. Open an issue with workflow run URL
4. Tag with `ci/cd` label
