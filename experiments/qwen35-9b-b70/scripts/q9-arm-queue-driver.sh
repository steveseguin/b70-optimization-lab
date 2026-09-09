#!/usr/bin/env bash
# Queue-driven arm runner for the open-ended Qwen3.5-9B campaign.
#
# Reads a TSV queue and runs arms across the four cards, PARALLELISM at a time. The queue is
# append-friendly: new rungs can be added while the driver is running, so the lever ladder can grow
# as results come in without rewriting a chain script. An arm whose campaign root already exists is
# skipped, which makes the driver safe to restart.
#
# Queue format, tab-separated, '#' comments and blank lines ignored:
#   run_label <TAB> depth <TAB> stages <TAB> harness_env <TAB> extra_env
# harness_env is a space-separated KEY=VALUE list of variables the harness itself names
#   (GDN_SPEC_GROUP, W4A16_PAD, RMSNORM_SERIAL_ROWS, GPU_MEMORY_UTILIZATION, LADDER_*, ...).
# extra_env is a space-separated KEY=VALUE list of container knobs the harness does NOT name; it is
#   forwarded as EXTRA_ENV and each entry is verified inside the container, so a knob that never
#   arrives aborts the arm instead of producing a clean null. Example:
#   a2scr	3	strict	""	VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
#
# PARALLELISM=1 gives a quiet host, which is what a timed row requires.
set -uo pipefail
REPO=/home/steve/llm-optimizations
H=$REPO/experiments/qwen35-9b-b70/scripts/run-20260909-qwen35-campaign-v3.sh
QUEUE=${QUEUE:-$REPO/experiments/qwen35-9b-b70/data/q9-arm-queue.tsv}
PARALLELISM=${PARALLELISM:-4}
LANE=${LANE:-qwen35-9b-w4a16}
MODEL=${MODEL:-/home/steve/llm-models/qwen35-9b-w4a16}
MANIFEST=${MANIFEST:-$REPO/experiments/qwen35-9b-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json}
OUT=/mnt/fast-ai/bench-results
LOGDIR=$OUT/chain-logs; mkdir -p "$LOGDIR"
LOG=$LOGDIR/q9-queue-driver.log
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) queue driver start (queue=$QUEUE parallelism=$PARALLELISM lane=$LANE) ==="

declare -A CARD_PID=()   # card -> pid of the arm holding it

card_port_free() {
  local p=$((18131 + $1))
  ! ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":${p}\$"
}

free_card() {
  local c
  while :; do
    for c in 0 1 2 3; do
      local p=${CARD_PID[$c]:-}
      if [[ -z "$p" ]] || ! kill -0 "$p" 2>/dev/null; then
        local running=0 k
        for k in "${!CARD_PID[@]}"; do
          local q=${CARD_PID[$k]:-}
          [[ -n "$q" ]] && kill -0 "$q" 2>/dev/null && running=$((running+1))
        done
        (( running < PARALLELISM )) && card_port_free "$c" && { echo "$c"; return 0; }
      fi
    done
    sleep 20
  done
}

run_arm() {
  local run=$1 depth=$2 stages=$3 card=$4 harness_env=$5 extra_env=$6
  local port=$((18131 + card))
  local envs=(RUN="$run" LANE="$LANE" TP=1 DEPTH="$depth" GRAPH=1 DRAFT_HEAD=1
              STAGES="$stages" PORT="$port" XPU_DEVICE_MASK="$card" ARM_DEVICES="$card"
              MODEL_DIR="$MODEL" MODEL_MANIFEST="$MANIFEST" QUANT=compressed-tensors
              CAMPAIGN_DATE=20260909)
  local kv
  for kv in $harness_env; do envs+=("$kv"); done
  [[ -n "$extra_env" ]] && envs+=(EXTRA_ENV="$extra_env")
  echo "$(date -u +%FT%TZ) START arm=$run depth=$depth stages='$stages' card=$card port=$port harness_env='$harness_env' extra_env='$extra_env'"
  env "${envs[@]}" bash "$H" >"$LOGDIR/q9-arm-$run.log" 2>&1
  local rc=$?
  local why=""
  [[ $rc -ne 0 ]] && why=" reason='$(grep -o 'ABORT: .*' "$LOGDIR/q9-arm-$run.log" 2>/dev/null | tail -1 | cut -c1-120)'"
  echo "$(date -u +%FT%TZ) END   arm=$run exit=$rc$why"
}

processed=0
while IFS= read -r line || [[ -n "$line" ]]; do
  line=${line%%#*}
  [[ -z "${line// /}" ]] && continue
  IFS=$'\t' read -r run depth stages harness_env extra_env <<<"$line"
  [[ -z "${run:-}" || -z "${depth:-}" ]] && continue
  harness_env=${harness_env:-}; extra_env=${extra_env:-}
  # Skip an arm whose root already exists: the harness refuses a reused root anyway, and this makes
  # the driver restartable after an interrupt.
  shopt -s nullglob
  existing=("$OUT/${LANE}-tp1-mtp${depth}-graph1-dhint4"*"-20260909-${run}")
  shopt -u nullglob
  if (( ${#existing[@]} > 0 )); then echo "$(date -u +%FT%TZ) SKIP arm=$run (root exists)"; continue; fi
  card=$(free_card)
  run_arm "$run" "$depth" "$stages" "$card" "$harness_env" "$extra_env" &
  CARD_PID[$card]=$!
  processed=$((processed+1))
  sleep 5
done < "$QUEUE"

for k in "${!CARD_PID[@]}"; do p=${CARD_PID[$k]:-}; [[ -n "$p" ]] && wait "$p" 2>/dev/null; done
echo "=== $(date -u +%FT%TZ) queue driver done; $processed arms dispatched ==="
echo "Q9-QUEUE-DONE"
