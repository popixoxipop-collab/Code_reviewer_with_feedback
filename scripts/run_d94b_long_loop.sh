#!/bin/zsh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

mkdir -p logs
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
LOG="logs/d94b_long_loop_${STAMP}.log"
STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

python3 publish_d94_rerun_status.py \
  --status running \
  --started-at "$STARTED_AT" \
  --log-name "$(basename "$LOG")" \
  --note "Targets: meta/llama-3.3-70b-instruct, nvidia/llama-3.3-nemotron-super-49b-v1.5" \
  --note "Config: llama timeout 360s / workers 1 / rpm 12" \
  --note "Config: nemotron timeout 180s / max_tokens 2048 / workers 1 / rpm 12"

git add docs/d94-rerun-status.json
if ! git diff --cached --quiet; then
  git commit -m "docs(share): mark D94 rerun in progress" || true
  git push origin main || true
fi

if {
  echo "[run_d94b_long_loop] started_at=$STARTED_AT"
  echo "[run_d94b_long_loop] log=$LOG"
  python3 rerun_two_models_fixed_settings.py
} 2>&1 | tee "$LOG"; then
  python3 publish_d94_rerun_status.py \
    --status completed \
    --started-at "$STARTED_AT" \
    --log-name "$(basename "$LOG")"

  git add \
    docs/d94-rerun-status.json \
    turn_engine_grading_16models_sonnet_results.json \
    turn_engine_grading_16models_sonnet_summary.json \
    turn_engine_grading_16models_sonnet_by_lang.json

  if ! git diff --cached --quiet; then
    git commit -m "bench(benchmark): publish D94 two-model rerun results" || true
    git push origin main || true
  fi
else
  python3 publish_d94_rerun_status.py \
    --status failed \
    --started-at "$STARTED_AT" \
    --log-name "$(basename "$LOG")" \
    --note "Long-running rerun failed before publishing refreshed result JSON."

  git add docs/d94-rerun-status.json
  if ! git diff --cached --quiet; then
    git commit -m "docs(share): record D94 rerun failure state" || true
    git push origin main || true
  fi
  exit 1
fi
