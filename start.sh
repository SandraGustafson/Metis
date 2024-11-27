#!/bin/bash

# Activate Python virtual environment
source $VIRTUAL_ENV/bin/activate

# Add virtual environment to PATH
export PATH="$VIRTUAL_ENV/bin:$PATH"
export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Verify gunicorn installation
which gunicorn || pip install gunicorn

# Start gunicorn with debug logging
exec gunicorn app:app --bind 0.0.0.0:$PORT --log-level debug
