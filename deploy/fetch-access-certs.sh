#!/usr/bin/env bash
# Refresh Cloudflare Access's public signing keys for the learning site.
#
# The site has no route to the internet, so it cannot fetch these itself; this
# runs on the host (deploy/learning-access-certs.timer, daily) and writes them
# where the container reads them. Access rotates keys every few weeks and
# publishes the next one ahead of time, so a daily refresh never falls behind.
#
#   deploy/fetch-access-certs.sh deploy/.env
set -euo pipefail

ENV_FILE="${1:-$(dirname "$0")/.env}"
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${LEARN_ACCESS_ISSUER:?set LEARN_ACCESS_ISSUER in $ENV_FILE}"
: "${LEARN_CERTS_DIR:?set LEARN_CERTS_DIR in $ENV_FILE}"

mkdir -p "$LEARN_CERTS_DIR"
tmp="$(mktemp "$LEARN_CERTS_DIR/.certs.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
curl -fsS --max-time 30 "${LEARN_ACCESS_ISSUER%/}/cdn-cgi/access/certs" -o "$tmp"
python3 -c 'import json, sys; keys = json.load(open(sys.argv[1]))["keys"]; assert keys and all("kid" in k for k in keys)' "$tmp"
chmod 644 "$tmp"
mv "$tmp" "$LEARN_CERTS_DIR/certs.json"
trap - EXIT
echo "refreshed $LEARN_CERTS_DIR/certs.json"
