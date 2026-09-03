#!/usr/bin/env bash
# One Laguna M8 Breakable-graph leg with the replicated-embedding selector.
# Descended from the sealed measurement leg. Every added treatment is explicit,
# recorded in identity.txt, and validated before the service starts.
# No warmup is performed.  The caller must execute the four legs sequentially.
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly venv_root="${REPRO_VENV_ROOT:-/home/steve/.venvs/deepseek-v4-xpu}"
readonly frozen_path="$venv_root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PATH="$frozen_path"
export PYTHONDONTWRITEBYTECODE=1

readonly nvme_paths="$script_dir/laguna_nvme_paths.sh"
# shellcheck source=laguna_nvme_paths.sh
source "$nvme_paths"

treatment="${1:?usage: run_laguna_m8_metadata_formal_crossover_leg.sh control|candidate A1|B1|B2|A2 RUN_DIR}"
label="${2:?usage: run_laguna_m8_metadata_formal_crossover_leg.sh control|candidate A1|B1|B2|A2 RUN_DIR}"
run_dir="${3:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA}"
readonly laguna_m="${4:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA}"
readonly laguna_spec="${5:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA}"
readonly metadata_arg="${6:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA DRAFTGRAPH}"
# 0 leaves the drafter eager, as every record run to date has. 1 captures it
# in its own breakable graph; the target's audited topology is unaffected
# because the two wrappers are independent instances.
readonly draft_graph="${7:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA DRAFTGRAPH [FUSIONS]}"
# The exact shared-elementwise and QKNorm/RoPE fusions, on by default. They are
# separable so a width can be measured with and without them, which is the only
# way to attribute a failure at a new width to the width or to the fusions.
readonly fusions="${8:-1}"
# QKNorm/RoPE is separable from shared-elementwise because only its launcher
# maps work-groups onto whole heads. With the target's 48 attention heads that
# is H=14 per TP4 rank, so rows*H divides HEADS_PER_WG at 8 and 16 but not at
# 12. Shared-elementwise has no such constraint, so the two are controlled
# independently and width 12 can use the half that is reachable.
readonly qknorm="${9:-$fusions}"
# Vocab-parallel local argmax in the drafter. The draft head is a ParallelLMHead
# over a 100352-token vocabulary, so the default path all-gathers roughly 4.8 MB
# of logits every cycle across a PCIe-connected TP4 group; this exchanges
# (value, index) pairs instead. It must select the same token, which the leg's
# bitwise gate decides.
readonly local_argmax="${10:-0}"
# Capture each of the 48 target attention boundaries as its own XPU subgraph.
# This remains default-off and is mutually exclusive with the prebuilt metadata
# experiment until their combination is validated separately.
readonly capture_attention="${11:-0}"
# Record each target attention body directly into its surrounding outer graph,
# retiring the 48 attention breaks while preserving all 97 collective breaks.
# This is a separate treatment from nested attention subgraphs and requires the
# proven persistent exact-attention metadata path.
readonly inline_attention="${12:-0}"
# Exact width-12 router plus DFlash context-KV workspace stack. The control
# uses the same source and candidate native binary with this selector off.
readonly width12_stack="${13:-0}"
# Draft-only per-channel FP8 W8A16 projections, independent FP8 draft LM head,
# and the exact auxiliary-combine workspace. This is valid only on top of the
# complete width-12 stack and leaves the target model and verifier unchanged.
readonly dflash_fp8="${14:-0}"
# Hold the whole target embedding table on every TP rank. The table is
# deterministic and read-only, so this cannot change an emitted token, but it
# retires one all-reduce per verifier cycle and therefore changes the audited
# topology from 146/145 to 145/144. The leg expects the reduced topology when
# the selector is on, so a silently-ignored flag fails the run rather than
# passing it as a control.
readonly replicated_embedding="${15:-0}"
# Diagnostic only: log the drafted and sampled token ids, and their storage,
# for the first N cycles. A run with this set is not a measurement -- the
# per-cycle host logging perturbs the very timing the leg exists to record --
# so it must never be quoted as a rate.
readonly draft_identity_probe="${16:-0}"
# Diagnostic only: absolute directory under the NVMe artifact root that the
# breakable-graph replay event profile writes rank{0..3}.json into. Splits one
# verifier forward into its 146 graph segments and 145 eager boundaries, which
# is the only way to attribute the cycle rather than infer it. Perturbs timing;
# never quote a rate from a run with this set.
readonly event_profile_root="${17:-}"
# MoE W1 N-tile: literal 32, 64, or 128. The kernel takes it as a runtime
# argument and the record has only ever run 64, because the tile was tuned at
# eight rows and pinned everywhere else. Requires the batched-MoE,
# fused-W1/route-W2, and route-interleave selectors, which this leg sets.
readonly w1_n_tile="${18:-64}"
# Diagnostic only: log each distinct MoE row count the batched path emits.
readonly LAGUNA_LOG_MOE_ROWS_ARG="${19:-0}"
# Generic grouped-GEMM N-tile for the 12-row decode: empty (default 64), 32,
# or 128. Despite the MXFP4 name this selects the INT4 policy too, and it is
# the only tile knob that reaches the width-12 path -- the Laguna M8 tile knob
# is gated to eight rows and never fires here.
readonly mxfp4_small_m_n="${20:-}"
# INT4 mainloop prefetch distance: empty (default 6), 3, 6, or 12. A memory
# pipeline hint only -- it cannot reach any operand, accumulation order or
# rounding step, so exactness is preserved by construction and still gated.
readonly prefetch_dist="${21:-}"
# Fold the per-(N,K-group) scale into the FP32 accumulator instead of applying
# it to every B element. Literal 0 or 1, unset means unfolded. Changes rounding
# and is strictly closer to the FP32 reference; the 13/13 gate decides it.
readonly scale_fold="${22:-}"
# Remove the per-mul marshalling movs from the scale block: 64 instructions per
# k-tile become 32. Verified bitwise identical, so exactness is preserved by
# construction rather than by hope.
readonly scale_vec="${23:-}"
# Fuse the dequantize bias-subtract and the scale multiply into one mad.
# Verified bitwise identical over 1,044,480 exhaustive cases plus 4.8M-element
# tensor comparisons, so exactness is structural.
readonly dequant_mad="${24:-}"
# Hoist the per-k-tile scale reload and its prefetch-address recomputation out
# of the mainloop body; the scale only changes on group boundaries and
# group_size % tile_k == 0 is asserted. Bitwise-neutral by construction.
readonly scale_hoist="${25:-}"
# Safe replacement for the retired whole-drafter graph. Captures only DFlash
# compute segments; six attention calls and thirteen TP all-reduces remain eager.
# The candidate has its own audited 20/19 topology and requires draft_graph=0.
readonly dflash_segmented_graph="${26:-0}"
# Diagnostic gate only: run two 400-token requests and validate each against
# the q=1 teacher prefix, request-local speculation, graph topology, and clean
# teardown. It emits no score and is valid only for the segmented candidate.
readonly dflash_segmented_smoke="${27:-0}"
# Explicit graph-memory reserve. The default preserves every promoted result;
# 0.82 is the previously established width-12 high-graph-memory setting.
readonly gpu_util="${28:-0.90}"
# Reduce the retained graph-produced DFlash boundary tensors in place instead
# of copying each into a second fixed-address buffer. This remains default-off
# and is valid only with the segmented drafter graph.
readonly dflash_inplace_collectives="${29:-0}"
# Record each fixed-output copy in the preceding DFlash graph segment while
# keeping the corresponding all-reduce eager and in the same boundary slot.
readonly dflash_capture_collective_copies="${30:-0}"
# Capture only the six attention bodies inside the segmented DFlash wrapper.
# The target attention selector above remains independent and default-off.
readonly dflash_capture_attention_graphs="${31:-0}"
# Record the same six graph-safe attention bodies directly in their surrounding
# draft segments. Mutually exclusive with the nested attention treatment.
readonly dflash_inline_attention_graphs="${32:-0}"
# Record only the target's 96 fixed-output TP all-gathers in the surrounding
# graph. The embedding ordinary all-reduce and all 48 target attention calls
# remain eager, so the audited target topology must become exactly 50/49.
readonly target_inline_gathers="${33:-0}"
# Select the separately named 128-GRF BF16/INT4 grouped-GEMM kernel only for
# the width-12 target decode call (total_m=120). The candidate DSO itself
# retains explicit 256-GRF properties for draft, prefill, selector-off, and
# every other policy; component bitwise parity is still only a precondition,
# and this leg's frozen 13/13 gate remains authoritative.
readonly decode_grf128="${34:-0}"
# Store the immutable target INT4 BF16 scale tables as [expert,K/32,N] for
# the exact width-12 decode GEMMs only.  Prefill and all other row counts keep
# the checkpoint [expert,N,K/32] layout.  The C++ and Python selectors both
# accept only literal 0/1 and the endpoint exactness gate remains authoritative.
readonly decode_transposed_scales="${35:-0}"
# Diagnostic only: reserve the one-shot replay event profile for the exact
# 146/145 target wrapper when the same process also contains the 14/13
# segmented DFlash wrapper. It has no effect unless event_profile_root is set.
readonly event_profile_target_only="${36:-0}"
# Native BF16 MM for the exact target QKV/O projections at width 8 or 12.
# The candidate remains restricted to the four audited physical shapes and
# raw-BF16 component equality; all other unquantized linears retain BMM.
readonly bf16_attn_native_mm="${37:-0}"
# Fuse the target verifier's FP32-softplus/BF16-round/per-head multiply into
# one exact M12 XPU kernel. Restricted in source to contiguous BF16 width 12,
# head_dim 128, and the two physical target head counts (12 or 18).
readonly m12_attention_gate="${38:-0}"
# Exact width-12 shared-expert SiLU/multiply and routed-scale/add operations.
# This is separate from the legacy M8 selector and may only be enabled for the
# frozen M12/DFlash11 candidate identity.
readonly m12_shared_elementwise="${39:-0}"
# Defer each exact target TP4 rank sum into its immediately following
# residual-add RMSNorm. The unchanged all-gathers stay eager and preserve the
# audited topology. This stack also requires the independently exact native
# M12 attention projection member.
readonly m12_rank_sum_rmsnorm="${40:-0}"
# Diagnostic only: capture DFlash top-2 token ids and logits for offline tree
# policy analysis. The path must be a new directory inside this run. Any value
# makes the leg non-scored; default empty leaves every promoted path unchanged.
readonly confidence_probe_root="${41:-}"
# Diagnostic-only prefix of the target's 96 all-gathers to capture. The
# promoted selector-off identity and the original all-inline treatment both
# retain the default of 96.
readonly target_inline_gather_limit="${42:-96}"
# Diagnostic-only single gather kept eager inside the selected prefix. -1
# preserves both the promoted selector-off path and the original full prefix.
readonly target_inline_gather_skip="${43:--1}"
# Expand the non-scored smoke from its default 2x400 contract to the complete
# frozen 13x512 exactness contract. It remains inside the smoke branch and
# never emits a promoted score.
readonly dflash_full_exactness="${44:-0}"
# Diagnostic only: record the preregistered target verifier row-0 packet at
# position 420/input 20253. The synchronous copy perturbs timing, so this is
# restricted to the non-scored segmented smoke and may never emit a rate.
readonly parity_probe="${45:-0}"
# Diagnostic only: preload the checksum-pinned public oneCCL 2022 runtime that
# passed the Laguna TP4 transaction and row-0 model oracles. This remains
# restricted to non-scored smoke/full-exactness gates; scored legs require a
# separate runtime lock and preregistration.
readonly public_oneccl="${46:-0}"
# Replace the exact M12 mapped gather plus late routed-scale/shared-add pair
# with one arithmetic-identical mapped tail. This is valid only on the frozen
# M12 shared-elementwise candidate and remains default-off.
readonly m12_mapped_tail="${47:-0}"
# Select the separately named exact-small M12 GRF128 kernel that omits only
# the component-proven K-loop barrier pair. This process-wide native selector
# is wired explicitly here so an integration gate cannot silently measure the
# mapped-tail half of the portfolio alone.
readonly decode_no_kloop_barriers="${48:-0}"
# Select scale-lane deduplication in the same exact-small M12 kernel. The two
# grouped-GEMM members are a single preregistered treatment and therefore must
# be enabled together.
readonly scale_lane_dedup="${49:-0}"

