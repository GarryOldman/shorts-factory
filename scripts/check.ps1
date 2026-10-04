# Полная локальная проверка = то же, что в CI: линтер, формат, тесты + покрытие >= 80%
$ErrorActionPreference = "Stop"
ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
ruff format --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
pytest -m "not slow and not gpu"
exit $LASTEXITCODE
