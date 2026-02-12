#!/bin/bash
# Run the auto claim integration test with real OpenAI API
#
# Usage: 
#   ./tests/run_integration_test.sh
#
# This script will use environment variables from your shell or .env file

cd "$(dirname "$0")/.."

echo "Running integration test with real database and OpenAI API..."
echo "Note: This requires Neo4j running and the auto claim document to be ingested"
echo ""

uv run pytest tests/test_qa_service.py::test_auto_claim_real_retriever -v -s -m integration
