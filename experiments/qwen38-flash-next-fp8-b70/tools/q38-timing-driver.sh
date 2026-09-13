#!/usr/bin/env bash
# Diagnostic driver for a timing arm: wait for the frozen server, run N exact-2K rows through the
# depth harness into the attempt's run directory, summarize Q38_STEP_TIMING and Q38_EVENT_SUMS
# lines from server.log into <run_dir>/step-timing-2k.json, then write the stop file so the
# supervisor tears the server down. Usage: q38-timing-driver.sh <attempt> <port> <mtp0|mtp1> [rows]
set -euo pipefail
attempt=${1:?attempt}; port=${2:?port}; mtp=${3:?mtp0|mtp1}; rows=${4:-3}
repo=/home/steve/llm-optimizations; python=/home/steve/.venvs/vllm-xpu/bin/python
B=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
depth_harness="${repo}/scripts/bench-openai-token-depth-suite.py"
fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
rc_file="/tmp/q38-${mtp}-ple-only-a${attempt}.rc"; stop_file="/tmp/q38-${mtp}-ple-only-a${attempt}.stop"
deadline=$(( $(date +%s) + 2700 ))
until curl -fsS --max-time 5 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; do
  [[ -f "$rc_file" ]] && { echo "driver: server exited before healthy (rc $(cat "$rc_file"))"; exit 1; }
  (( $(date +%s) < deadline )) || { echo "driver: server not healthy after 45 minutes"; exit 1; }
  sleep 15
done
RD=$(ls -d $B/*fullgraphdet-${mtp}-4352-ple-only-r1-attempt${attempt} 2>/dev/null | grep -v supervisor | head -1)
[[ -n "$RD" && -d "$RD" ]] || { echo "driver: no run dir for attempt ${attempt}"; exit 1; }
sleep 20
echo "driver: server healthy at $(date +%H:%M:%S); ${rows} exact-2K rows into $RD"
set +e
for row in $(seq 1 "$rows"); do
  timeout --signal=TERM --kill-after=10s 910s "$python" "$depth_harness" --execute \
    --fixture "$fixture" --depth 2048 --context-capacity 4352 \
    --base-url "http://127.0.0.1:${port}" --model qwen38-flash-next-fp8-tp4 --response-adapter vllm --timeout 900 \
    --out "${RD}/exact-depth-2k-r${row}.json" >"${RD}/exact-depth-2k-r${row}.log" 2>&1
  rc=$?; echo "$rc" >"${RD}/exact-depth-2k-r${row}.rc"; echo "driver: row ${row} rc=${rc}"
done
set -e
"$python" - "$RD" <<'PY'
import json, re, sys, statistics, collections
rd = sys.argv[1]
log = open(f"{rd}/server.log", errors="replace").read()
steps = collections.defaultdict(list)
for m in re.finditer(r"Q38_STEP_TIMING step=(\d+) tokens=(\d+) forward_ms=([\d.]+) sample_ms=([\d.]+) draft_ms=([\d.]+)", log):
    steps[int(m.group(2))].append(tuple(float(x) for x in m.group(3, 4, 5)))
def stat(v): return {"n": len(v), "median": round(statistics.median(v), 2), "min": round(min(v), 2), "max": round(max(v), 2)} if v else None
out = {"steps": {f"tokens={k}": {"forward_ms": stat([r[0] for r in v]), "sample_ms": stat([r[1] for r in v]), "draft_ms": stat([r[2] for r in v])} for k, v in steps.items()}}
sums = collections.defaultdict(list)
for m in re.finditer(r"Q38_EVENT_SUMS (\{.*?\})\s*$", log, re.M):
    try: d = json.loads(m.group(1))
    except Exception: continue
    for k, v in d.items(): sums[k].append(v)
out["event_sums_per_report"] = {k: stat(v) for k, v in sums.items()}
hashes = []
for row in range(1, 8):
    try:
        j = json.load(open(f"{rd}/exact-depth-2k-r{row}.json")); s = json.dumps(j)
        h = re.findall(r'"(?:output_token_ids_sha256|output_sha256)":\s*"([0-9a-f]{8,64})"', s)
        hashes.append((row, h[:1]))
    except FileNotFoundError: break
out["exact_2k_row_hashes"] = hashes
json.dump(out, open(f"{rd}/step-timing-2k.json", "w"), indent=1)
print("driver: summary", json.dumps(out["steps"])[:400])
PY
echo "STOP after timing rows a${attempt}" > "$stop_file"
echo "driver: done at $(date +%H:%M:%S)"
