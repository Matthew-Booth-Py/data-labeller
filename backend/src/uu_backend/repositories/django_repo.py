"""Django ORM-backed repository adapter (phase scaffolding)."""


class DjangoORMRepository:
    """Repository adapter placeholder for future ORM implementation."""

    def health(self) -> dict:
        return {
            "backend": "django",
            "status": "not_implemented",
        }
