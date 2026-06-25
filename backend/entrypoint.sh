#!/bin/sh
set -eu

wait_for_database() {
    if [ -z "${DATABASE_HOST:-}" ]; then
        return 0
    fi

    db_port="${DATABASE_PORT:-5432}"
    echo "Waiting for database at ${DATABASE_HOST}:${db_port}..."
    until nc -z "${DATABASE_HOST}" "${db_port}"; do
        sleep 1
    done
    echo "Database is available."
}

wait_for_database

echo "Running database migrations..."
python manage.py migrate --noinput

mode="${1:-dev}"

case "${mode}" in
    dev)
        echo "Starting Django development server on 0.0.0.0:8000..."
        exec python manage.py runserver 0.0.0.0:8000
        ;;
    prod|gunicorn)
        workers="${GUNICORN_WORKERS:-3}"
        echo "Starting Gunicorn on 0.0.0.0:8000 with ${workers} workers..."
        exec gunicorn config.wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers "${workers}" \
            --access-logfile - \
            --error-logfile -
        ;;
    *)
        echo "Running custom command: $*"
        exec "$@"
        ;;
esac
