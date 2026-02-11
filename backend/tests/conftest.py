"""Test suite defaults and shared fixtures."""

from __future__ import annotations

import os


def pytest_configure(config):
    """Set safe defaults for tests that instantiate OpenAI clients."""
    _ = config
    os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
