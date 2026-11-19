#!/bin/sh
# Запуск бэкенда в контейнере: сначала миграции, затем сервер.
set -e

python -m alembic upgrade head

# ROOT_PATH=/api нужен, когда перед бэкендом стоит прокси, который отрезает префикс /api (Swagger строит правильные адреса)
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --root-path "${ROOT_PATH:-}" --proxy-headers --forwarded-allow-ips "*"
