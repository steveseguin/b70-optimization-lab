#!/usr/bin/env bash
# Qwen3.5-9B campaign harness v3 (2026-09-09), derived from run-20260907-qwen35-campaign.sh.
# v2 is preserved unchanged as the record of the 2026-09-07 campaigns; v3 is the four-card variant.
#
# Why v3 exists (three v2 literals abort on this host, steve-b70s / 4x B70 / 125 GiB):
#   1. repo=/home/steve/b70-optimization-lab was an absolute path; v3 resolves the repo from its own location.
#   2. devices_normal() grep'd 'Device State: normal' and required exactly 2. This driver's xpu-smi
#      (CLI 1.3.6.20260210) prints no Device State line at all, so the gate failed closed on every run.
#      v3 uses `xpu-smi health -d N` per device and requires every subsystem Status: OK.
#   3. lane_containers() counted every qwen3[58] container host-wide and health checked every card.
#      With parallel single-card arms that aborts each arm on its neighbours. v3 scopes both to this arm.
#
# env: as v2, plus ARM_DEVICES (default = mask; the cards this arm owns), CAMPAIGN_DATE, REPO,
#      EXPECTED_DEVICES (default = all discovered).
set -uo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=${REPO:-$(cd -- "${here}/../../.." && pwd)}
out=${OUT_ROOT:-/mnt/fast-ai/bench-results}
LANE=${LANE:-qwen35-9b-w4a16}; QUANT=${QUANT:-compressed-tensors}; W4A16_PAD=${W4A16_PAD:-0}
CAMPAIGN_DATE=${CAMPAIGN_DATE:-$(date +%Y%m%d)}
RUN=${RUN:?set RUN}; TP=${TP:-1}; DEPTH=${DEPTH:-3}; GRAPH=${GRAPH:-1}; DRAFT_HEAD=${DRAFT_HEAD:-1}
STAGES=${STAGES:-strict ladders}; port=${PORT:-18131}
root=${ROOT:-${out}/${LANE}-tp${TP}-mtp${DEPTH}-graph${GRAPH}$([[ "${DRAFT_HEAD}" == 1 ]] && echo -dhint4)$([[ "${W4A16_PAD}" == 1 ]] && echo -pad)-${CAMPAIGN_DATE}-${RUN}}
repro=${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-sync-free-r276}
image_id=${IMAGE_ID:-sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad}
model_dir=${MODEL_DIR:-/home/steve/llm-models/qwen35-9b-w4a16}
manifest=${MODEL_MANIFEST:-${repo}/experiments/qwen35-9b-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json}
strict_suite=${STRICT_SUITE:-${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}
ladder_suite=${LADDER_SUITE:-${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json}
ladder=${repo}/scripts/bench-openai-concurrency-oracle.py; compare=${repo}/scripts/compare-strict-attempt-outputs.py
health=${repo}/scripts/check-qwen36-xpu-xccl-health.sh; health_timeout=${HEALTH_TIMEOUT:-1800}
health_python=${HEALTH_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}
fault_re='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup'
if [[ "$TP" == 2 ]]; then mask=${XPU_DEVICE_MASK:-0,1}; else mask=${XPU_DEVICE_MASK:-0}; fi
ARM_DEVICES=${ARM_DEVICES:-${mask}}
if [[ "$GRAPH" == 1 ]]; then
  comp=${COMPILATION_CONFIG_OVERRIDE:-'{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64],"max_cudagraph_capture_size":64,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'}
  eager=0; xgraph=1
else
  comp=${COMPILATION_CONFIG_OVERRIDE:-'{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'}
  eager=0; xgraph=0
fi
log() { printf '[q35 %s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "${root}/campaign.log"; }
abort() {
  log "ABORT: $*"; printf '%s\n' "$*" >"${root}/ABORTED"
  # Release the card and port before leaving. A failed arm that leaves its container up holds the
  # device and the bound port, so the next arm dispatched there dies for a reason that has nothing
  # to do with its own lever - which is how one bad assertion took out a whole queue on 2026-09-09.
  local c
  for c in $(docker ps --format '{{.Names}}' | grep -E "^${LANE}-${RUN}-" || true); do
    log "ABORT: stopping ${c}"; docker stop -t 120 "${c}" >/dev/null 2>&1 || true
  done
  exit 2
}
mkdir -p "${root}"; [[ -e "${root}/campaign-start.txt" ]] && { echo "campaign root already used: ${root}" >&2; exit 1; }
date --iso-8601=seconds >"${root}/campaign-start.txt"; campaign_start=$(date '+%Y-%m-%d %H:%M:%S')
cat /proc/sys/kernel/random/boot_id >"${root}/boot-id.txt"; git -C "${repo}" rev-parse HEAD >"${root}/repo-head.txt"
printf 'LANE=%s RUN=%s TP=%s DEPTH=%s GRAPH=%s DRAFT_HEAD=%s QUANT=%s PAD=%s mask=%s arm_devices=%s model=%s image=%s port=%s\n' \
  "$LANE" "$RUN" "$TP" "$DEPTH" "$GRAPH" "$DRAFT_HEAD" "$QUANT" "$W4A16_PAD" "$mask" "$ARM_DEVICES" "$model_dir" "$image_id" "$port" >"${root}/config.txt"

# v3: per-device health. Requires rc=0 and no non-OK Status line for every card this arm owns.
devices_normal() {
  local tag=$1 f="${root}/$1-xpu-smi-health.txt" d rc=0
  : >"${f}"
  for d in ${ARM_DEVICES//,/ }; do
    { echo "--- device ${d} ---"; timeout 60 xpu-smi health -d "${d}" 2>&1; } >>"${f}" || rc=1
  done
  (( rc == 0 )) || return 1
  ! grep -E '^\|.*Status:' "${f}" | grep -qv 'Status: OK'
}
journal_check() { journalctl -k -b 0 --no-pager --since "${campaign_start}" >"${root}/$1-kernel-journal.txt" 2>&1 || true; ! grep -qiE "${fault_re}" "${root}/$1-kernel-journal.txt"; }
# v3: only this arm's own containers, so parallel arms on other cards do not abort each other.
lane_containers() { docker ps --format '{{.Names}}' | grep -cE "^${LANE}-${RUN}-" || true; }
arm_health() { PYTHON="${health_python}" PHYSICAL_DEVICES="${ARM_DEVICES}" XCCL_DEVICES="${ARM_DEVICES}" ROOT="${repo}" "${health}"; }
postflight() { devices_normal "$1" || abort "$1: a B70 this arm owns is not healthy"; journal_check "$1" || abort "$1: fault signature in the kernel journal"; arm_health >"${root}/$1-compute-xccl.txt" 2>&1 || abort "$1: compute/XCCL health failed"; [[ "$(lane_containers)" == 0 ]] || abort "$1: this arm's container is still running"; log "$1: postflight clean"; }
wait_health() { local pid=$1 deadline=$(( $(date +%s) + health_timeout )); while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1 && return 0; kill -0 "${pid}" 2>/dev/null || return 1; sleep 15; done; return 1; }
stop_server() { docker inspect "$1" >"$3/container-inspect.json" 2>/dev/null || true; docker stop -t 180 "$1" >/dev/null 2>&1 || true; wait "$2" 2>/dev/null || true; for _ in $(seq 1 24); do docker ps -a --format '{{.Names}}' | grep -q "^$1$" || break; sleep 5; done; grep -iE "${fault_re}" "$3/server.log" >"$3/server-fault-lines.txt" || true; [[ ! -s "$3/server-fault-lines.txt" ]] || abort "$(basename "$3"): fault signature in server.log"; }
wait_for_memory() {
  local need_mib=${LOAD_MEMORY_MIB:-11500} deadline=$(( $(date +%s) + ${LOAD_MEMORY_TIMEOUT:-300} )) avail
  while :; do
    avail=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
    (( avail >= need_mib )) && { [[ -n "${1:-}" ]] && log "$1: ${avail} MiB available, loading"; return 0; }
    (( $(date +%s) >= deadline )) && { log "${1:-launch}: only ${avail} MiB available after waiting, proceeding anyway"; return 0; }
    sleep 10
  done
}

# launch <label> <mtp0|mtpn> <mml> <mns> <mbt>
launch() {
  local label=$1 kind=$2 mml=$3 mns=$4 mbt=$5 dir=${root}/$1 cache=${root}/$1-cache
  mkdir -p "${dir}"; [[ ! -e "${cache}" ]] || abort "${label}: cache exists"; mkdir -p "${cache}"
  wait_for_memory "${label}"
  local name=${LANE}-${RUN}-${label} served=${LANE}-${label} launcher=run-w8a16-mtp0-strict-server.sh spec='{}'
  if [[ "${kind}" != mtp0 ]]; then launcher=run-w8a16-mtp1-strict-server.sh; spec="{\"method\":\"qwen3_5_mtp\",\"num_speculative_tokens\":${DEPTH}}"; fi
  date --iso-8601=seconds >"${dir}/started-at.txt"
  local specenv=(); [[ "${kind}" == mtp0 ]] || specenv=(SPECULATIVE_CONFIG="${spec}")
  # EXTRA_ENV: arbitrary "KEY=VALUE KEY=VALUE" passthrough for knobs this harness does not name.
  # Every entry is verified in the container below; a knob that never reaches the container
  # produces a clean null that is indistinguishable from a real no-effect result, which this lane
  # has already been burned by once.
  local extraenv=(); local _kv
  for _kv in ${EXTRA_ENV:-}; do extraenv+=("${_kv}"); done
  env IMAGE="${image}" EXPECTED_IMAGE_ID="${image_id}" EXPECTED_XPU_EXTENSION_SHA256=271db0d4882124e21ac6a4d080bfeab303fbb08b9ec10e11f21d10fb0723998f \
    EXPECTED_XPU_OPS_SHA256=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3 EXPECTED_LAYERNORM_SHA256=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 \
    VLLM_BATCH_INVARIANT=0 VLLM_XPU_GDN_SPLIT_MIXED=1 VLLM_XPU_GDN_SPEC_GROUP=${GDN_SPEC_GROUP:-16} VLLM_XPU_GEMMA_RMSNORM_TRITON=0 VLLM_XPU_RMSNORM_TRITON=0 \
    VLLM_XPU_DRAFT_LM_HEAD_INT4="${DRAFT_HEAD}" VLLM_XPU_W4A16_DETERMINISM_PAD="${W4A16_PAD}" VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH="${W4A16_PAD}" GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.95} \
    EXPECTED_XPU_COMMUNICATOR_SHA256="${EXPECTED_XPU_COMMUNICATOR_SHA256:-}" VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS="${ROWWISE_ALLREDUCE_MAX_ROWS:-0}" \
    EXPECTED_LOGITS_PROCESSOR_SHA256="${EXPECTED_LOGITS_PROCESSOR_SHA256:-}" EXPECTED_IR_LAYERNORM_SHA256="${EXPECTED_IR_LAYERNORM_SHA256:-}" VLLM_XPU_RMSNORM_SERIAL_ROWS="${RMSNORM_SERIAL_ROWS:-0}" \
    VLLM_XPU_LM_HEAD_BATCH_INVARIANT="${LM_HEAD_BATCH_INVARIANT:-0}" VLLM_XPU_LM_HEAD_ROW_CHUNK="${LM_HEAD_ROW_CHUNK:-0}" \
    MODEL_DIR="${model_dir}" MODEL_MANIFEST="${manifest}" VLLM_CACHE_DIR="${cache}" "${specenv[@]}" "${extraenv[@]}" \
    CONTAINER_NAME="${name}" PORT="${port}" SERVED_MODEL_NAME="${served}" COMPILATION_CONFIG="${comp}" \
    TENSOR_PARALLEL_SIZE="${TP}" XPU_DEVICE_MASK="${mask}" QUANTIZATION="${QUANT}" VLLM_XPU_FP8_BLOCK_W8A16=0 \
    MAX_MODEL_LEN="${mml}" MAX_NUM_SEQS="${mns}" MAX_NUM_BATCHED_TOKENS="${mbt}" ENFORCE_EAGER="${eager}" VLLM_XPU_ENABLE_XPU_GRAPH="${xgraph}" \
    CONTAINER_MEMORY=${CONTAINER_MEMORY:-12g} CONTAINER_MEMORY_SWAP=${CONTAINER_MEMORY_SWAP:-20g} \
    "${repro}/${launcher}" >"${dir}/server.log" 2>&1 &
  server_pid=$!; log "${label}: launched ${kind} (${launcher}) pid ${server_pid} port ${port} cards ${mask}"
  wait_health "${server_pid}" || { docker stop -t 60 "${name}" >/dev/null 2>&1 || true; abort "${label}: server did not become healthy"; }
  docker inspect "${name}" >"${dir}/container-inspect.json" 2>/dev/null || true
  for knob in VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS:${ROWWISE_ALLREDUCE_MAX_ROWS:-0} \
              VLLM_XPU_RMSNORM_SERIAL_ROWS:${RMSNORM_SERIAL_ROWS:-0} \
              VLLM_XPU_LM_HEAD_BATCH_INVARIANT:${LM_HEAD_BATCH_INVARIANT:-0} \
              VLLM_XPU_LM_HEAD_ROW_CHUNK:${LM_HEAD_ROW_CHUNK:-0} \
              VLLM_XPU_W4A16_DETERMINISM_PAD:${W4A16_PAD}; do
    want=${knob#*:}; name_=${knob%%:*}
    [[ "${want}" == 0 ]] && continue
    grep -q "\"${name_}=${want}\"" "${dir}/container-inspect.json" 2>/dev/null \
      || abort "${label}: ${name_}=${want} was requested but is not in the container environment"
  done
  if [[ "${kind}" != mtp0 && "${GDN_SPEC_GROUP:-16}" != 16 ]]; then
    grep -q "\"VLLM_XPU_GDN_SPEC_GROUP=${GDN_SPEC_GROUP}\"" "${dir}/container-inspect.json" 2>/dev/null \
      || abort "${label}: VLLM_XPU_GDN_SPEC_GROUP=${GDN_SPEC_GROUP} requested but not in the container environment"
  fi
  for _kv in ${EXTRA_ENV:-}; do
    grep -q "\"${_kv}\"" "${dir}/container-inspect.json" 2>/dev/null \
      || abort "${label}: EXTRA_ENV ${_kv} was requested but is not in the container environment"
  done
  log "${label}: healthy"; server_name=${name}; server_dir=${dir}; served_model=${served}
}
strict_attempt() {
  OUT_DIR="${server_dir}/strict" BASE_URL="http://127.0.0.1:${port}" MODEL_NAME="${served_model}" SUITE="${strict_suite}" \
    PROFILE_LABEL="${LANE}-${RUN}-$1" ATTEMPT_LABEL="fresh-cache-$1" "${repro}/bench-w8a16-mtp1-strict.sh" >"${server_dir}/strict.stdout" 2>&1 || abort "$1: strict suite failed its workload/cache/canary gate"
  log "$1: $(grep -E 'class_balanced_median_tok_s|median_tok_s' "${server_dir}/strict.stdout" | head -2 | tr '\n' ' ')"
}
compare_pair() { python3 "${compare}" "$1" "$2" --output "$3" >/dev/null 2>&1 || true; python3 -c "import json,sys;c=json.load(open(sys.argv[1]))['comparison'];print(f\"{c['exact_prompts']}/{c['total_prompts']}\")" "$3" 2>/dev/null || echo "compare-failed"; }
run_ladder() { python3 "${ladder}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" --api-mode completions --suite "${ladder_suite}" --concurrency "${LADDER_CONCURRENCY:-1,2,4,8,16,32,64}" --repeats "${LADDER_REPEATS:-2}" --max-tokens 128 --seed 42 --timeout 900 --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --require-output-identity ${LADDER_EXTRA_ARGS:-} --out "${server_dir}/ladder.json" >"${server_dir}/ladder.stdout" 2>&1; log "$1 ladder harness exit $?"; }

# ---------------- preflight ----------------
[[ "$(lane_containers)" == 0 ]] || abort "preflight: this arm's container is already running"
[[ "$(docker image inspect "${image}" --format '{{.Id}}')" == "${image_id}" ]] || abort "preflight: image id mismatch"
devices_normal preflight || abort "preflight: a B70 this arm owns is not healthy"
arm_health >"${root}/preflight-compute-xccl.txt" 2>&1 || abort "preflight: compute/XCCL health failed"
journalctl -k -b 0 --no-pager >"${root}/preflight-kernel-journal-full.txt" 2>&1 || true
grep -iE "${fault_re}" "${root}/preflight-kernel-journal-full.txt" >"${root}/preflight-kernel-fault-lines.txt" || true
[[ ! -s "${root}/preflight-kernel-fault-lines.txt" ]] || log "WARNING: boot carries prior fault signatures"
log "preflight clean; boot $(cat "${root}/boot-id.txt"); LANE=${LANE} TP=${TP} DEPTH=${DEPTH} GRAPH=${GRAPH} cards=${mask}"

if [[ " ${STAGES} " == *" strict "* ]]; then
  for label in mtp0-a mtp0-b; do launch "${label}" mtp0 1024 1 1024; strict_attempt "${label}"; stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight "${label}-post"; done
  g1=$(compare_pair "${root}/mtp0-a/strict" "${root}/mtp0-b/strict" "${root}/compare-mtp0-a-vs-mtp0-b.json"); log "G1 mtp0-a vs mtp0-b: ${g1}"
  [[ "${g1}" == "12/12" ]] || abort "G1 failed (${g1}): MTP0 is not repeat-exact"
  if [[ "${DEPTH}" != 0 ]]; then
    for label in mtp${DEPTH}-a mtp${DEPTH}-b; do launch "${label}" mtpn 1024 1 1024; strict_attempt "${label}"; stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight "${label}-post"; done
    log "G2 mtp${DEPTH}-a vs mtp${DEPTH}-b: $(compare_pair "${root}/mtp${DEPTH}-a/strict" "${root}/mtp${DEPTH}-b/strict" "${root}/compare-mtp${DEPTH}-a-vs-b.json")"
    log "G3 mtp${DEPTH}-a vs mtp0-a: $(compare_pair "${root}/mtp${DEPTH}-a/strict" "${root}/mtp0-a/strict" "${root}/compare-mtp${DEPTH}-a-vs-mtp0-a.json")"
    log "G3 mtp${DEPTH}-b vs mtp0-a: $(compare_pair "${root}/mtp${DEPTH}-b/strict" "${root}/mtp0-a/strict" "${root}/compare-mtp${DEPTH}-b-vs-mtp0-a.json")"
  fi
fi
if [[ " ${STAGES} " == *" ladders "* ]]; then
  if [[ "${DEPTH}" != 0 ]]; then
    launch ladder mtpn "${LADDER_MML:-256}" "${LADDER_MNS:-64}" "${LADDER_MBT:-512}"; run_ladder "G6(mtp${DEPTH})"; stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight ladder-post
  fi
  launch ladder-mtp0 mtp0 "${LADDER_MML:-256}" "${LADDER_MNS:-64}" "${LADDER_MBT:-512}"; run_ladder "G6(mtp0)"; stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight ladder-mtp0-post
fi
if [[ " ${STAGES} " == *" depth32k "* ]]; then
  depth_stage() { local label=$1 kind=$2 oracle=$3
    launch "${label}" "${kind}" "${DEPTH_MML:-33024}" 1 "${DEPTH_MBT:-4096}"
    OUT_DIR="${server_dir}/depth" ARM="$([[ "${kind}" == mtp0 ]] && echo mtp0 || echo mtp1)" BASE_URL="http://127.0.0.1:${port}" SERVED_MODEL_NAME="${served_model}" ORACLE_DIR="${oracle}" \
      "${repro}/bench-w8a16-real-content-depth.sh" >"${server_dir}/depth.stdout" 2>&1 || log "${label}: depth bench exited nonzero"
    log "${label}: $(tail -n 2 "${server_dir}/depth.stdout" | tr '\n' ' ' | cut -c1-200)"
    stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight "${label}-post"; }
  depth_stage depth-mtp0 mtp0 ""
  [[ "${DEPTH}" == 0 ]] || depth_stage depth-mtp${DEPTH} mtpn "${root}/depth-mtp0/depth"
fi
date --iso-8601=seconds >"${root}/campaign-end.txt"; log "campaign complete"
