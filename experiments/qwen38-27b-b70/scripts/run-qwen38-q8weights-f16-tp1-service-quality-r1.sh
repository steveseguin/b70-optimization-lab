#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
campaign=qwen38-q8weights-f16-tp1-service-quality-20260825-r1
ack="RUN ${campaign}"
manifest="${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8weights-f16-tp1-service-quality-r1-prereg.json"
model=/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/Qwen3.8-27B-Q8_0.gguf
tokenizer=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround
build=/mnt/extended-ssd/steve-archive/active-qwen38-tp1-concurrency-20260825/build-sycl-aot-bmg-g31
server="${build}/bin/llama-server"
backend="${build}/bin/libggml-sycl.so"
quality="${repo}/scripts/qwen38-text-quality-suite.py"
python=/home/steve/.venvs/vllm-xpu/bin/python
output=/mnt/extended-ssd/b70-runs/qwen38-q8weights-f16-tp1-service-quality-20260825-r1
port=18087
unit=nd-q38-q8-quality-r1
model_sha=f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8
server_sha=35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545
backend_sha=0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
if [[ "${1:-}" != --execute ]]; then
  jq '{campaign_id,state,model,runtime,tokenizer,service,quality_gate,execution}' "${manifest}"
  exit 0
fi
[[ "${2:-}" == --ack && "${3:-}" == "${ack}" && $# -eq 3 ]] || fail "exact acknowledgement required: ${ack}"
[[ -f "${manifest}" && -f "${model}" && -x "${server}" && -f "${backend}" && -x "${python}" && -f "${quality}" ]] || fail 'frozen dependency missing'

[[ "$(git -C "${repo}" branch --show-current)" == main ]] || fail 'repo must be on main'
[[ -z "$(git -C "${repo}" status --porcelain=v1 --untracked-files=all)" ]] || fail 'repo must be clean'
head=$(git -C "${repo}" rev-parse HEAD)
[[ "${head}" == "$(git -C "${repo}" rev-parse origin/main)" ]] || fail 'local main is not origin/main'
remote=$(timeout 30 git -C "${repo}" ls-remote origin refs/heads/main | awk '{print $1}')
[[ "${head}" == "${remote}" ]] || fail 'origin/main advanced'

exec 6>"/run/lock/muse-glimmer-gpu-exclusive.lock"; flock -n 6 || fail 'host GPU lock held'
exec 7>"/tmp/b70-benchmark.lock"; flock -n 7 || fail 'benchmark lock held'
exec 8>"/tmp/b70-gpu0.lock"; flock -n 8 || fail 'GPU0 lock held'
mkdir -p "/run/user/$(id -u)/qwen36-b70-gpu-leases"
exec 9>"/run/user/$(id -u)/qwen36-b70-gpu-leases/gpu0.lock"; flock -n 9 || fail 'legacy GPU0 lease held'
pgrep -af '[l]lama-(server|bench|batched-bench)|[v]llm' >/dev/null && fail 'another model process is running'
ss -ltn | awk '{print $4}' | grep -Eq "(^|:)${port}$" && fail "port ${port} is already listening"
if container_ids=$(docker ps -q 2>/dev/null); then
  :
elif [[ -r /home/steve/SUDOPASSWORD.txt ]]; then
  container_ids=$(sudo -S -p '' docker ps -q < /home/steve/SUDOPASSWORD.txt 2>/dev/null) || fail 'could not verify Docker state'
else
  fail 'could not verify Docker state without direct access or the local sudo file'
fi
[[ -z "${container_ids}" ]] || fail 'a Docker container is running'

[[ "$(stat -c %s "${model}")" == 28595763552 ]] || fail 'model size mismatch'
[[ "$(sha256sum "${model}" | awk '{print $1}')" == "${model_sha}" ]] || fail 'model SHA mismatch'
[[ "$(sha256sum "${server}" | awk '{print $1}')" == "${server_sha}" ]] || fail 'server SHA mismatch'
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == "${backend_sha}" ]] || fail 'backend SHA mismatch'
[[ "$(sha256sum "${quality}" | awk '{print $1}')" == 67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d ]] || fail 'quality suite SHA mismatch'
[[ "$(sha256sum "${tokenizer}/tokenizer.json" | awk '{print $1}')" == 06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523 ]] || fail 'tokenizer.json SHA mismatch'
[[ "$(sha256sum "${tokenizer}/tokenizer_config.json" | awk '{print $1}')" == 792fa3f0cb88b111e54ef3134c873531008c4df471d108da17903426e308aa7b ]] || fail 'tokenizer_config.json SHA mismatch'
[[ "$(sha256sum "${tokenizer}/config.json" | awk '{print $1}')" == 9a1c29a807e34529bec03cba92b4dc00ba61e37a703b029b08a3142b6dc08cd1 ]] || fail 'config.json SHA mismatch'
[[ ! -e "${output}" ]] || fail "create-only output already exists: ${output}"
mkdir -p "$(dirname "${output}")"
[[ "$(findmnt -n -o FSTYPE --target "$(dirname "${output}")")" == ext4 ]] || fail 'output parent must be ext4'
mkdir "${output}"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export GGML_SYCL_ENABLE_GRAPH=0
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
export UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
export GGML_SYCL_COMM_SINGLE_KERNEL=1
export GGML_META_FUSE_ALLREDUCE_ADD=1
export GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL=1
export GGML_SYCL_COMM_FUSED_Q8=1
export GGML_SYCL_FUSED_SWIGLU_Q8=1
export GGML_SYCL_FUSED_ATTN_Q8=1
export GGML_SYCL_FUSED_GDN_Q8=1
export GGML_SYCL_FUSED_MMVQ_PAIR=1
export GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=1
export GGML_SYCL_FUSED_MMVQ_PAIR_GDN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN=1
export GGML_SYCL_FUSED_MMVQ_QUAD_GDN=1
export GGML_SYCL_FUSED_GDN_BETA_SIGMOID=1
export GGML_SYCL_FUSED_CONCAT_STATE=1
export GGML_SYCL_FUSED_GDN_STATE_IO=1
export GGML_SYCL_FUSED_CONV_STATE_IO=1
export GGML_SYCL_COMM_DIRECT_Q8=2
export GGML_SYCL_FUSED_ROPE_SET_ROWS=1
export GGML_SYCL_COMM_REDUCE_VEC4=1
export GGML_SYCL_FUSED_QK_NORM_ROPE=1
export GGML_SYCL_FUSED_CONV_SILU_L2=1
export GGML_SYCL_FUSE_EXT=31
export GGML_SYCL_QDEDUP_STATS=1
export GGML_SYCL_MMQ_Q4K_REORDER=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1