readonly repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"

readonly vllm_root="${REPRO_VLLM_TREE:-/home/steve/src/laguna-vllm-width12-stack-clean-20260726}"
readonly kernel_root="${REPRO_KERNEL_TREE:-/home/steve/src/laguna-xpu-kernels-width12-router-clean-20260726}"
readonly venv_python="$venv_root/bin/python"
readonly vllm_binary="$venv_root/bin/vllm"
readonly repro_root="$repo_root/repro/laguna-s-2.1-int4-b70-102tps-20260726"
readonly runtime_lock="${REPRO_RUNTIME_LOCK:-$repro_root/manifests/runtime-lock.json}"
readonly runtime_verifier="${REPRO_RUNTIME_VERIFIER:-$repro_root/verify-runtime.py}"
readonly model_release_manifest="${REPRO_MODEL_MANIFEST:-$repro_root/manifests/model-release-files.sha256}"
readonly xpumem_module="${REPRO_XPUMEM_MODULE:-/home/steve/src/deepseek-v4-xpu-kernels-qnorm-routeportfolio/vllm_xpu_kernels/xpumem_allocator.abi3.so}"
readonly kernel_package="$kernel_root/vllm_xpu_kernels"
readonly native_library_path="$kernel_package:$venv_root/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib"
readonly public_oneccl_root="${REPRO_PUBLIC_ONECCL_ROOT:-/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public}"
readonly public_oneccl_library="$public_oneccl_root/lib/libccl.so.1.0"
readonly public_oneccl_kernels="$public_oneccl_root/lib/ccl/kernels/kernels.spv"
readonly expected_public_oneccl=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700
readonly expected_public_oneccl_kernels=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9
readonly graph_serve="$script_dir/serve_laguna_mwide_graph_nvme.sh"
readonly comparator="$script_dir/compare_exact_runs.py"
readonly benchmark="$repo_root/scripts/bench-openai-realistic-suite.py"
readonly segmented_smoke_runner="$script_dir/run_laguna_dflash_segmented_smoke.py"
readonly metric_qualifier="$repo_root/scripts/qualify_realistic_window_metrics.py"
readonly idle_wrapper="$script_dir/capture_laguna_m8_idle_snapshot.py"
readonly suite="$repo_root/experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
readonly teacher="${REPRO_TEACHER:-$LAGUNA_NVME_RUN_ROOT/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json}"
readonly teacher_text_oracle="${REPRO_TEACHER_TEXT_ORACLE:-}"
readonly expected_vllm="$(git -C "$vllm_root" rev-parse HEAD)"
readonly expected_kernels="$(git -C "$kernel_root" rev-parse HEAD)"
readonly expected_suite=9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
readonly expected_teacher="${REPRO_TEACHER_SHA256:-d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1}"
readonly expected_teacher_text_oracle="${REPRO_TEACHER_TEXT_ORACLE_SHA256:-}"
readonly expected_comparator=c18b6f37aa0f5a848a9d771fa91de14bab115b41557b9d7066bce5984c2a6945
readonly expected_benchmark=40a483d9127a42c6e9f4a3651a429d39d25336d39eee0c782ba2c7712988aa2a
readonly expected_metric_qualifier=3f930c1789a468873b23181353c77c7f8ba875db8415b409670f034e9ca92b20
readonly expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
readonly expected_vllm_binary=d16721cbe3e6bef44881b6b45ce64d9362a82bec4748754bd91ec85704c243fb
readonly expected_native_c="${REPRO_NATIVE_C_SHA256:-126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2}"
readonly expected_moe_c="${REPRO_MOE_C_SHA256:-00fd81608f057039d31e1b316fecbecec60b3b03151e66b95d0f844185119715}"
readonly expected_target_config=9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6
readonly expected_draft_config=6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926
readonly expected_runtime_lock="${REPRO_RUNTIME_LOCK_SHA256:-8c861e5c9d44232346770e2822aa795179f8f90c2678d2ebbb42a690ef4f4a97}"
readonly expected_runtime_verifier=e43f3c9f46e299eeaa8d7bbc828fadeec2ae60f69f39529f7130f154d158f20d
readonly expected_model_release_manifest=c19edb79458a24ceb4bb26c991302de71ef29be40e70124e90bf6c13538c692e
readonly rpc_dir="$LAGUNA_NVME_TMP_ROOT/m8mc-${label,,}"

case "$treatment:$label" in
  control:A1|control:A2|candidate:B1|candidate:B2) ;;
  *) echo "formal label/treatment must be control:A1, candidate:B1, candidate:B2, or control:A2" >&2; exit 2 ;;
esac
(( $# >= 7 && $# <= 49 )) || { echo "seven to forty-nine arguments are required" >&2; exit 2; }
[[ "$target_inline_gather_limit" =~ ^[0-9]+$ ]] \
  && (( target_inline_gather_limit >= 1 && target_inline_gather_limit <= 96 )) \
  || { echo "TARGET_INLINE_GATHER_LIMIT must be an integer from 1 to 96" >&2; exit 2; }
(( target_inline_gathers == 1 || target_inline_gather_limit == 96 )) \
  || { echo "TARGET_INLINE_GATHER_LIMIT requires target inline gathers" >&2; exit 2; }
[[ "$target_inline_gather_skip" =~ ^-1$|^0$|^[1-9][0-9]*$ ]] \
  && (( target_inline_gather_skip >= -1 && target_inline_gather_skip <= 95 )) \
  || { echo "TARGET_INLINE_GATHER_SKIP must be -1 or an integer from 0 to 95" >&2; exit 2; }
(( target_inline_gathers == 1 || target_inline_gather_skip == -1 )) \
  || { echo "TARGET_INLINE_GATHER_SKIP requires target inline gathers" >&2; exit 2; }
(( target_inline_gather_skip < target_inline_gather_limit )) \
  || { echo "TARGET_INLINE_GATHER_SKIP must be below the prefix limit" >&2; exit 2; }
case "$dflash_full_exactness" in 0|1) ;; *) echo "DFLASH_FULL_EXACTNESS must be 0 or 1" >&2; exit 2 ;; esac
(( dflash_full_exactness == 0 || dflash_segmented_smoke == 1 )) \
  || { echo "DFLASH_FULL_EXACTNESS requires the non-scored smoke mode" >&2; exit 2; }
case "$parity_probe" in 0|1) ;; *) echo "PARITY_PROBE must be 0 or 1" >&2; exit 2 ;; esac
(( parity_probe == 0 || (dflash_segmented_smoke == 1 && dflash_full_exactness == 0) )) \
  || { echo "PARITY_PROBE=1 requires the 2x400 non-scored smoke" >&2; exit 2; }
case "$public_oneccl" in 0|1) ;; *) echo "PUBLIC_ONECCL must be 0 or 1" >&2; exit 2 ;; esac
(( public_oneccl == 0 || dflash_segmented_smoke == 1 )) \
  || { echo "PUBLIC_ONECCL=1 requires a non-scored smoke/exactness gate" >&2; exit 2; }
