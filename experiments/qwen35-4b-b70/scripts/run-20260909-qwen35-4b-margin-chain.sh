#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 4 (2026-09-09): measure the logit margin at divergence points.
#
# Everything so far infers the tie model from output shapes: two variants and never a third, 39 sites
# seen substituting both ways across independently regenerated oracles, three of eight prompts never
# diverging at all. None of it measures the margin, because no ladder captured logprobs - the shared
# harness parses only the chat shape while the ladders run completions, so `logprob_content` is empty
# in all 170 ladder files on disk.
#
# The harness is not patched to fix that: scripts/bench-openai-realistic-suite.py is pinned by SHA256
# in several qualification gates and in a published record gate, and editing shared pinned tooling in
# place is exactly the failure recorded in notes/2026-09-08-a-good-tooling-change-broke-a-record-gate.md.
# probe-tie-margin.py talks to the endpoint directly instead.
#
# Launch env is copied from the campaign engine's launch() so the server under the probe is the same
# server the ladders measured, including the image contract identities the strict launchers verify.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-margin-20260909-wrapper.log
root=${out}/qwen35-4b-w4a16-20260909-m1
repro=${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json
probe=${repo}/experiments/qwen35-4b-b70/scripts/probe-tie-margin.py
health=${repo}/scripts/check-qwen36-xpu-xccl-health.sh
image=neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-sync-free-r276
image_id=sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad
port=18131
comp='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64],"max_cudagraph_capture_size":64,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'

echo $$ >"${out}/qwen35-4b-margin-20260909.pid"
log() { printf '[margin %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

log "waiting for chain 3"
while [[ ! -e "${out}/qwen35-4b-depth-20260909-DONE" && ! -e "${out}/qwen35-4b-depth-20260909-STOPPED" ]]; do sleep 60; done
[[ -e "${out}/qwen35-4b-depth-20260909-STOPPED" ]] && { log "chain 3 stopped; not starting"; exit 1; }
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10
mkdir -p "${root}"

serve() { # serve <label> <mtp0|mtpn>
  local label=$1 kind=$2 dir=${root}/$1 name=qwen35-4b-w4a16-m1-$1
  mkdir -p "${dir}"
  local launcher=run-w8a16-mtp0-strict-server.sh specenv=()
  if [[ "${kind}" != mtp0 ]]; then
    launcher=run-w8a16-mtp1-strict-server.sh
    specenv=(SPECULATIVE_CONFIG='{"method":"qwen3_5_mtp","num_speculative_tokens":3}')
  fi
  env IMAGE="${image}" EXPECTED_IMAGE_ID="${image_id}" \
    EXPECTED_XPU_EXTENSION_SHA256=271db0d4882124e21ac6a4d080bfeab303fbb08b9ec10e11f21d10fb0723998f \
    EXPECTED_XPU_OPS_SHA256=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3 \
    EXPECTED_LAYERNORM_SHA256=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 \
    VLLM_BATCH_INVARIANT=0 VLLM_XPU_GDN_SPLIT_MIXED=1 VLLM_XPU_GDN_SPEC_GROUP=16 \
    VLLM_XPU_GEMMA_RMSNORM_TRITON=0 VLLM_XPU_RMSNORM_TRITON=0 \
    VLLM_XPU_DRAFT_LM_HEAD_INT4=1 VLLM_XPU_W4A16_DETERMINISM_PAD=0 VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH=0 \
    GPU_MEMORY_UTILIZATION=0.95 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" \
    VLLM_CACHE_DIR="${root}/$1-cache" CONTAINER_NAME="${name}" PORT="${port}" \
    SERVED_MODEL_NAME="qwen35-4b-w4a16-$1" COMPILATION_CONFIG="${comp}" \
    TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0 QUANTIZATION=compressed-tensors VLLM_XPU_FP8_BLOCK_W8A16=0 \
    MAX_MODEL_LEN=256 MAX_NUM_SEQS=64 MAX_NUM_BATCHED_TOKENS=512 ENFORCE_EAGER=0 \
    VLLM_XPU_ENABLE_XPU_GRAPH=1 CONTAINER_MEMORY=12g CONTAINER_MEMORY_SWAP=20g \
    "${specenv[@]}" "${repro}/${launcher}" >"${dir}/server.log" 2>&1 &
  local pid=$! deadline=$(( $(date +%s) + 1800 ))
  log "${label}: launched (${launcher}) pid ${pid}"
  while (( $(date +%s) < deadline )); do
    curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1 && break
    kill -0 "${pid}" 2>/dev/null || { log "${label}: launcher exited before healthy"; return 1; }
    sleep 15
  done
  curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1 || { log "${label}: never healthy"; docker stop -t 60 "${name}" >/dev/null 2>&1; return 1; }
  log "${label}: healthy"

  python3 "${probe}" --base-url "http://127.0.0.1:${port}" --model "qwen35-4b-w4a16-$1" \
    --suite "${fragile}" --concurrency 64 --repeats 5 --max-tokens 128 --logprobs 5 \
    --out "${dir}/margins.json" >"${dir}/probe.stdout" 2>&1
  log "${label}: probe exit $? -> ${dir}/probe.stdout"
  tail -n 6 "${dir}/probe.stdout" | tee -a "${wrap}"

  docker stop -t 180 "${name}" >/dev/null 2>&1 || true
  wait "${pid}" 2>/dev/null || true
  for _ in $(seq 1 24); do docker ps -a --format '{{.Names}}' | grep -q "^${name}$" || break; sleep 5; done
  ROOT="${repo}" "${health}" >"${root}/$1-postflight.txt" 2>&1 || log "${label}: postflight health FAILED"
  log "${label}: stopped"
}

serve mtp0 mtp0
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 20; done; sleep 10
serve mtp3 mtpn

log "=== chain 4 complete ==="
echo done >"${out}/qwen35-4b-margin-20260909-DONE"