cmd=("${server}" --model "${model}" --device SYCL0 --gpu-layers 99
  --split-mode none --fit off --flash-attn on --batch-size 2048 --ubatch-size 512
  --cache-type-k f16 --cache-type-v f16 --cache-ram 0 --ctx-checkpoints 0
  --reasoning off --threads 16 --poll 50 --ctx-size 8192 --parallel 1
  --metrics --host 127.0.0.1 --port "${port}")
printf '%q ' "${cmd[@]}" > "${output}/server-command.txt"; printf '\n' >> "${output}/server-command.txt"
env | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|ONEAPI_ROOT=|LD_LIBRARY_PATH=|PATH=|TRANSFORMERS_OFFLINE=|HF_HUB_OFFLINE=)' | LC_ALL=C sort > "${output}/environment.txt"
sha256sum "${model}" "${server}" "${backend}" "${manifest}" "${quality}" "${tokenizer}/tokenizer.json" "${tokenizer}/tokenizer_config.json" "${tokenizer}/config.json" > "${output}/sha256sums.txt"
free -b > "${output}/memory-before.txt"
xpu-smi dump -d 0 -m 0,1,2,3,4,5 -n 1 > "${output}/xpu-before.txt" 2>&1 || true

cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill -TERM "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  systemctl --user stop "${unit}.scope" >/dev/null 2>&1 || true
  free -b > "${output}/memory-after.txt" 2>/dev/null || true
  xpu-smi dump -d 0 -m 0,1,2,3,4,5 -n 1 > "${output}/xpu-after.txt" 2>&1 || true
}
trap cleanup EXIT INT TERM

