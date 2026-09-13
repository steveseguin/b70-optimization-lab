#!/usr/bin/env bash
# R304 rerun (2026-09-13) of the r189 real-content 2K-32K depth ladder: identical to the original script except the image
# (the v0.29.0 rebase), its identities, and the output root. Both cards.
# R189 (2026-09-03): R150 depth curve re-measured on the R187 line (R156 image, whole-graph compile). Original header:
# R150: 2K-32K real-content depth matrix on the R139 image, MTP0 oracle then MTP1.
# R147c: MTP0-only determinism qualification on the R139 fixed-K W8A16 image:
# a third same-image MTP0 strict server with the 100-300-token repeat probe,
# then an MTP0 c1-c64 identity ladder. Amendment to the R147 preregistration. Preregistration:
# experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-prereg.json
set -uo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
repro=${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
root=${ROOT:-/mnt/fast-ai/bench-results/qwen38-fp8-r304-real-content-depth-20260913}
image=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304
image_id=sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2
ext_sha=bbce7295fb8a58bad456675cfac7cdf3d1e29fe7a9dd5c0970741b130616c932
model_dir=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-fp8}
port=18128
# RESUME_FROM=mtp1-b ORACLE_ROOT=<original root> resumes after a fault on a fresh boot,
# reusing the original mtp0-a oracle and mtp1-a attempt; ROOT must be a new sibling.
resume=${RESUME_FROM:-}
oracle_root=${ORACLE_ROOT:-/mnt/fast-ai/bench-results/qwen38-fp8-fixed-k-regenerated-oracle-20260902-r147}
strict_suite=${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json
ladder_suite=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
frozen_oracle=${repo}/experiments/qwen38-27b-b70/data/qwen38-fp8-mtp0-explicit-deterministic-r54a-r50
probe=${script_dir}/probe-qwen38-fp8-c1-prefill-length-determinism.py
ladder=${repo}/scripts/bench-openai-concurrency-oracle.py
compare=${repo}/scripts/compare-strict-attempt-outputs.py
canaries=${repo}/scripts/neural-download-canaries.py
health=${repo}/scripts/check-qwen36-xpu-xccl-health.sh
health_timeout=3600
fault_re='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup'

export EXPECTED_XPU_EXTENSION_SHA256=${ext_sha}
# R304 (2026-09-13): the v0.29.0 rebase; the image contract selects its own digest set from the kernel-head label.
export EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0 EXPECTED_XPU_OPS_SHA256=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3 EXPECTED_LAYERNORM_SHA256=3f949e537ccc52744d7eba52ed2034b20ee3fbaeaabbfab4e672f1dc9767602c
export MODEL_DIR=${model_dir}

log() { printf '[r147 %s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "${root}/campaign.log"; }
abort() { log "ABORT: $*"; printf '%s\n' "$*" >"${root}/ABORTED"; exit 2; }

mkdir -p "${root}"
[[ -e "${root}/campaign-start.txt" ]] && { echo "campaign root already used: ${root}" >&2; exit 1; }
date --iso-8601=seconds >"${root}/campaign-start.txt"
campaign_start=$(date '+%Y-%m-%d %H:%M:%S')
cat /proc/sys/kernel/random/boot_id >"${root}/boot-id.txt"
git -C "${repo}" rev-parse HEAD >"${root}/repo-head.txt"

devices_normal() {
  xpu-smi discovery >"${root}/$1-xpu-smi-discovery.txt" 2>&1 || true
  [[ "$(grep -c 'Device State: normal' "${root}/$1-xpu-smi-discovery.txt")" == 2 ]]
}
journal_check() {
  journalctl -k -b 0 --no-pager --since "${campaign_start}" >"${root}/$1-kernel-journal.txt" 2>&1 || true
  ! grep -qiE "${fault_re}" "${root}/$1-kernel-journal.txt"
}
lane_containers() { docker ps --format '{{.Names}}' | grep -c 'qwen38' || true; }
postflight() {
  local tag=$1
  devices_normal "${tag}" || abort "${tag}: a B70 is not in normal state"
  journal_check "${tag}" || abort "${tag}: fault signature in the kernel journal"
  ROOT="${repo}" "${health}" >"${root}/${tag}-compute-xccl.txt" 2>&1 || abort "${tag}: compute/XCCL health failed"
  [[ "$(lane_containers)" == 0 ]] || abort "${tag}: a lane container is still running"
  log "${tag}: postflight clean"
}
wait_health() {
  local pid=$1 deadline=$(( $(date +%s) + health_timeout ))
  while (( $(date +%s) < deadline )); do
    curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1 && return 0
    kill -0 "${pid}" 2>/dev/null || return 1
    sleep 15
  done
  return 1
}
stop_server() {
  local name=$1 pid=$2 dir=$3
  docker inspect "${name}" >"${dir}/container-inspect.json" 2>/dev/null || true
  docker stop -t 180 "${name}" >/dev/null 2>&1 || true
  wait "${pid}" 2>/dev/null || true
  grep -iE "${fault_re}" "${dir}/server.log" >"${dir}/server-fault-lines.txt" || true
  [[ ! -s "${dir}/server-fault-lines.txt" ]] || abort "$(basename "${dir}"): fault signature in server.log"
}
# launch <label> <mtp0|mtp1> <max_model_len> <max_num_seqs> <max_batched>
launch() {
  local label=$1 kind=$2 mml=$3 mns=$4 mbt=$5 dir=${root}/$1 cache=${root}/$1-cache
  mkdir -p "${dir}"; [[ ! -e "${cache}" ]] || abort "${label}: cache exists"; mkdir -p "${cache}"
  local name=qwen38-fp8-r147-${label} served=qwen38-fp8-fixed-k-r147-${label}
  date --iso-8601=seconds >"${dir}/started-at.txt"
  if [[ "${kind}" == mtp0 ]]; then
    env IMAGE="${image}" EXPECTED_IMAGE_ID="${image_id}" VLLM_CACHE_DIR="${cache}" \
      CONTAINER_NAME="${name}" PORT="${port}" SERVED_MODEL_NAME="${served}" \
      MAX_MODEL_LEN="${mml}" MAX_NUM_SEQS="${mns}" MAX_NUM_BATCHED_TOKENS="${mbt}" \
      CONTAINER_MEMORY=12g CONTAINER_MEMORY_SWAP=16g \
      "${script_dir}/run-20260903-qwen38-fp8-mtp0-whole-graph-r187-server.sh" >"${dir}/server.log" 2>&1 &
  else
    env IMAGE="${image}" EXPECTED_IMAGE_ID="${image_id}" VLLM_CACHE_DIR="${cache}" \
      CONTAINER_NAME="${name}" PORT="${port}" SERVED_MODEL_NAME="${served}" \
      MAX_MODEL_LEN="${mml}" MAX_NUM_SEQS="${mns}" MAX_NUM_BATCHED_TOKENS="${mbt}" \
      "${script_dir}/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh" >"${dir}/server.log" 2>&1 &
  fi
  server_pid=$!
  log "${label}: launched ${kind} pid ${server_pid}"
  wait_health "${server_pid}" || { docker stop -t 60 "${name}" >/dev/null 2>&1 || true; abort "${label}: server did not become healthy"; }
  log "${label}: healthy"
  server_name=${name}; server_dir=${dir}; served_model=${served}
}
strict_attempt() {
  local label=$1
  python3 "${canaries}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" \
    --out "${server_dir}/pre-canaries.json" >"${server_dir}/pre-canaries.stdout" 2>&1 || abort "${label}: pre-canaries failed"
  OUT_DIR="${server_dir}/strict" BASE_URL="http://127.0.0.1:${port}" MODEL_NAME="${served_model}" \
    PROFILE_LABEL="r147-${label}" ATTEMPT_LABEL="fresh-cache-${label}" \
    "${repro}/bench-w8a16-mtp1-strict.sh" >"${server_dir}/strict.stdout" 2>&1 || abort "${label}: strict suite failed its workload/cache/canary gate"
  log "${label}: $(grep class_balanced_median_tok_s "${server_dir}/strict.stdout")"
}
compare_pair() { python3 "${compare}" "$1" "$2" --output "$3" >/dev/null 2>&1 || true; python3 -c "import json,sys;c=json.load(open(sys.argv[1]))['comparison'];print(f\"{c['exact_prompts']}/{c['total_prompts']}\")" "$3"; }

# ---------------- preflight ----------------
[[ "$(lane_containers)" == 0 ]] || abort "preflight: lane container running"
[[ "$(docker image inspect "${image}" --format '{{.Id}}')" == "${image_id}" ]] || abort "preflight: image id mismatch"
for f in "${strict_suite}" "${ladder_suite}" "${probe}" "${ladder}" "${compare}" "${canaries}" "${health}" "${frozen_oracle}/performance.json"; do
  [[ -f "${f}" ]] || abort "preflight: missing ${f}"
done
devices_normal preflight || abort "preflight: a B70 is not normal"
ROOT="${repo}" "${health}" >"${root}/preflight-compute-xccl.txt" 2>&1 || abort "preflight: compute/XCCL health failed"
journalctl -k -b 0 --no-pager >"${root}/preflight-kernel-journal-full.txt" 2>&1 || true
grep -iE "${fault_re}" "${root}/preflight-kernel-journal-full.txt" >"${root}/preflight-kernel-fault-lines.txt" || true
if [[ -s "${root}/preflight-kernel-fault-lines.txt" ]]; then
  [[ -n "${resume}" && "${ALLOW_FAULTED_BOOT:-0}" == 1 ]] || abort "preflight: this boot already carries a fault signature"
  log "WARNING: continuing on a boot with prior fault signatures by explicit user authorization (ALLOW_FAULTED_BOOT=1); speed from this run is diagnostic only"
fi
log "preflight clean; boot $(cat "${root}/boot-id.txt")"

depth_stage() {
  local label=$1 kind=$2 oracle=$3
  launch "${label}" "${kind}" 33024 1 4096
  OUT_DIR="${server_dir}/depth" ARM="${kind}" BASE_URL="http://127.0.0.1:${port}" SERVED_MODEL_NAME="${served_model}" ORACLE_DIR="${oracle}" \
    "${repro}/bench-w8a16-real-content-depth.sh" >"${server_dir}/depth.stdout" 2>&1 || log "${label}: depth bench exited nonzero"
  log "${label}: $(tail -n 2 "${server_dir}/depth.stdout" | tr '\n' ' ' | cut -c1-200)"
  stop_server "${server_name}" "${server_pid}" "${server_dir}"
  postflight "${label}-post"
}
depth_stage depth-mtp0 mtp0 ""
depth_stage depth-mtp1 mtp1 "${root}/depth-mtp0/depth"
date --iso-8601=seconds >"${root}/campaign-end.txt"
log "campaign complete"
