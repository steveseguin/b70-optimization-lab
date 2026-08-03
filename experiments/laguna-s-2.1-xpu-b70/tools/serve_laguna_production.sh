#!/usr/bin/env bash
# Production Laguna launcher. This is deliberately NOT a benchmark launcher and
# must never be used to produce a record: it exists to serve traffic under a
# selector set whose batch behaviour has been audited, and it refuses by name
# any combination whose optimizations would silently stop firing.
#
# Two profiles, and only two, because only two are decidable from source:
#
#   sealed-single-stream  the measured record identity at --max-num-seqs 1.
#                         Every exact selector fires. This is the only profile
#                         whose decode rate has ever been measured.
#
#   concurrent            --max-num-seqs > 1 with every BATCH-HOSTILE selector
#                         explicitly off. Nothing classified UNKNOWN is enabled.
#                         Its decode rate has never been measured at any batch
#                         size and this launcher does not imply one.
#
# The audit behind the classification is in
# notes/2026-08-03-production-concurrency-audit.md.
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

readonly target_revision=4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb
readonly draft_revision=5e07c246915c86dc6920fead03d019989224f2ba

readonly profile="${LAGUNA_PRODUCTION_PROFILE:-sealed-single-stream}"
readonly max_num_seqs="${LAGUNA_PRODUCTION_MAX_NUM_SEQS:-1}"
readonly max_model_len="${LAGUNA_PRODUCTION_MAX_MODEL_LEN:-32768}"
readonly gpu_util="${LAGUNA_PRODUCTION_GPU_UTIL:-0.80}"
readonly host="${LAGUNA_PRODUCTION_HOST:-127.0.0.1}"
readonly port="${LAGUNA_PRODUCTION_PORT:-18080}"
readonly meminfo="${LAGUNA_PRODUCTION_MEMINFO:-/proc/meminfo}"

# Measured on this host at gpu_memory_utilization 0.80: the KV cache held
# between 91,258 and 109,059 tokens across startups. The floor is used, not the
# ceiling, because a launcher may not assume it drew the lucky allocation.
# Utilization 0.90 allocated 224,081 tokens, exhausted host swap, and took the
# host down; that is why the ceiling below is hard and not advisory.
readonly kv_token_floor="${LAGUNA_PRODUCTION_KV_TOKEN_FLOOR:-91258}"
readonly max_gpu_util_permille=800

# Host-memory guard, calibrated on the 2026-08-02 host OOM: stop unconditionally
# below 12 GiB available RAM, or when free swap is below 4 GiB and available RAM
# is below 16 GiB.
readonly min_available_ram_kib=12582912
readonly swap_pressure_ram_kib=16777216
readonly min_free_swap_kib=4194304

die() { echo "Laguna production launcher: $*" >&2; exit 2; }

