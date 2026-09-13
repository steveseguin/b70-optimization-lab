#!/usr/bin/env bash
# Single-user reproducibility on a multi-sequence server: wait for the frozen server, run two exact-2K rows
# (certified pin), then the full 1,2,4,8 concurrency oracle twice (each pass regenerates all eight sequential
# oracle rows; two files), then stop the server. A391 ran it at concurrency 1, which covers one prompt only.
#   q38-repro-driver.sh <attempt> <port> <mtp0|mtp1> <capacity>
set -euo pipefail
attempt=${1:?attempt}; port=${2:?port}; mtp=${3:?mtp}; cap=${4:?capacity}
repo=/home/steve/llm-optimizations; python=/home/steve/.venvs/vllm-xpu/bin/python
B=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
depth_harness="${repo}/scripts/bench-openai-token-depth-suite.py"
fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
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
echo "driver: server healthy at $(date +%H:%M:%S); exact-2K x2 then oracle c=1 x2 into $RD"
set +e
for row in 1 2; do
  timeout --signal=TERM --kill-after=10s 1810s "$python" "$depth_harness" --execute \
    --fixture "$fixture" --depth 2048 --context-capacity "$cap" \
    --base-url "http://127.0.0.1:${port}" --model qwen38-flash-next-fp8-tp4 --response-adapter vllm --timeout 1800 \
    --out "${RD}/exact-depth-2k-r${row}.json" >"${RD}/exact-depth-2k-r${row}.log" 2>&1
  rc=$?; echo "$rc" >"${RD}/exact-depth-2k-r${row}.rc"; echo "driver: depth 2k row ${row} rc=${rc} at $(date +%H:%M:%S)"
done
for pass in 1 2; do
  timeout --signal=TERM --kill-after=10s 2700s "$python" "$oracle" --base-url "http://127.0.0.1:${port}" --model qwen38-flash-next-fp8-tp4 \
    --api-mode completions --suite "$suite" --concurrency 1,2,4,8 --repeats 1 --max-tokens 128 --seed 42 --timeout 900 \
    --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --require-output-identity \
    --out "${RD}/concurrency-oracle-pass${pass}.json" > "${RD}/concurrency-oracle-pass${pass}.log" 2>&1
  rc=$?; echo "$rc" >"${RD}/concurrency-oracle-pass${pass}.rc"; echo "driver: oracle pass ${pass} rc=${rc} at $(date +%H:%M:%S)"
done
set -e
echo "STOP after the reproducibility driver a${attempt}" >"$stop_file"
echo "driver: done at $(date +%H:%M:%S)"
