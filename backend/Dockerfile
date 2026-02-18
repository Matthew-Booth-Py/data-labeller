# Unstructured Unlocked Backend
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    poppler-utils \
    ocrmypdf \
    tesseract-ocr \
    tesseract-ocr-eng \
    unpaper \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy ONLY dependency files first (for caching)
COPY pyproject.toml .
COPY .python-version .
COPY README.md .
COPY settings.yml .

# Create a minimal stub for the package so uv sync can work
RUN mkdir -p src/uu_backend && \
    echo '"""Stub for dependency installation."""' > src/uu_backend/__init__.py

# Install dependencies with UV (this layer will be cached if pyproject.toml hasn't changed)
RUN uv sync --no-dev

# Now copy the actual source code (this invalidates only from here)
COPY src/ ./src/

# Copy sample documents for tutorial
COPY sample_docs/ ./sample_docs/
COPY manage.py ./manage.py

# Reinstall just the local package (fast - dependencies are already cached)
RUN uv sync --no-dev

# Create data directory
RUN mkdir -p /app/data/chroma

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CHROMA_PERSIST_DIRECTORY=/app/data/chroma

# Expose port
EXPOSE 8000

# Run migrations then start the application
CMD ["sh", "-c", "uv run python manage.py migrate && uv run uvicorn uu_backend.asgi_dispatcher:application --host 0.0.0.0 --port 8000 --workers 4"]
