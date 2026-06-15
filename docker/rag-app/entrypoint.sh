#!/bin/sh
set -e

echo "Running database migrations..."

cd /app/models/db_schemes/rag_app_db/
alembic upgrade head

cd /app

exec "$@"