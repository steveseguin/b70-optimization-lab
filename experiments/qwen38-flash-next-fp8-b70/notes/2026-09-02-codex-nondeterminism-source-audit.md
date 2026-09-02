# Codex read-only source audit: order-dependent computations on the Flash-Next prefill/first-decode path

Date: 2026-09-02 19:05--19:19 EDT. Produced by `codex exec` (gpt-5.6-sol, read-only sandbox) from the prompt preserved below the findings; no GPU work. Requested by the Claude session as bulk source reading while A62 ran. Findings are source claims, not measurements.

## Ranked findings

1. **TP4 BF16 XCCL all-reduce — highest-probability cause.**
   - **Source:** `vllm/platforms/xpu.py:111,467-474`; `vllm/distributed/device_communicators/xpu_communicator.py:48-51`; `vllm/model_executor/layers/linear.py:1653-1661`; GDN/QSA row-parallel outputs at `qwen_gdn_linear_attn.py:476-483,992-1000` and `vllm/models/qwen4_exp/amd/qsa.py:235-242,410-414`.
   - **Why order-dependent:** vLLM clones the tensor and calls `dist.all_reduce` without fixing the algorithm, rank-reduction tree, accumulation precision, or deterministic mode. The preloaded oneCCL implementation controls all of those. A `[1,2560]` BF16 decode result is 5,120 bytes—just above the configured 4,096-byte `twoshots` threshold. Arrival-dependent BF16 accumulation fits the observed 0.125-step logit gaps.
   - **Phase:** both; M=1 is 5,120 bytes, while M=64 is 327,680 bytes.
   - **Cheapest test:** remove the preload and both `CCL_SYCL_ALLREDUCE_LL*` variables; run `repeat-xccl-allreduce-gate.py` at M=1 and M=64 with real-valued BF16 inputs. `probe-xpu-graph-xccl-allreduce.py` and `probe-xpu-graph-xccl-sequence.py` test graph behavior, although their exactly representable fixtures are weaker.

2. **EP4 expert-output reduce-scatter — same oneCCL risk at a second boundary.**
   - **Source:** XPU always chooses `AgRsAll2AllManager` at `xpu_communicator.py:29-46`; combine calls reduce-scatter at `device_communicators/all2all.py:138-150`; XPU delegates directly to `dist.reduce_scatter_tensor` at `xpu_communicator.py:53-75`.
   - **Why order-dependent:** multiple expert ranks contribute floating-point values for each returned token; no fixed summation order or FP32 accumulator is requested.
   - **Phase:** both.
   - **Cheapest test:** replace combine temporarily with all-gather followed by rank-ordered FP32 summation, or run a matched no-EP component gate. The existing all-reduce gate does not exclude reduce-scatter nondeterminism.

3. **XE2 chunk-GDN prefill reductions and recurrent state construction.**
   - **Source:** B70 prefill selects XE2 whenever `num_prefills > 0` at `gdn_attn_interface.cpp:430-488`; Q/K norms and gate prefix scans are at `xe_2/chunk_gated_delta_rule_kernels_xe2.hpp:80-115,119-170`; later DPAS/state stages are at `:1074-1258`.
   - **Why order-dependent:** floating `reduce_over_group`, `inclusive_scan_over_group`, DPAS GEMMs, and recurrent updates are non-associative. Four M=64 prompt chunks construct the state consumed by the first decode token. No atomic race was found.
   - **Phase:** prefill, with direct first-decode consequences through stored state.
   - **Cheapest test:** one-line-disable the `num_prefills > 0` XE2 branch to force `NATIVE_LAUNCHER`; compare with `probe-q38-a57-depth-determinism.py` or `probe-q38-a59-logprob-determinism.py`. `repeat-ple-short-conv-state-gate.py` is the narrow state/conv gate.

