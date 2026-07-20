#!/bin/sh
set -e

python /app/scripts/run_migrations.py

cd /app

exec "$@"
