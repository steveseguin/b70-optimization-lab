#!/usr/bin/env bash
# R152: R139 + Triton RMSNorm image; same-image regenerated oracle, repeat probe,
# and c1-c64 identity ladders on both profiles. Preregistration:
# experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-prereg.json
set -uo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
repro=${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
root=${ROOT:-/mnt/fast-ai/bench-results/qwen38-fp8-triton-rmsnorm-20260902-r152}
image=${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-triton-rmsnorm-r152}
image_id=${IMAGE_ID_OVERRIDE:?set IMAGE_ID_OVERRIDE to the built R152 image id}
export EXPECTED_XPU_OPS_SHA256=${XPU_OPS_SHA256_OVERRIDE:-}
export EXPECTED_XPU_COMMUNICATOR_SHA256=${XPU_COMMUNICATOR_SHA256_OVERRIDE:-}
export EXPECTED_LAYERNORM_SHA256=${LAYERNORM_SHA256_OVERRIDE:-c2562d10a2ddb58763c556389372cd621c1de1ce78db000ac22f59aee31e6740}
export VLLM_XPU_GEMMA_RMSNORM_TRITON=${GEMMA_TRITON:-1}
export VLLM_XPU_RMSNORM_TRITON=${RMSNORM_TRITON:-1}
export VLLM_XPU_LM_HEAD_CHUNK_ROWS=${LM_HEAD_CHUNK_ROWS:-0}
export VLLM_XPU_GDN_SPLIT_MIXED=${GDN_SPLIT_MIXED:-0}
export VLLM_XPU_ENABLE_XPU_GRAPH=${XPU_GRAPH:-0}
export VLLM_XPU_DRAFT_LM_HEAD_INT4_APPLY_ROWS=${DRAFT_HEAD_APPLY_ROWS:-0}
ext_sha=f912e12de1d79206221142c9a50af2aba70d2c77c735c9cd2d5d8d9def0740d1
model_dir=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-fp8}
port=18128
# RESUME_FROM=mtp1-b ORACLE_ROOT=<original root> resumes after a fault on a fresh boot,
# reusing the original mtp0-a oracle and mtp1-a attempt; ROOT must be a new sibling.
resume=${RESUME_FROM:-}
oracle_root=${ORACLE_ROOT:-${root}}
strict_suite=${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json
ladder_suite=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
frozen_oracle=${repo}/experiments/qwen38-27b-b70/data/qwen38-fp8-mtp0-explicit-deterministic-r54a-r50
probe=${script_dir}/probe-qwen38-fp8-c1-prefill-length-determinism.py
ladder=${repo}/scripts/bench-openai-concurrency-oracle.py
compare=${repo}/scripts/compare-strict-attempt-outputs.py
canaries=${repo}/scripts/neural-download-canaries.py
health=${repo}/scripts/check-qwen36-xpu-xccl-health.sh
health_timeout=2700
fault_re='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup'

# XPU_EXTENSION_SHA256_OVERRIDE: candidates that replace _xpu_C.abi3.so (R139-style rebuilt kernel library, e.g. R221) pass their exact digest.
export EXPECTED_XPU_EXTENSION_SHA256=${XPU_EXTENSION_SHA256_OVERRIDE:-${ext_sha}}
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
      "${repro}/run-w8a16-mtp0-strict-server.sh" >"${dir}/server.log" 2>&1 &
  else
    env IMAGE="${image}" EXPECTED_IMAGE_ID="${image_id}" VLLM_CACHE_DIR="${cache}" \
      CONTAINER_NAME="${name}" PORT="${port}" SERVED_MODEL_NAME="${served}" \
      MAX_MODEL_LEN="${mml}" MAX_NUM_SEQS="${mns}" MAX_NUM_BATCHED_TOKENS="${mbt}" \
      "${script_dir}/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh" >"${dir}/server.log" 2>&1 &
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

# ---------------- MTP0 controls ----------------
if [[ "${QUERY_ONLY:-0}" == 1 ]]; then
  # QUERY_ONLY=1 QUERY_KINDS="mtp1 mtp0" QUERY_SCRIPT=<python>: launch each kind (strict config), run the script against it, stop.
  for kind in ${QUERY_KINDS:-mtp1 mtp0}; do
    launch "query-${kind}" "${kind}" ${QUERY_LAUNCH:-1024 1 1024}
    python3 "${QUERY_SCRIPT}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" \
      --out "${server_dir}/query.json" >"${server_dir}/query.stdout" 2>&1 || log "query-${kind}: script exited nonzero"
    log "query-${kind}: $(tail -n 1 "${server_dir}/query.stdout")"
    stop_server "${server_name}" "${server_pid}" "${server_dir}"
    postflight "query-${kind}-post"
  done
  date --iso-8601=seconds >"${root}/campaign-end.txt"; log "campaign complete"; exit 0
fi
if [[ "${PROBE_AND_LADDER_MTP1:-0}" == 1 ]]; then
  log "PROBE_AND_LADDER_MTP1: repeat probe on a strict-config MTP1 server, then the c1-c64 ladder"
  launch probe-mtp1 mtp1 1024 1 1024
  python3 "${probe}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" \
    --out "${server_dir}/medium-prefill-probe.json" >"${server_dir}/medium-prefill-probe.stdout" 2>&1 || log "probe exited nonzero"
  log "G5 probe: $(tail -n 3 "${server_dir}/medium-prefill-probe.stdout" | tr '\n' ' ')"
  stop_server "${server_name}" "${server_pid}" "${server_dir}"
  postflight probe-mtp1-post
  launch ladder mtp1 256 64 512
  python3 "${ladder}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" --api-mode completions \
    --suite "${ladder_suite}" --concurrency 1,2,4,8,16,32,64 --repeats 1 --max-tokens 128 \
    --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' \
    --return-token-ids --require-output-identity \
    --out "${server_dir}/ladder.json" >"${server_dir}/ladder.stdout" 2>&1
  log "G6 ladder harness exit $?"
  stop_server "${server_name}" "${server_pid}" "${server_dir}"
  postflight ladder-post
  date --iso-8601=seconds >"${root}/campaign-end.txt"; log "campaign complete"; exit 0
fi
if [[ "${STRICT_MTP1_ONLY:-0}" == 1 ]]; then
  log "STRICT_MTP1_ONLY: two MTP1 candidates against the oracle at ${oracle_root}/mtp0-a"
  for label in mtp1-a mtp1-b; do
    launch "${label}" mtp1 1024 1 1024
    strict_attempt "${label}"
    stop_server "${server_name}" "${server_pid}" "${server_dir}"
    postflight "${label}-post"
  done
  log "G2 mtp1-a vs mtp1-b: $(compare_pair "${root}/mtp1-a/strict" "${root}/mtp1-b/strict" "${root}/compare-mtp1-a-vs-mtp1-b.json")"
  log "G3 mtp1-a vs oracle: $(compare_pair "${root}/mtp1-a/strict" "${oracle_root}/mtp0-a/strict" "${root}/compare-mtp1-a-vs-mtp0-a.json")"
  log "G3 mtp1-b vs oracle: $(compare_pair "${root}/mtp1-b/strict" "${oracle_root}/mtp0-a/strict" "${root}/compare-mtp1-b-vs-mtp0-a.json")"
  date --iso-8601=seconds >"${root}/campaign-end.txt"; log "campaign complete"; exit 0
fi
if [[ "${LADDERS_ONLY:-0}" == 1 ]]; then
  log "LADDERS_ONLY: skipping the strict oracle and candidate stages"
  launch ladder mtp1 256 64 512
  python3 "${ladder}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" --api-mode completions \
    --suite "${ladder_suite}" --concurrency 1,2,4,8,16,32,64 --repeats 1 --max-tokens 128 \
    --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' \
    --return-token-ids --require-output-identity \
    --out "${server_dir}/ladder.json" >"${server_dir}/ladder.stdout" 2>&1
  log "G6 ladder harness exit $?"
  stop_server "${server_name}" "${server_pid}" "${server_dir}"
  postflight ladder-post
  launch ladder-mtp0 mtp0 256 64 512
  python3 "${ladder}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" --api-mode completions \
    --suite "${ladder_suite}" --concurrency 1,2,4,8,16,32,64 --repeats 1 --max-tokens 128 \
    --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' \
    --return-token-ids --require-output-identity \
    --out "${server_dir}/ladder.json" >"${server_dir}/ladder.stdout" 2>&1
  log "G6(mtp0) ladder harness exit $?"
  stop_server "${server_name}" "${server_pid}" "${server_dir}"
  postflight ladder-mtp0-post
  date --iso-8601=seconds >"${root}/campaign-end.txt"; log "campaign complete"; exit 0
fi
if [[ -n "${resume}" ]]; then
  [[ "${resume}" == mtp1-b && -f "${oracle_root}/mtp0-a/strict/performance.json" && -f "${oracle_root}/mtp1-a/strict/performance.json" ]] || abort "resume: need RESUME_FROM=mtp1-b and an ORACLE_ROOT holding mtp0-a and mtp1-a"
  for d in mtp0-a mtp0-b mtp1-a; do ln -s "${oracle_root}/${d}" "${root}/${d}"; done
  for f in "${oracle_root}"/compare-*.json; do ln -s "${f}" "${root}/"; done
  log "resume from mtp1-b using oracle root ${oracle_root}"
fi
for label in mtp0-a mtp0-b; do
  [[ -z "${resume}" ]] || break
  launch "${label}" mtp0 1024 1 1024
  strict_attempt "${label}"
  stop_server "${server_name}" "${server_pid}" "${server_dir}"
  postflight "${label}-post"
done
g1=$(python3 -c "import json,sys;c=json.load(open(sys.argv[1]))['comparison'];print(f\"{c['exact_prompts']}/{c['total_prompts']}\")" "${root}/compare-mtp0-a-vs-mtp0-b.json" 2>/dev/null || compare_pair "${root}/mtp0-a/strict" "${root}/mtp0-b/strict" "${root}/compare-mtp0-a-vs-mtp0-b.json")
log "G1 mtp0-a vs mtp0-b: ${g1}"
[[ "${g1}" == "12/12" ]] || abort "G1 failed (${g1}): same-image MTP0 is not repeat-exact; no MTP1 launch"
log "information: mtp0-a vs frozen R54a natural oracle: $(compare_pair "${root}/mtp0-a/strict" "${frozen_oracle}" "${root}/compare-mtp0-a-vs-r54a.json")"

# ---------------- MTP1 candidates ----------------
for label in mtp1-a mtp1-b; do
  [[ -z "${resume}" || "${label}" != mtp1-a ]] || continue
  launch "${label}" mtp1 1024 1 1024
  strict_attempt "${label}"
  if [[ "${label}" == mtp1-b ]]; then
    python3 "${probe}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" \
      --out "${server_dir}/medium-prefill-probe.json" >"${server_dir}/medium-prefill-probe.stdout" 2>&1 || log "probe exited nonzero"
    log "G5 probe: $(tail -n 3 "${server_dir}/medium-prefill-probe.stdout" | tr '\n' ' ')"
  fi
  stop_server "${server_name}" "${server_pid}" "${server_dir}"
  postflight "${label}-post"
done
log "G2 mtp1-a vs mtp1-b: $(compare_pair "${root}/mtp1-a/strict" "${root}/mtp1-b/strict" "${root}/compare-mtp1-a-vs-mtp1-b.json")"
log "G3 mtp1-a vs mtp0-a: $(compare_pair "${root}/mtp1-a/strict" "${root}/mtp0-a/strict" "${root}/compare-mtp1-a-vs-mtp0-a.json")"
log "G3 mtp1-b vs mtp0-a: $(compare_pair "${root}/mtp1-b/strict" "${root}/mtp0-a/strict" "${root}/compare-mtp1-b-vs-mtp0-a.json")"
log "information: mtp1-a vs frozen R54a: $(compare_pair "${root}/mtp1-a/strict" "${frozen_oracle}" "${root}/compare-mtp1-a-vs-r54a.json")"

# ---------------- identity ladder ----------------
launch ladder mtp1 256 64 512
python3 "${ladder}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" --api-mode completions \
  --suite "${ladder_suite}" --concurrency 1,2,4,8,16,32,64 --repeats 1 --max-tokens 128 \
  --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' \
  --return-token-ids --require-output-identity \
  --out "${server_dir}/ladder.json" >"${server_dir}/ladder.stdout" 2>&1
ladder_rc=$?
echo "${ladder_rc}" >"${server_dir}/ladder.rc"
log "G6 ladder harness exit ${ladder_rc}"
grep -c "R152 Gemma RMSNorm Triton route armed" "${server_dir}/server.log" >"${server_dir}/r152-marker-count.txt" || true
log "ladder: R152 marker lines $(cat "${server_dir}/r152-marker-count.txt")"
stop_server "${server_name}" "${server_pid}" "${server_dir}"
postflight ladder-post
launch ladder-mtp0 mtp0 256 64 512
python3 "${ladder}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" --api-mode completions \
  --suite "${ladder_suite}" --concurrency 1,2,4,8,16,32,64 --repeats 1 --max-tokens 128 \
  --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' \
  --return-token-ids --require-output-identity \
  --out "${server_dir}/ladder.json" >"${server_dir}/ladder.stdout" 2>&1
ladder_rc=$?
echo "${ladder_rc}" >"${server_dir}/ladder.rc"
log "G6(mtp0) ladder harness exit ${ladder_rc}"
stop_server "${server_name}" "${server_pid}" "${server_dir}"
postflight ladder-mtp0-post
date --iso-8601=seconds >"${root}/campaign-end.txt"
log "campaign complete"
