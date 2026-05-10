#!/usr/bin/env bash
# setup.sh — install deps, verify proxy, health-check four models.
# Four green checkmarks = ready.
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[!!]${NC} $*"; }
fail() { echo -e "${RED}[XX]${NC} $*"; exit 1; }

echo "==> Portability Tax — setup"

# --- Python ---
if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 not found. Install Python 3.10+."
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
ok "python ${PY_VER}"

# --- venv ---
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  ok "created .venv"
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- deps ---
pip install --quiet --upgrade pip
pip install --quiet \
  "litellm>=1.50.0" \
  "httpx>=0.27" \
  "python-dotenv>=1.0" \
  "rich>=13.7" \
  "jsonschema>=4.21" \
  "pyyaml>=6.0"
ok "python deps installed"

# --- .env ---
if [ ! -f ".env" ]; then
  cp .env.example .env
  warn "created .env from .env.example — set PROXY_TOKEN before running tasks"
fi
# shellcheck disable=SC1091
set -a; source .env; set +a

# --- sandbox ---
mkdir -p "${SANDBOX_DIR:-./sandbox}"
mkdir -p results
ok "sandbox at ${SANDBOX_DIR:-./sandbox}"

# --- node (for MCP tool servers, if attendees want to run them locally) ---
if command -v node >/dev/null 2>&1; then
  ok "node $(node --version) (optional — proxy hosts MCP servers)"
else
  warn "node not found — using proxy-hosted MCP servers (fine for tonight)"
fi

# --- proxy reachability ---
if [ -z "${PROXY_TOKEN:-}" ] || [ "${PROXY_TOKEN}" = "vcn-attendee-XXXXXXXX" ]; then
  warn "PROXY_TOKEN not set in .env — skipping model health checks"
  warn "Get a token from a host, then re-run ./setup.sh"
  exit 0
fi

echo "==> health-checking models via ${PROXY_URL}"
HEALTH_OK=0
HEALTH_FAIL=0
for model in claude qwen glm kimi; do
  if python3 -c "
import os, sys
from litellm import completion
try:
    r = completion(
        model='openai/${model}',
        messages=[{'role':'user','content':'ping'}],
        api_base=os.environ['PROXY_URL'],
        api_key=os.environ['PROXY_TOKEN'],
        max_tokens=4,
        timeout=15,
    )
    sys.exit(0)
except Exception as e:
    print(f'  {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
    ok "${model}"
    HEALTH_OK=$((HEALTH_OK+1))
  else
    warn "${model} unreachable"
    HEALTH_FAIL=$((HEALTH_FAIL+1))
  fi
done

echo
if [ "${HEALTH_OK}" -eq 4 ]; then
  ok "all four models reachable — you're ready"
  echo
  echo "Try:  python run.py --task 1 --model claude"
elif [ "${HEALTH_OK}" -ge 1 ]; then
  warn "${HEALTH_OK}/4 models reachable — proceed but expect failures on the unreachable ones"
else
  fail "0/4 models reachable — check PROXY_URL and PROXY_TOKEN in .env, then ask a host"
fi
