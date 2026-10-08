#!/usr/bin/env bash
# Smoke-test a running `docker compose` stack through the dashboard, as a browser would.
# Usage: scripts/compose-smoke.sh [dashboard URL] [API URL]
set -euo pipefail

WEB=${1:-http://localhost:3000}
API=${2:-http://localhost:8000}
JAR=$(mktemp)
trap 'rm -f "$JAR"' EXIT

json() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "Waiting for the dashboard…"
for _ in $(seq 1 90); do
  [ "$(status "$WEB/login")" = 200 ] && break
  sleep 2
done
[ "$(status "$WEB/login")" = 200 ] || fail "dashboard did not start"

[ "$(status "$API/livez")" = 200 ] || fail "API liveness"
[ "$(status "$API/projects")" = 401 ] || fail "API answered without credentials"
[ "$(status "$WEB/api/indra/projects")" = 401 ] || fail "dashboard proxy answered while signed out"

echo "Creating the first account…"
code=$(status -c "$JAR" -H 'Content-Type: application/json' \
  -d '{"email":"smoke@example.test","password":"smoke-test-password"}' "$WEB/api/auth/register")
[ "$code" = 201 ] || fail "first sign-up returned $code"
grep -q indra_session "$JAR" || fail "no session cookie"
code=$(status -H 'Content-Type: application/json' \
  -d '{"email":"second@example.test","password":"smoke-test-password"}' "$WEB/api/auth/register")
[ "$code" = 403 ] || fail "second sign-up should be closed, got $code"

echo "Creating a project and starting a session…"
project=$(curl -sf -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"title":"Smoke test"}' "$WEB/api/indra/projects" | json "['id']")
session=$(curl -sf -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"project_id\":\"$project\",\"initial_query\":\"graph neural networks\",\"source_providers\":[\"arxiv\"],\"parameters\":{\"research\":{\"max_papers\":1,\"max_claims\":1,\"max_depth\":0,\"synthesize\":false}}}" \
  "$WEB/api/indra/sessions" | json "['id']")
[ "$(status -b "$JAR" -X POST "$WEB/api/indra/sessions/$session/start")" = 200 ] || fail "start"

echo "Waiting for the research worker to pick up the job…"
for _ in $(seq 1 60); do
  job=$(curl -sf -b "$JAR" "$WEB/api/indra/sessions/$session/state" | json "['jobs'][0]['status']")
  [ "$job" != queued ] && break
  sleep 2
done
[ "$job" != queued ] || fail "no worker leased the research job"
echo "Research job status: $job"

[ "$(status -b "$JAR" "$WEB/api/indra/sessions/$session/map")" != 401 ] || fail "map through proxy"
curl -sf -b "$JAR" "$WEB/api/indra/auth/me" | json "['user']['email']" | grep -q smoke@example.test \
  || fail "signed-in user"
echo "Compose smoke test passed."
