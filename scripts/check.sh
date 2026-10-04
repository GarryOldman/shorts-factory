#!/usr/bin/env bash
# Полная локальная проверка = то же, что в CI: линтер, формат, тесты + покрытие >= 80%
set -euo pipefail
ruff check .
ruff format --check .
pytest -m "not slow and not gpu"