4. **QSA sparse-attention split-K and merge.**
   - **Source:** the actual XPU prefill/decode backend is `QWEN4_EXP_QSA_TRITON`, not generic XPU FlashAttention (`vllm/models/qwen4_exp/amd/qsa.py:66-94,148-158,272-284`). Partial online-softmax work is `amd/ops/qsa.py:188-353`; merge reductions are `:356-397`; split policy and launch are `:884-981`.
   - **Why order-dependent:** attention is partitioned into independently normalized FP32 partials and merged with `tl.max`/`tl.sum`. The reduction association differs from split=1, although partial slots are disjoint and the merge is not visibly scheduling-racy.
   - **Phase:** both; decode selects many splits, while the M=64 shape ordinarily selects eight.
   - **Cheapest test:** insert `num_splits = 1` immediately after `amd/ops/qsa.py:908`, then use either logprob/depth probe.

5. **Native GDN first-decode subgroup reductions.**
   - **Source:** no-prefill calls select `NATIVE_LAUNCHER` at `gdn_attn_interface.cpp:489-491`; `gated_delta_rule.hpp:242-337` performs Q/K norm sums (`:250-275`), state·K (`:277-305`), state·Q (`:308-335`), then stores the updated state (`:339-348`).
   - **Why order-dependent:** `sycl::reduce_over_group(...plus)` has non-associative floating-point association. It is fixed-shape and contains no atomic/data race, so it is less compelling than oneCCL.
   - **Phase:** decode; also prefill only when the XE2 path is unavailable or disabled.
   - **Cheapest test:** replace one subgroup sum with a lane-0 serial sum plus broadcast, or component-repeat the native kernel before using A59 end to end.

6. **Fused RMSNorm plus block-FP8 activation quantization.**
   - **Source:** FP32 variance is reduced with `reduce_over_group` at `vllm-xpu-kernels/csrc/layernorm_quant.cpp:68-87,209-248,543-560,631-654`; block scales/stores are `:251-310`; launch geometry is `:750-807`.
   - **Why order-dependent:** RMS variance is a non-associative work-group reduction. Its geometry is fixed by hidden width rather than M, making timing-dependent variation unlikely; FP8 quantization can nevertheless amplify a preceding one-ULP change.
   - **Phase:** both.
   - **Cheapest test:** set compilation `pass_config.fuse_norm_quant=false`, then repeat A59. If identical drift remains, exclude it.

7. **MoE alignment uses relaxed integer atomics to permute same-expert rows.**
   - **Source:** `vllm-xpu-kernels/csrc/moe/moe_align_sum_kernels.cpp:428-455` assigns positions using device-scope relaxed `fetch_add`; the path is launched at `:1122-1180` and consumed by `experts/triton_moe.py:319-333`.
   - **Why order-dependent:** tokens routed to the same expert receive scheduler-dependent positions in `sorted_token_ids`. However, the GEMM scatters each row back to its original flattened token slot (`fused_moe.py:408-423,472-479,607-610`), and final expert summation is fixed-order (`moe_align_sum_kernels.cpp:631-665`). The permutation alone should not alter values.
   - **Phase:** mainly prefill M=64; at decode M=1, distinct top-k experts normally increment distinct counters.
   - **Cheapest test:** stable-sort assignments by `(expert_id, flattened_token_id)` or compare alignment permutations and final outputs with A59. A wait between submissions is not useful: the serving queue is required to be in-order.

8. **PLE UVA side-stream workspace — race-shaped but explicitly fenced.**
   - **Source:** persistent stream/events/buffer at `vllm/models/qwen4_exp/nvidia/ple_layer.py:319-337`; producer and lookup fencing at `:497-534`; consumer wait and overlap rejection at `:536-565`.
   - **Why potentially racy:** a reused output buffer would be vulnerable to cross-generation overwrite, but visible source has producer/consumer events, records the ID tensor on the side stream, rejects overlapping starts, and checks token count.
   - **Phase:** both when enabled. It is eager-only: `vllm/models/qwen4_exp/amd/model.py:496-528`; therefore it cannot explain the validated full-graph configuration.
   - **Cheapest test:** `VLLM_XPU_PLE_UVA_PREFETCH=0`; use `repeat-ple-uva-fp8-lookup-gate.py`, `repeat-ple-async-source-parity-gate.py`, or `probe-ple-uva-fp8-lookup-graph.py`.

