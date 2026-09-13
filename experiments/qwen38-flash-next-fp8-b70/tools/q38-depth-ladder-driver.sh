#!/usr/bin/env bash
# Long-context ladder driver: wait for the frozen server, then run <rows> exact rows at each depth
# through the depth harness with the arm's context capacity, summarize rates and output hashes into
# <run_dir>/depth-ladder.json, then write the stop file. Usage:
#   q38-depth-ladder-driver.sh <attempt> <port> <mtp0|mtp1> <capacity> <rows> <depths-csv>
set -euo pipefail
attempt=${1:?attempt}; port=${2:?port}; mtp=${3:?mtp0|mtp1}; cap=${4:?capacity}; rows=${5:?rows}; depths=${6:?depths csv}
repo=/home/steve/llm-optimizations; python=/home/steve/.venvs/vllm-xpu/bin/python
B=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
depth_harness="${repo}/scripts/bench-openai-token-depth-suite.py"
fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
rc_file="/tmp/q38-${mtp}-ple-only-a${attempt}.rc"; stop_file="/tmp/q38-${mtp}-ple-only-a${attempt}.stop"
deadline=$(( $(date +%s) + 3600 ))
until curl -fsS --max-time 5 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; do
  [[ -f "$rc_file" ]] && { echo "driver: server exited before healthy (rc $(cat "$rc_file"))"; exit 1; }
  (( $(date +%s) < deadline )) || { echo "driver: server not healthy after 60 minutes"; exit 1; }
  sleep 15
done
RD=$(ls -d $B/*fullgraphdet-${mtp}-${cap}-ple-only-r1-attempt${attempt} 2>/dev/null | grep -v supervisor | head -1)
[[ -n "$RD" && -d "$RD" ]] || { echo "driver: no run dir for attempt ${attempt}"; exit 1; }
sleep 20
echo "driver: server healthy at $(date +%H:%M:%S); depths ${depths} x ${rows} rows at capacity ${cap} into $RD"
set +e
for depth in ${depths//,/ }; do
  tag="$((depth / 1024))k"
  for row in $(seq 1 "$rows"); do
    timeout --signal=TERM --kill-after=10s 1810s "$python" "$depth_harness" --execute \
      --fixture "$fixture" --depth "$depth" --context-capacity "$cap" \
      --base-url "http://127.0.0.1:${port}" --model qwen38-flash-next-fp8-tp4 --response-adapter vllm --timeout 1800 \
      --out "${RD}/exact-depth-${tag}-r${row}.json" >"${RD}/exact-depth-${tag}-r${row}.log" 2>&1
    rc=$?; echo "$rc" >"${RD}/exact-depth-${tag}-r${row}.rc"; echo "driver: depth ${tag} row ${row} rc=${rc} at $(date +%H:%M:%S)"
  done
done
set -e
"$python" - "$RD" "$depths" "$rows" <<'PY'
import json, re, sys, glob, os
rd, depths, rows = sys.argv[1], sys.argv[2].split(','), int(sys.argv[3])
out = {}
for d in depths:
    tag = f"{int(d)//1024}k"; out[tag] = []
    for r in range(1, rows + 1):
        p = f"{rd}/exact-depth-{tag}-r{r}.json"
        if not os.path.exists(p):
            out[tag].append({"row": r, "missing": True}); continue
        j = json.load(open(p)); t = open(p).read()
        m = re.search(r'output_token_ids_sha256": "([0-9a-f]{64})', t)
        mw = j.get("metric_window", {})
        out[tag].append({"row": r, "status": j.get("status"), "output_token_ids_sha256": m.group(1) if m else None,
                         "tok_s_99_intervals": round(1 / mw["interval_s"]["mean"], 3) if mw.get("interval_s") else None,
                         "ttft_s": mw.get("time_to_first_token_s") or mw.get("first_event_offset_s")})
json.dump(out, open(f"{rd}/depth-ladder.json", "w"), indent=1)
print("driver: summary", json.dumps(out)[:600])
PY
echo "STOP after the depth ladder a${attempt}" >"$stop_file"
echo "driver: done at $(date +%H:%M:%S)"
