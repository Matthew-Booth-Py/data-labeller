#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

check() {
  local method="$1"
  local path="$2"
  local expected_prefix="$3"

  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "${BASE_URL}${path}")
  if [[ "$code" != "$expected_prefix"* ]]; then
    echo "[FAIL] ${method} ${path} -> ${code}"
    exit 1
  fi
  echo "[PASS] ${method} ${path} -> ${code}"
}

echo "Running migration smoke checks against ${BASE_URL}"
check GET "/health" "2"
check GET "/api/v1/documents" "2"
check GET "/api/v1/timeline/range" "2"
check GET "/api/v1/evaluation" "2"
check GET "/api/v1/deployments/projects/tutorial/versions" "2"

echo "Smoke checks complete"
