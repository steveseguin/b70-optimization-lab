#!/usr/bin/env bash
# Check one exact-fusion arm on the work-tree build (card 1, Gemma on card 0, restored at the end):
#   1. verify server (fusion + LLAMA_SYCL_FUSE_VERIFY=1, graph dump): the logprob probe; every fused call is also run
#      unfused and compared byte for byte, mismatches counted from the server log
#   2. two fresh fast servers with the fusion: the 12-prompt suite (arrays vs R0 + speed), probe + long probe on the
#      second (logprobs vs R0)
#   FUSE_ENV="LLAMA_SYCL_FUSE_RMS_NORM_MUL=1" TAG=f1 fusion-check.sh      (SUDO_ASKPASS set; under systemd-run --user)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
E=$LAB/experiments/lfm25-24b-a2b-b70
PKG=$LAB/repro/lfm25-24b-a2b-q8-b70
BUILD_DIR=${BUILD_DIR:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25}
MODEL_DIR=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf
FUSE_ENV=${FUSE_ENV:?}
TAG=${TAG:?}
OUT=/mnt/fast-ai/bench-results/lfm25-24b-a2b/fusion/$TAG
PROBE=/mnt/fast-ai/bench-results/lfm25-24b-a2b/probe
PORT=18110
UNIT=lfm25-fuse-srv
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

wait_port_free() {
  for _ in $(seq 1 120); do
    [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && return 0
    sleep 1
  done
  log "port $PORT still busy"; return 1
}
serve() {  # NAME EXTRA_ENV...
  local name=$1; shift
  wait_port_free || return 1
  systemctl --user reset-failed $UNIT 2>/dev/null
  local envs=(-E BUILD_DIR="$BUILD_DIR" -E MODEL_DIR="$MODEL_DIR" -E GPU=1 -E PORT=$PORT)
  for kv in $FUSE_ENV "$@"; do envs+=(-E "$kv"); done
  systemd-run --user --unit=$UNIT --collect -p WorkingDirectory=$LAB "${envs[@]}" \
    bash -c "exec $PKG/serve.sh fast > $OUT/server-$name.log 2>&1" >/dev/null
  for i in $(seq 1 240); do
    curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { log "$name ready after ${i}s"; return 0; }
    systemctl --user is-active --quiet $UNIT || { log "$name server died"; tail -5 "$OUT/server-$name.log"; return 1; }
    sleep 1
  done
  log "$name not ready after 240 s"; return 1
}
stop_server() {
  systemctl --user stop $UNIT
  for _ in $(seq 1 30); do systemctl --user is-active --quiet $UNIT || break; sleep 1; done
}

log "arm $TAG: $FUSE_ENV; moving Gemma to card 0"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -2

rm -f "$OUT/graph.txt"
serve verify LLAMA_SYCL_FUSE_VERIFY=1 LLAMA_SYCL_DUMP_GRAPH="$OUT/graph.txt" || exit 1
log "verify: probe (96 tokens x 12) with byte-compare of every fused call"
python3 "$E/scripts/identity_probe.py" run --out "$OUT/probe-verify.json" 2>&1 | tail -2
log "verify: long prompts"
python3 "$E/scripts/identity_probe.py" run --prompts "$PROBE/long-prompts.json" --tokens 128 --out "$OUT/long-verify.json" 2>&1 | tail -2
stop_server
echo "verify mismatches: $(grep -c 'FUSE_VERIFY mismatch' "$OUT/server-verify.log")"
grep 'FUSE_VERIFY' "$OUT/server-verify.log" | tail -3

servers="a b"
[[ ${VERIFY_ONLY:-0} == 1 ]] && servers=""   # VERIFY_ONLY=1: the verify server only (diagnosis)
for name in $servers; do
  serve "$name" || exit 1
  log "$name: suite"
  RESULTS_DIR=$OUT PORT=$PORT "$PKG/check.sh" run "suite-$name" 2>&1 | grep -v "^Against\|^compiler"
  if [[ $name == b ]]; then
    log "b: probe + long probe"
    python3 "$E/scripts/identity_probe.py" run --out "$OUT/probe-b.json" 2>&1 | tail -1
    python3 "$E/scripts/identity_probe.py" run --prompts "$PROBE/long-prompts.json" --tokens 128 --out "$OUT/long-b.json" 2>&1 | tail -1
  fi
  stop_server
done
if [[ -n ${BENCH_SETS:-} ]]; then
  # speed of each fusion alone: llama-bench -p 0 -n 128 -r 3 on the fast environment, one line per set ("none" = x1)
  log "llama-bench per set"
  set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null; set -u
  IFS=';' read -ra sets <<< "$BENCH_SETS"
  k=0
  for set in "${sets[@]}"; do
    k=$((k + 1))
    env_args=()
    [[ $set != none ]] && read -ra env_args <<< "$set"
    env ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
      GGML_SYCL_DNNL_DETERMINISTIC=1 GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_PRIORITIZE_DMMV=1 \
      LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4 LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1 \
      "${env_args[@]}" "$BUILD_DIR/bin/llama-bench" -m "$MODEL_DIR/LFM2.5-24B-A2B-Q8_0.gguf" -ngl 99 -fa 1 \
      -ctk f16 -ctv f16 -b 2048 -ub 512 -t 8 --poll 50 -p 0 -n 128 -r 3 -o json > "$OUT/bench-$k.json" 2>/dev/null
    python3 -c "
import json; r=json.load(open('$OUT/bench-$k.json'))[0]
print(f'bench $k [$set]: {r[\"avg_ts\"]:.2f} tok/s (sd {r[\"stddev_ts\"]:.2f}), {1000/r[\"avg_ts\"]:.3f} ms/token')" \
      || echo "bench $k [$set]: FAILED"
  done
fi
log "logprob identity vs R0 (probe), and long prompts vs R0"
b_probe=() b_long=()
[[ -f $OUT/probe-b.json ]] && b_probe=("$OUT/probe-b.json")
[[ -f $OUT/long-b.json ]] && b_long=("$OUT/long-b.json")
python3 "$E/scripts/identity_probe.py" diff "$PROBE/r0-prod.json" "$OUT/probe-verify.json" "${b_probe[@]}" 2>&1 | tail -3
python3 "$E/scripts/identity_probe.py" diff "$PROBE/long-r0.json" "$OUT/long-verify.json" "${b_long[@]}" 2>&1 | tail -3
