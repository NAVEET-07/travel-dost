#!/usr/bin/env bash
set -e

echo "=== [Railway Deploy] Applying database migrations ==="
python manage.py migrate --noinput

echo "=== [Railway Deploy] Collecting static files ==="
python manage.py collectstatic --noinput

echo "=== [Railway Deploy] Starting Daphne ASGI Server on port ${PORT:-8000} ==="
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" travel_dost_backend.asgi:application