if [[ -n "$confidence_probe_root" ]]; then
  [[ "$confidence_probe_root" == "$run_dir"/* ]] \
    || { echo "confidence probe root must be inside the run directory" >&2; exit 2; }
  [[ ! -e "$confidence_probe_root" && ! -L "$confidence_probe_root" ]] \
    || { echo "confidence probe root must not already exist" >&2; exit 2; }
fi
case "$gpu_util" in 0.82|0.90) ;; *) echo "GPU_UTIL must be 0.82 or 0.90" >&2; exit 2 ;; esac
case "$dflash_inplace_collectives" in
  0|1) ;;
  *) echo "DFLASH_INPLACE_COLLECTIVES must be 0 or 1" >&2; exit 2 ;;
esac
case "$dflash_capture_collective_copies" in
  0|1) ;;
  *) echo "DFLASH_CAPTURE_COLLECTIVE_COPIES must be 0 or 1" >&2; exit 2 ;;
esac
case "$dflash_capture_attention_graphs" in
  0|1) ;;
  *) echo "DFLASH_CAPTURE_ATTENTION_GRAPHS must be 0 or 1" >&2; exit 2 ;;
esac
case "$dflash_inline_attention_graphs" in
  0|1) ;;
  *) echo "DFLASH_INLINE_ATTENTION_GRAPHS must be 0 or 1" >&2; exit 2 ;;
esac
case "$target_inline_gathers" in
  0|1) ;;
  *) echo "TARGET_INLINE_GATHERS must be 0 or 1" >&2; exit 2 ;;
esac
case "$decode_grf128" in
  0|1) ;;
  *) echo "DECODE_GRF128 must be 0 or 1" >&2; exit 2 ;;
esac
case "$decode_transposed_scales" in
  0|1) ;;
  *) echo "DECODE_TRANSPOSED_SCALES must be 0 or 1" >&2; exit 2 ;;
esac
case "$event_profile_target_only" in
  0|1) ;;
  *) echo "EVENT_PROFILE_TARGET_ONLY must be 0 or 1" >&2; exit 2 ;;
esac
case "$bf16_attn_native_mm" in
  0|1) ;;
  *) echo "BF16_ATTN_NATIVE_MM must be 0 or 1" >&2; exit 2 ;;
esac
case "$m12_attention_gate" in
  0|1) ;;
  *) echo "M12_ATTENTION_GATE must be 0 or 1" >&2; exit 2 ;;
esac
(( m12_attention_gate == 0 || (laguna_m == 12 && laguna_spec == 11) )) \
  || { echo "M12_ATTENTION_GATE=1 requires M=12 and SPEC=11" >&2; exit 2; }
[[ "$m12_attention_gate" == 0 || "$treatment" == candidate ]] \
  || { echo "M12_ATTENTION_GATE=1 requires candidate treatment" >&2; exit 2; }
case "$m12_shared_elementwise" in
  0|1) ;;
  *) echo "M12_SHARED_ELEMENTWISE must be 0 or 1" >&2; exit 2 ;;
esac
(( m12_shared_elementwise == 0 || (laguna_m == 12 && laguna_spec == 11) )) \
  || { echo "M12_SHARED_ELEMENTWISE=1 requires M=12 and SPEC=11" >&2; exit 2; }
[[ "$m12_shared_elementwise" == 0 || "$treatment" == candidate ]] \
  || { echo "M12_SHARED_ELEMENTWISE=1 requires candidate treatment" >&2; exit 2; }
(( m12_shared_elementwise == 0 || fusions == 0 )) \
  || { echo "M12 and M8 shared-elementwise selectors are mutually exclusive" >&2; exit 2; }
case "$m12_mapped_tail" in
  0|1) ;;
  *) echo "M12_MAPPED_TAIL must be 0 or 1" >&2; exit 2 ;;
esac
(( m12_mapped_tail == 0 || m12_shared_elementwise == 1 )) \
  || { echo "M12_MAPPED_TAIL=1 requires M12_SHARED_ELEMENTWISE=1" >&2; exit 2; }
[[ "$m12_mapped_tail" == 0 || "$treatment" == candidate ]] \
  || { echo "M12_MAPPED_TAIL=1 requires candidate treatment" >&2; exit 2; }
case "$decode_no_kloop_barriers" in
  0|1) ;;
  *) echo "DECODE_NO_KLOOP_BARRIERS must be 0 or 1" >&2; exit 2 ;;
esac
case "$scale_lane_dedup" in
  0|1) ;;
  *) echo "SCALE_LANE_DEDUP must be 0 or 1" >&2; exit 2 ;;
esac
(( decode_no_kloop_barriers == scale_lane_dedup )) \
  || { echo "exact-small grouped-GEMM selectors must be enabled together" >&2; exit 2; }
(( decode_no_kloop_barriers == 0 || m12_mapped_tail == 1 )) \
  || { echo "exact-small grouped-GEMM portfolio requires M12_MAPPED_TAIL=1" >&2; exit 2; }
(( decode_no_kloop_barriers == 0 || (laguna_m == 12 && laguna_spec == 11) )) \
  || { echo "exact-small grouped-GEMM portfolio requires M=12 and SPEC=11" >&2; exit 2; }
(( decode_no_kloop_barriers == 0 || (width12_stack == 1 && decode_grf128 == 1 && decode_transposed_scales == 1) )) \
  || { echo "exact-small grouped-GEMM portfolio requires width-12 GRF128/transposed scales" >&2; exit 2; }
[[ "$decode_no_kloop_barriers" == 0 || \
   ("$scale_vec" == 1 && "$scale_fold" == 0 && "$dequant_mad" == 0) ]] \
  || { echo "exact-small grouped-GEMM portfolio requires SCALE_VEC=1, SCALE_FOLD=0, DEQUANT_MAD=0" >&2; exit 2; }
[[ "$decode_no_kloop_barriers" == 0 || "$LAGUNA_LOG_MOE_ROWS_ARG" == 1 ]] \
  || { echo "exact-small grouped-GEMM portfolio requires LAGUNA_LOG_MOE_ROWS=1" >&2; exit 2; }
(( decode_no_kloop_barriers == 0 || (dflash_segmented_smoke == 1 && dflash_full_exactness == 0) )) \
  || { echo "exact-small grouped-GEMM portfolio is authorized only for the 2x400 non-scored smoke" >&2; exit 2; }
[[ "$decode_no_kloop_barriers" == 0 || "$treatment" == candidate ]] \
  || { echo "exact-small grouped-GEMM portfolio requires candidate treatment" >&2; exit 2; }
case "$m12_rank_sum_rmsnorm" in
  0|1) ;;
  *) echo "M12_RANK_SUM_RMSNORM must be 0 or 1" >&2; exit 2 ;;
esac
(( m12_rank_sum_rmsnorm == 0 || (laguna_m == 12 && laguna_spec == 11) )) \
  || { echo "M12_RANK_SUM_RMSNORM=1 requires M=12 and SPEC=11" >&2; exit 2; }
[[ "$m12_rank_sum_rmsnorm" == 0 || "$treatment" == candidate ]] \
  || { echo "M12_RANK_SUM_RMSNORM=1 requires candidate treatment" >&2; exit 2; }
(( m12_rank_sum_rmsnorm == 0 || bf16_attn_native_mm == 1 )) \
  || { echo "M12_RANK_SUM_RMSNORM=1 requires BF16_ATTN_NATIVE_MM=1" >&2; exit 2; }
[[ "$event_profile_target_only" == 0 || -n "$event_profile_root" ]] \
  || die "EVENT_PROFILE_TARGET_ONLY requires EVENT_PROFILE_ROOT"
[[ "$dflash_segmented_graph" == 0 || "$dflash_segmented_graph" == 1 ]] ||
  { echo "DFLASH_SEGMENTED_GRAPH must be 0 or 1" >&2; exit 2; }
[[ "$dflash_segmented_smoke" == 0 || "$dflash_segmented_smoke" == 1 ]] ||
  { echo "DFLASH_SEGMENTED_SMOKE must be 0 or 1" >&2; exit 2; }
(( draft_graph == 0 || dflash_segmented_graph == 0 )) ||
  { echo "retired whole-draft graph and segmented draft graph are mutually exclusive" >&2; exit 2; }
case "$draft_graph" in 0|1) ;; *) echo "DRAFTGRAPH must be 0 or 1" >&2; exit 2 ;; esac
case "$metadata_arg" in 0|1) ;; *) echo "METADATA must be 0 or 1" >&2; exit 2 ;; esac
case "$fusions" in 0|1) ;; *) echo "FUSIONS must be 0 or 1" >&2; exit 2 ;; esac
case "$qknorm" in 0|1) ;; *) echo "QKNORM must be 0 or 1" >&2; exit 2 ;; esac
case "$local_argmax" in 0|1) ;; *) echo "LOCAL_ARGMAX must be 0 or 1" >&2; exit 2 ;; esac
case "$capture_attention" in 0|1) ;; *) echo "CAPTURE_ATTENTION must be 0 or 1" >&2; exit 2 ;; esac
case "$inline_attention" in 0|1) ;; *) echo "INLINE_ATTENTION must be 0 or 1" >&2; exit 2 ;; esac
case "$width12_stack" in 0|1) ;; *) echo "WIDTH12_STACK must be 0 or 1" >&2; exit 2 ;; esac
case "$dflash_fp8" in 0|1) ;; *) echo "DFLASH_FP8 must be 0 or 1" >&2; exit 2 ;; esac
(( capture_attention == 0 || metadata_arg == 0 )) \
  || { echo "CAPTURE_ATTENTION=1 requires METADATA=0" >&2; exit 2; }
(( capture_attention == 0 || inline_attention == 0 )) \
  || { echo "CAPTURE_ATTENTION and INLINE_ATTENTION are mutually exclusive" >&2; exit 2; }
(( inline_attention == 0 || metadata_arg == 1 )) \
  || { echo "INLINE_ATTENTION=1 requires METADATA=1" >&2; exit 2; }
(( width12_stack == 0 || (laguna_m == 12 && laguna_spec == 11) )) \
  || { echo "WIDTH12_STACK=1 requires M=12 and SPEC=11" >&2; exit 2; }
[[ "$width12_stack" == 0 || "$treatment" == candidate ]] \
  || { echo "WIDTH12_STACK=1 requires candidate treatment" >&2; exit 2; }
(( dflash_fp8 == 0 || width12_stack == 1 )) \
  || { echo "DFLASH_FP8=1 requires WIDTH12_STACK=1" >&2; exit 2; }
[[ "$dflash_fp8" == 0 || "$treatment" == candidate ]] \
  || { echo "DFLASH_FP8=1 requires candidate treatment" >&2; exit 2; }
(( dflash_segmented_graph == 0 || width12_stack == 1 )) \
  || { echo "DFLASH_SEGMENTED_GRAPH=1 requires WIDTH12_STACK=1" >&2; exit 2; }
(( dflash_segmented_graph == 0 || dflash_fp8 == 1 )) \
  || { echo "DFLASH_SEGMENTED_GRAPH=1 requires DFLASH_FP8=1" >&2; exit 2; }
(( dflash_segmented_graph == 0 || (laguna_m == 12 && laguna_spec == 11) )) \
  || { echo "DFLASH_SEGMENTED_GRAPH=1 requires M=12 and SPEC=11" >&2; exit 2; }
[[ "$dflash_segmented_graph" == 0 || "$treatment" == candidate ]] \
  || { echo "DFLASH_SEGMENTED_GRAPH=1 requires candidate treatment" >&2; exit 2; }
(( dflash_segmented_smoke == 0 || dflash_segmented_graph == 1 )) \
  || { echo "DFLASH_SEGMENTED_SMOKE=1 requires DFLASH_SEGMENTED_GRAPH=1" >&2; exit 2; }
(( dflash_inplace_collectives == 0 || dflash_segmented_graph == 1 )) \
  || { echo "DFLASH_INPLACE_COLLECTIVES=1 requires DFLASH_SEGMENTED_GRAPH=1" >&2; exit 2; }
(( dflash_capture_collective_copies == 0 || dflash_segmented_graph == 1 )) \
  || { echo "DFLASH_CAPTURE_COLLECTIVE_COPIES=1 requires DFLASH_SEGMENTED_GRAPH=1" >&2; exit 2; }
(( dflash_capture_attention_graphs == 0 || dflash_segmented_graph == 1 )) \
  || { echo "DFLASH_CAPTURE_ATTENTION_GRAPHS=1 requires DFLASH_SEGMENTED_GRAPH=1" >&2; exit 2; }
(( dflash_inline_attention_graphs == 0 || dflash_segmented_graph == 1 )) \
  || { echo "DFLASH_INLINE_ATTENTION_GRAPHS=1 requires DFLASH_SEGMENTED_GRAPH=1" >&2; exit 2; }
(( dflash_capture_attention_graphs == 0 || dflash_inline_attention_graphs == 0 )) \
  || { echo "nested and inline DFlash attention graphs are mutually exclusive" >&2; exit 2; }
(( dflash_inplace_collectives == 0 || dflash_capture_collective_copies == 0 )) \
  || { echo "DFlash in-place and captured-copy collectives are mutually exclusive" >&2; exit 2; }
(( target_inline_gathers == 0 || dflash_segmented_graph == 1 )) \
  || { echo "TARGET_INLINE_GATHERS=1 requires DFLASH_SEGMENTED_GRAPH=1" >&2; exit 2; }
(( target_inline_gathers == 0 || dflash_inline_attention_graphs == 1 )) \
  || { echo "TARGET_INLINE_GATHERS=1 requires DFLASH_INLINE_ATTENTION_GRAPHS=1" >&2; exit 2; }
(( target_inline_gathers == 0 || metadata_arg == 1 )) \
  || { echo "TARGET_INLINE_GATHERS=1 requires METADATA=1" >&2; exit 2; }
(( target_inline_gathers == 0 || (capture_attention == 0 && inline_attention == 0) )) \
  || { echo "TARGET_INLINE_GATHERS=1 requires target attention treatments off" >&2; exit 2; }
(( target_inline_gathers == 0 || replicated_embedding == 0 )) \
  || { echo "TARGET_INLINE_GATHERS and replicated embedding are mutually exclusive" >&2; exit 2; }
[[ "$target_inline_gathers" == 0 || "$treatment" == candidate ]] \
  || { echo "TARGET_INLINE_GATHERS=1 requires candidate treatment" >&2; exit 2; }
(( decode_grf128 == 0 || (laguna_m == 12 && width12_stack == 1) )) \
  || { echo "DECODE_GRF128=1 requires M=12 and WIDTH12_STACK=1" >&2; exit 2; }
(( decode_grf128 == 0 || (scale_vec == 1 && dequant_mad == 0 && scale_fold == 0) )) \
  || { echo "DECODE_GRF128=1 requires SCALE_VEC=1, DEQUANT_MAD=0, SCALE_FOLD=0" >&2; exit 2; }
[[ "$decode_grf128" == 0 || "$treatment" == candidate ]] \
  || { echo "DECODE_GRF128=1 requires candidate treatment" >&2; exit 2; }
(( decode_transposed_scales == 0 || decode_grf128 == 1 )) \
  || { echo "DECODE_TRANSPOSED_SCALES=1 requires DECODE_GRF128=1" >&2; exit 2; }
(( decode_transposed_scales == 0 || (laguna_m == 12 && width12_stack == 1) )) \
  || { echo "DECODE_TRANSPOSED_SCALES=1 requires M=12 and WIDTH12_STACK=1" >&2; exit 2; }
[[ "$decode_transposed_scales" == 0 || "$treatment" == candidate ]] \
  || { echo "DECODE_TRANSPOSED_SCALES=1 requires candidate treatment" >&2; exit 2; }

# CPU-only argument-contract tests set this explicit guard. It exits after all
# argument validation but before interface discovery, Git/NVMe checks, model
# verification, an idle observer, or any service/device action. The production
# coordinator launches through env -i and never sets it.
case "${LAGUNA_RUNNER_VALIDATE_ONLY:-0}" in
  0) ;;
  1) printf 'argument_validation=PASS\n'; exit 0 ;;
  *) echo "LAGUNA_RUNNER_VALIDATE_ONLY must be 0 or 1" >&2; exit 2 ;;
esac

die() { echo "Laguna formal M8 crossover leg: $*" >&2; exit 2; }

# The interface carrying the cluster IP is resolved at runtime, not hardcoded.
# A reboot on 2026-07-26 swapped the onboard NIC names: the port holding
# 10.0.0.65 (MAC 3c:ec:ef:ce:5a:7e) moved from eno1 to eth1, and a different
# port took the name eno1 and stayed down. oneCCL then failed with
# "can't find interface eno1 to get host IP", which aborts KVS and PMI
# bootstrap before any GPU transport is created. Deriving the name keeps the
# harness correct across renames. This affects only CCL's rendezvous, not the
# GPU data path.
laguna_cluster_iface() {
  local ip="${REPRO_CLUSTER_IP:-${LAGUNA_CLUSTER_IP:-10.0.0.65}}" iface
  iface="$(ip -o -4 addr show 2>/dev/null | awk -v ip="$ip" '$4 ~ "^"ip"/" {print $2; exit}')"
  [[ -n "$iface" ]] || { echo "no interface carries $ip" >&2; return 1; }
  [[ "$(cat "/sys/class/net/$iface/operstate" 2>/dev/null)" == up ]] \
    || { echo "interface $iface carrying $ip is not up" >&2; return 1; }
  printf '%s\n' "$iface"
}

check_hash() { [[ "$(sha256sum -- "$1" | awk '{print $1}')" == "$2" ]] || die "SHA256 drift: $1"; }

[[ "$run_dir" == "$LAGUNA_NVME_RUN_ROOT"/* ]] || die "run directory must be below fixed NVMe run root"
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "run directory must be canonical"
cluster_iface="$(laguna_cluster_iface)" || die "cannot resolve the cluster interface"
readonly cluster_iface
laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$run_dir"
ambient_sensitive="$(compgen -e | LC_ALL=C sort -u | awk '/^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {print}')"
[[ -z "$ambient_sensitive" ]] || die "refusing inherited runtime variables: $ambient_sensitive"
for path in \
  "$vllm_root" "$kernel_root" "$graph_serve" "$nvme_paths" "$comparator" \
  "$benchmark" "$segmented_smoke_runner" "$metric_qualifier" "$idle_wrapper" \
  "$suite" "$teacher" \
  "$runtime_lock" "$runtime_verifier" "$model_release_manifest" \
  "$xpumem_module"; do
  [[ -e "$path" && "$(realpath -e -- "$path")" != /media/* ]] || die "missing or USB-resident required path: $path"
done
if (( public_oneccl == 1 )); then
  [[ -d "$public_oneccl_root" ]] \
    || die "public oneCCL root is absent: $public_oneccl_root (set REPRO_PUBLIC_ONECCL_ROOT)"
  public_oneccl_real="$(realpath -e -- "$public_oneccl_root")"
  for path in "$public_oneccl_library" "$public_oneccl_kernels"; do
    [[ -f "$path" && "$(realpath -e -- "$path")" == "$public_oneccl_real"/* && "$public_oneccl_real" != /media/* ]] \
      || die "missing or relocated public oneCCL artifact: $path"
  done
  check_hash "$public_oneccl_library" "$expected_public_oneccl"
  check_hash "$public_oneccl_kernels" "$expected_public_oneccl_kernels"
fi
if [[ -n "$teacher_text_oracle" ]]; then
  [[ -n "$expected_teacher_text_oracle" ]] \
    || die "REPRO_TEACHER_TEXT_ORACLE_SHA256 is required with the text oracle"
  [[ -f "$teacher_text_oracle" ]] || die "missing text oracle: $teacher_text_oracle"
  check_hash "$teacher_text_oracle" "$expected_teacher_text_oracle"
fi
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
check_hash "$suite" "$expected_suite"; check_hash "$teacher" "$expected_teacher"
check_hash "$comparator" "$expected_comparator"
check_hash "$benchmark" "$expected_benchmark"
check_hash "$metric_qualifier" "$expected_metric_qualifier"
check_hash "$runtime_lock" "$expected_runtime_lock"
check_hash "$runtime_verifier" "$expected_runtime_verifier"
check_hash "$model_release_manifest" "$expected_model_release_manifest"
check_hash "$venv_python" "$expected_python"
check_hash "$vllm_binary" "$expected_vllm_binary"
check_hash "$LAGUNA_NVME_TARGET_ROOT/config.json" "$expected_target_config"
check_hash "$LAGUNA_NVME_DRAFT_ROOT/config.json" "$expected_draft_config"
check_hash "$kernel_root/vllm_xpu_kernels/_C.abi3.so" "$expected_native_c"
check_hash "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" \
  f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
check_hash "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" \
  "$expected_moe_c"
check_hash "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" \
  "${REPRO_GROUPED_GEMM_SHA256:-fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96}"
check_hash "$kernel_root/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" \
  3390a3065de25e06dbe95a8fbc2c8456c3489a2295816782e90a4086aedc9dd4
check_hash "$kernel_root/vllm_xpu_kernels/libattn_kernels_xe_2.so" \
  ad0eb26f3b0680fcd54a50de821e9c881524d50ad5361b872f88cb0b333b65ca
check_hash "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_default.so" \
  982fb0b7fc96c877aaefa33f3342936af9403ed3960106dececf08697d98d53c
check_hash "$kernel_root/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so" \
  cdcf9539ac1715ef1dd9a81df422dd5bc1f3a58eff93e1bc5bde05959b5d34bb
check_hash "$kernel_root/vllm_xpu_kernels/libmqa_logits_kernels_xe_2.so" \
  58cca1a0507914762b36874d719557715f3a8ae045106bc0aed42bd16e5b6aeb
check_hash "$kernel_root/vllm_xpu_kernels/libmhc_kernels_xe_2.so" \
  f689c3d200731167394c387d267df90311fd5ec21eff9dededb619e871ce1a4f
check_hash "$xpumem_module" \
  8981f5e312cfab901a5bfa8e40a5a1f194e65db3a207784bfa602e5901e5a1a8
laguna_nvme_verify_model_contents
[[ ! -e "$rpc_dir" && ! -L "$rpc_dir" ]] || die "refusing reused RPC path"
! ss -H -ltn 'sport = :18080' | grep -q . || die "port 18080 already has a listener"
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 || die "existing vLLM workers block leg"
parity_trigger="$LAGUNA_NVME_ARTIFACT_ROOT/parity-trigger.json"
(( parity_probe == 0 )) || [[ ! -e "$parity_trigger" && ! -L "$parity_trigger" ]] \
  || die "refusing a stale Laguna parity trigger"

laguna_nvme_prepare_run_dir "$run_dir"
chmod 700 -- "$run_dir"
mkdir -p "$run_dir"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state},idle-interval}
chmod -R 700 -- "$run_dir"
/usr/bin/env -i \
  PATH="$frozen_path" \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 \
  PYTHONSAFEPATH=1 \
  PYTHONPATH="$vllm_root:$kernel_root" \
  LD_LIBRARY_PATH="$native_library_path" \
  "$venv_python" "$runtime_verifier" \
  --lock "$runtime_lock" \
  --vllm-tree "$vllm_root" \
  --kernel-tree "$kernel_root" \
  --venv-root "$venv_root" \
  --xpumem-module "$xpumem_module" \
  --json-out "$run_dir/runtime-verification.json" \
  > "$run_dir/runtime-verification.stdout"

capture_idle() { "$venv_python" "$idle_wrapper" --output "$1"; }
verify_idle_interval() {
  local phase="$1" started elapsed index
  started="$(date +%s)"
  for index in $(seq -w 0 12); do
    capture_idle "$run_dir/idle-interval/${phase}-${index}.json" || return 1
    [[ "$index" == 12 ]] || sleep 5
  done
  elapsed=$(( $(date +%s) - started ))
  (( elapsed >= 60 )) || die "verified idle interval was only ${elapsed}s"
  printf '%s elapsed_seconds=%s snapshots=13\n' "$phase" "$elapsed" >> "$run_dir/idle-interval/summary.txt"
}
assert_no_workers() {
  ! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 || return 1
  ! ss -H -ltn 'sport = :18080' | grep -q .
}
wait_for_no_workers() {
  # The API parent can reap before its multiprocessing children finish their
  # ordinary shutdown.  This boundary is outside the scored request window;
  # wait a bounded interval for clean exit rather than misclassifying that
  # short reaping lag as a surviving worker.
  local attempt
  for attempt in $(seq 1 30); do
    assert_no_workers && return 0
    sleep 1
  done
  return 1
}
server_pid=""
service_alive() { [[ -n "$server_pid" ]] && (kill -0 "$server_pid" 2>/dev/null || kill -0 -- "-$server_pid" 2>/dev/null); }
stop_service() {
  local signal attempts
  [[ -n "$server_pid" ]] || return 0
  for signal in INT TERM KILL; do
    service_alive || break
    kill "-$signal" -- "-$server_pid" 2>/dev/null || true; kill "-$signal" "$server_pid" 2>/dev/null || true
    case "$signal" in INT) attempts=30 ;; TERM) attempts=15 ;; KILL) attempts=10 ;; esac
    for _ in $(seq 1 "$attempts"); do service_alive || break; sleep 1; done
  done
  wait "$server_pid" 2>/dev/null || true
  ! service_alive
}
finalize() {
  local status="$?" stop_status=0 worker_status=0 idle_status=0
  trap - EXIT INT TERM; set +e
  (( parity_probe == 0 )) || rm -f -- "$parity_trigger"
  stop_service || stop_status=1
  wait_for_no_workers || worker_status=1
  capture_idle "$run_dir/failure-post-idle.json" || idle_status=1
  printf 'original_status=%s\nstop_status=%s\nworker_status=%s\nidle_status=%s\n' "$status" "$stop_status" "$worker_status" "$idle_status" > "$run_dir/cleanup-status.txt"
  # Move the RPC directory under the failed run rather than leaving it in the
  # shared tmp root. It stays as evidence, and the path is freed so a retry at
  # the same label is not blocked by the reused-path guard -- which is an
  # integrity check against cross-run contamination, not a reason to require
  # manual cleanup after every failure.
  if [[ -e "$rpc_dir" && ! -e "$run_dir/rpc-after-stop" ]]; then
    mv -- "$rpc_dir" "$run_dir/rpc-after-failure" 2>/dev/null ||
      rm -rf -- "$rpc_dir" 2>/dev/null || true
  fi
  chmod -R a-w -- "$run_dir" 2>/dev/null || true
  exit "$status"
}
trap finalize EXIT; trap 'exit 130' INT; trap 'exit 143' TERM
mkdir --mode=700 "$rpc_dir"

# The shared-elementwise and QKNorm/RoPE fusion kernels were pinned to eight
# rows and so had to be disabled at other widths. They now take the row count at
# runtime, so they are enabled at every width and the flags are recorded in
# identity.txt alongside the width.
se="$fusions"; qk="$qknorm"
metadata_selector="$metadata_arg"
selected_ld_preload=""
selected_ccl_kernel_path=""
selected_native_library_path="$native_library_path"
if (( public_oneccl == 1 )); then
  selected_ld_preload="$public_oneccl_library"
  selected_ccl_kernel_path="$(dirname -- "$public_oneccl_kernels")"
  selected_native_library_path="$public_oneccl_root/lib:$native_library_path"
fi
captured_target_gathers="$(( target_inline_gather_limit - (target_inline_gather_skip >= 0 ? 1 : 0) ))"
expected_num_graphs="$(( target_inline_gathers == 1 ? 146 - captured_target_gathers : (inline_attention == 1 ? 98 : (replicated_embedding == 1 ? 145 : 146)) ))"
expected_num_eager_breaks="$(( target_inline_gathers == 1 ? 145 - captured_target_gathers : (inline_attention == 1 ? 97 : (replicated_embedding == 1 ? 144 : 145)) ))"
dflash_segmented_expected_graphs="$(( dflash_inline_attention_graphs == 1 ? (replicated_embedding == 1 ? 13 : 14) : (replicated_embedding == 1 ? 19 : 20) ))"
dflash_segmented_expected_eager_breaks="$(( dflash_segmented_expected_graphs - 1 ))"
capture_idle "$run_dir/pre-idle.json"
verify_idle_interval prestart
{
  printf 'schema=laguna-replemb-measurement-leg-v1\nlabel=%s\ntreatment=%s\n' "$label" "$treatment"
  printf 'replicated_embedding=%s\n' "$replicated_embedding"
  printf 'exact_max_m=%s\nnum_speculative_tokens=%s\nprebuilt_exact_attn_metadata=%s\n' "$laguna_m" "$laguna_spec" "$metadata_arg"
  printf 'draft_breakable_graph=%s\ncluster_iface=%s\nlocal_argmax=%s\n' "$draft_graph" "$cluster_iface" "$local_argmax"
  printf 'dflash_segmented_graph=%s\ndflash_segmented_expected_graphs=%s\ndflash_segmented_expected_eager_breaks=%s\n' "$dflash_segmented_graph" "$dflash_segmented_expected_graphs" "$dflash_segmented_expected_eager_breaks"
  printf 'dflash_inplace_collectives=%s\n' "$dflash_inplace_collectives"
  printf 'dflash_capture_collective_copies=%s\n' "$dflash_capture_collective_copies"
  printf 'dflash_capture_attention_graphs=%s\n' "$dflash_capture_attention_graphs"
  printf 'dflash_inline_attention_graphs=%s\n' "$dflash_inline_attention_graphs"
  printf 'target_inline_gathers=%s\n' "$target_inline_gathers"
  printf 'target_inline_gather_limit=%s\n' "$target_inline_gather_limit"
  printf 'target_inline_gather_skip=%s\n' "$target_inline_gather_skip"
  printf 'dflash_full_exactness=%s\n' "$dflash_full_exactness"
  printf 'parity_probe=%s\nparity_row=%s\n' "$parity_probe" "$(( parity_probe == 1 ? 0 : -1 ))"
  printf 'public_oneccl=%s\npublic_oneccl_library=%s\npublic_oneccl_sha256=%s\npublic_oneccl_kernels_sha256=%s\n' \
    "$public_oneccl" "$selected_ld_preload" \
    "$([[ "$public_oneccl" == 1 ]] && echo "$expected_public_oneccl" || echo '')" \
    "$([[ "$public_oneccl" == 1 ]] && echo "$expected_public_oneccl_kernels" || echo '')"
  printf 'decode_grf128=%s\n' "$decode_grf128"
  printf 'decode_transposed_scales=%s\n' "$decode_transposed_scales"
  printf 'event_profile_target_only=%s\n' "$event_profile_target_only"
  printf 'bf16_attn_native_mm=%s\n' "$bf16_attn_native_mm"
  printf 'm12_attention_gate=%s\n' "$m12_attention_gate"
  printf 'm12_shared_elementwise=%s\n' "$m12_shared_elementwise"
  printf 'm12_mapped_tail=%s\n' "$m12_mapped_tail"
  printf 'decode_no_kloop_barriers=%s\n' "$decode_no_kloop_barriers"
  printf 'scale_lane_dedup=%s\n' "$scale_lane_dedup"
  printf 'm12_rank_sum_rmsnorm=%s\n' "$m12_rank_sum_rmsnorm"
  printf 'confidence_probe=%s\nconfidence_probe_root=%s\n' \
    "$([[ -n "$confidence_probe_root" ]] && echo 1 || echo 0)" \
    "$confidence_probe_root"
  printf 'native_c_sha256=%s\n' "$expected_native_c"
  scored_measurement=1
  [[ "$dflash_segmented_smoke" == 0 && "$LAGUNA_LOG_MOE_ROWS_ARG" == 0 \
      && "$parity_probe" == 0 && -z "$event_profile_root" \
      && -z "$confidence_probe_root" ]] \
    || scored_measurement=0
  printf 'dflash_segmented_smoke=%s\nscored_measurement=%s\n' "$dflash_segmented_smoke" "$scored_measurement"
  printf 'capture_attention_graphs=%s\ninline_attention_graphs=%s\n' "$capture_attention" "$inline_attention"
  printf 'width12_router_workspace_stack=%s\nmwide_bf16_router_topk=%s\ndflash_context_kv_workspace=%s\n' "$width12_stack" "$width12_stack" "$width12_stack"
  printf 'dflash_fp8_w8a16=%s\ndflash_fp8_target_unchanged=true\n' "$dflash_fp8"
  printf 'm8_shared_elementwise=%s\nm8_qknorm_rope=%s\ngpu_memory_utilization=%s\n' "$se" "$qk" "$gpu_util"
  printf 'log_moe_rows=%s\n' "$LAGUNA_LOG_MOE_ROWS_ARG"
  printf 'identity_source=actual_worktree_heads\nmeasurement_leg_not_record_leg=true\nvllm_commit=%s\nkernel_commit=%s\nmodel=%s\ndraft=%s\nmodel_manifest_sha256=%s\n' "$expected_vllm" "$expected_kernels" "$LAGUNA_NVME_TARGET_ROOT" "$LAGUNA_NVME_DRAFT_ROOT" "$LAGUNA_NVME_MANIFEST_SHA256"
  printf 'model_release_manifest_sha256=%s\nruntime_lock_sha256=%s\nruntime_verifier_sha256=%s\n' "$expected_model_release_manifest" "$expected_runtime_lock" "$expected_runtime_verifier"
  printf 'runtime_verification_sha256=%s\nxpumem_module_sha256=%s\n' "$(sha256sum "$run_dir/runtime-verification.json" | awk '{print $1}')" "$(sha256sum "$xpumem_module" | awk '{print $1}')"
  printf 'shared_native_module_sha256=%s\nxpu_native_module_sha256=%s\nmoe_native_module_sha256=%s\ngrouped_gemm_native_module_sha256=%s\n' "$(sha256sum "$kernel_package/_C.abi3.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/_xpu_C.abi3.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/_moe_C.abi3.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/libgrouped_gemm_xe_2.so" | awk '{print $1}')"
  printf 'fa2_binary_sha256=%s\n' "$(sha256sum "$kernel_root/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" | awk '{print $1}')"
  printf 'attn_library_sha256=%s\n' "$(sha256sum "$kernel_root/vllm_xpu_kernels/libattn_kernels_xe_2.so" | awk '{print $1}')"
  printf 'grouped_gemm_default_sha256=%s\ngdn_attn_library_sha256=%s\nmqa_logits_library_sha256=%s\nmhc_library_sha256=%s\n' "$(sha256sum "$kernel_package/libgrouped_gemm_xe_default.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/libgdn_attn_kernels_xe_2.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/libmqa_logits_kernels_xe_2.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/libmhc_kernels_xe_2.so" | awk '{print $1}')"
  printf 'suite_sha256=%s\nteacher_sha256=%s\nteacher_text_oracle_sha256=%s\nselector_stack=exact-m%s-dflash%s-breakablegraph-w1routew2-routeinterleave-n64-routerworkspace%s-draftfp8%s-draftseg%s\n' "$expected_suite" "$expected_teacher" "${expected_teacher_text_oracle:-embedded-in-teacher}" "$laguna_m" "$laguna_spec" "$width12_stack" "$dflash_fp8" "$dflash_segmented_graph"
  printf 'metadata_selector=%s\nattention_capture_selector=%s\ninline_attention_selector=%s\n' "$metadata_selector" "$capture_attention" "$inline_attention"
  printf 'expected_num_graphs=%s\nexpected_num_eager_breaks=%s\n' "$expected_num_graphs" "$expected_num_eager_breaks"
  printf 'no_warmup=true\nsuite_invocations=1\nretries=0\nverified_idle_interval_seconds=60\n'
  sha256sum "$0" "$graph_serve" "$nvme_paths" "$comparator" "$benchmark" \
    "$segmented_smoke_runner" "$metric_qualifier" "$idle_wrapper" \
    "$venv_python" "$vllm_binary"
} > "$run_dir/identity.txt"

graph=1
serve_script="$graph_serve"
setsid /usr/bin/env -i \
  PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 HOME="$run_dir/private-home" TMPDIR="$run_dir/private-tmp" \
  HF_HOME="$run_dir/private-cache/hf" HF_HUB_CACHE="$run_dir/private-cache/hf/hub" TRANSFORMERS_CACHE="$run_dir/private-cache/hf/transformers" VLLM_CACHE_ROOT="$run_dir/private-cache/vllm" TORCHINDUCTOR_CACHE_DIR="$run_dir/private-cache/torchinductor" TRITON_CACHE_DIR="$run_dir/private-cache/triton" SYCL_CACHE_DIR="$run_dir/private-cache/sycl" NUMBA_CACHE_DIR="$run_dir/private-cache/numba" PYTHONPYCACHEPREFIX="$run_dir/private-cache/pycache" XDG_CACHE_HOME="$run_dir/private-cache" XDG_CONFIG_HOME="$run_dir/private-xdg/config" XDG_DATA_HOME="$run_dir/private-xdg/data" XDG_STATE_HOME="$run_dir/private-xdg/state" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=0 PYTHONPATH="$vllm_root:$kernel_root" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 VLLM_RPC_BASE_PATH="$rpc_dir" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 LD_PRELOAD="$selected_ld_preload" CCL_KERNEL_PATH="$selected_ccl_kernel_path" ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE="$cluster_iface" CCL_KVS_IFACE="$cluster_iface" TORCH_XCCL_ASYNC_ERROR_HANDLING=1 LD_LIBRARY_PATH="$selected_native_library_path" \
  VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1 VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1 VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE="$se" VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE="$m12_shared_elementwise" VLLM_XPU_LAGUNA_M12_MAPPED_GATHER_SCALE_ADD="$m12_mapped_tail" VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS="$decode_no_kloop_barriers" VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP="$scale_lane_dedup" VLLM_XPU_LAGUNA_M12_RANK_SUM_RMSNORM="$m12_rank_sum_rmsnorm" VLLM_XPU_LAGUNA_M8_QKNORM_ROPE="$qk" VLLM_XPU_LAGUNA_M12_ATTENTION_GATE="$m12_attention_gate" VLLM_XPU_LAGUNA_M8_W1_N_TILE="$w1_n_tile" LAGUNA_LOG_MOE_ROWS="${LAGUNA_LOG_MOE_ROWS_ARG:-0}" VLLM_XPU_MXFP4_SMALL_M_N="$mxfp4_small_m_n" VLLM_XPU_LAGUNA_PREFETCH_DIST="$prefetch_dist" VLLM_XPU_LAGUNA_SCALE_FOLD="$scale_fold" VLLM_XPU_LAGUNA_SCALE_VEC="$scale_vec" VLLM_XPU_LAGUNA_DEQUANT_MAD="$dequant_mad" VLLM_XPU_LAGUNA_SCALE_HOIST="$scale_hoist" VLLM_XPU_LAGUNA_DECODE_GRF128="$decode_grf128" VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES="$decode_transposed_scales" VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK="$width12_stack" VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK="$width12_stack" VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE="$width12_stack" VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16="$dflash_fp8" VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH="$dflash_segmented_graph" VLLM_XPU_LAGUNA_DFLASH_INPLACE_COLLECTIVES="$dflash_inplace_collectives" VLLM_XPU_LAGUNA_DFLASH_CAPTURE_COLLECTIVE_COPIES="$dflash_capture_collective_copies" VLLM_XPU_LAGUNA_DFLASH_CAPTURE_ATTENTION_GRAPHS="$dflash_capture_attention_graphs" VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS="$dflash_inline_attention_graphs" VLLM_XPU_LAGUNA_M8_INLINE_GATHERS="$target_inline_gathers" LAGUNA_TARGET_INLINE_GATHER_LIMIT="$target_inline_gather_limit" LAGUNA_TARGET_INLINE_GATHER_SKIP="$target_inline_gather_skip" VLLM_XPU_LAGUNA_REPLICATED_EMBEDDING="$replicated_embedding" VLLM_XPU_LAGUNA_DRAFT_IDENTITY_PROBE="$draft_identity_probe" VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_ROOT="$event_profile_root" VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_TARGET_ONLY="$event_profile_target_only" VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM="$bf16_attn_native_mm" VLLM_XPU_LAGUNA_ARTIFACT_ROOT="$LAGUNA_NVME_ARTIFACT_ROOT" VLLM_XPU_LAGUNA_PARITY_ROW="$(( parity_probe == 1 ? 0 : -1 ))" VLLM_XPU_LAGUNA_PARITY_PROBE="$parity_probe" VLLM_TRACE_FUNCTION=0 VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 VLLM_USE_AOT_COMPILE=0 LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS="$laguna_spec" VLLM_XPU_LAGUNA_EXACT_MAX_M="$laguna_m" VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH="$draft_graph" LAGUNA_M="$laguna_m" LAGUNA_SPEC="$laguna_spec" LAGUNA_GPU_UTIL="$gpu_util" LAGUNA_LOCAL_ARGMAX="$([[ "$local_argmax" == 1 ]] && echo true || echo false)" VLLM_XPU_LAGUNA_CAPTURE_FILTER_DEBUG=1 VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH="$graph" VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS="$capture_attention" VLLM_XPU_LAGUNA_M8_INLINE_ATTENTION_GRAPHS="$inline_attention" VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA="$metadata_arg" VLLM_USE_BREAKABLE_CUDAGRAPH="$graph" XPU_GRAPH="$graph" VLLM_XPU_ENABLE_XPU_GRAPH="$graph" \
  VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 \
  VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_ROOT="$confidence_probe_root" VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_TOPK_PROBE="$([[ -n "$confidence_probe_root" ]] && echo 1 || echo 0)" \
  REPRO_MODEL_ROOT="$LAGUNA_NVME_MODEL_ROOT" REPRO_ARTIFACT_ROOT="$LAGUNA_NVME_ARTIFACT_ROOT" REPRO_NVME_DEVICE="$LAGUNA_NVME_DEVICE" REPRO_NVME_FSTYPE="$LAGUNA_NVME_FSTYPE" \
  "$serve_script" "$run_dir" >"$run_dir/server.log" 2>&1 &
server_pid="$!"; printf '%s\n' "$server_pid" > "$run_dir/server.pid"
for _ in $(seq 1 180); do curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1 && break; service_alive || die "service exited before health"; sleep 5; done
curl -fsS http://127.0.0.1:18080/health >/dev/null || die "service startup timed out"
tr '\0' '\n' < "/proc/$server_pid/environ" | LC_ALL=C sort > "$run_dir/service-environment.txt"
grep -Fx "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=$width12_stack" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=$width12_stack" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=$width12_stack" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=$dflash_fp8" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH=$dflash_segmented_graph" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DFLASH_INPLACE_COLLECTIVES=$dflash_inplace_collectives" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DFLASH_CAPTURE_COLLECTIVE_COPIES=$dflash_capture_collective_copies" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DFLASH_CAPTURE_ATTENTION_GRAPHS=$dflash_capture_attention_graphs" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS=$dflash_inline_attention_graphs" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_M8_INLINE_GATHERS=$target_inline_gathers" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "LAGUNA_TARGET_INLINE_GATHER_LIMIT=$target_inline_gather_limit" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "LAGUNA_TARGET_INLINE_GATHER_SKIP=$target_inline_gather_skip" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DECODE_GRF128=$decode_grf128" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES=$decode_transposed_scales" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_TARGET_ONLY=$event_profile_target_only" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=$bf16_attn_native_mm" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_M12_ATTENTION_GATE=$m12_attention_gate" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=$m12_shared_elementwise" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_M12_MAPPED_GATHER_SCALE_ADD=$m12_mapped_tail" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS=$decode_no_kloop_barriers" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP=$scale_lane_dedup" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_SCALE_FOLD=$scale_fold" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_SCALE_VEC=$scale_vec" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DEQUANT_MAD=$dequant_mad" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=$qk" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_M12_RANK_SUM_RMSNORM=$m12_rank_sum_rmsnorm" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_REPLICATED_EMBEDDING=$replicated_embedding" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_ARTIFACT_ROOT=$LAGUNA_NVME_ARTIFACT_ROOT" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_PARITY_ROW=$(( parity_probe == 1 ? 0 : -1 ))" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_PARITY_PROBE=$parity_probe" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "LAGUNA_LOG_MOE_ROWS=$LAGUNA_LOG_MOE_ROWS_ARG" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "LD_PRELOAD=$selected_ld_preload" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "CCL_KERNEL_PATH=$selected_ccl_kernel_path" "$run_dir/service-environment.txt" >/dev/null
if (( decode_no_kloop_barriers == 1 )); then
  mapfile -t portfolio_workers < <(pgrep -f 'VLLM::Worker' | sort -n)
  (( ${#portfolio_workers[@]} == 4 )) \
    || die "exact-small portfolio expected four model workers"
  : > "$run_dir/exact-small-worker-environments.txt"
  : > "$run_dir/exact-small-worker-grouped-gemm-maps.txt"
  for worker_pid in "${portfolio_workers[@]}"; do
    worker_environment="$run_dir/worker-environment-${worker_pid}.txt"
    tr '\0' '\n' < "/proc/$worker_pid/environ" | LC_ALL=C sort \
      > "$worker_environment"
    grep -Fx "VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_DECODE_GRF128=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_SCALE_FOLD=0" "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_SCALE_VEC=1" "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_DEQUANT_MAD=0" "$worker_environment" >/dev/null
    grep -Fx "LAGUNA_LOG_MOE_ROWS=1" "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_M12_MAPPED_GATHER_SCALE_ADD=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS=1" \
      "$worker_environment" >/dev/null
    grep -Fx "VLLM_XPU_LAGUNA_EXACT_MAX_M=12" "$worker_environment" >/dev/null
    grep -Fx "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=11" \
      "$worker_environment" >/dev/null
    grep -Fx "LAGUNA_M=12" "$worker_environment" >/dev/null
    grep -Fx "LAGUNA_SPEC=11" "$worker_environment" >/dev/null
    printf 'pid=%s sha256=%s\n' "$worker_pid" \
      "$(sha256sum "$worker_environment" | awk '{print $1}')" \
      >> "$run_dir/exact-small-worker-environments.txt"
    mapfile -t grouped_maps < <(
      awk '$NF ~ /^\// && $NF ~ /libgrouped_gemm_xe_2\.so$/ {print $NF}' \
        "/proc/$worker_pid/maps" | sort -u
    )
    (( ${#grouped_maps[@]} == 1 )) \
      || die "worker $worker_pid did not map exactly one grouped-GEMM DSO"
    [[ "$(realpath -e -- "${grouped_maps[0]}")" == \
       "$(realpath -e -- "$kernel_package/libgrouped_gemm_xe_2.so")" ]] \
      || die "worker $worker_pid mapped the wrong grouped-GEMM DSO"
    check_hash "${grouped_maps[0]}" \
      "${REPRO_GROUPED_GEMM_SHA256:-fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96}"
    printf 'pid=%s path=%s sha256=%s\n' "$worker_pid" "${grouped_maps[0]}" \
      "${REPRO_GROUPED_GEMM_SHA256:-fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96}" \
      >> "$run_dir/exact-small-worker-grouped-gemm-maps.txt"
  done
fi
verify_exact_small_route_evidence() {
  (( decode_no_kloop_barriers == 1 )) || return 0
  "$venv_python" - "$run_dir/server.log" <<'PY'
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
rank_pattern = re.compile(r"Worker_TP([0-3])_EP([0-3])")
rows = [line for line in lines if "LAGUNA_MOE_ROWS num_rows=12" in line]
ranks = {
    tuple(map(int, match.groups()))
    for line in rows
    if (match := rank_pattern.search(line))
}
expected = {(0, 0), (1, 1), (2, 2), (3, 3)}
if len(rows) != 4 or ranks != expected:
    raise SystemExit(
        "exact-small real-M12 route evidence mismatch: "
        f"rows={len(rows)} ranks={sorted(ranks)}"
    )
PY
}
if (( public_oneccl == 1 )); then
  mapfile -t public_oneccl_workers < <(pgrep -f 'VLLM::Worker' | sort -n)
  (( ${#public_oneccl_workers[@]} == 4 )) \
    || die "public oneCCL gate expected four model workers"
  : > "$run_dir/public-oneccl-worker-maps.txt"
  for worker_pid in "${public_oneccl_workers[@]}"; do
    mapfile -t mapped_ccl < <(
      awk '$NF ~ /^\// && $NF ~ /libccl\.so/ {print $NF}' "/proc/$worker_pid/maps" \
        | sort -u
    )
    (( ${#mapped_ccl[@]} == 1 )) \
      || die "worker $worker_pid did not map exactly one public libccl"
    [[ "$(realpath -e -- "${mapped_ccl[0]}")" == "$public_oneccl_library" ]] \
      || die "worker $worker_pid mapped the wrong libccl: ${mapped_ccl[0]}"
    check_hash "${mapped_ccl[0]}" "$expected_public_oneccl"
    printf 'pid=%s path=%s sha256=%s\n' "$worker_pid" "${mapped_ccl[0]}" \
      "$expected_public_oneccl" >> "$run_dir/public-oneccl-worker-maps.txt"
  done
fi
if (( parity_probe == 1 )); then
  jq -n \
    --arg output_dir "$run_dir/parity" \
    --arg run_label "$label" \
    '{expected_position:420, expected_input_id:20253, output_dir:$output_dir, run_label:$run_label}' \
    > "$parity_trigger"
fi
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-before-suite.prom"
if (( dflash_segmented_smoke == 1 )); then
  smoke_request_count="$(( dflash_full_exactness == 1 ? 13 : 2 ))"
  smoke_max_tokens="$(( dflash_full_exactness == 1 ? 512 : 400 ))"
  "$venv_python" "$segmented_smoke_runner" \
    --base-url http://127.0.0.1:18080 \
    --model laguna-s-2.1-int4 \
    --suite "$suite" \
    --teacher "$teacher" \
    --benchmark-helper "$benchmark" \
    --server-log "$run_dir/server.log" \
    --replicated-embedding "$replicated_embedding" \
    --target-graphs "$expected_num_graphs" \
    --target-eager-breaks "$expected_num_eager_breaks" \
    --draft-graphs "$dflash_segmented_expected_graphs" \
    --draft-eager-breaks "$dflash_segmented_expected_eager_breaks" \
    --request-count "$smoke_request_count" \
    --max-tokens "$smoke_max_tokens" \
    --out "$run_dir/segmented-smoke.json" \
    > "$run_dir/segmented-smoke.stdout"
  curl -fsS http://127.0.0.1:18080/metrics \
    > "$run_dir/metrics-after-smoke.prom"
  verify_exact_small_route_evidence
  "$venv_python" - "$run_dir/server.log" "$target_inline_gathers" "$target_inline_gather_limit" "$target_inline_gather_skip" "$m12_mapped_tail" <<'PY'
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
prefix = "Laguna target inline gathers using "
rows = [line for line in lines if prefix in line]
rank = re.compile(r"Worker_TP([0-3])_EP([0-3])")
observed = {
    tuple(map(int, match.groups()))
    for line in rows
    if (match := rank.search(line))
}
expected = {(0, 0), (1, 1), (2, 2), (3, 3)}
if int(sys.argv[2]) == 1:
    marker = (
        f"Laguna target inline gathers using "
        f"{int(sys.argv[3]) - int(int(sys.argv[4]) >= 0)} captured fixed BF16 "
        f"input slots with prefix limit {int(sys.argv[3])} and skip "
        f"{int(sys.argv[4])}, plus 96 fixed BF16 output slots with shape "
        "[1,12,3072]"
    )
    matching_rows = [line for line in rows if marker in line]
    if len(matching_rows) != 4 or len(rows) != 4 or observed != expected:
        raise SystemExit(
            "target inline-gather fixed-slot activation mismatch: "
            f"rows={len(rows)} ranks={sorted(observed)}"
        )
elif rows:
    raise SystemExit(
        "target inline-gather fixed-slot marker appeared in a flag-off smoke: "
        f"rows={len(rows)}"
    )
mapped_enabled = [
    line for line in lines
    if "Enabled exact Laguna M=12 mapped gather/scale/add tail." in line
]
mapped_dispatched = [
    line for line in lines
    if "LAGUNA_M12_MAPPED_GATHER_SCALE_ADD dispatched" in line
]
dispatched_ranks = {
    tuple(map(int, match.groups()))
    for line in mapped_dispatched
    if (match := rank.search(line))
}
enabled_ranks = {
    tuple(map(int, match.groups()))
    for line in mapped_enabled
    if (match := rank.search(line))
}
if int(sys.argv[5]) == 1:
    if (
        len(mapped_enabled) != 4
        or enabled_ranks != expected
        or len(mapped_dispatched) != 4
        or dispatched_ranks != expected
    ):
        raise SystemExit(
            "M12 mapped-tail activation mismatch: "
            f"enabled={len(mapped_enabled)} ranks={sorted(enabled_ranks)} "
            f"dispatched={len(mapped_dispatched)} "
            f"dispatch_ranks={sorted(dispatched_ranks)}"
        )
elif mapped_enabled or mapped_dispatched:
    raise SystemExit(
        "M12 mapped-tail marker appeared in a flag-off smoke: "
        f"enabled={len(mapped_enabled)} dispatched={len(mapped_dispatched)}"
    )
PY
  stop_service; server_pid=""
  (( parity_probe == 0 )) || rm -f -- "$parity_trigger"
  wait_for_no_workers || die "workers or listener survived smoke shutdown"
  capture_idle "$run_dir/post-idle.json"
  verify_idle_interval poststop
  mv -- "$rpc_dir" "$run_dir/rpc-after-stop"
  printf 'status=PASS\nscored_measurement=false\n' > "$run_dir/status.txt"
  trap - EXIT INT TERM
  chmod -R a-w -- "$run_dir"
  echo "Laguna segmented DFlash smoke PASS: $label $treatment $run_dir"
  exit 0
fi
cd "$repo_root"
"$venv_python" "$benchmark" --base-url http://127.0.0.1:18080 --model laguna-s-2.1-int4 --suite experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json --max-tokens 512 --metric-tokens 100 --seed 1 --timeout 1800 --return-token-ids --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' --out "$run_dir/bench.json" > "$run_dir/bench.stdout"
"$venv_python" "$metric_qualifier" "$run_dir/bench.json" --in-place > "$run_dir/metric-accounting.stdout"
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-after-suite.prom"
comparator_args=(--teacher "$teacher" --require-text-hash)
if [[ -n "$teacher_text_oracle" ]]; then
  comparator_args+=(--teacher-text-oracle "$teacher_text_oracle")
fi
"$venv_python" "$comparator" "${comparator_args[@]}" --candidate "$run_dir/bench.json" --out "$run_dir/exactness-vs-q1.json" > "$run_dir/exactness-vs-q1.stdout"
jq -e '.fresh_response_validity.valid == true and .fresh_response_validity.each_prompt_run_once == true and .fresh_response_validity.cached_tokens_all_zero == true and .realistic_final_gate.passed == true and .run_identity.prompt_count == 13 and .run_identity.max_tokens == 512 and .run_identity.seed == 1' "$run_dir/bench.json" >/dev/null
jq -e '.all_exact == true and .candidates[0].comparison.exact_count == 13 and .candidates[0].comparison.total == 13 and .candidates[0].comparison.all_cached_zero == true and .candidates[0].comparison.text_sha256_checked_count == 13 and .candidates[0].comparison.all_text_sha256_equal == true' "$run_dir/exactness-vs-q1.json" >/dev/null
verify_exact_small_route_evidence
"$venv_python" - "$run_dir/server.log" "$expected_num_graphs" "$expected_num_eager_breaks" "$dflash_fp8" "$dflash_segmented_graph" "$dflash_segmented_expected_graphs" "$dflash_segmented_expected_eager_breaks" "$m12_shared_elementwise" "$m12_rank_sum_rmsnorm" "$m12_mapped_tail" <<'PY'
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
expected_shape = (
    f"(graphs={int(sys.argv[2])}, eager_breaks={int(sys.argv[3])})"
)
captures = [line for line in lines if "Captured audited breakable cudagraph" in line]
replays = [line for line in lines if "Replayed audited breakable cudagraph" in line]
rank = re.compile(r"Worker_TP([0-3])_EP([0-3])")
expected = {(0, 0), (1, 1), (2, 2), (3, 3)}
for name, rows in (("capture", captures), ("replay", replays)):
    target_rows = [line for line in rows if expected_shape in line]
    observed = {
        tuple(map(int, match.groups()))
        for line in target_rows
        if (match := rank.search(line))
    }
    if len(target_rows) != 4 or observed != expected:
        raise SystemExit(
            f"target graph {name} topology mismatch: "
            f"rows={len(target_rows)} ranks={sorted(observed)}"
        )
    draft_shape = (
        f"(graphs={int(sys.argv[6])}, eager_breaks={int(sys.argv[7])})"
    )
    draft_rows = [line for line in rows if draft_shape in line]
    draft_observed = {
        tuple(map(int, match.groups()))
        for line in draft_rows
        if (match := rank.search(line))
    }
    if int(sys.argv[5]) == 1:
        if len(draft_rows) != 4 or draft_observed != expected:
            raise SystemExit(
                f"draft graph {name} topology mismatch: "
                f"rows={len(draft_rows)} ranks={sorted(draft_observed)}"
            )
        if len(rows) != 8:
            raise SystemExit(f"unexpected audited {name} rows: {len(rows)}")
    elif draft_rows or len(rows) != 4:
        raise SystemExit(
            f"draft graph appeared in flag-off {name}: "
            f"draft_rows={len(draft_rows)} all_rows={len(rows)}"
        )
fp8_rows = [
    line for line in lines
    if "Prepared Laguna DFlash FP8 W8A16 draft projections: count=31" in line
]
fp8_ranks = {
    tuple(map(int, match.groups()))
    for line in fp8_rows
    if (match := rank.search(line))
}
if int(sys.argv[4]) == 1:
    if len(fp8_rows) != 4 or fp8_ranks != expected:
        raise SystemExit(
            "draft FP8 projection treatment mismatch: "
            f"rows={len(fp8_rows)} ranks={sorted(fp8_ranks)}"
        )
elif fp8_rows:
    raise SystemExit(
        f"draft FP8 treatment appeared in a flag-off run: rows={len(fp8_rows)}"
    )
shared_rows = [
    line for line in lines
    if "Enabled exact Laguna M=12 shared elementwise ops." in line
]
shared_ranks = {
    tuple(map(int, match.groups()))
    for line in shared_rows
    if (match := rank.search(line))
}
if int(sys.argv[8]) == 1:
    if len(shared_rows) != 4 or shared_ranks != expected:
        raise SystemExit(
            "M12 shared-elementwise treatment mismatch: "
            f"rows={len(shared_rows)} ranks={sorted(shared_ranks)}"
        )
elif shared_rows:
    raise SystemExit(
        "M12 shared-elementwise treatment appeared in a flag-off run: "
        f"rows={len(shared_rows)}"
    )
rank_sum_rows = [
    line for line in lines
    if "Enabled exact Laguna M12 deferred rank-sum/RMSNorm stack." in line
]
rank_sum_ranks = {
    tuple(map(int, match.groups()))
    for line in rank_sum_rows
    if (match := rank.search(line))
}
if int(sys.argv[9]) == 1:
    if len(rank_sum_rows) != 4 or rank_sum_ranks != expected:
        raise SystemExit(
            "M12 rank-sum/RMSNorm treatment mismatch: "
            f"rows={len(rank_sum_rows)} ranks={sorted(rank_sum_ranks)}"
        )
elif rank_sum_rows:
    raise SystemExit(
        "M12 rank-sum/RMSNorm treatment appeared in a flag-off run: "
        f"rows={len(rank_sum_rows)}"
    )
mapped_enabled = [
    line for line in lines
    if "Enabled exact Laguna M=12 mapped gather/scale/add tail." in line
]
mapped_dispatched = [
    line for line in lines
    if "LAGUNA_M12_MAPPED_GATHER_SCALE_ADD dispatched" in line
]
mapped_dispatch_ranks = {
    tuple(map(int, match.groups()))
    for line in mapped_dispatched
    if (match := rank.search(line))
}
mapped_ranks = {
    tuple(map(int, match.groups()))
    for line in mapped_enabled
    if (match := rank.search(line))
}
if int(sys.argv[10]) == 1:
    if (
        len(mapped_enabled) != 4
        or mapped_ranks != expected
        or len(mapped_dispatched) != 4
        or mapped_dispatch_ranks != expected
    ):
        raise SystemExit(
            "M12 mapped-tail treatment mismatch: "
            f"enabled={len(mapped_enabled)} ranks={sorted(mapped_ranks)} "
            f"dispatched={len(mapped_dispatched)} "
            f"dispatch_ranks={sorted(mapped_dispatch_ranks)}"
        )
elif mapped_enabled or mapped_dispatched:
    raise SystemExit(
        "M12 mapped-tail treatment appeared in a flag-off run: "
        f"enabled={len(mapped_enabled)} dispatched={len(mapped_dispatched)}"
    )
PY
stop_service; server_pid=""
wait_for_no_workers || die "workers or listener survived shutdown"
capture_idle "$run_dir/post-idle.json"
verify_idle_interval poststop
mv -- "$rpc_dir" "$run_dir/rpc-after-stop"
printf 'status=PASS\n' > "$run_dir/status.txt"
echo "Laguna formal M8 metadata crossover leg PASS: $label $treatment $run_dir"