9. **QSA cache stores would race only if slot metadata contains duplicates.**
   - **Source:** `_store_qsa_rows_kernel` writes one row per supplied slot without uniqueness checking at `amd/ops/qsa.py:400-434`; compression reads cache/current rows in a fixed loop at `:438-539`.
   - **Why potentially racy:** two valid rows mapped to the same slot would write concurrently. Normal paged-attention metadata should provide unique slots, so this is conditional rather than a demonstrated live race.
   - **Phase:** both.
   - **Cheapest test:** add a debug uniqueness assertion over valid slot mappings before `qsa_store_cache_rows`.

## Source-excluded or strongly weakened candidates

- **QSA top-k:** the historical XPU atomic-reservation race is documented at `amd/ops/qsa.py:799-806`, but current HEAD uses stable descending `torch.argsort` and logical-index tie order at `:807-815`. Confirm that this exact branch is imported.
- **MoE routing ties:** generic XPU top-k uses maximum then minimum expert index (`vllm-xpu-kernels/csrc/moe/topk.cpp:232-264`); the specialized kernel explicitly makes lower expert IDs win ties (`:533-580`). Timing does not decide ties.
- **Triton MoE split-K:** FP32 accumulation and one final store are at `fused_moe.py:512-610`; launcher forcibly sets `SPLIT_K=1` at `:842-844`. No active `tl.atomic_add`.
- **Fused SiLU/block-FP8 quant:** `fused_silu_mul_block_quant.cpp:60-123` uses fixed XOR max reductions and unique stores; no atomics. Gate it by disabling the manual branch at `triton_moe.py:461-472`.
- **Direct UVA lookup:** `offloader/uva.py:71-88,130-136` creates a stable accelerator view of pinned host storage; it performs no request-time host/device copy. PLE owner reduction uses an `int8` view with exactly one nonzero owner (`ple_layer.py:460-495,551-560`), so SUM order is arithmetically exact.
- **Generic XPU FlashAttention:** its Python API accepts `deterministic=False` at `vllm_xpu_kernels/flash_attn_interface.py:413`, but never reads it. This model’s QSA owner bypasses that attention computation.

## Relevant controls and flags

- `CCL_SYCL_ALLREDUCE_LL`, `CCL_SYCL_ALLREDUCE_LL_THRESHOLD`: externally consumed by oneCCL; vLLM neither validates nor overrides them.
- `VLLM_BATCH_INVARIANT`: `vllm/envs.py:621-623`; XPU overrides only `mm/addmm` (`batch_invariant.py:947-951`), while collective settings are NCCL-only (`:980-995`). It does not make XCCL deterministic.
- `VLLM_TRITON_FORCE_FIRST_CONFIG`: `env_override.py:861-873`; fixes Triton autotuner choice.
- `VLLM_TRITON_USE_TD`: changes MoE gather/codegen, not split-K.
- `VLLM_XPU_ENABLE_XPU_GRAPH`: changes capture only; the observed eager/graph agreement already weakens graph scheduling.
- `VLLM_XPU_PLE_UVA_PREFETCH`, `VLLM_PLE_CPU_OFFLOAD`, `VLLM_WEIGHT_OFFLOADING_DISABLE_PIN_MEMORY`, `VLLM_WEIGHT_OFFLOADING_DISABLE_UVA`: PLE/offload isolation controls.
- `pass_config.fuse_norm_quant`, `pass_config.fuse_act_quant`: `vllm/config/compilation.py:120-124`.
- `VLLM_XPU_TOPK_512_SKIP_UNUSED_WORKSPACE`: `vllm-xpu-kernels/csrc/moe/topk.cpp:13-29,925-938`; allocation-only diagnostic.
- `NUM_SPLITS/num_splits`: QSA’s only determinism-relevant split control; no QSA environment toggle exists.
- `VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE`, `_RECURRENT_SERIAL_EXACT`, `_COMPLETION_BARRIER`, `_SPEC_PERSISTENT_SCRATCH`: `gdn_attn_interface.cpp:936-943`; MTP-only and irrelevant here.
- Inactive atomic controls: `VLLM_MARLIN_USE_ATOMIC_ADD` is Marlin-only; `VLLM_XPU_MOE_W8A8_WORKSPACE_ATOMIC` is W8A8 layerlet-only, not this Triton block-FP8 path.

