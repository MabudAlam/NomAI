#!/bin/bash

set -e

cd "$(dirname "$0")"

if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

uv run uvicorn main:app --host "$HOST" --port "$PORT" --reload