# Every selector that source analysis shows cannot fire, or cannot fire as
# measured, once more than one sequence is scheduled. Each entry carries the
# reason so a refusal explains itself rather than merely naming a variable.
batch_hostile_reasons() {
  case "$1" in
    VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH)
      echo "startup validator _validate_laguna_m8_breakable_graph_config requires max_num_seqs == 1" ;;
    VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS|VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA|VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS)
      echo "requires VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH, which requires max_num_seqs == 1" ;;
    VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH)
      echo "requires the width-12 breakable target graph, which requires max_num_seqs == 1" ;;
    VLLM_XPU_LAGUNA_DFLASH_CAPTURE_ATTENTION_GRAPHS|VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS)
      echo "requires VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH, which requires max_num_seqs == 1" ;;
    VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE)
      echo "DFlash context-KV contract carries a literal batch term and rejects max_num_seqs != 1" ;;
    VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16)
      echo "inherits the DFlash context-KV contract, including its batch term" ;;
    VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS)
      echo "startup validator _validate_laguna_exact_prefill_chunks_config requires max_num_seqs == 1" ;;
    VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE)
      echo "startup validator _validate_laguna_wide_prefill_qknorm_rope_config requires max_num_seqs == 1" ;;
    VLLM_XPU_LAGUNA_M8_EVIDENCE)
      echo "diagnostic arm validator requires max_num_seqs == 1, and evidence capture does not belong in production" ;;
    VLLM_XPU_LAGUNA_M8_QKNORM_ROPE)
      echo "fires only at exactly 8 or 12 rows and falls back SILENTLY otherwise; batched rows are 12*num_seqs" ;;
    VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE)
      echo "fires only at exactly 8 rows and falls back SILENTLY to F.silu(gate)*up otherwise" ;;
    VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE)
      echo "fires only at exactly 12 rows and falls back SILENTLY to F.silu(gate)*up otherwise" ;;
    VLLM_XPU_LAGUNA_M12_MAPPED_GATHER_SCALE_ADD)
      echo "requires VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE, which is row-exact at 12" ;;
    VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK|VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK)
      echo "the BF16 router cast-skip accepts only [8,256] or [12,256] logits and is silently bypassed otherwise" ;;
    VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE)
      echo "row gate is 1..VLLM_XPU_LAGUNA_EXACT_MAX_M; above it the MoE SILENTLY degrades to a per-row Python loop" ;;
    VLLM_XPU_EXACT_SPEC_ATTN)
      echo "with speculation on, batched decode rows exceed the exact width and every projection SILENTLY becomes a per-row loop, which is slower than plain batched execution" ;;
    VLLM_XPU_PERSISTENT_KSTEP_DECODE)
      echo "worker init raises: persistent K-step decode requires max_num_seqs=1" ;;
    VLLM_XPU_LAGUNA_DECODE_GRF128)
      echo "the GRF128 route requires total_m == 120 exactly (12 rows x top-10); at batch N it is 120*N and the kernel SILENTLY reverts to the 256-GRF kernel with no log" ;;
    VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED)
      echo "strictly downstream of the GRF128 total_m == 120 gate and dies with it, SILENTLY" ;;
    VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES)
      echo "host gate num_rows == 12 and device gate total_m == 120 both go false together, so its TORCH_CHECK tripwire cannot fire; the fallback is SILENT" ;;
    VLLM_XPU_LAGUNA_M8_REMOTE_ZERO|VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION|VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE)
      echo "lives inside the kernel branch gated on 1 <= num_rows <= 8, which has no else and no raise; at batch N the MoE rows are 12*N and the branch is SILENTLY skipped" ;;
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2|VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE)
      echo "required by the shared-elementwise contract that also asserts max_num_seqs == 1, and its kernel branch is gated on 1 <= num_rows <= 8" ;;
    VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM)
      echo "fires only at exactly 8 rows and falls back SILENTLY to the stride-zero bmm otherwise" ;;
    *) echo "classified BATCH-HOSTILE by the concurrency audit" ;;
  esac
}

readonly batch_hostile=(
  VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH
  VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS
  VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA
  VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS
  VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH
  VLLM_XPU_LAGUNA_DFLASH_CAPTURE_ATTENTION_GRAPHS
  VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS
  VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE
  VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16
  VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS
  VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE
  VLLM_XPU_LAGUNA_M8_EVIDENCE
  VLLM_XPU_LAGUNA_M8_QKNORM_ROPE
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE
  VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE
  VLLM_XPU_LAGUNA_M12_MAPPED_GATHER_SCALE_ADD
  VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK
  VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK
  VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE
  VLLM_XPU_EXACT_SPEC_ATTN
  VLLM_XPU_PERSISTENT_KSTEP_DECODE
  VLLM_XPU_LAGUNA_DECODE_GRF128
  VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED
  VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES
  VLLM_XPU_LAGUNA_M8_REMOTE_ZERO
  VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION
  VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2
  VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM
  VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE
  VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE
)

# Selectors whose batch behaviour source analysis cannot settle. They are held
# off in every profile that this launcher is willing to start concurrently,
# because an unmeasured selector that may or may not fire produces exactly the
# uninterpretable measurement this campaign refuses to generate.
readonly batch_unknown=(
  # No consumer exists in either repo: the only references are the worker
  # evidence string list. They may be inert, or they may belong to a sibling
  # kernel branch that never landed. Either way they are not enabled here.
  VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS
  VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP
)