set +e
systemd-run --user --scope --quiet --collect --unit="${unit}" \
  -p MemoryHigh=11G -p MemoryMax=13G -p MemorySwapMax=12G \
  timeout --signal=TERM --kill-after=30 3600 "${cmd[@]}" >"${output}/server.log" 2>&1 &
server_pid=$!
set -e

healthy=0
for _ in $(seq 1 420); do
  if curl -fsS "http://127.0.0.1:${port}/health" > "${output}/health.json" 2>/dev/null; then healthy=1; break; fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then break; fi
  sleep 1
done
if (( healthy == 0 )); then
  set +e; wait "${server_pid}"; status=$?; set -e
  printf '%s\n' "${status}" > "${output}/server-exit-status.txt"
  if rg -qi 'out of memory|allocation.*fail|alloc.*failed|PI_ERROR_OUT_OF_RESOURCES' "${output}/server.log"; then
    printf '{"classification":"unsupported-fit","exit_status":%s}\n' "${status}" > "${output}/qualification.json"
    printf 'UNSUPPORTED-FIT: %s\n' "${output}"
    exit 4
  fi
  fail "server did not become healthy; retained at ${output}"
fi
curl -fsS "http://127.0.0.1:${port}/props" > "${output}/props.json"
curl -fsS "http://127.0.0.1:${port}/slots" > "${output}/slots-before.json"

set +e
"${python}" -B "${quality}" --base-url "http://127.0.0.1:${port}" \
  --model qwen38-q8weights-f16-tp1 --tokenizer "${tokenizer}" \
  --repeat-runs 8 --long-context-tokens 8192 --timeout 900 \
  --request-id-prefix qwen38-q8-service-quality-r1 \
  --output-json "${output}/quality.json" | tee "${output}/quality-summary.txt"
quality_status=${PIPESTATUS[0]}
set -e
printf '%s\n' "${quality_status}" > "${output}/quality-exit-status.txt"
curl -fsS "http://127.0.0.1:${port}/slots" > "${output}/slots-after.json"

"${python}" -B - "${output}/quality.json" > "${output}/qualification.json" <<'PY'
import json, sys
d=json.load(open(sys.argv[1], encoding='utf-8'))
runs=list(d['exact_cases']) + list(d['repeat_case']['runs']) + [d['long_context_case']]
cached=[]
for row in runs:
    usage=row.get('usage') or {}
    details=usage.get('prompt_tokens_details') or {}
    cached.append(details.get('cached_tokens'))
checks={
    'pass_all': d.get('pass_all') is True,
    'exact_cases_7_of_7': len(d.get('exact_cases') or []) == 7 and all(x.get('pass') is True for x in d['exact_cases']),
    'repeat_hash_8_of_8': d['repeat_case'].get('repeats') == 8 and d['repeat_case'].get('pass') is True and len(d['repeat_case'].get('unique_hashes') or []) == 1,
    'long_context_needle': d.get('long_context_case', {}).get('pass') is True,
    'long_context_fits_8192': int(d.get('long_context_case', {}).get('actual_prompt_tokens', 999999)) < 8192,
    'cached_tokens_explicit_zero': len(cached) == 16 and all(x == 0 for x in cached),
}
qualified=all(checks.values())
out={
    'classification': 'service-quality-qualified' if qualified else 'service-quality-failed',
    'checks': checks,
    'response_count': len(runs),
    'cached_tokens': cached,
    'baseline_comparison': 'not required; Q4_K_M is a different weight quantization',
}
json.dump(out,sys.stdout,indent=2); print()
if not qualified: raise SystemExit(3)
PY

(( quality_status == 0 )) || fail "quality suite exited ${quality_status}"
printf 'PASS: %s\n' "${output}"
