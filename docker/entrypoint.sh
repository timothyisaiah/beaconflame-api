#!/bin/sh
set -e
if [ "${RUN_MIGRATE_ON_START:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi
exec "$@"
