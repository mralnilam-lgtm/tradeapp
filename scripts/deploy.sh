#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
REQ_FILE="${ROOT_DIR}/requirements.txt"
ENV_FILE="${ROOT_DIR}/.env"

PORT="${PORT:-5000}"
WORKERS="${WORKERS:-2}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: .env not found at ${ENV_FILE}"
  echo "Create it first with your API keys."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required but not installed."
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating virtual environment at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

echo "Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

if [[ -f "${REQ_FILE}" ]]; then
  echo "Installing dependencies from ${REQ_FILE}"
  pip install -r "${REQ_FILE}"
else
  echo "ERROR: ${REQ_FILE} not found."
  exit 1
fi

echo "Starting app with gunicorn on port ${PORT} (workers=${WORKERS})"
exec gunicorn \
  --workers "${WORKERS}" \
  --bind "0.0.0.0:${PORT}" \
  --timeout 120 \
  app:app
