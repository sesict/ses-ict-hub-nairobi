#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" == "--attach" ]]; then
  exec node "$PROJECT_ROOT/scripts/client-domains.mjs" attach-www
fi
exec node "$PROJECT_ROOT/scripts/client-domains.mjs" stage-www
