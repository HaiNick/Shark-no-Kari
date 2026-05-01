#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-https://kari.snowy-burbot.com}"

echo "==> Protected resource metadata"
curl -fsS "$BASE/.well-known/oauth-protected-resource" | jq

echo ""
echo "==> Authorization server metadata"
curl -fsS "$BASE/.well-known/oauth-authorization-server" | jq

echo ""
echo "==> Unauthenticated /mcp must 401 with WWW-Authenticate"
curl -isS "$BASE/mcp" -X POST \
     -H 'Content-Type: application/json' \
     -H 'Accept: application/json' \
     --data '{"jsonrpc":"2.0","id":1,"method":"initialize"}' \
     | grep -i www-authenticate
