#!/usr/bin/env bash
# Package check for repro/lfm25-24b-a2b-q8-b70 (registered in notes/2026-10-14-lfm25-24b-a2b-bringup.md, 2026-10-15):
# the package's own serve.sh/check.sh on a build made by its build.sh, card 1, Gemma moved to card 0 meanwhile.
#   BUILD_DIR=... package-check.sh        (run under systemd-run --user; SUDO_ASKPASS for the Gemma recipe switch)
# Runs: reference, unfused (the first version's fast path), fast a, fast b (+ canaries, + the top-8 logprob probe and
# the long prompts vs R0), then a llama-bench depth sweep on the fast path. Gemma's two-card throughput recipe is
# restored on exit, whatever happens.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
PKG=$LAB/repro/lfm25-24b-a2b-q8-b70
E=$LAB/experiments/lfm25-24b-a2b-b70
PROBE=/mnt/fast-ai/bench-results/lfm25-24b-a2b/probe
BUILD_DIR=${BUILD_DIR:?}
MODEL_DIR=${MODEL_DIR:-/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf}
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b/pkgcheck}
PORT=18110
UNIT=lfm25-pkg-srv
mkdir -p "$OUT"
log() { echo "### $(date +%T) $*"; }

restore_gemma() {
  systemctl --user stop $UNIT 2>/dev/null
  log "restoring Gemma's two-card throughput recipe"
  "$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput 2>&1 | tail -4
  journalctl -k --since "$START" --no-pager -o cat | grep -iE 'xe .*(fault|reset|error)|GT[0-9]*: .*reset' | head -5 ||
    true
  log "done"
}
START=$(date '+%Y-%m-%d %H:%M:%S')
trap restore_gemma EXIT

