#!/usr/bin/env bash
# Prompt-reading (prefill) check for LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED (registered in
# notes/2026-10-14-lfm25-24b-a2b-bringup.md, 2026-10-15): card 1, Gemma on card 0 meanwhile, restored at the end.
#   A. llama-bench: combined pp2048+tg128 sweeps with the old and the new reordered-Q8_0 dequant, and a pp-only sweep
#      (weights never reordered), to show whether the "pp after the first point reads low" effect is the reorder
#   B. what a server delivers: prompt rate reported by llama-server (serve.sh fast) for the 2K/8K/24K prompts, old vs
#      new dequant, after the server's own warm-up (which reorders the weights)
#   C. identity: a verify server (=2: every reordered dequant also run on the old kernel and compared byte for byte)
#      over the logprob probe and long prompts, then two fresh fast servers with the new dequant: the 12-prompt suite
#      vs R0, and the probe and long prompts vs R0
#   BUILD_DIR=... prefill-reorder-check.sh      (SUDO_ASKPASS set; under systemd-run --user)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
E=$LAB/experiments/lfm25-24b-a2b-b70
PKG=$LAB/repro/lfm25-24b-a2b-q8-b70
BUILD_DIR=${BUILD_DIR:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25}
MODEL_DIR=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b/prefill-reorder}
PROBE=/mnt/fast-ai/bench-results/lfm25-24b-a2b/probe
FLAG=LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED
PORT=18110
UNIT=lfm25-prefill-srv
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
  for kv in "$@"; do envs+=(-E "$kv"); done
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
bench() {  # NAME FLAG_VALUE LLAMA_BENCH_ARGS...
  local name=$1 val=$2; shift 2
  wait_port_free
  (
    set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null; set -u
    env ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
      GGML_SYCL_DNNL_DETERMINISTIC=1 GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_PRIORITIZE_DMMV=1 \
      LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4 LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1 \
      LLAMA_SYCL_FUSE_RMS_NORM_MUL=1 LLAMA_SYCL_FUSE_ADD_RMS_NORM_MUL=1 LLAMA_SYCL_FUSE_MOE_SUM=1 \
      LLAMA_SYCL_FUSE_MOE_ROUTE=1 LLAMA_SYCL_FUSE_SHORTCONV=1 LLAMA_SYCL_FUSE_F16_SHADOW=1 LLAMA_SYCL_FUSE_Q8_SHADOW=1 \
      LLAMA_SYCL_FUSE_MOE_GATE_UP=1 LLAMA_SYCL_FUSE_NORM_ROPE=1 LLAMA_SYCL_FUSE_NORM_Q8=1 LLAMA_SYCL_FUSE_MOE_DOWN_SUM=1 \
      LLAMA_SYCL_FUSE_CONV_STATE_ROWS=1 $FLAG=$val \
      timeout 1200 "$BUILD_DIR/bin/llama-bench" -m "$MODEL_DIR/LFM2.5-24B-A2B-Q8_0.gguf" -ngl 99 -fa 1 -ctk f16 -ctv f16 \
      -b 2048 -ub 512 -t 8 --poll 50 "$@" -o json > "$OUT/bench-$name.json" 2> "$OUT/bench-$name.err"
    echo "llama-bench $name rc=$?"
  )
  python3 - "$OUT/bench-$name.json" "$name" <<'EOF'
import json, sys
try:
    rows = json.load(open(sys.argv[1]))
except Exception as exc:
    print(sys.argv[2], "unreadable:", exc); raise SystemExit
print(sys.argv[2] + ": " + ", ".join(
    f'{"pp" if r["n_prompt"] else "tg"}@{r["n_depth"]} {r["avg_ts"]:.1f}' for r in rows))
EOF
}
server_prefill() {  # NAME: prompt rate the server reports, each long prompt twice
  python3 - "$PROBE/long-prompts.json" "http://127.0.0.1:$PORT" "$OUT/prefill-$1.json" "$1" <<'EOF'
import json, sys, urllib.request
prompts, base, out, name = json.load(open(sys.argv[1]))["prompts"], sys.argv[2], sys.argv[3], sys.argv[4]
rows = []
for rep in (1, 2):
    for p in sorted(prompts, key=lambda p: len(p["prompt"])):
        req = urllib.request.Request(base + "/completion", data=json.dumps({
            "prompt": p["prompt"], "n_predict": 1, "temperature": 0, "cache_prompt": False}).encode(),
            headers={"Content-Type": "application/json"})
        t = json.load(urllib.request.urlopen(req, timeout=900))["timings"]
        rows.append({"id": p["id"], "rep": rep, "prompt_n": t["prompt_n"], "prompt_ms": t["prompt_ms"],
                     "prompt_per_second": t["prompt_per_second"]})
        print(f'{name} {p["id"]} rep {rep}: {t["prompt_n"]} tokens, {t["prompt_per_second"]:.1f} tok/s')
json.dump(rows, open(out, "w"), indent=1)
EOF
}

log "moving Gemma to card 0 (throughput-card0)"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -2

log "A. llama-bench (3 reps each)"
bench combined-old 0 -p 2048 -n 128 -d 0,2048,8192 -r 3
bench combined-new 1 -p 2048 -n 128 -d 0,2048,8192 -r 3
bench pponly 0 -p 2048 -n 0 -d 0,2048,8192 -r 3
bench tgonly-new 1 -p 0 -n 128 -d 0 -r 3

log "B. prompt rate a server delivers, old then new dequant"
serve prefill-old $FLAG=0 || exit 1
server_prefill old
stop_server
serve prefill-new $FLAG=1 || exit 1
server_prefill new
stop_server

log "C. identity: verify server ($FLAG=2)"
serve verify $FLAG=2 || exit 1
python3 "$E/scripts/identity_probe.py" run --out "$OUT/probe-verify.json" 2>&1 | tail -1
python3 "$E/scripts/identity_probe.py" run --prompts "$PROBE/long-prompts.json" --tokens 128 --out "$OUT/long-verify.json" 2>&1 | tail -1
stop_server
echo "verify mismatched calls: $(grep -c 'Q8_0_REORDER_DEQ_VERIFY mismatch' "$OUT/server-verify.log")"
grep 'Q8_0_REORDER_DEQ_VERIFY calls' "$OUT/server-verify.log" | tail -1
for name in a b; do
  serve "$name" $FLAG=1 || exit 1
  log "$name: suite"
  RESULTS_DIR=$OUT PORT=$PORT "$PKG/check.sh" run "suite-$name" 2>&1 | grep -v "^Against\|^compiler"
  if [[ $name == b ]]; then
    log "b: probe + long probe"
    python3 "$E/scripts/identity_probe.py" run --out "$OUT/probe-b.json" 2>&1 | tail -1
    python3 "$E/scripts/identity_probe.py" run --prompts "$PROBE/long-prompts.json" --tokens 128 --out "$OUT/long-b.json" 2>&1 | tail -1
  fi
  stop_server
done
log "logprob identity vs R0 (probe), and long prompts vs R0"
python3 "$E/scripts/identity_probe.py" diff "$PROBE/r0-prod.json" "$OUT/probe-verify.json" "$OUT/probe-b.json" 2>&1 | tail -3
python3 "$E/scripts/identity_probe.py" diff "$PROBE/long-r0.json" "$OUT/long-verify.json" "$OUT/long-b.json" 2>&1 | tail -3
