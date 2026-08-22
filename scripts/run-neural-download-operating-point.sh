#!/usr/bin/env bash
set -euo pipefail

# Published operating-point capture for one neural.download packet:
# two fresh-server runs of the 12-prompt suite at 512/100 windows
# (conventional median, cache-zero gates), canaries on the second boot.
#
# Env: SERVER_CMD (full server command line, without --port/--host),
#      POINT_ID, OUT_ROOT, ALIAS. Uses port 18100.

point_id="${POINT_ID:?}"
out_root="${OUT_ROOT:?}"
alias_name="${ALIAS:?}"
server_cmd="${SERVER_CMD:?}"
repo=/home/steve/llm-optimizations
port=18100

pgrep -x llama-server >/dev/null && { echo 'server already running' >&2; exit 1; }
mkdir -p "$out_root"

set +u
[[ -r /opt/intel/oneapi/setvars.sh ]] && source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR=level_zero:0

server_pid=
cleanup() {
  [[ -n "${server_pid}" ]] && kill "$server_pid" 2>/dev/null
  sleep 2
  pgrep -x llama-server >/dev/null && pkill -9 -x llama-server
  true
}
trap cleanup EXIT

boot_and_wait() {
  local log=$1
  bash -c "exec $server_cmd --host 127.0.0.1 --port $port" > "$log" 2>&1 &
  server_pid=$!
  for _ in $(seq 1 240); do
    curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && return 0
    kill -0 "$server_pid" 2>/dev/null || { echo "server died; see $log" >&2; return 1; }
    sleep 5
  done
  echo 'health timeout' >&2; return 1
}

stop_server() {
  kill "$server_pid" 2>/dev/null || true
  for _ in $(seq 1 20); do pgrep -x llama-server >/dev/null || return 0; sleep 1; done
  pkill -9 -x llama-server || true
  sleep 2
}

run_suite() {
  local out=$1
  python3 "$repo/scripts/bench-openai-realistic-suite.py" \
    --base-url "http://127.0.0.1:$port" --model "$alias_name" \
    --api-mode completions \
    --suite "$repo/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
    --max-tokens 512 --metric-tokens 100 --seed 1 --timeout 900 --out "$out" \
    --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0}'
  python3 - "$out" <<'PY'
import json, statistics, sys
d = json.load(open(sys.argv[1]))
assert d["fresh_response_validity"]["valid"], "fresh-response validity failed"
assert d["realistic_final_gate"]["cached_tokens_all_zero"], "cached tokens nonzero"
# Conventional 99-interval rate computed directly from raw event offsets
# (this script version's summary only carries the legacy 100-event form).
rates = []
for r in d["rows"]:
    o = r["chunk_offsets_s"]
    assert len(o) >= 100, f"row {r['prompt_id']} has <100 events"
    rates.append(99.0 / (o[99] - o[0]))
rates.sort()
med = statistics.median(rates)
p10 = rates[max(0, int(len(rates) * 0.1) - 0)]
print(f"conv_median={med:.6f} conv_p10={p10:.6f} rows={len(rates)}")
PY
}

echo "=== $point_id run A ==="
boot_and_wait "$out_root/$point_id.serverA.log"
run_suite "$out_root/$point_id.benchA.json"
stop_server

echo "=== $point_id run B + canaries ==="
boot_and_wait "$out_root/$point_id.serverB.log"
run_suite "$out_root/$point_id.benchB.json"
python3 "$repo/scripts/neural-download-canaries.py" \
  --base-url "http://127.0.0.1:$port" --model "$alias_name" \
  --out "$out_root/$point_id.canaries.json"; canary_rc=$?
stop_server
echo "CANARY-RC:$canary_rc"
echo "=== $point_id complete ==="
exit "$canary_rc"
