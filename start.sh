#!/bin/bash

# Activate the Python virtual environment
source /opt/render/project/.venv/bin/activate

# Add virtual environment to PATH
export PATH="/opt/render/project/.venv/bin:$PATH"
export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Start gunicorn with debug logging
exec gunicorn app:app --bind 0.0.0.0:$PORT --log-level debug
