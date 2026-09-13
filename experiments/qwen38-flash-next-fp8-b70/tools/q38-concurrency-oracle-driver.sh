#!/usr/bin/env bash
# Multi-user identity ladder driver: wait for the frozen server, run the concurrency oracle (each
# prompt's concurrent output must equal its sequential oracle) at 1,2,4,...,N users on the fixed
# realistic suite in completions mode, write <run_dir>/concurrency-oracle.json, then stop the server.
# Usage: q38-concurrency-oracle-driver.sh <attempt> <port> <mtp0|mtp1> <capacity> <concurrency-csv>
set -euo pipefail
attempt=${1:?attempt}; port=${2:?port}; mtp=${3:?mtp}; cap=${4:?capacity}; conc=${5:?concurrency csv}
repo=/home/steve/llm-optimizations; python=/home/steve/.venvs/vllm-xpu/bin/python
B=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
oracle="${repo}/scripts/bench-openai-concurrency-oracle.py"
suite="${repo}/repro/rapid-model-snapshots-b70/realistic-suite-v1.json"
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
echo "driver: server healthy at $(date +%H:%M:%S); concurrency oracle ${conc} into $RD"
set +e
timeout --signal=TERM --kill-after=10s 5400s "$python" "$oracle" --base-url "http://127.0.0.1:${port}" --model qwen38-flash-next-fp8-tp4 \
  --api-mode completions --suite "$suite" --concurrency "$conc" --repeats 2 --max-tokens 128 --seed 42 --timeout 900 \
  --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --require-output-identity \
  --out "${RD}/concurrency-oracle.json" > "${RD}/concurrency-oracle.log" 2>&1
rc=$?; echo "$rc" > "${RD}/concurrency-oracle.rc"; echo "driver: oracle rc=${rc} at $(date +%H:%M:%S)"
tail -5 "${RD}/concurrency-oracle.log" | cut -c1-200
set -e
echo "STOP after the concurrency oracle a${attempt}" >"$stop_file"
echo "driver: done at $(date +%H:%M:%S)"
