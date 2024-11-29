#!/bin/bash
export PORT=${PORT:-10000}
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export FLASK_ENV=development
exec python3 -m gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 --log-level debug --capture-output --enable-stdio-inheritance --max-requests 1000 --max-requests-jitter 50
