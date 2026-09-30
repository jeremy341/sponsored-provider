#!/usr/bin/env bash
# Reseed demo data after a sandbox reset (idempotent, safe to re-run).
# Usage: BASE_URL=http://127.0.0.1:8080 ORIGIN=https://<preview-host> ./scripts/reseed-demo.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
ORIGIN="${ORIGIN:-${PORTAL_PUBLIC_ORIGIN:-http://127.0.0.1:8080}}"
JAR="/tmp/portal-operator.cookies"
DEV_JAR="/tmp/portal-developer.cookies"

csrf_from() { python3 -c "import json,sys;print(json.load(sys.stdin)['csrfToken'])"; }

# --- operator session -------------------------------------------------------
curl -sf -H "Origin: $ORIGIN" "$BASE_URL/api/session" -c "$JAR" >/dev/null
CSRF=$(curl -sf -H "Origin: $ORIGIN" "$BASE_URL/api/session" -b "$JAR" | csrf_from)

guardrails=$(curl -s -X PATCH "$BASE_URL/api/operator/guardrails" \
  -H "Origin: $ORIGIN" -H "X-CSRF-Token: $CSRF" -H "Content-Type: application/json" \
  -b "$JAR" -w "\n%{http_code}" -d '{"globalSpendCapUsd":25,"safetyReserveUsd":2.5,"globalStopped":false}')
[ "$(echo "$guardrails" | tail -1)" = "200" ] || { echo "guardrails failed: $guardrails" >&2; exit 1; }

blocked=$(curl -s -X POST "$BASE_URL/api/operator/blocked-ips" \
  -H "Origin: $ORIGIN" -H "X-CSRF-Token: $CSRF" -H "Content-Type: application/json" \
  -b "$JAR" -w "\n%{http_code}" -d '{"ip":"203.0.113.24","reason":"Observed request abuse"}')
[ "$(echo "$blocked" | tail -1)" = "201" ] || echo "blocked-ip skipped: $(echo "$blocked" | head -1)" >&2

# --- developer session + sample keys ---------------------------------------
curl -sf -H "Origin: $ORIGIN" "$BASE_URL/api/session?as=developer" -c "$DEV_JAR" >/dev/null
DCSRF=$(curl -sf -H "Origin: $ORIGIN" "$BASE_URL/api/session" -b "$DEV_JAR" | csrf_from)

for payload in '{"label":"OpenCode laptop"}' '{"label":"CI runner","rpmLimit":10}'; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/developer/keys" \
    -H "Origin: $ORIGIN" -H "X-CSRF-Token: $DCSRF" -H "Content-Type: application/json" \
    -b "$DEV_JAR" -d "$payload")
  [ "$code" = "201" ] || [ "$code" = "200" ] || echo "key create returned $code" >&2
done

echo "Reseed complete (guardrails, blocked IP demo entry, 2 developer keys)."
