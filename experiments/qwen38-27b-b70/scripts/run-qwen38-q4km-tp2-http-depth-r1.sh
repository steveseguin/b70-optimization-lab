#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
source_dir="${SOURCE_DIR:-}"
build_dir="${BUILD_DIR:-}"
model="${MODEL:-}"
profile="${PROFILE:-q4km}"
out_parent="${OUT_DIR:-/mnt/extended-ssd/b70-runs}"
attempt="${ATTEMPT:-1}"
port="${PORT:-18089}"
fixture="${repo_root}/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
expected_source_commit=a4349bcee933cd2b13820bc72fbe842e9c2f4b7a
expected_server_sha=6ae782c7e8f7a992e0eeced10ade2a84b3cbb9ba65c65cbb917e52d1ce09777d
expected_backend_sha=375f6d251b022b62367e73d2cd6b7eb0200efc9cc9c854a509af45950938c3ed

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
case "${profile}" in
  q4km)
    campaign="qwen38-q4km-tp2-http-depth-20260825-r1"
    prereg="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-depth-r1-prereg.json"
    expected_model_sha=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
    model_label=qwen38-q4km-tp2-http-depth
    tuple_label="Qwen3.8-27B Q4_K_M TP2, two B70s, F16 KV, target-only/MTP0, one HTTP slot"
    model_verifier="${repo_root}/repro/qwen38-27b-q4km-tp1-b70/verify-model-direct.sh"
    runtime_dir="${repo_root}/repro/qwen38-27b-q4km-tp2-asrock-b70"
    ;;
  q8)
    campaign="qwen38-q8-tp2-http-depth-20260825-r2"
    prereg="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp2-http-depth-r2-prereg.json"
    expected_model_sha=f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8
    model_label=qwen38-q8-tp2-http-depth
    tuple_label="Qwen3.8-27B Q8_0 TP2, two B70s, F16 KV, target-only/MTP0, one HTTP slot"
    model_verifier="${repo_root}/repro/qwen38-27b-q8-tp2-asrock-b70/verify-model-direct.sh"
    runtime_dir="${repo_root}/repro/qwen38-27b-q8-tp2-asrock-b70"
    ;;
  *) fail 'PROFILE must be q4km or q8' ;;
esac
[[ -n "${source_dir}" && -n "${build_dir}" && -n "${model}" ]] || fail 'set SOURCE_DIR, BUILD_DIR, and MODEL'
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'

server="${build_dir}/bin/llama-server"
backend="${build_dir}/bin/libggml-sycl.so"
[[ -d "${source_dir}/.git" && -f "${model}" && -x "${server}" && -f "${backend}" ]] || fail 'source/model/server/backend missing'
[[ -f "${fixture}" && -f "${prereg}" ]] || fail 'frozen preregistration dependency missing'

exec 7>"/run/lock/muse-glimmer-gpu-exclusive.lock"
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>"/tmp/b70-benchmark.lock"
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>"/tmp/b70-gpu0.lock"
flock -n 9 || fail 'GPU 0 lock is held'
exec 10>"/tmp/b70-gpu1.lock"
flock -n 10 || fail 'GPU 1 lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

[[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${expected_source_commit}" ]] || fail 'source commit mismatch'
[[ "$(sha256sum "${model}" | awk '{print $1}')" == "${expected_model_sha}" ]] || fail 'ordinary model SHA-256 mismatch'
[[ "$(sha256sum "${server}" | awk '{print $1}')" == "${expected_server_sha}" ]] || fail 'server SHA-256 mismatch'
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == "${expected_backend_sha}" ]] || fail 'backend SHA-256 mismatch'
"${model_verifier}" "$(dirname -- "${model}")" >/dev/null

run_dir="${out_parent}/${campaign}-attempt${attempt}"
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
mkdir -p "${run_dir}"
unit="nd-q38-${profile}-tp2-depth-a${attempt}"
server_log="${run_dir}/server.log"

export QWEN38_SOURCE_DIR="${source_dir}"
export QWEN38_BUILD_DIR="${build_dir}"
export QWEN38_MODEL="${model}"
export QWEN38_PREFILL_MODE=0
# shellcheck disable=SC1091
source "${runtime_dir}/runtime-common.sh"
# shellcheck disable=SC1091
source "${runtime_dir}/config.env"

env | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|ONEAPI_ROOT=|LD_LIBRARY_PATH=|PATH=)' | LC_ALL=C sort > "${run_dir}/environment.txt"
sha256sum "${model}" "${server}" "${backend}" "${fixture}" "${prereg}" \
  "${repo_root}/scripts/bench-openai-token-depth-suite.py" > "${run_dir}/sha256sums.txt"
git -C "${source_dir}" status --short > "${run_dir}/source-status.txt"
free -b > "${run_dir}/memory-before.txt"

cmd=("${server}" --model "${model}" --device SYCL0,SYCL1 --gpu-layers 99
  --split-mode tensor --tensor-split 1,1 --fit off --flash-attn on
  --batch-size 1024 --ubatch-size 256 --cache-type-k f16 --cache-type-v f16
  --cache-ram 0 --ctx-checkpoints 0 --reasoning off --threads 8 --poll 50
  --ctx-size 33024 --parallel 1 --no-cache-prompt --slot-prompt-similarity 0
  --metrics --host 127.0.0.1 --port "${port}")
printf '%q' "${cmd[0]}" > "${run_dir}/server-command.txt"
printf ' %q' "${cmd[@]:1}" >> "${run_dir}/server-command.txt"
printf '\n' >> "${run_dir}/server-command.txt"

cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill -TERM "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  systemctl --user stop "${unit}.scope" >/dev/null 2>&1 || true
  free -b > "${run_dir}/memory-after.txt" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

systemd-run --user --scope --quiet --collect --unit="${unit}" \
  -p MemoryHigh=11G -p MemoryMax=13G -p MemorySwapMax=12G \
  timeout --signal=TERM --kill-after=30 3600 "${cmd[@]}" >"${server_log}" 2>&1 &
server_pid=$!

healthy=0
for _ in $(seq 1 420); do
  if curl -fsS "http://127.0.0.1:${port}/health" > "${run_dir}/health.json" 2>/dev/null; then healthy=1; break; fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then break; fi
  sleep 1
done
if (( healthy == 0 )); then
  wait "${server_pid}" || status=$?
  printf '%s\n' "${status:-1}" > "${run_dir}/server-exit-status.txt"
  fail "33,024-token TP2 profile did not become healthy; retained at ${run_dir}"
fi
curl -fsS "http://127.0.0.1:${port}/props" > "${run_dir}/props.json" || true

for depth in 2048 4096 8192 16384 24576 32768; do
  python3 "${repo_root}/scripts/bench-openai-token-depth-suite.py" \
    --execute --fixture "${fixture}" --depth "${depth}" --context-capacity 33024 \
    --base-url "http://127.0.0.1:${port}" --model "${model_label}" \
    --response-adapter llama-server --timeout 1800 \
    --out "${run_dir}/depth-${depth}.json" > "${run_dir}/depth-${depth}.stdout.json"
done

python3 -B - "${run_dir}" "${tuple_label}" > "${run_dir}/summary.json" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
paths = [p for p in sorted(root.glob("depth-*.json")) if not p.name.endswith(".stdout.json")]
rows = [json.loads(p.read_text()) for p in paths]
points = [{
    "active_context_tokens": row["run_identity"]["active_context_tokens"],
    "status": row["status"],
    "decode_tok_s": row["metric_window"]["conventional_99_interval_tok_s"],
    "ttft_ms": row["metric_window"]["time_to_first_token_s"] * 1000,
    "cached_tokens_zero": row["gate"]["checks"]["cached_tokens_zero"],
} for row in rows]
passed = len(points) == 6 and all(p["status"] == "passed" and p["cached_tokens_zero"] for p in points)
out = {
    "classification": "qualified-exact-depth" if passed else "failed-closed",
    "tuple": sys.argv[2],
    "points": points,
    "workload_boundary": "Grade-C exact repeated-token context fixture; no interpolation or extrapolation; not a natural-prose latency claim."
}
json.dump(out, sys.stdout, indent=2, sort_keys=True); print()
if not passed: raise SystemExit(3)
PY

sha256sum "${run_dir}"/depth-*.json "${run_dir}/summary.json" > "${run_dir}/result-sha256sums.txt"
printf 'PASS: %s\n' "${run_dir}"
