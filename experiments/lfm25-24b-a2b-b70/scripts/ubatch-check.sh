#!/usr/bin/env bash
# Prompt batch-size check (registered in notes/2026-10-14-lfm25-24b-a2b-bringup.md, 2026-10-15 evening): the package's
# serve.sh fast with `-ub N` in place of `-ub 512`, so the reordered weights are converted to 16-bit once per N prompt
# tokens instead of once per 512. Card 1, Gemma on card 0 meanwhile, restored on exit.
#   BUILD_DIR=... UBS="2048 1024" ubatch-check.sh      (under systemd-run --user; SUDO_ASKPASS for the Gemma switch)
# Each N on a fresh server: the 12-prompt suite (vs R0), the top-8 logprob probe and the long prompts (vs R0), then
# the server's prompt rate on the 2K / 8K / 24K prompts twice, and the compute-buffer sizes from the server log.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
PKG=$LAB/repro/lfm25-24b-a2b-q8-b70
E=$LAB/experiments/lfm25-24b-a2b-b70
PROBE=/mnt/fast-ai/bench-results/lfm25-24b-a2b/probe
BUILD_DIR=${BUILD_DIR:?}
MODEL_DIR=${MODEL_DIR:-/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf}
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b/ubatch-20261015}
PORT=18110
UNIT=lfm25-ub-srv
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

for ub in ${UBS:-2048 1024}; do
  name=ub$ub
  sed "s/-ub 512 /-ub $ub /" "$PKG/serve.sh" > "$OUT/serve-$name.sh"
  grep -q -- "-ub $ub " "$OUT/serve-$name.sh" || { log "could not set -ub $ub"; exit 1; }
  chmod +x "$OUT/serve-$name.sh"
  for _ in $(seq 1 120); do [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && break; sleep 1; done
  systemctl --user reset-failed $UNIT 2>/dev/null
  systemd-run --user --unit=$UNIT --collect -p WorkingDirectory=$LAB -E BUILD_DIR="$BUILD_DIR" -E MODEL_DIR="$MODEL_DIR" \
    -E GPU=1 -E PORT=$PORT bash -c "exec $OUT/serve-$name.sh fast > $OUT/server-$name.log 2>&1" >/dev/null
  ok=0
  for i in $(seq 1 240); do
    curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { log "$name ready after ${i}s"; ok=1; break; }
    systemctl --user is-active --quiet $UNIT || { log "$name server died"; tail -5 "$OUT/server-$name.log"; break; }
    sleep 1
  done
  [[ $ok == 1 ]] || exit 1
  grep -a "compute buffer size" "$OUT/server-$name.log" | sed 's/.*: *//' | head -4
  log "$name: suite"
  RESULTS_DIR=$OUT PORT=$PORT "$PKG/check.sh" run "$name" 2>&1
  log "$name: logprob probe and long prompts"
  python3 "$E/scripts/identity_probe.py" run --out "$OUT/probe-$name.json" 2>&1 | tail -1
  python3 "$E/scripts/identity_probe.py" run --prompts "$PROBE/long-prompts.json" --tokens 128 \
    --out "$OUT/long-$name.json" 2>&1 | tail -1
  python3 "$E/scripts/identity_probe.py" diff "$PROBE/r0-prod.json" "$OUT/probe-$name.json" 2>&1 | tail -2
  python3 "$E/scripts/identity_probe.py" diff "$PROBE/long-r0.json" "$OUT/long-$name.json" 2>&1 | tail -2
  log "$name: prompt reading as the server reports it, 2K / 8K / 24K prompts twice"
  python3 - "$PROBE/long-prompts.json" "http://127.0.0.1:$PORT" "$OUT/prompt-rate-$name.json" "$name" <<'EOF'
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
        print(f'{name} {p["id"]} rep {rep}: {t["prompt_n"]} tokens, {t["prompt_per_second"]:.1f} tok/s', flush=True)
json.dump(rows, open(out, "w"), indent=1)
EOF
  systemctl --user stop $UNIT
  for _ in $(seq 1 30); do systemctl --user is-active --quiet $UNIT || break; sleep 1; done
done
