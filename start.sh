#!/bin/bash

# Ensure environment variables are set
export PORT=${PORT:-10000}

# Start gunicorn with memory-optimized settings
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 2 \
    --timeout 120 \
    --log-level info \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --preload
