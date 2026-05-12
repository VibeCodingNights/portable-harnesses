#!/usr/bin/env bash
# setup.sh — install deps, verify OpenRouter key, health-check four models.
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

# --- venv + deps ---
# Prefer uv when present (faster, sidesteps broken ensurepip on some Pythons).
DEPS=(
  "smolagents[openai]>=1.24"
  "httpx>=0.27"
  "python-dotenv>=1.0"
  "rich>=13.7"
  "jsonschema>=4.21"
  "pyyaml>=6.0"
)
if command -v uv >/dev/null 2>&1; then
  [ -d ".venv" ] || { uv venv .venv >/dev/null && ok "created .venv (uv)"; }
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv pip install --quiet "${DEPS[@]}"
else
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv || fail "venv creation failed. Install uv (brew install uv) or fix python3 -m ensurepip."
    ok "created .venv"
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --quiet --upgrade pip
  pip install --quiet "${DEPS[@]}"
fi
ok "python deps installed"

# --- .env ---
if [ ! -f ".env" ]; then
  cp .env.example .env
  warn "created .env from .env.example — paste your OpenRouter key, then re-run ./setup.sh"
  warn "get a key at https://openrouter.ai/keys (add ~\$10 of credit)"
  exit 0
fi
# shellcheck disable=SC1091
set -a; source .env; set +a

# --- sandbox ---
mkdir -p "${SANDBOX_DIR:-./sandbox}"
mkdir -p results
ok "sandbox at ${SANDBOX_DIR:-./sandbox}"

# --- OpenRouter key present? ---
if [ -z "${OPENROUTER_API_KEY:-}" ] || [[ "${OPENROUTER_API_KEY}" == *"..."* ]]; then
  warn "OPENROUTER_API_KEY not set in .env — skipping model health checks"
  warn "get a key at https://openrouter.ai/keys, paste into .env, re-run ./setup.sh"
  exit 0
fi

# --- key validity (cheap probe) ---
if ! python3 -c "
import os, sys, httpx
r = httpx.get('https://openrouter.ai/api/v1/auth/key',
              headers={'Authorization': f'Bearer {os.environ[\"OPENROUTER_API_KEY\"]}'},
              timeout=10)
sys.exit(0 if r.status_code == 200 else 1)
" 2>/dev/null; then
  fail "OpenRouter rejected the key. Check OPENROUTER_API_KEY in .env."
fi
ok "OpenRouter key valid"

# --- Brave key (optional, only needed for Tasks 2/3 real search) ---
if [ -n "${BRAVE_API_KEY:-}" ]; then
  ok "Brave Search key present (real web_search enabled)"
else
  warn "BRAVE_API_KEY not set — web_search returns stubs. Task 1 works; Tasks 2/3 will be degraded."
fi

# --- health-check the four models via OpenRouter ---
echo "==> health-checking models via OpenRouter"
HEALTH_OK=0
HEALTH_FAIL=0
for model in claude qwen glm kimi; do
  if python3 -c "
import os, sys
from harness.agent import MODEL_SLUGS, LAB_PROVIDERS
from openai import OpenAI
try:
    client = OpenAI(api_key=os.environ['OPENROUTER_API_KEY'], base_url='https://openrouter.ai/api/v1')
    client.chat.completions.create(
        model=MODEL_SLUGS['${model}'],
        messages=[{'role':'user','content':'ping'}],
        max_tokens=4,
        timeout=20,
        extra_body={'provider': {'order': [LAB_PROVIDERS['${model}']], 'allow_fallbacks': False}},
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
  warn "common causes: insufficient credit, model temporarily unavailable on OpenRouter"
else
  fail "0/4 models reachable — check OPENROUTER_API_KEY and account credit at openrouter.ai/credits"
fi
