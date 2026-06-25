#!/bin/sh
set -eu

mode="${1:-dev}"

case "${mode}" in
    dev)
        echo "Starting Next.js development server on 0.0.0.0:3000..."
        exec npm run dev
        ;;
    prod|start)
        if [ ! -d ".next" ]; then
            echo "No production build found; running next build..."
            npm run build
        fi
        echo "Starting Next.js production server on 0.0.0.0:3000..."
        exec npm run start
        ;;
    *)
        echo "Running custom command: $*"
        exec "$@"
        ;;
esac
