#!/usr/bin/env bash
# bench.sh — run all tasks × all models, output a comparison table.
#
#   ./bench.sh naive             passthrough adapter for everyone (baseline)
#   ./bench.sh adapted           model-specific adapter when one exists
#   ./bench.sh both              both, side-by-side
#   ./bench.sh <mode> --force    bypass run_id cache and re-run every cell
set -euo pipefail

MODE="${1:-naive}"
FORCE_FLAG=""
if [[ "${2:-}" == "--force" ]]; then
  FORCE_FLAG="--force"
fi
MODELS=(claude qwen glm kimi)
TASKS=(1 2 3)

# shellcheck disable=SC1091
source .venv/bin/activate

run_cell() {
  local task="$1" model="$2" adapter="$3"
  python run.py --task "${task}" --model "${model}" --adapter "${adapter}" ${FORCE_FLAG} \
    --out "results/task${task}-${model}-${adapter}.json" >/dev/null 2>&1 || true
  python -c "
import json, sys
r = json.load(open('results/task${task}-${model}-${adapter}.json'))
mark = '✓' if r['completed'] else '✗'
hits = (r.get('alignment') or {}).get('anchor_hits') or []
anchor_summary = ''.join('✓' if h['satisfied'] else '✗' for h in hits) or '-'
print(f\"{r['task']:>4} | {r['model']:<10} | {r['adapter']:<11} | {mark:<9} | {r['tool_calls']:<10} | {r['errors']:<6} | {r['loops']:<5} | {anchor_summary}\")
" 2>/dev/null || echo "  ${task} | ${model:<10} | ${adapter:<11} | ERR       | -          | -      | -     | -"
}

print_header() {
  echo
  echo "Task | Model      | Adapter     | Completed | Tool Calls | Errors | Loops | Anchors"
}

case "${MODE}" in
  naive)
    print_header
    for t in "${TASKS[@]}"; do for m in "${MODELS[@]}"; do
      run_cell "$t" "$m" passthrough
    done; done
    ;;
  adapted)
    print_header
    for t in "${TASKS[@]}"; do for m in "${MODELS[@]}"; do
      run_cell "$t" "$m" "$m"
    done; done
    ;;
  both)
    print_header
    for t in "${TASKS[@]}"; do for m in "${MODELS[@]}"; do
      run_cell "$t" "$m" passthrough
      run_cell "$t" "$m" "$m"
    done; done
    ;;
  *)
    echo "usage: ./bench.sh [naive|adapted|both]"; exit 2;;
esac

echo
echo "Per-cell records under results/. The delta between passthrough and adapted is the portability tax."