# Recorded for the audit trail: these carry no batch or row constraint and are
# safe to leave enabled at any batch size. They are not enforced by this
# launcher, which only refuses; they are listed so the classification is
# complete where a reader will look for it.
# VLLM_XPU_LAGUNA_INT4_TILE_RECORD   load-time contract only, raises on drift
# VLLM_XPU_LAGUNA_SCALE_VEC          runtime bool, identical at every M
# VLLM_XPU_LAGUNA_SCALE_FOLD         runtime bool, off in the record
# VLLM_XPU_LAGUNA_DEQUANT_MAD        runtime bool, off in the record
# VLLM_XPU_LAGUNA_REPLICATED_EMBEDDING  no batch or row term anywhere; it
#                                    trades three extra shards of embedding
#                                    weight per rank for one dropped all-gather
# VLLM_XPU_LAGUNA_PREFETCH_DIST      consumed only by the 1..8-row launchers,
#                                    so it is already inert on the M=12 path

# Batch-safe but refused anyway, for reasons that are not batch behaviour.
# VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH sets skip_compiled for every step wider
# than 8 tokens, so at the width-12 verifier it permanently disables compiled
# execution while its own exact paths (all gated <= 8 rows) never fire.
readonly production_unsuitable=(
  VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH
)

# The sealed record identity. These are the selectors the protected
# 125.4619731637751 tok/s conventional decode was measured with.
readonly sealed_required=(
  VLLM_XPU_EXACT_SPEC_ATTN
  VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE
  VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH
  VLLM_USE_BREAKABLE_CUDAGRAPH
  XPU_GRAPH
  VLLM_XPU_ENABLE_XPU_GRAPH
  VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2
  VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE
  VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA
  VLLM_XPU_LAGUNA_M8_QKNORM_ROPE
  VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK
  VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK
  VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE
  VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16
  VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH
  VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS
  VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE
  VLLM_XPU_LAGUNA_DECODE_GRF128
  VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES
)

readonly sealed_forbidden=(
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE
  VLLM_XPU_LAGUNA_DFLASH_FP8_Q8
  VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH
  VLLM_XPU_LAGUNA_PARITY_PROBE
  VLLM_XPU_LAGUNA_M8_EVIDENCE
  VLLM_USE_AOT_COMPILE
)

# Diagnostic selectors that write trace or evidence trees and slow execution.
# None of them belong in a service that is answering user requests.
readonly diagnostic_forbidden=(
  VLLM_XPU_LAGUNA_PARITY_PROBE
  VLLM_XPU_LAGUNA_M8_EVIDENCE
  VLLM_XPU_LAGUNA_DRAFT_IDENTITY_PROBE
  VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_TOPK_PROBE
  VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_DEVICE_CYCLES
)

require_enabled() {
  local name reason="$2"
  name="$1"
  [[ "${!name:-}" == 1 ]] || die "$name must be explicitly set to 1 $reason"
}

require_disabled() {
  local name reason="$2"
  name="$1"
  [[ "${!name:-}" == 0 ]] || die "$name must be explicitly set to 0 $reason"
}

meminfo_kib() {
  local key="$1" value
  value="$(awk -v k="$key:" '$1 == k { print $2; found = 1; exit } END { if (!found) exit 1 }' "$meminfo")" \
    || die "could not read $key from $meminfo"
  echo "$value"
}

case "$profile" in
  sealed-single-stream|concurrent) ;;
  *) die "LAGUNA_PRODUCTION_PROFILE must be sealed-single-stream or concurrent, not '$profile'" ;;
esac

[[ "$max_num_seqs" =~ ^[1-9][0-9]*$ ]] \
  || die "LAGUNA_PRODUCTION_MAX_NUM_SEQS must be a positive integer, not '$max_num_seqs'"
