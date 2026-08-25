#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
campaign=qwen38-q8weights-f16-tp1-local-20260825-r2
ack="RUN ${campaign}"
manifest="${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8weights-f16-tp1-local-r2-prereg.json"
model=/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/Qwen3.8-27B-Q8_0.gguf
build=/mnt/extended-ssd/steve-archive/active-qwen38-tp1-concurrency-20260825/build-sycl-aot-bmg-g31
bench="${build}/bin/llama-bench"
backend="${build}/bin/libggml-sycl.so"
output=/mnt/extended-ssd/b70-runs/qwen38-q8weights-f16-tp1-local-20260825-r2
model_sha=f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8
bench_sha=f8fe61241c010d91dba839ff3d5505def9ba569ae98c0ca498efc01b5fb4e2f0
backend_sha=0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
if [[ "${1:-}" != --execute ]]; then
  jq '{campaign_id,state,model,runtime,measurement,execution}' "${manifest}"
  exit 0
fi
[[ "${2:-}" == --ack && "${3:-}" == "${ack}" && $# -eq 3 ]] || fail "exact acknowledgement required: ${ack}"
[[ -f "${manifest}" && -f "${model}" && -x "${bench}" && -f "${backend}" ]] || fail 'frozen dependency missing'

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
# The unprivileged shell intentionally opens the protected local password file;
# sudo reads only its contents on stdin and command output remains captured.
# shellcheck disable=SC2024
container_ids=$(sudo -S -p '' docker ps -q < /home/steve/SUDOPASSWORD.txt 2>/dev/null) || fail 'could not verify Docker state'
[[ -z "${container_ids}" ]] || fail 'a Docker container is running'

[[ "$(stat -c %s "${model}")" == 28595763552 ]] || fail 'model size mismatch'
[[ "$(sha256sum "${model}" | awk '{print $1}')" == "${model_sha}" ]] || fail 'model SHA mismatch'
[[ "$(sha256sum "${bench}" | awk '{print $1}')" == "${bench_sha}" ]] || fail 'bench SHA mismatch'
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == "${backend_sha}" ]] || fail 'backend SHA mismatch'
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

cmd=("${bench}" -m "${model}" -dev SYCL0 -ngl 99 -sm layer -p 2048 -n 128
  -d "0,2048,4096,8192,16384,24576,32768" -b 2048 -ub 512 -fa on
  -ctk f16 -ctv f16 -t 16 --poll 50 -r 5 -o json)
printf '%q ' "${cmd[@]}" > "${output}/command.txt"; printf '\n' >> "${output}/command.txt"
env | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|ONEAPI_ROOT=|LD_LIBRARY_PATH=|PATH=)' | LC_ALL=C sort > "${output}/environment.txt"
sha256sum "${model}" "${bench}" "${backend}" "${manifest}" > "${output}/sha256sums.txt"
free -b > "${output}/memory-before.txt"
xpu-smi dump -d 0 -m 0,1,2,3,4,5 -n 1 > "${output}/xpu-before.txt" 2>&1 || true

set +e
systemd-run --user --scope --quiet --collect -p MemoryHigh=11G -p MemoryMax=13G -p MemorySwapMax=12G \
  timeout --signal=TERM --kill-after=30 3600 "${cmd[@]}" > "${output}/raw.json" 2> "${output}/stderr.log"
status=$?
set -e
printf '%s\n' "${status}" > "${output}/exit-status.txt"
free -b > "${output}/memory-after.txt"
xpu-smi dump -d 0 -m 0,1,2,3,4,5 -n 1 > "${output}/xpu-after.txt" 2>&1 || true

if (( status != 0 )); then
  if rg -qi 'out of memory|allocation.*fail|alloc.*failed|PI_ERROR_OUT_OF_RESOURCES' "${output}/stderr.log" "${output}/raw.json"; then
    printf '{"classification":"unsupported-fit","exit_status":%s}\n' "${status}" > "${output}/result.json"
    printf 'UNSUPPORTED-FIT: %s\n' "${output}"
    exit 4
  fi
  fail "benchmark exited ${status}; evidence retained at ${output}"
fi

python3 -B - "${output}/raw.json" > "${output}/result.json" <<'PY'
import json, sys
rows=json.load(open(sys.argv[1], encoding='utf-8'))
depths=[0,2048,4096,8192,16384,24576,32768]
if len(rows)!=14: raise SystemExit(f'expected 14 rows, got {len(rows)}')
seen=[]
for row in rows:
    kind='decode' if row.get('n_prompt')==0 and row.get('n_gen')==128 else 'prefill' if row.get('n_prompt')==2048 and row.get('n_gen')==0 else None
    if kind is None: raise SystemExit(f'unexpected row shape: {row.get("n_prompt")}/{row.get("n_gen")}')
    if len(row.get('samples_ts') or [])!=5: raise SystemExit('every row must contain five samples')
    seen.append((row.get('n_depth'),kind))
expected=[(d,k) for d in depths for k in ('prefill','decode')]
if sorted(seen)!=sorted(expected): raise SystemExit(f'matrix mismatch: {seen}')
json.dump({'classification':'complete-raw-engine','quality_gate':'artifact quality is separate','rows':rows},sys.stdout,indent=2); print()
PY
printf 'PASS: %s\n' "${output}"