**Top bet 1:** preloaded oneCCL `twoshots` BF16 TP all-reduce at the 5,120-byte M=1 shape.

**Top bet 2:** oneCCL EP4 BF16 reduce-scatter combine.

**Top bet 3:** XE2 chunk-GDN prefill state construction, if the no-preload control does not become bit-exact.

## Prompt

```
You are auditing source code only. Hard constraints: read-only; do not run any GPU work, do not run Python that imports torch/vllm/triton, do not touch /mnt/usb-models or /mnt/fast-ai, do not start or inspect running servers, do not run pgrep/ps with model names. Another agent owns the GPUs right now.

Context: on a 4x Intel Arc Pro B70 host, the vLLM XPU serving line for Qwen/Qwen3.8-Flash-Next-FP8 (TP4/EP4, MTP off, eager or full-decode-graph, chunked prefill with max_num_batched_tokens=64, PLE embeddings offloaded to host UVA memory, Triton block-FP8 fused MoE with EP expert_map, QSA sparse attention, Qwen GDN linear attention) returns different logits for byte-identical greedy requests on the same healthy server. Measured: first decode step after a 256-token prompt, top-1 logprob spread 0.22 nats over 8 repeats; top-2 logit gaps step in multiples of 0.125 (BF16 ulps). It happens with and without the decode graph. A server from 2026-08-28 that used the venv's bundled oneCCL was bit-exact; every server since preloads /mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public (not readable to you, just the name) with CCL_SYCL_ALLREDUCE_LL=twoshots and CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096. A control without that preload is being measured right now by the other agent; your job is the kernel/source side.

Sources: vLLM overlay checkout /home/steve/src/vllm-current-main (HEAD cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9) and XPU kernels /home/steve/src/vllm-xpu-kernels (HEAD e421889999bc1e5a5f11044d14548b9afdba644d). The model code path names to start from: qwen_gdn_linear_attn.py, files containing _qsa_sparse_paged_gqa_splitk_kernel, _qsa_merge_splitk_kernel, _compress_qsa_groups_kernel, _store_qsa_rows_kernel, _qsa_mqa_paged_kernel, _expand_qsa_indices_kernel; vllm/model_executor/layers/fused_moe/{fused_moe.py,moe_align_block_size.py,experts/triton_moe.py}; the XPU platform/communicator under vllm/platforms/xpu.py and vllm/distributed/device_communicators/ (xccl/xpu); any PLE / UVA / cpu-offload embedding lookup code; the XPU attention backend used for prefill of this model; top-k routing (fused_topk / grouped topk) tie handling; RMSNorm/quant fusions ('norm_quant', 'act_quant' custom fusions); the FP8 block quantization of activations (per-token-group quant) and any atomics in it.

Deliverable (markdown, at most 160 lines, no preamble): a ranked list of concrete order-dependent or racy computations on the prefill+first-decode path of this model. For each: file:line(s), what makes it non-reproducible (atomicAdd float accumulation, split-K partial merge order, unordered work-group reduction, data race on a workspace, host/device async copy without sync, tie-breaking that depends on timing, allreduce algorithm), whether it affects prefill (M=64 chunks), decode (M=1), or both, and the cheapest experiment to confirm or exclude it (an env toggle, a config knob, a one-line source guard, or a component gate that already exists under /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools whose name starts with repeat- or probe-). Also list any existing determinism-related env vars or config flags in these trees (grep for 'determin', 'ATOMIC', 'atomic_add', 'tl.atomic', 'split_k', 'SPLIT_K', 'num_splits', 'use_atomic'). End with your top-3 bets in one line each.
```
