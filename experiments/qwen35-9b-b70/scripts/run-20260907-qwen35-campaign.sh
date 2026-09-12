#!/usr/bin/env bash
# Qwen3.5 campaign harness (2026-09-07), generalized over model/quantization; modelled on the Qwen3.8 runner: strict pairs (G1 MTP0 a/b exact,
# G2 MTPn a/b exact, G3 MTPn vs MTP0 exact) and two-pass c1-c64 identity ladders, on the strict FP8-lane launchers with
# the R276 image. env: RUN (label), TP (1|2), DEPTH (>0), GRAPH (1 full decode-only capture | 0 eager),
# DRAFT_HEAD (1 default: draft-only INT4 lm_head copy, VLLM_XPU_DRAFT_LM_HEAD_INT4; 0 = FP8 head for drafts too)
# LANE (default qwen35-9b-fp8), MODEL_DIR, MODEL_MANIFEST, QUANT (default compressed-tensors): select the checkpoint under test.
# W4A16_PAD (default 0): pad decode row counts to fixed tiers on the INT4 W4A16 kernel, removing the row-count dependence
#   that flips near-tie tokens at high concurrency. Costs throughput above 128 rows on the 27B lane; measured here.
# STAGES (space list of: strict ladders depth32k)  [v2 adds depth32k: real-content 2K-32K exact-depth ladder, MTP0 arm as oracle then MTPn arm], LADDER_CONCURRENCY, LADDER_REPEATS, LADDER_MML/MNS/MBT, XPU_DEVICE_MASK.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; out=/mnt/fast-ai/bench-results
LANE=${LANE:-qwen35-9b-fp8}; QUANT=${QUANT:-compressed-tensors}; W4A16_PAD=${W4A16_PAD:-0}
RUN=${RUN:?set RUN}; TP=${TP:-1}; DEPTH=${DEPTH:-3}; GRAPH=${GRAPH:-1}; DRAFT_HEAD=${DRAFT_HEAD:-1}; STAGES=${STAGES:-strict ladders}; port=${PORT:-18131}
root=${ROOT:-${out}/${LANE}-tp${TP}-mtp${DEPTH}-graph${GRAPH}$([[ "${DRAFT_HEAD}" == 1 ]] && echo -dhint4)$([[ "${W4A16_PAD}" == 1 ]] && echo -pad)-20260907-${RUN}}
repro=${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
# IMAGE/IMAGE_ID select the runtime. They default to the published R276 image; a diagnostic overlay sets both plus
# EXPECTED_XPU_COMMUNICATOR_SHA256, which is how verify-image-contract.sh lets a candidate opt into a replaced
# communicator module while every other pinned digest stays closed.
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-sync-free-r276}
image_id=${IMAGE_ID:-sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad}
model_dir=${MODEL_DIR:-/home/steve/llm-models/qwen35-9b-fp8-dynamic}
manifest=${MODEL_MANIFEST:-${repo}/experiments/qwen35-9b-b70/manifests/model-direct-redhatai-qwen35-9b-fp8-dynamic-790f0576.json}
strict_suite=${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json
# LADDER_SUITE/LADDER_EXTRA_ARGS let a targeted run swap the prompt set and pass extra harness flags
# (--verbatim-prompts, for suites whose exact prompt text is the thing under study). Defaults unchanged.
ladder_suite=${LADDER_SUITE:-${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json}
ladder=${repo}/scripts/bench-openai-concurrency-oracle.py; compare=${repo}/scripts/compare-strict-attempt-outputs.py
health=${repo}/scripts/check-qwen36-xpu-xccl-health.sh; health_timeout=1800
fault_re='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup'
if [[ "$TP" == 2 ]]; then mask=${XPU_DEVICE_MASK:-0,1}; else mask=${XPU_DEVICE_MASK:-0}; fi
if [[ "$GRAPH" == 1 ]]; then
  # CAPTURE_SIZES/CAPTURE_MAX default to the published c1-c64 capture set; raise both together to take a ladder past 64 users
  # (an uncaptured decode shape falls back to eager, which is a different execution path and would confound an identity ladder).
  csizes=${CAPTURE_SIZES:-1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64}; cmax=${CAPTURE_MAX:-64}
  comp='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":['"${csizes}"'],"max_cudagraph_capture_size":'"${cmax}"',"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
  eager=0; xgraph=1
else
  # "graph off" as the INT4 lane defines it: piecewise Inductor compile with the XPU graph disabled (the strict launcher pins enforce-eager off)
  comp='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
  eager=0; xgraph=0
fi
log() { printf '[q35 %s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "${root}/campaign.log"; }
abort() { log "ABORT: $*"; printf '%s\n' "$*" >"${root}/ABORTED"; exit 2; }
mkdir -p "${root}"; [[ -e "${root}/campaign-start.txt" ]] && { echo "campaign root already used: ${root}" >&2; exit 1; }
date --iso-8601=seconds >"${root}/campaign-start.txt"; campaign_start=$(date '+%Y-%m-%d %H:%M:%S')
cat /proc/sys/kernel/random/boot_id >"${root}/boot-id.txt"; git -C "${repo}" rev-parse HEAD >"${root}/repo-head.txt"
printf 'LANE=%s RUN=%s TP=%s DEPTH=%s GRAPH=%s DRAFT_HEAD=%s QUANT=%s PAD=%s mask=%s model=%s image=%s\n' "$LANE" "$RUN" "$TP" "$DEPTH" "$GRAPH" "$DRAFT_HEAD" "$QUANT" "$W4A16_PAD" "$mask" "$model_dir" "$image_id" >"${root}/config.txt"
devices_normal() { xpu-smi discovery >"${root}/$1-xpu-smi-discovery.txt" 2>&1 || true; [[ "$(grep -c 'Device State: normal' "${root}/$1-xpu-smi-discovery.txt")" == 2 ]]; }
journal_check() { journalctl -k -b 0 --no-pager --since "${campaign_start}" >"${root}/$1-kernel-journal.txt" 2>&1 || true; ! grep -qiE "${fault_re}" "${root}/$1-kernel-journal.txt"; }
lane_containers() { docker ps --format '{{.Names}}' | grep -cE 'qwen3[58]' || true; }
postflight() { devices_normal "$1" || abort "$1: a B70 is not in normal state"; journal_check "$1" || abort "$1: fault signature in the kernel journal"; ROOT="${repo}" "${health}" >"${root}/$1-compute-xccl.txt" 2>&1 || abort "$1: compute/XCCL health failed"; [[ "$(lane_containers)" == 0 ]] || abort "$1: a lane container is still running"; log "$1: postflight clean"; }
wait_health() { local pid=$1 deadline=$(( $(date +%s) + health_timeout )); while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1 && return 0; kill -0 "${pid}" 2>/dev/null || return 1; sleep 15; done; return 1; }
stop_server() { docker inspect "$1" >"$3/container-inspect.json" 2>/dev/null || true; docker stop -t 180 "$1" >/dev/null 2>&1 || true; wait "$2" 2>/dev/null || true; for _ in $(seq 1 24); do docker ps -a --format '{{.Names}}' | grep -q "^$1$" || break; sleep 5; done; grep -iE "${fault_re}" "$3/server.log" >"$3/server-fault-lines.txt" || true; [[ ! -s "$3/server-fault-lines.txt" ]] || abort "$(basename "$3"): fault signature in server.log"; }
# Weight loading needs about 10.7 GiB for the 9B on a 15.5 GiB host, and the previous server's page
# cache is not always released by the time the next one starts. When it is not, the container hits its
# memory cap and the worker dies with no Python traceback, which the harness can only report as "server
# did not become healthy" - as happened to the serial-norm s1 arm on 2026-09-08 after three servers of
# the same campaign had loaded fine. Waiting for the memory back is cheaper than losing the campaign.
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
  # SPEC_SCHEDULE (2026-09-11, as in campaign-v3): vLLM's per-batch-size draft schedule, a JSON list of
  # [range_start,range_end,K] inclusive batch-size ranges capped at DEPTH. Optional; default unchanged.
  if [[ "${kind}" != mtp0 && -n "${SPEC_SCHEDULE:-}" ]]; then spec="{\"method\":\"qwen3_5_mtp\",\"num_speculative_tokens\":${DEPTH},\"num_speculative_tokens_per_batch_size\":${SPEC_SCHEDULE}}"; fi
  date --iso-8601=seconds >"${dir}/started-at.txt"
  local specenv=(); [[ "${kind}" == mtp0 ]] || specenv=(SPECULATIVE_CONFIG="${spec}")
  # The strict launchers verify the image contract; these are the R276 identities the INT4 public launcher exports, plus the
  # GDN/RMSNorm switches every published R276 measurement ran with (the 9B is a GDN hybrid too). No INT4 draft head here.
  env IMAGE="${image}" EXPECTED_IMAGE_ID="${image_id}" EXPECTED_XPU_EXTENSION_SHA256=271db0d4882124e21ac6a4d080bfeab303fbb08b9ec10e11f21d10fb0723998f \
    EXPECTED_XPU_OPS_SHA256=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3 EXPECTED_LAYERNORM_SHA256=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 \
    VLLM_BATCH_INVARIANT=0 VLLM_XPU_GDN_SPLIT_MIXED=1 VLLM_XPU_GDN_SPEC_GROUP=${GDN_SPEC_GROUP:-16} VLLM_XPU_GEMMA_RMSNORM_TRITON=0 VLLM_XPU_RMSNORM_TRITON=0 \
    VLLM_XPU_DRAFT_LM_HEAD_INT4="${DRAFT_HEAD}" VLLM_XPU_W4A16_DETERMINISM_PAD="${W4A16_PAD}" VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH="${W4A16_PAD}" GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.95} \
    EXPECTED_XPU_COMMUNICATOR_SHA256="${EXPECTED_XPU_COMMUNICATOR_SHA256:-}" VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS="${ROWWISE_ALLREDUCE_MAX_ROWS:-0}" \
    EXPECTED_LOGITS_PROCESSOR_SHA256="${EXPECTED_LOGITS_PROCESSOR_SHA256:-}" EXPECTED_IR_LAYERNORM_SHA256="${EXPECTED_IR_LAYERNORM_SHA256:-}" VLLM_XPU_RMSNORM_SERIAL_ROWS="${RMSNORM_SERIAL_ROWS:-0}" \
    VLLM_XPU_LM_HEAD_BATCH_INVARIANT="${LM_HEAD_BATCH_INVARIANT:-0}" VLLM_XPU_LM_HEAD_ROW_CHUNK="${LM_HEAD_ROW_CHUNK:-0}" \
    MODEL_DIR="${model_dir}" MODEL_MANIFEST="${manifest}" VLLM_CACHE_DIR="${cache}" "${specenv[@]}" \
    CONTAINER_NAME="${name}" PORT="${port}" SERVED_MODEL_NAME="${served}" COMPILATION_CONFIG="${comp}" \
    TENSOR_PARALLEL_SIZE="${TP}" XPU_DEVICE_MASK="${mask}" QUANTIZATION="${QUANT}" VLLM_XPU_FP8_BLOCK_W8A16=0 \
    MAX_MODEL_LEN="${mml}" MAX_NUM_SEQS="${mns}" MAX_NUM_BATCHED_TOKENS="${mbt}" ENFORCE_EAGER="${eager}" VLLM_XPU_ENABLE_XPU_GRAPH="${xgraph}" \
    CONTAINER_MEMORY=12g CONTAINER_MEMORY_SWAP=20g \
    "${repro}/${launcher}" >"${dir}/server.log" 2>&1 &
  server_pid=$!; log "${label}: launched ${kind} (${launcher}) pid ${server_pid}"
  wait_health "${server_pid}" || { docker stop -t 60 "${name}" >/dev/null 2>&1 || true; abort "${label}: server did not become healthy"; }
  # Fail closed if a knob the campaign asked for never reached the container. Two experiments were
  # run and written up before this existed, both comparing arms that were in fact identical: the
  # no-speculation path goes through run-server.sh, and neither the row-wise all-reduce nor the
  # serialised-norm knob was forwarded there. An intervention that silently does not apply produces a
  # clean null that looks exactly like a real "no effect".
  docker inspect "${name}" >"${dir}/container-inspect.json" 2>/dev/null || true
  for knob in VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS:${ROWWISE_ALLREDUCE_MAX_ROWS:-0} \
              VLLM_XPU_RMSNORM_SERIAL_ROWS:${RMSNORM_SERIAL_ROWS:-0} \
              VLLM_XPU_LM_HEAD_BATCH_INVARIANT:${LM_HEAD_BATCH_INVARIANT:-0} \
              VLLM_XPU_LM_HEAD_ROW_CHUNK:${LM_HEAD_ROW_CHUNK:-0}; do
    want=${knob#*:}; name_=${knob%%:*}
    [[ "${want}" == 0 ]] && continue
    grep -q "\"${name_}=${want}\"" "${dir}/container-inspect.json" 2>/dev/null \
      || abort "${label}: ${name_}=${want} was requested but is not in the container environment"
  done
  if [[ "${kind}" != mtp0 && -n "${SPEC_SCHEDULE:-}" ]]; then
    grep -q "num_speculative_tokens_per_batch_size" "${dir}/container-inspect.json" 2>/dev/null \
      || abort "${label}: SPEC_SCHEDULE requested but no num_speculative_tokens_per_batch_size in the container args"
    grep -q "Dynamic speculative decoding is not supported\|falling back to static num_speculative_tokens" "${dir}/server.log" 2>/dev/null \
      && abort "${label}: vLLM disabled the dynamic speculative schedule (see server.log)"
  fi
  log "${label}: healthy"; server_name=${name}; server_dir=${dir}; served_model=${served}
}
strict_attempt() {
  OUT_DIR="${server_dir}/strict" BASE_URL="http://127.0.0.1:${port}" MODEL_NAME="${served_model}" SUITE="${strict_suite}" \
    PROFILE_LABEL="qwen35-9b-${RUN}-$1" ATTEMPT_LABEL="fresh-cache-$1" "${repro}/bench-w8a16-mtp1-strict.sh" >"${server_dir}/strict.stdout" 2>&1 || abort "$1: strict suite failed its workload/cache/canary gate"
  log "$1: $(grep -E 'class_balanced_median_tok_s|median_tok_s' "${server_dir}/strict.stdout" | head -2 | tr '\n' ' ')"
}
compare_pair() { python3 "${compare}" "$1" "$2" --output "$3" >/dev/null 2>&1 || true; python3 -c "import json,sys;c=json.load(open(sys.argv[1]))['comparison'];print(f\"{c['exact_prompts']}/{c['total_prompts']}\")" "$3" 2>/dev/null || echo "compare-failed"; }
run_ladder() { python3 "${ladder}" --base-url "http://127.0.0.1:${port}" --model "${served_model}" --api-mode completions --suite "${ladder_suite}" --concurrency "${LADDER_CONCURRENCY:-1,2,4,8,16,32,64}" --repeats "${LADDER_REPEATS:-2}" --max-tokens 128 --seed 42 --timeout 900 --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --require-output-identity ${LADDER_EXTRA_ARGS:-} --out "${server_dir}/ladder.json" >"${server_dir}/ladder.stdout" 2>&1; log "$1 ladder harness exit $?"; }
# ---------------- preflight ----------------
[[ "$(lane_containers)" == 0 ]] || abort "preflight: lane container running"
[[ "$(docker image inspect "${image}" --format '{{.Id}}')" == "${image_id}" ]] || abort "preflight: image id mismatch"
devices_normal preflight || abort "preflight: a B70 is not normal"
ROOT="${repo}" "${health}" >"${root}/preflight-compute-xccl.txt" 2>&1 || abort "preflight: compute/XCCL health failed"
journalctl -k -b 0 --no-pager >"${root}/preflight-kernel-journal-full.txt" 2>&1 || true
grep -iE "${fault_re}" "${root}/preflight-kernel-journal-full.txt" >"${root}/preflight-kernel-fault-lines.txt" || true
[[ ! -s "${root}/preflight-kernel-fault-lines.txt" ]] || log "WARNING: boot carries prior fault signatures"
log "preflight clean; boot $(cat "${root}/boot-id.txt"); TP=${TP} DEPTH=${DEPTH} GRAPH=${GRAPH}"
if [[ " ${STAGES} " == *" strict "* ]]; then
  for label in mtp0-a mtp0-b; do launch "${label}" mtp0 1024 1 1024; strict_attempt "${label}"; stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight "${label}-post"; done
  g1=$(compare_pair "${root}/mtp0-a/strict" "${root}/mtp0-b/strict" "${root}/compare-mtp0-a-vs-mtp0-b.json"); log "G1 mtp0-a vs mtp0-b: ${g1}"
  [[ "${g1}" == "12/12" ]] || abort "G1 failed (${g1}): MTP0 is not repeat-exact"
  for label in mtp${DEPTH}-a mtp${DEPTH}-b; do launch "${label}" mtpn 1024 1 1024; strict_attempt "${label}"; stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight "${label}-post"; done
  log "G2 mtp${DEPTH}-a vs mtp${DEPTH}-b: $(compare_pair "${root}/mtp${DEPTH}-a/strict" "${root}/mtp${DEPTH}-b/strict" "${root}/compare-mtp${DEPTH}-a-vs-b.json")"
  log "G3 mtp${DEPTH}-a vs mtp0-a: $(compare_pair "${root}/mtp${DEPTH}-a/strict" "${root}/mtp0-a/strict" "${root}/compare-mtp${DEPTH}-a-vs-mtp0-a.json")"
  log "G3 mtp${DEPTH}-b vs mtp0-a: $(compare_pair "${root}/mtp${DEPTH}-b/strict" "${root}/mtp0-a/strict" "${root}/compare-mtp${DEPTH}-b-vs-mtp0-a.json")"
fi
if [[ " ${STAGES} " == *" ladders "* ]]; then
  launch ladder mtpn "${LADDER_MML:-256}" "${LADDER_MNS:-64}" "${LADDER_MBT:-512}"; run_ladder "G6(mtp${DEPTH})"; stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight ladder-post
  launch ladder-mtp0 mtp0 "${LADDER_MML:-256}" "${LADDER_MNS:-64}" "${LADDER_MBT:-512}"; run_ladder "G6(mtp0)"; stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight ladder-mtp0-post
fi
if [[ " ${STAGES} " == *" depth32k "* ]]; then
  depth_stage() { local label=$1 kind=$2 oracle=$3
    launch "${label}" "${kind}" 33024 1 4096
    OUT_DIR="${server_dir}/depth" ARM="$([[ "${kind}" == mtp0 ]] && echo mtp0 || echo mtp1)" BASE_URL="http://127.0.0.1:${port}" SERVED_MODEL_NAME="${served_model}" ORACLE_DIR="${oracle}" \
      "${repro}/bench-w8a16-real-content-depth.sh" >"${server_dir}/depth.stdout" 2>&1 || log "${label}: depth bench exited nonzero"
    log "${label}: $(tail -n 2 "${server_dir}/depth.stdout" | tr '\n' ' ' | cut -c1-200)"
    stop_server "${server_name}" "${server_pid}" "${server_dir}"; postflight "${label}-post"; }
  depth_stage depth-mtp0 mtp0 ""
  depth_stage depth-mtp${DEPTH} mtpn "${root}/depth-mtp0/depth"
fi
date --iso-8601=seconds >"${root}/campaign-end.txt"; log "campaign complete"
