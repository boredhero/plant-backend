#!/bin/bash
set -e
exec gunicorn wsgi:app \
    --bind 0.0.0.0:5050 \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