[[ "$max_model_len" =~ ^[1-9][0-9]*$ ]] \
  || die "LAGUNA_PRODUCTION_MAX_MODEL_LEN must be a positive integer, not '$max_model_len'"
[[ "$kv_token_floor" =~ ^[1-9][0-9]*$ ]] \
  || die "LAGUNA_PRODUCTION_KV_TOKEN_FLOOR must be a positive integer, not '$kv_token_floor'"
[[ "$port" =~ ^[1-9][0-9]*$ ]] || die "LAGUNA_PRODUCTION_PORT must be a positive integer"

# --- Physical ceiling -------------------------------------------------------
# Concurrency on this host is bounded by KV memory, not by software. Refuse the
# utilization that took the host down rather than trusting an operator to
# remember which value did it.
[[ "$gpu_util" =~ ^0\.[0-9]+$ ]] \
  || die "LAGUNA_PRODUCTION_GPU_UTIL must be a decimal fraction below 1, not '$gpu_util'"
gpu_util_permille="$(awk -v u="$gpu_util" 'BEGIN { printf "%d", (u * 1000) + 0.5 }')"
[[ "$gpu_util_permille" -le "$max_gpu_util_permille" ]] || die \
  "LAGUNA_PRODUCTION_GPU_UTIL=$gpu_util exceeds the measured safe ceiling of 0.80. \
Utilization 0.90 allocated 224081 KV tokens, exhausted host swap, and took the host down. \
This launcher will not start above 0.80 under any override."

kv_tokens_required="$((max_num_seqs * max_model_len))"
[[ "$kv_tokens_required" -le "$kv_token_floor" ]] || die \
  "max_num_seqs=$max_num_seqs at max_model_len=$max_model_len needs $kv_tokens_required KV tokens, \
above the measured floor of $kv_token_floor tokens at utilization 0.80 \
(measured range 91258-109059). At 32768 tokens per request this host fits \
$((kv_token_floor / max_model_len)) concurrent full-length requests, not $max_num_seqs. \
Lower LAGUNA_PRODUCTION_MAX_NUM_SEQS or LAGUNA_PRODUCTION_MAX_MODEL_LEN."

# --- Host memory preflight --------------------------------------------------
# The host OOM was a swap exhaustion, not a device OOM, so it is checked here
# before a model is ever touched.
available_ram_kib="$(meminfo_kib MemAvailable)"
free_swap_kib="$(meminfo_kib SwapFree)"
[[ "$available_ram_kib" -ge "$min_available_ram_kib" ]] || die \
  "available RAM ${available_ram_kib} KiB is below the unconditional floor of ${min_available_ram_kib} KiB (12 GiB)"
if [[ "$free_swap_kib" -lt "$min_free_swap_kib" \
      && "$available_ram_kib" -lt "$swap_pressure_ram_kib" ]]; then
  die "free swap ${free_swap_kib} KiB is below 4 GiB while available RAM ${available_ram_kib} KiB is below 16 GiB; \
this is the combination that preceded the 2026-08-02 host OOM"
fi

# --- Diagnostics are never production ---------------------------------------
for name in "${diagnostic_forbidden[@]}"; do
  [[ "${!name:-0}" != 1 ]] \
    || die "$name is a diagnostic selector and must not be enabled in a production service"
done
for name in "${production_unsuitable[@]}"; do
  [[ "${!name:-0}" != 1 ]] || die \
    "$name carries no batch constraint, but at the width-12 verifier it forces every step \
wider than 8 tokens onto the uncompiled path while its own exact routes never fire. \
It is refused in production for that reason, not for batch behaviour."
done
for name in VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM \
            VLLM_XPU_LAGUNA_REPLAY_TRACE_SESSION VLLM_XPU_LAGUNA_PARITY_RETURN_STAGE; do
  [[ -z "${!name:-}" ]] \
    || die "$name is set; trace, evidence, and parity capture must be unset in a production service"
done

