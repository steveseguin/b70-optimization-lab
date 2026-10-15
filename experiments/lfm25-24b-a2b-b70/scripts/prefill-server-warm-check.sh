#!/usr/bin/env bash
# Follow-up to prefill-reorder-check.sh part B (registered in notes/2026-10-14-lfm25-24b-a2b-bringup.md): there every
# timed request asked for one token, which comes from the prompt pass itself, so no decode step ran and the expert
# weights were never reordered. Here each server first answers one short request with 32 generated tokens (as any
# chat reply does), then the 2K/8K/24K prompts are timed (each twice), old dequant vs new, two fresh servers each.
#   prefill-server-warm-check.sh      (SUDO_ASKPASS set; under systemd-run --user; card 1, Gemma on card 0, restored)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
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
timed() {  # NAME
  python3 - "$PROBE/long-prompts.json" "http://127.0.0.1:$PORT" "$OUT/prefill-warm-$1.json" "$1" <<'EOF'
import json, sys, urllib.request
prompts, base, out, name = json.load(open(sys.argv[1]))["prompts"], sys.argv[2], sys.argv[3], sys.argv[4]
def post(body):
    req = urllib.request.Request(base + "/completion", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))
w = post({"prompt": "Write a short paragraph about rivers.", "n_predict": 32, "temperature": 0, "cache_prompt": False})
print(f'{name} warm-up reply: {w["timings"]["predicted_n"]} tokens generated')
rows = []
for rep in (1, 2):
    for p in sorted(prompts, key=lambda p: len(p["prompt"])):
        t = post({"prompt": p["prompt"], "n_predict": 1, "temperature": 0, "cache_prompt": False})["timings"]
        rows.append({"id": p["id"], "rep": rep, "prompt_n": t["prompt_n"], "prompt_ms": t["prompt_ms"],
                     "prompt_per_second": t["prompt_per_second"]})
        print(f'{name} {p["id"]} rep {rep}: {t["prompt_n"]} tokens, {t["prompt_per_second"]:.1f} tok/s')
json.dump(rows, open(out, "w"), indent=1)
EOF
}

log "moving Gemma to card 0 (throughput-card0)"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -2
for run in old-a:0 new-a:1 old-b:0 new-b:1; do
  name=${run%%:*}; val=${run#*:}
  serve "warm-$name" $FLAG=$val || exit 1
  timed "$name"
  stop_server
done
