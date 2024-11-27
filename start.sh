#!/bin/bash
export PATH="/opt/render/project/.venv/bin:$PATH"
export PYTHONPATH="${PYTHONPATH}:${PWD}"
gunicorn app:app --bind 0.0.0.0:$PORT --log-level debug