wait_port_free() {
  for _ in $(seq 1 120); do
    [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && return 0
    sleep 1
  done
  log "port $PORT still busy"; return 1
}

serve() {  # MODE NAME
  wait_port_free || return 1
  systemctl --user reset-failed $UNIT 2>/dev/null
  systemd-run --user --unit=$UNIT --collect -p WorkingDirectory=$LAB -E BUILD_DIR="$BUILD_DIR" -E MODEL_DIR="$MODEL_DIR" \
    -E GPU=1 -E PORT=$PORT bash -c "exec $PKG/serve.sh $1 > $OUT/server-$2.log 2>&1" >/dev/null
  for i in $(seq 1 240); do
    curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { log "$2 ($1) ready after ${i}s"; return 0; }
    systemctl --user is-active --quiet $UNIT || { log "$2 server died"; tail -5 "$OUT/server-$2.log"; return 1; }
    sleep 1
  done
  log "$2 not ready after 240 s"; return 1
}

stop_server() {
  systemctl --user stop $UNIT
  for _ in $(seq 1 30); do systemctl --user is-active --quiet $UNIT || break; sleep 1; done
}

log "moving Gemma to card 0 (throughput-card0)"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | tail -4
sleep 5

for run in reference:ref unfused:unfused fast:fast-a fast:fast-b; do
  mode=${run%%:*}; name=${run#*:}
  serve "$mode" "$name" || exit 1
  log "$name: suite"
  RESULTS_DIR=$OUT PORT=$PORT "$PKG/check.sh" run "$name" 2>&1
  if [[ $name == fast-b ]]; then
    log "fast-b: canaries"
    python3 "$LAB/scripts/neural-download-canaries.py" --base-url "http://127.0.0.1:$PORT" --model lfm25-24b-a2b \
      --out "$OUT/canaries-fast-b.json" 2>&1 | tail -3
    log "fast-b: logprob probe (12 x 96 tokens) and long prompts (2K/8K/24K x 128 tokens)"
    python3 "$E/scripts/identity_probe.py" run --out "$OUT/probe-fast-b.json" 2>&1 | tail -1
    python3 "$E/scripts/identity_probe.py" run --prompts "$PROBE/long-prompts.json" --tokens 128 \
      --out "$OUT/long-fast-b.json" 2>&1 | tail -1
    log "fast-b: prompt reading as the server reports it (after the replies above), 2K / 8K / 24K prompts twice"
    python3 - "$PROBE/long-prompts.json" "http://127.0.0.1:$PORT" "$OUT/prompt-rate-fast-b.json" <<'PYEOF'
import json, sys, urllib.request
prompts, base, out = json.load(open(sys.argv[1]))["prompts"], sys.argv[2], sys.argv[3]
rows = []
for rep in (1, 2):
    for p in sorted(prompts, key=lambda p: len(p["prompt"])):
        req = urllib.request.Request(base + "/completion", data=json.dumps({
            "prompt": p["prompt"], "n_predict": 1, "temperature": 0, "cache_prompt": False}).encode(),
            headers={"Content-Type": "application/json"})
        t = json.load(urllib.request.urlopen(req, timeout=900))["timings"]
        rows.append({"id": p["id"], "rep": rep, "prompt_n": t["prompt_n"], "prompt_ms": t["prompt_ms"],
                     "prompt_per_second": t["prompt_per_second"]})
        print(f'{p["id"]} rep {rep}: {t["prompt_n"]} tokens, {t["prompt_per_second"]:.1f} tok/s', flush=True)
json.dump(rows, open(out, "w"), indent=1)
PYEOF
  fi
  stop_server
done
log "fast a vs fast b, and the reference vs fast b"
"$PKG/check.sh" compare "$OUT/fast-a.json" "$OUT/fast-b.json" 2>&1
"$PKG/check.sh" compare "$OUT/ref.json" "$OUT/fast-b.json" 2>&1
log "logprob identity vs R0: probe, long prompts"
python3 "$E/scripts/identity_probe.py" diff "$PROBE/r0-prod.json" "$OUT/probe-fast-b.json" 2>&1 | tail -2
python3 "$E/scripts/identity_probe.py" diff "$PROBE/long-r0.json" "$OUT/long-fast-b.json" 2>&1 | tail -2

# pp and tg alternate: every pp point after the first runs on weights a decode step has reordered, as a server does
log "llama-bench depth sweep, fast path (pp2048 + tg128 at depths 0-32K, 3 reps)"
wait_port_free
(
  set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null; set -u
  export ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
    GGML_SYCL_DNNL_DETERMINISTIC=1 GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_PRIORITIZE_DMMV=1 \
    LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4 LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1
  # the fusions serve.sh fast turns on
  export LLAMA_SYCL_FUSE_RMS_NORM_MUL=1 LLAMA_SYCL_FUSE_ADD_RMS_NORM_MUL=1 LLAMA_SYCL_FUSE_MOE_SUM=1 \
    LLAMA_SYCL_FUSE_MOE_ROUTE=1 LLAMA_SYCL_FUSE_SHORTCONV=1 LLAMA_SYCL_FUSE_F16_SHADOW=1 LLAMA_SYCL_FUSE_Q8_SHADOW=1 \
    LLAMA_SYCL_FUSE_MOE_GATE_UP=1 LLAMA_SYCL_FUSE_NORM_ROPE=1 LLAMA_SYCL_FUSE_NORM_Q8=1 LLAMA_SYCL_FUSE_MOE_DOWN_SUM=1 \
    LLAMA_SYCL_FUSE_CONV_STATE_ROWS=1 LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED=1
  timeout 1800 "$BUILD_DIR/bin/llama-bench" -m "$MODEL_DIR/LFM2.5-24B-A2B-Q8_0.gguf" -ngl 99 -fa 1 -ctk f16 -ctv f16 \
    -b 2048 -ub 512 -t 8 --poll 50 -p 2048 -n 128 -d 0,2048,4096,8192,16384,32768 -r 3 -o json \
    > "$OUT/sweep-fast.json" 2> "$OUT/sweep-fast.err"
  echo "llama-bench rc=$?"
)
python3 - "$OUT/sweep-fast.json" <<'EOF'
import json, sys
try:
    rows = json.load(open(sys.argv[1]))
except Exception as exc:
    print("sweep unreadable:", exc); raise SystemExit
for r in rows:
    kind = "pp" if r["n_prompt"] else "tg"
    print(f'{kind}{r["n_prompt"] or r["n_gen"]} @ depth {r["n_depth"]}: {r["avg_ts"]:.1f} tok/s (sd {r["stddev_ts"]:.1f})')
EOF
