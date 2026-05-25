#!/bin/bash
set -e

case "$1" in
  serve)
    echo "Starting StaffHub API server..."
    exec gunicorn src.main:app \
      -w "${WORKERS:-4}" \
      -k uvicorn.workers.UvicornWorker \
      --bind 0.0.0.0:8000 \
      --access-logfile - \
      --error-logfile -
    ;;

  migrate)
    echo "Running database migrations..."
    cd /app/db
    python -m alembic upgrade head
    echo "Migrations complete."
    ;;

  seed-admin)
    echo "Seeding admin user..."
    cd /app
    python -m scripts.seed_admin
    echo "Admin seed complete."
    ;;

  seed-mock)
    echo "Seeding mock data..."
    cd /app
    python -m scripts.seed_mock_data
    echo "Mock data seed complete."
    ;;

  seed-full)
    echo "Seeding comprehensive mock data..."
    cd /app
    python -m scripts.seed_mock_data
    python -m scripts.seed_comprehensive_mock
    echo "Full mock data seed complete."
    ;;

  expire-reservations)
    echo "Running reservation expiry job..."
    cd /app
    python -m scripts.expire_reservations
    echo "Expiry job complete."
    ;;

  *)
    exec "$@"
    ;;
esac
