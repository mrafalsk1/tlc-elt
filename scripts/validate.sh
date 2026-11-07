#!/usr/bin/env bash
set -euo pipefail

echo "=== check-env ==="
python scripts/check_env.py

echo ""
echo "=== lint ==="
ruff check scripts dags

echo ""
echo "=== dbt parse (build-check) ==="
dbt build --profiles-dir . --target ci

echo ""
echo "VALIDAÇÃO COMPLETA OK"
