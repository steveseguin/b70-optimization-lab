#!/usr/bin/env bash
# Prompt-reading check for Gemma 4 26B A4B Q8 (2026-10-15; registered in the LFM2.5 bring-up note, which found the
# same reordered-Q8_0 conversion kernel build-dependent slow): a TEST server on card 1 through the production
# launcher (service profile, one user, 32K), never the LAN service itself, which is moved to card 0 meanwhile and
# put back on its throughput recipe at the end. Each server answers one 32-token reply, then the 2K / 8K / 24K
# prompts are timed twice by the server's own counters.
#   RUNS="prod-a:prod:0 new-a:copy:1 old-a:copy:0 prod-b:prod:0 new-b:copy:1" gemma-prefill-check.sh
#   (NAME:BUILD:FLAG; BUILD prod = the production binary, copy = the test build with the new kernel compiled in,
#    FLAG = LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED)      SUDO_ASKPASS set; under systemd-run --user
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
LAUNCH=/home/steve/llm-optimizations/scripts/serve-gemma4-26b-q8-production.sh
PROD=/home/steve/src/llama.cpp-gemma-c926-oneapi2026.1-compat/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server
COPY=/home/steve/src/llama.cpp-gemma-c926-compat-q8deq-20261015/build-q8deq/bin/llama-server
OUT=${OUT:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/prefill-reorder-20261015}
PROBE=/mnt/fast-ai/bench-results/lfm25-24b-a2b/probe
PORT=18120
UNIT=gemma-prefill-srv
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
log "moving the Gemma service to card 0 (throughput-card0)"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -2
for run in ${RUNS:-prod-a:prod:0 new-a:copy:1 old-a:copy:0 prod-b:prod:0 new-b:copy:1}; do
  IFS=: read -r name build val <<< "$run"
  bin=$PROD; [[ $build == copy ]] && bin=$COPY
  for _ in $(seq 1 120); do [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && break; sleep 1; done
  systemctl --user reset-failed $UNIT 2>/dev/null
  systemd-run --user --unit=$UNIT --collect -E GEMMA4_26B_PROFILE=service -E GPU_INDEX=1 -E PORT=$PORT \
    -E CTX_SIZE=32768 -E PARALLEL=1 -E LLAMA_SERVER="$bin" -E OUT_DIR="$OUT" -E LOG="$OUT/server-$name.log" \
    -E LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED=$val bash -c "exec $LAUNCH > $OUT/launch-$name.log 2>&1" >/dev/null
  ok=0
  for i in $(seq 1 400); do
    curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { log "$name ($build, flag $val) ready after ${i}s"; ok=1; break; }
    systemctl --user is-active --quiet $UNIT || { log "$name server died"; tail -5 "$OUT/launch-$name.log"; break; }
    sleep 1
  done
  [[ $ok == 1 ]] || exit 1
  python3 - "$PROBE/long-prompts.json" "http://127.0.0.1:$PORT" "$OUT/prompt-rate-$name.json" "$name" <<'EOF'
import json, sys, urllib.request
prompts, base, out, name = json.load(open(sys.argv[1]))["prompts"], sys.argv[2], sys.argv[3], sys.argv[4]
def post(body):
    req = urllib.request.Request(base + "/completion", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))
w = post({"prompt": "Write a short paragraph about rivers.", "n_predict": 32, "temperature": 0, "cache_prompt": False})
print(f'{name} warm-up reply: {w["timings"]["predicted_n"]} tokens generated', flush=True)
rows = []
for rep in (1, 2):
    for p in sorted(prompts, key=lambda p: len(p["prompt"])):
        t = post({"prompt": p["prompt"], "n_predict": 1, "temperature": 0, "cache_prompt": False})["timings"]
        rows.append({"id": p["id"], "rep": rep, "prompt_n": t["prompt_n"], "prompt_ms": t["prompt_ms"],
                     "prompt_per_second": t["prompt_per_second"]})
        print(f'{name} {p["id"]} rep {rep}: {t["prompt_n"]} tokens, {t["prompt_per_second"]:.1f} tok/s', flush=True)
json.dump(rows, open(out, "w"), indent=1)
EOF
  systemctl --user stop $UNIT
  for _ in $(seq 1 60); do systemctl --user is-active --quiet $UNIT || break; sleep 1; done
done
