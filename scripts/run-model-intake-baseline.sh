#!/usr/bin/env bash
set -euo pipefail

# Conservative first-launch harness for a downloaded model-intake GGUF.
# This is deliberately target-only and one-card. It preserves failures and
# identities; it does not claim that an untested architecture is supported.

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/.." && pwd)
intake_id="${INTAKE_ID:-}"
model_root="${MODEL_ROOT:-/mnt/usb-models}"
llama_build="${LLAMA_BUILD:-}"
llama_source="${LLAMA_SOURCE:-}"
gpu_index="${GPU_INDEX:-0}"
host_addr="${HOST_ADDR:-127.0.0.1}"
port="${PORT:-18100}"
ctx_size="${CTX_SIZE:-8192}"
out_dir="${OUT_DIR:-${PWD}/intake-baseline-${intake_id:-unset}}"

fail() { printf 'BASELINE PREFLIGHT FAIL: %s\n' "$*" >&2; exit 1; }

[[ -n "${intake_id}" ]] || fail "set INTAKE_ID to a queued catalog id"
[[ -n "${llama_build}" ]] || fail "set LLAMA_BUILD to a llama.cpp build directory"
[[ -n "${llama_source}" ]] || fail "set LLAMA_SOURCE to its exact Git source tree"
[[ "${gpu_index}" =~ ^[0-9]+$ ]] || fail "GPU_INDEX must be numeric"
[[ "${port}" =~ ^[0-9]+$ ]] || fail "PORT must be numeric"
[[ "${ctx_size}" =~ ^[1-9][0-9]*$ ]] || fail "CTX_SIZE must be positive"
server="${llama_build}/bin/llama-server"
[[ -x "${server}" ]] || fail "missing executable: ${server}"
git -C "${llama_source}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || \
    fail "LLAMA_SOURCE is not a Git worktree: ${llama_source}"
pgrep -x llama-server >/dev/null && fail "another llama-server is already running"

store_flags=()
if [[ "${ALLOW_NON_USB:-0}" == 1 ]]; then
    store_flags+=(--allow-non-usb)
fi
python3 "${repo_root}/scripts/model-intake.py" verify \
    --root "${model_root}" --id "${intake_id}" "${store_flags[@]}"
model_path=$(python3 "${repo_root}/scripts/model-intake.py" path \
    --root "${model_root}" --id "${intake_id}")
[[ -f "${model_path}" ]] || fail "verified model path disappeared: ${model_path}"

mkdir -p "${out_dir}"
server_sha=$(sha256sum "${server}" | awk '{print $1}')
sycl_lib="${llama_build}/bin/libggml-sycl.so"
sycl_sha="missing"
[[ ! -f "${sycl_lib}" ]] || sycl_sha=$(sha256sum "${sycl_lib}" | awk '{print $1}')
source_head=$(git -C "${llama_source}" rev-parse HEAD)
source_status=$(git -C "${llama_source}" status --porcelain)
source_dirty=false
if [[ -n "${source_status}" ]]; then
    source_dirty=true
    [[ "${ALLOW_DIRTY_SOURCE:-0}" == 1 ]] || \
        fail "LLAMA_SOURCE is dirty; preserve or clean it, or set ALLOW_DIRTY_SOURCE=1 for a labeled diagnostic"
fi
source_status_sha=$(printf '%s' "${source_status}" | sha256sum | awk '{print $1}')

python3 - \
    "${out_dir}/launch-identity.json" "${intake_id}" "${model_path}" \
    "${model_root}" "${server}" "${server_sha}" "${sycl_sha}" \
    "${llama_source}" "${source_head}" "${source_dirty}" "${source_status_sha}" \
    "${gpu_index}" "${ctx_size}" "${host_addr}" "${port}" <<'PY'
import json, platform, sys
(
    output, intake_id, model_path, model_root, server, server_sha, sycl_sha,
    source_dir, source_head, source_dirty, source_status_sha, gpu_index,
    ctx_size, host_addr, port,
) = sys.argv[1:]
json.dump({
  "format": "b70-model-intake-baseline-launch-v1",
  "status": "launch-attempt",
  "intake_id": intake_id,
  "model_path": model_path,
  "model_root": model_root,
  "server_path": server,
  "server_sha256": server_sha,
  "libggml_sycl_sha256": sycl_sha,
  "source_dir": source_dir,
  "source_head": source_head,
  "source_dirty": source_dirty == "true",
  "source_status_sha256": source_status_sha,
  "gpu_index": int(gpu_index),
  "context": int(ctx_size),
  "host": host_addr,
  "port": int(port),
  "target_only": True,
  "speculation": False,
  "cache_ram_mib": 0,
  "kernel": platform.release(),
}, open(output, "w"), indent=2)
PY

set +u
if [[ -r /opt/intel/oneapi/setvars.sh ]]; then
    # shellcheck disable=SC1091
    source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
fi
set -u
export ONEAPI_DEVICE_SELECTOR="level_zero:${gpu_index}"

printf 'Starting diagnostic baseline for %s; logs: %s\n' "${intake_id}" "${out_dir}/server.log"
exec "${server}" \
    --model "${model_path}" --alias "${intake_id}" \
    --device SYCL0 --gpu-layers 99 --flash-attn auto \
    --ctx-size "${ctx_size}" --parallel 1 \
    --cache-type-k f16 --cache-type-v f16 --cache-ram 0 --ctx-checkpoints 0 \
    --fit off --metrics --no-webui --host "${host_addr}" --port "${port}" \
    2>&1 | tee "${out_dir}/server.log"
