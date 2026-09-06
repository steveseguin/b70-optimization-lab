#!/usr/bin/env bash
# Driver for the frozen launcher: wait until the packet's server answers /health
# (the load from the USB checkpoint takes 9-12 minutes; graph capture and warmup
# follow), then send the fixed cold realistic suite exactly once with the record's
# flags (A134/A182/A188/A189: chat mode, 512 max tokens, 100 metric tokens, seed
# 20260609, enable_thinking=false, temperature 0, token ids returned), and stop
# the server through the packet's stop file. The record (A226) was produced this
# way on a fresh server; the frozen-client battery is the separate certification
# packet (A190) and is not re-run by this gate.
set -euo pipefail
attempt=${1:?attempt}; port=${2:?port}
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
python="${REPRO_VENV_ROOT:-/home/steve/.venvs/vllm-xpu}/bin/python"
results="${REPRO_RESULT_PARENT:-/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70}"
rc_file="/tmp/q38-mtp1-ple-only-a${attempt}.rc"; stop_file="/tmp/q38-mtp1-ple-only-a${attempt}.stop"
deadline=$(( $(date +%s) + 2700 ))
until curl -fsS --max-time 5 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; do
  [[ -f "$rc_file" ]] && { echo "server exited before becoming healthy (rc $(cat "$rc_file"))"; exit 1; }
  (( $(date +%s) < deadline )) || { echo "server not healthy after 45 minutes"; exit 1; }
  sleep 15
done
run_dir="$results/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-4352-ple-only-r1-attempt${attempt}"
[[ -d "$run_dir" ]] || { echo "run directory absent: $run_dir"; exit 1; }
[[ ! -e "$run_dir/realistic-suite-v1-result.json" ]] || { echo "refusing to overwrite the suite result"; exit 1; }
sleep 30
echo "server healthy at $(date +%H:%M:%S); sending the fixed cold realistic suite once"
"$python" "$repo/scripts/bench-openai-realistic-suite.py" --base-url "http://127.0.0.1:${port}" --model qwen38-flash-next-fp8-tp4 --api-mode chat \
  --suite "$repo/repro/rapid-model-snapshots-b70/realistic-suite-v1.json" --max-tokens 512 --metric-tokens 100 --seed 20260609 --timeout 900 --return-token-ids \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false},"seed":20260609,"temperature":0,"top_p":1.0}' \
  --out "$run_dir/realistic-suite-v1-result.json" > "$run_dir/realistic-suite-v1-result.log" 2>&1; rc=$?
echo "STOP after the replay suite a${attempt}" > "$stop_file"
echo "suite rc=$rc at $(date +%H:%M:%S)"; exit $rc
