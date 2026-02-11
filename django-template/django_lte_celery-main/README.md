# django_lte_celery

A Django project with AdminLTE UI, Celery task queue, and Docker-based local development.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Quick Start

The entire stack runs via Docker Compose using the `local.sh` helper script.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- The environment files in `.envs/.local/` (`.django` and `.postgres`)

### Spin Up the Project

```bash
# Build and start all services
./local.sh up --build

# Or run in detached mode
./local.sh up --build -d
```

This starts the following services:

| Service         | Description                  | URL / Port            |
| --------------- | ---------------------------- | --------------------- |
| **django**      | Django dev server            | http://localhost:8000  |
| **postgres**    | PostgreSQL 18 database       | internal              |
| **redis**       | Redis 7.2 (broker/cache)     | internal              |
| **celeryworker**| Celery worker                | —                     |
| **celerybeat**  | Celery beat scheduler        | —                     |
| **flower**      | Celery task monitor          | http://localhost:5555  |
| **mailpit**     | Local email testing server   | http://localhost:8025  |

### Common Commands

```bash
# View logs
./local.sh logs -f

# Stop all services
./local.sh down

# Restart a single service
./local.sh restart django

# Run a management command
./local.sh exec django uv run python manage.py migrate

# Create a superuser
./local.sh exec django uv run python manage.py createsuperuser

# Open a Django shell
./local.sh exec django uv run python manage.py shell
```

`./local.sh` is a thin wrapper around `docker-compose -f docker-compose.local.yml` — any valid Docker Compose arguments work.

## Running Tests

```bash
# Run the full test suite
./local.sh exec django uv run pytest

# With coverage
./local.sh exec django uv run coverage run -m pytest
./local.sh exec django uv run coverage html
```

## Type Checks

```bash
./local.sh exec django uv run mypy backend
```

## Celery

Celery worker and beat are started automatically as part of `./local.sh up`. Flower is available at http://localhost:5555 to monitor tasks.

To run Celery commands manually inside the container:

```bash
# Worker
./local.sh exec django uv run celery -A config.celery_app worker -l info

# Beat
./local.sh exec django uv run celery -A config.celery_app beat
```

## Email (Mailpit)

Mailpit captures all outgoing emails in development. Browse captured messages at http://localhost:8025.

## Sentry

Sentry is an error logging aggregator service. You can sign up for a free account at <https://sentry.io/signup/?code=cookiecutter> or download and host it yourself. Set the DSN url in production via the environment file.

## Deployment

See the [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/3-deployment/deployment-with-docker.html) for production deployment details.
