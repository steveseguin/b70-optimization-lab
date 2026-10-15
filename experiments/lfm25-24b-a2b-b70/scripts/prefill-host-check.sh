#!/usr/bin/env bash
# Is the server's prompt reading waiting on the host? (notes/2026-10-14-lfm25-24b-a2b-bringup.md, 2026-10-15.)
# serve.sh fast on card 1 (Gemma on card 0, restored at the end): one short reply, then the 2K / 8K / 24K prompts
# twice each; for each request the render-engine idle time of both cards (gtidle idle_residency_ms) is read before
# and after, and the server's per-thread CPU use is sampled each second during the second 24K prompt.
#   prefill-host-check.sh      (SUDO_ASKPASS set; under systemd-run --user)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
PKG=$LAB/repro/lfm25-24b-a2b-q8-b70
BUILD_DIR=${BUILD_DIR:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25}
MODEL_DIR=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b/prefill-reorder}
PROBE=/mnt/fast-ai/bench-results/lfm25-24b-a2b/probe
PORT=18110
UNIT=lfm25-prefill-srv
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
systemctl --user reset-failed $UNIT 2>/dev/null
systemd-run --user --unit=$UNIT --collect -p WorkingDirectory=$LAB -E BUILD_DIR="$BUILD_DIR" -E MODEL_DIR="$MODEL_DIR" \
  -E GPU=1 -E PORT=$PORT bash -c "exec $PKG/serve.sh fast > $OUT/server-host.log 2>&1" >/dev/null
for i in $(seq 1 240); do
  curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { log "server ready after ${i}s"; break; }
  sleep 1
done
PID=$(systemctl --user show -p MainPID --value $UNIT)
python3 - "$PROBE/long-prompts.json" "http://127.0.0.1:$PORT" "$PID" "$OUT/host-check.json" <<'EOF'
import glob, json, subprocess, sys, time, urllib.request
prompts, base, pid, out = json.load(open(sys.argv[1]))["prompts"], sys.argv[2], sys.argv[3], sys.argv[4]
idle_files = sorted(glob.glob("/sys/class/drm/card*/device/tile0/gt0/gtidle/idle_residency_ms"))
def idle():
    return {f.split("/")[4]: int(open(f).read()) for f in idle_files}
def post(body):
    req = urllib.request.Request(base + "/completion", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))
post({"prompt": "Write a short paragraph about rivers.", "n_predict": 32, "temperature": 0, "cache_prompt": False})
rows = []
for rep in (1, 2):
    for p in sorted(prompts, key=lambda p: len(p["prompt"])):
        sampler = None
        if rep == 2 and p["id"] == "long-24k":
            sampler = subprocess.Popen(["pidstat", "-t", "-u", "-p", pid, "1"], stdout=open(out + ".pidstat", "w"))
        i0, t0 = idle(), time.monotonic()
        t = post({"prompt": p["prompt"], "n_predict": 1, "temperature": 0, "cache_prompt": False})["timings"]
        wall_ms = (time.monotonic() - t0) * 1000
        i1 = idle()
        if sampler:
            sampler.terminate()
        idle_ms = {c: i1[c] - i0[c] for c in i0}
        rows.append({"id": p["id"], "rep": rep, "prompt_n": t["prompt_n"], "prompt_ms": t["prompt_ms"],
                     "wall_ms": wall_ms, "render_idle_ms": idle_ms})
        print(f'{p["id"]} rep {rep}: {t["prompt_n"]} tokens, {t["prompt_per_second"]:.1f} tok/s, prompt '
              f'{t["prompt_ms"]:.0f} ms of {wall_ms:.0f} ms wall; render idle ms per card {idle_ms}', flush=True)
json.dump(rows, open(out, "w"), indent=1)
EOF
systemctl --user stop $UNIT
echo "busiest server threads during the second 24K prompt (average %CPU):"
awk '$0 ~ /\|__/ {k=$(NF-7)" "$NF; n[k]++; s[k]+=$(NF-2)} END {for (k in s) printf "%7.1f %s\n", s[k]/n[k], k}' \
  "$OUT/host-check.json.pidstat" | sort -rn | head -8