# --- Profile selector contracts ---------------------------------------------
case "$profile" in
  sealed-single-stream)
    [[ "$max_num_seqs" == 1 ]] || die \
      "the sealed-single-stream profile is the measured record identity and requires \
LAGUNA_PRODUCTION_MAX_NUM_SEQS=1; you asked for $max_num_seqs. Use \
LAGUNA_PRODUCTION_PROFILE=concurrent, which turns the exact stack off, or keep batch 1."
    [[ "$max_model_len" == 32768 ]] || die \
      "the sealed identity is pinned to max_model_len 32768, not $max_model_len"
    for name in "${sealed_required[@]}"; do
      require_enabled "$name" "for the sealed-single-stream profile"
    done
    for name in "${sealed_forbidden[@]}"; do
      require_disabled "$name" "for the sealed-single-stream profile"
    done
    [[ "${LAGUNA_M:-}" == 12 && "${LAGUNA_SPEC:-}" == 11 ]] \
      || die "the sealed-single-stream profile requires LAGUNA_M=12 and LAGUNA_SPEC=11"
    [[ "${VLLM_XPU_LAGUNA_EXACT_MAX_M:-}" == 12 ]] \
      || die "the sealed-single-stream profile requires VLLM_XPU_LAGUNA_EXACT_MAX_M=12"
    ;;
  concurrent)
    [[ "$max_num_seqs" -ge 2 ]] || die \
      "the concurrent profile exists to serve more than one sequence; \
LAGUNA_PRODUCTION_MAX_NUM_SEQS=$max_num_seqs would pay the concurrent profile's cost \
for none of its benefit. Use LAGUNA_PRODUCTION_PROFILE=sealed-single-stream."
    for name in "${batch_hostile[@]}"; do
      if [[ "${!name:-0}" == 1 ]]; then
        die "$name is BATCH-HOSTILE and cannot be combined with max_num_seqs=$max_num_seqs: \
$(batch_hostile_reasons "$name"). Set $name=0, or run the sealed-single-stream profile."
      fi
    done
    for name in "${batch_unknown[@]}"; do
      [[ "${!name:-0}" != 1 ]] || die \
        "$name has UNKNOWN batch behaviour and this launcher will not enable it concurrently. \
Its row dependence cannot be settled from source; enabling it would make the run \
uninterpretable rather than fast."
    done
    # Speculative decoding at batch > 1 is unmeasured on this stack. DFlash is
    # only reachable here with the exact attention path off, and no arm has ever
    # run that combination, so the concurrent profile does not speculate.
    [[ "${LAGUNA_PRODUCTION_CONCURRENT_SPECULATION:-0}" == 0 ]] || die \
      "DFlash speculation at max_num_seqs > 1 has never been measured on this stack and \
is only reachable with VLLM_XPU_EXACT_SPEC_ATTN=0, which no arm has run. \
LAGUNA_PRODUCTION_CONCURRENT_SPECULATION is refused."
    ;;
esac

# A batch-hostile selector left on at batch 1 is fine; left on at batch > 1 it
# is either a startup abort or, worse, a silent no-op. The check above already
# covers the concurrent profile, and this repeats it unconditionally so that a
# future profile cannot bypass it.
if [[ "$max_num_seqs" -gt 1 ]]; then
  for name in "${batch_hostile[@]}"; do
    [[ "${!name:-0}" != 1 ]] || die \
      "$name=1 with max_num_seqs=$max_num_seqs: $(batch_hostile_reasons "$name")"
  done
fi

