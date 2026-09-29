#!/usr/bin/env bash
# Rebuild the local environment and serve the portal preview.
# A sandbox reset wipes .venv, node_modules, frontend/dist and the dev
# database; this script brings everything back in one command:
#
#   ./scripts/serve-preview.sh
#
# The portal accounts are created from PORTAL_BOOTSTRAP_* env vars, so a
# fresh database needs no migration step. Set PORTAL_DEMO_MODE=true to
# skip sign-in entirely (sandbox/preview convenience only).
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8080}"
export PORTAL_PUBLIC_ORIGIN="${PORTAL_PUBLIC_ORIGIN:-}"
export PORTAL_ALLOW_FRAMING="${PORTAL_ALLOW_FRAMING:-true}"
export PORTAL_DEMO_MODE="${PORTAL_DEMO_MODE:-true}"
export PORTAL_AUTH_RATE_LIMIT_ATTEMPTS="${PORTAL_AUTH_RATE_LIMIT_ATTEMPTS:-20}"
export PORTAL_BOOTSTRAP_OPERATOR_USERNAME="${PORTAL_BOOTSTRAP_OPERATOR_USERNAME:-operator}"
export PORTAL_BOOTSTRAP_OPERATOR_PASSWORD="${PORTAL_BOOTSTRAP_OPERATOR_PASSWORD:-supersecret1}"
export PORTAL_BOOTSTRAP_DEVELOPER_USERNAME="${PORTAL_BOOTSTRAP_DEVELOPER_USERNAME:-pixiedev}"
export PORTAL_BOOTSTRAP_DEVELOPER_PASSWORD="${PORTAL_BOOTSTRAP_DEVELOPER_PASSWORD:-devpassword1}"
export DATABASE_PATH="${DATABASE_PATH:-./provider.db}"

if [ ! -x .venv/bin/uvicorn ]; then
  echo "==> creating .venv and installing backend deps"
  python3 -m venv .venv
  .venv/bin/pip install -q -e .
fi

if [ ! -d frontend/node_modules ]; then
  echo "==> installing frontend deps"
  (cd frontend && npm ci --silent)
fi

if [ ! -f frontend/dist/index.html ]; then
  echo "==> building frontend"
  (cd frontend && npm run build)
fi

echo "==> serving on http://0.0.0.0:${PORT} (demo mode: ${PORTAL_DEMO_MODE})"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
