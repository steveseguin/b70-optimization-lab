#!/usr/bin/env bash
# Edge check for the sliced prompt steps (registered in notes/2026-10-14-lfm25-24b-a2b-bringup.md, 2026-10-15 21:05):
# raw token prompts whose last 512-token piece is a few tokens long (the multi-token and one-token expert paths), on
#   ref     the v3 package build, serve.sh fast (-ub 512)                         REF_BUILD
#   sliced  the work build, serve.sh fast with -ub 2048 + LLAMA_SYCL_PREFILL_SLICE=512 + LLAMA_SYCL_PREFILL_SLICE_FA=1
# 64 tokens each, greedy, top-8 logprobs; pass = bit-exact. Card 1, Gemma on card 0 meanwhile, restored on exit.
#   REF_BUILD=... BUILD_DIR=... slice-edge-check.sh       (under systemd-run --user; SUDO_ASKPASS for the Gemma switch)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
PKG=$LAB/repro/lfm25-24b-a2b-q8-b70
E=$LAB/experiments/lfm25-24b-a2b-b70
PROBE=/mnt/fast-ai/bench-results/lfm25-24b-a2b/probe
REF_BUILD=${REF_BUILD:?}
BUILD_DIR=${BUILD_DIR:?}
MODEL_DIR=${MODEL_DIR:-/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf}
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b/slice-edge-20261015}
LENGTHS=${LENGTHS:-513,516,520,1029,1543,2047,2048,2049,2052,2056,4103,6151,8200}
PORT=18110
UNIT=lfm25-edge-srv
mkdir -p "$OUT"
log() { echo "### $(date +%T) $*"; }
START=$(date '+%Y-%m-%d %H:%M:%S')
restore() {
  systemctl --user stop $UNIT 2>/dev/null
  log "restoring Gemma's two-card throughput recipe"
  "$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput 2>&1 | grep -v "JSONDecode\|raise " | tail -3
  journalctl -k --since "$START" --no-pager -o cat | grep -iE 'xe .*(fault|reset|error)|GT[0-9]*: .*reset' | head -5 || true
  log done
}
trap restore EXIT
log "moving Gemma to card 0 (throughput-card0)"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -2

sed "s/-ub 512 /-ub 2048 /" "$PKG/serve.sh" > "$OUT/serve-sliced.sh"
grep -q -- "-ub 2048 " "$OUT/serve-sliced.sh" || { log "could not set -ub 2048"; exit 1; }
chmod +x "$OUT/serve-sliced.sh"
for run in ref sliced; do
  if [[ $run == ref ]]; then
    build=$REF_BUILD; script=$PKG/serve.sh; extra=()
  else
    build=$BUILD_DIR; script=$OUT/serve-sliced.sh
    extra=(-E LLAMA_SYCL_PREFILL_SLICE=512 -E LLAMA_SYCL_PREFILL_SLICE_FA=1)
  fi
  for _ in $(seq 1 120); do [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && break; sleep 1; done
  systemctl --user reset-failed $UNIT 2>/dev/null
  systemd-run --user --unit=$UNIT --collect -p WorkingDirectory=$LAB -E BUILD_DIR="$build" -E MODEL_DIR="$MODEL_DIR" \
    -E GPU=1 -E PORT=$PORT "${extra[@]}" bash -c "exec $script fast > $OUT/server-$run.log 2>&1" >/dev/null
  ok=0
  for i in $(seq 1 240); do
    curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { log "$run ready after ${i}s"; ok=1; break; }
    systemctl --user is-active --quiet $UNIT || { log "$run server died"; tail -5 "$OUT/server-$run.log"; break; }
    sleep 1
  done
  [[ $ok == 1 ]] || exit 1
  log "$run: raw token prompts of $LENGTHS tokens"
  python3 "$E/scripts/identity_probe.py" run --prompts "$PROBE/long-prompts.json" --token-lengths "$LENGTHS" \
    --tokens 64 --out "$OUT/edge-$run.json" 2>&1 | tail -2
  systemctl --user stop $UNIT
  for _ in $(seq 1 30); do systemctl --user is-active --quiet $UNIT || break; sleep 1; done
done
log "sliced vs ref"
python3 "$E/scripts/identity_probe.py" diff "$OUT/edge-ref.json" "$OUT/edge-sliced.json" 2>&1 | tail -2