# --- Network exposure -------------------------------------------------------
# vLLM's OpenAI-compatible server is unauthenticated unless an API key is given,
# and it terminates plain HTTP. The campaign's established posture is a
# loopback-only backend with a separate frontdoor, so this launcher defaults to
# loopback and refuses to bind anywhere else without a key. TLS, rate limiting,
# per-user identity, and audit remain the frontdoor's job and are out of scope
# here: a single shared bearer token is an access gate, not an authorization
# system, and this launcher does not pretend otherwise.
api_key_args=()
if [[ "$host" != 127.0.0.1 && "$host" != localhost && "$host" != ::1 ]]; then
  [[ "${LAGUNA_PRODUCTION_LAN_ACK:-0}" == 1 ]] || die \
    "LAGUNA_PRODUCTION_HOST=$host binds beyond loopback. vLLM's OpenAI endpoint is \
unauthenticated by default and this host is LAN-facing. Set LAGUNA_PRODUCTION_LAN_ACK=1 \
and supply LAGUNA_PRODUCTION_API_KEY_FILE, or keep the backend on 127.0.0.1 behind a frontdoor."
  key_file="${LAGUNA_PRODUCTION_API_KEY_FILE:-}"
  [[ -n "$key_file" ]] \
    || die "a non-loopback bind requires LAGUNA_PRODUCTION_API_KEY_FILE"
  [[ "$key_file" == /* ]] || die "LAGUNA_PRODUCTION_API_KEY_FILE must be an absolute path"
  [[ -r "$key_file" ]] || die "cannot read LAGUNA_PRODUCTION_API_KEY_FILE=$key_file"
  key_mode="$(stat -c '%a' -- "$key_file")" || die "cannot stat $key_file"
  [[ "$key_mode" == 600 || "$key_mode" == 400 ]] \
    || die "LAGUNA_PRODUCTION_API_KEY_FILE must be mode 600 or 400, found $key_mode"
  api_key="$(< "$key_file")"
  api_key="${api_key//[$'\r\n']/}"
  [[ "${#api_key}" -ge 32 ]] \
    || die "the API key in LAGUNA_PRODUCTION_API_KEY_FILE must be at least 32 characters"
  api_key_args=(--api-key "$api_key")
fi

laguna_nvme_prepare_paths

common_args=(
  "$LAGUNA_NVME_TARGET_ROOT"
  --host "$host"
  --port "$port"
  --served-model-name laguna-s-2.1-int4
  --revision "$target_revision"
  --tokenizer "$LAGUNA_NVME_TARGET_ROOT"
  --tokenizer-revision "$target_revision"
  --trust-remote-code
  --dtype bfloat16
  --tensor-parallel-size 4
  --data-parallel-size 1
  --pipeline-parallel-size 1
  --distributed-executor-backend mp
  --enable-expert-parallel
  --all2all-backend allgather_reducescatter
  --max-model-len "$max_model_len"
  --max-num-seqs "$max_num_seqs"
  --block-size 64
  --kv-cache-dtype bfloat16
  --gpu-memory-utilization "$gpu_util"
  --enable-chunked-prefill
  --no-enable-prefix-caching
  --generation-config vllm
  "${api_key_args[@]}"
)

if [[ "$profile" == sealed-single-stream ]]; then
  common_args+=(
    --max-num-batched-tokens 8192
    --no-async-scheduling
    --compilation-config
    "{\"mode\":\"NONE\",\"cudagraph_mode\":\"PIECEWISE\",\"cudagraph_capture_sizes\":[${LAGUNA_M}],\"max_cudagraph_capture_size\":${LAGUNA_M}}"
    --speculative-config
    "{\"method\":\"dflash\",\"model\":\"$LAGUNA_NVME_DRAFT_ROOT\",\"revision\":\"$draft_revision\",\"num_speculative_tokens\":${LAGUNA_SPEC},\"draft_sample_method\":\"greedy\",\"rejection_sample_method\":\"standard\",\"use_local_argmax_reduction\":false}"
  )
else
  common_args+=(
    --max-num-batched-tokens "${LAGUNA_PRODUCTION_MAX_NUM_BATCHED_TOKENS:-8192}"
    --enforce-eager
  )
fi

printf 'Laguna production: profile=%s max_num_seqs=%s max_model_len=%s gpu_util=%s host=%s kv_tokens_required=%s kv_token_floor=%s\n' \
  "$profile" "$max_num_seqs" "$max_model_len" "$gpu_util" "$host" \
  "$kv_tokens_required" "$kv_token_floor" >&2
if [[ "$profile" == concurrent ]]; then
  printf 'Laguna production: the concurrent profile has never been measured; it is not a record identity and no decode rate is implied.\n' >&2
fi

exec vllm serve "${common_args[@]}"
