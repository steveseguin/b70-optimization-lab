# vLLM Upstream and Local XPU Audit

Date: 2026-06-20

Scope: `vllm-project/vllm` issues/PRs plus the local
`/home/steve/src/vllm` tree. This is separate from the exhaustive
`vllm-xpu-kernels` fork audit.

## Answer To The Fork Question

I did go through all public `vllm-project/vllm-xpu-kernels` forks returned by
GitHub on 2026-06-20: 76 public forks total, with 10 ahead forks and one
high-signal GDN/spec metadata lead.

I did not attempt to exhaustively enumerate every `vllm-project/vllm` fork.
That fork network is much larger and much noisier. For `vllm` itself, the
higher-value method is issue/PR search plus local code presence checks. That is
what this audit records.

## Method

- Queried recent and relevant upstream `vllm-project/vllm` PRs/issues for:
  `XPU`, `B70`, `DFlash`, `MTP`, `speculative`, `GDN`, `MoE`, `Triton`,
  `ZE_AFFINITY_MASK`, `torchcomms`, and `nvfp4`.
- Fetched high-signal issue bodies, PR bodies, and issue comments where they
  changed the interpretation.
- Checked local `/home/steve/src/vllm` at commit `d7b9cee98`, branch
  `codex/qwen36-quark-int8-tracking`, with local dirty files:
  - `vllm/_xpu_ops.py`
  - `vllm/model_executor/layers/mamba/gdn_linear_attn.py`
  - `vllm/v1/attention/backends/gdn_attn.py`
  - `vllm/v1/worker/gpu_model_runner.py`
  - `vllm/v1/worker/mamba_utils.py`
- Mapped upstream work to local paths and status:
  `missing`, `partially present`, `present`, or `pattern only`.

## Executive Read

The strongest `vllm` upstream leads are not generic kernel wish-list items.
They cluster around four concrete gaps:

1. Multi-GPU XPU process/device isolation and communication:
   `ZE_AFFINITY_MASK` per worker, torchcomms/XCCL alternatives, and worker
   timeout behavior after Level Zero device loss.
2. Qwen3.5/3.6 GDN path efficiency:
   GDN projection fusion, Mamba/GDN pointer fixes, Triton tensor-descriptor
   stores, graph-padded metadata, and XPU test enablement.
3. Spec decode and DFlash correctness plumbing:
   DFlash support exists locally, but it is Triton-heavy and needs XPU-safe
   metadata, attention, mixed KV page, and GDN partial-accept state handling.
4. MoE/KV quant ideas:
   upstream has useful control-plane and Triton pattern work, but several
   CUDA/ROCm PRs are pattern sources only unless ported to SYCL/Triton-XPU.

The most actionable local misses found in this pass:

- Local XPU workers do not isolate each process with per-worker
  `ZE_AFFINITY_MASK` before process start, unlike upstream PR 46226.
- Local XPU platform still always selects `XpuCommunicator`; no torchcomms
  path from PR 46210 is present.
- Local `ssd_chunk_state.py` lacks the optional Triton tensor-descriptor store
  path from PR 45816, which reports a 5-7% device-time reduction for
  `_chunk_cumsum_fwd_kernel` on XPU.
- Local Qwen/GDN still has a separate `in_proj_ba` path; PR 41457 fuses it into
  a single 6-way projection for Qwen3.5/3.6 non-LoRA. Local dirty W8A8
  projection work must be reconciled before porting.
- DFlash is present locally, but `copy_and_expand_dflash_inputs_kernel` and
  several spec-decode kernels are Triton paths that still need XPU proof or a
  torch/SYCL replacement.

## Multi-GPU B70 And XPU Control Plane

### PR 46226: per-worker `ZE_AFFINITY_MASK`

- URL: https://github.com/vllm-project/vllm/pull/46226
- Status: open.
- Local status: missing.
- Local files checked:
  - `/home/steve/src/vllm/vllm/v1/worker/xpu_worker.py`
  - `/home/steve/src/vllm/vllm/platforms/xpu.py`

Why it matters:

- The local worker maps `local_rank` to an XPU index inside `init_device()`
  using `VLLM_XPU_LOCAL_RANK_DEVICE_MAP`, then sets `torch.xpu.set_device()`.
- PR 46226 does something earlier and stronger: each worker process is started
  with a per-worker `ZE_AFFINITY_MASK`, so the process only sees one physical
  XPU and internally uses worker-visible `xpu:0`.
- This directly targets the class of TP/PP worker-init, memory profiling, KV
  cache sizing, and Level Zero visibility bugs seen on B70 multi-GPU runs.

Porting work:

- Inspect PR 46226 patch and adapt the process-start env wrapper into the local
  multiproc executor path.
- Preserve the physical local rank for vLLM orchestration while using
  worker-visible rank/device index for torch/XPU setup.
- Make compile-factor hashing ignore XPU visibility envs, as the PR notes.

Validation:

- First run a device-visibility canary where each worker logs
  `visible_device_count=1`, `ZE_AFFINITY_MASK=<rank>`, and `device_index=0`.
- Then run the normal Qwen benchmark identity with graph flags unchanged.
- This is a stability/control-plane bakeoff before any speed claim.

### PR 46210: torchcomms backend for XPU

- URL: https://github.com/vllm-project/vllm/pull/46210
- Status: open, draft.
- Local status: missing.
- Local files checked:
  - `/home/steve/src/vllm/vllm/platforms/xpu.py`
  - `/home/steve/src/vllm/vllm/distributed/device_communicators/xpu_communicator.py`

Why it matters:

- Local `XPUPlatform.get_device_communicator_cls()` always returns
  `vllm.distributed.device_communicators.xpu_communicator.XpuCommunicator`.
- Local `XpuCommunicator` has several XPU-specific workarounds:
  - optional custom allreduce during compile;
  - timing wrappers around collectives;
  - padded uneven `all_gatherv`, because XCCL can hang on variable-size
    `all_gather(list, input)` for XPU;
  - `gather()` implemented via `all_gather` because gather does not work
    properly with Ray cluster.
- A torchcomms route gives a second communication implementation to A/B
  against these known fragilities.

Porting work:

- Do not replace the current communicator blindly. Add it as an opt-in backend.
- Smoke only collectives used by Qwen TP4 first: allreduce, allgather,
  reduce-scatter, broadcast, and shape-varying paths.
- Check whether torchcomms interacts better or worse with XPU graph capture.

Validation:

- Standalone distributed sweep, then vLLM startup, then endpoint canaries.
- Compare against identical launcher identity only after the communicator is
  stable for at least a sustained run.

### Issues 41663 and 46072: B70 TP/PP failure reports

- URLs:
  - https://github.com/vllm-project/vllm/issues/41663
  - https://github.com/vllm-project/vllm/issues/46072
- Status: open.
- Local relevance: high.

Key signals from issue 41663:

- Dual Arc Pro B70 TP=2 with Qwen3-30B-A3B dynamic FP8 reproduced worker GP
  faults and `xe` BCS resets on Ubuntu 24.04 HWE 6.17.
- Standalone XCCL/SYCL collective sweeps passed, suggesting the failure needs
  the vLLM TP worker-init / ProcessGroupXCCL context.
- Later comments report that some stacks got past init with
  `UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1`, `CCL_ALLREDUCE=ring`, and
  `UR_L0_USE_IMMEDIATE_COMMANDLISTS=0`, but not with a clear speed win.
- A later maintainer/user thread points to Linux 7.1 driver fixes as necessary
  for at least one working multi-root B70 setup.
- A vLLM CI XPU image was reported as working on Ubuntu 24.04.3, kernel
  6.17.0-22, PyTorch 2.11.0+xpu, triton-xpu 3.7.0, Level Zero driver
  25.48.36300.8, vLLM XPU kernels 0.1.9.

Key signals from issue 46072:

- PP=2 on Battlemage B70+B580 can load and answer briefly, then dies around
  live sampling/cross-worker communication with `UR_RESULT_ERROR_DEVICE_LOST`
  or `sample_tokens` RPC timeout.
- Comment thread says a proposed fix only improves failure detection and clean
  shutdown when a worker is wedged in `dist.broadcast()`; it does not fix the
  underlying Level Zero/oneCCL device-loss root cause.

Actionable conclusion:

- Treat B70 multi-GPU stability as a coupled vLLM/oneCCL/Level Zero/driver
  issue, not just a vLLM kernel issue.
- The controlled stack bakeoff should include:
  - current local stack;
  - upstream vLLM CI XPU image from issue 41663 comments if still available;
  - kernel >= 7.1 / NEO >= 26.14 lane from the bare-metal guide;
  - per-worker `ZE_AFFINITY_MASK` from PR 46226.

## Qwen GDN, Mamba, And Triton Kernel Leads

### PR 41457: fuse Qwen3.5/3.6 `in_proj_ba`

- URL: https://github.com/vllm-project/vllm/pull/41457
- Status: open.
- Local status: missing/needs reconciliation.
- Local file checked:
  - `/home/steve/src/vllm/vllm/model_executor/layers/mamba/gdn_linear_attn.py`

Why it matters:

- PR 41457 replaces separate `in_proj_qkvz` and small `in_proj_ba` GEMMs with a
  single 6-way `MergedColumnParallelLinear` for the Qwen3.5/3.6 non-LoRA path.
- The PR notes that `in_proj_ba` is tiny relative to `in_proj_qkvz`, so
  concatenating it into the same GEMM is nearly free and removes a launch/GEMM.
- Local `gdn_linear_attn.py` still has `self.in_proj_ba` as a separate module
  and local dirty W8A8 native int8 projection work around it.

Porting work:

- Read the PR patch and compare with local dirty W8A8 sections around
  `xpu_native_int8_activation_quant`.
- Decide whether to:
  - port the structural 6-way projection first and reattach local W8A8 paths;
  - or defer until the W8A8 projection path is stable.
- This should be a clean branch because it changes checkpoint loading,
  quantized projection routing, and GDN model code.

Validation:

- Weight-load sanity on the exact Qwen3.6 model and Quark W8A8 checkpoint.
- Deterministic short prompts and JSON/color endpoint canaries.
- Same-identity speed A/B only after the exact projection path is proven active.

### PRs 41995 and 44511, issue 41817: high-bit XPU pointers in Mamba copy meta

- URLs:
  - https://github.com/vllm-project/vllm/issues/41817
  - https://github.com/vllm-project/vllm/pull/41995
  - https://github.com/vllm-project/vllm/pull/44511
- Status: issue open, PRs open.
- Local status: largely present locally, but not necessarily identical.
- Local file checked:
  - `/home/steve/src/vllm/vllm/v1/worker/mamba_utils.py`

Why it matters:

- XPU device pointers can be >= 2^63. Signed int64 NumPy assignment can throw
  `OverflowError` during align-mode prefix-cache Mamba/GDN state copies.
- Local `MambaCopyBuffers.create()` already allocates `src_ptrs` and `dst_ptrs`
  with `torch.uint64`, so the main fix is likely present in this branch.
- Comments on the issue report successful fixes on other Arc Pro B50/B60
  systems with Qwen/GDN prefix caching.

Porting work:

- Check upstream final form before assuming local code is best. Upstream PR
  41995 uses a `uint64` NumPy view of existing buffers; local code uses
  `torch.uint64` buffers. Both preserve bit patterns but differ in API surface.
- Add or backport the high-bit pointer regression test if absent locally.

Validation:

- Prefix caching with align-mode on Qwen3.6 crossing the GDN/Mamba block
  boundary.
- Token-identical canary plus prefix-hit-rate logging.

### PR 45816: Triton tensor descriptor store in `_chunk_cumsum_fwd_kernel`

- URL: https://github.com/vllm-project/vllm/pull/45816
- Status: open.
- Local status: missing.
- Local file checked:
  - `/home/steve/src/vllm/vllm/model_executor/layers/mamba/ops/ssd_chunk_state.py`

Why it matters:

- PR 45816 adds an optional Triton tensor-descriptor store path for
  `dt_out` in `_chunk_cumsum_fwd_kernel`, auto-on for XPU via
  `VLLM_TRITON_USE_TD`.
- The PR reports about 5-7% kernel device-time reduction on XPU with no
  regression in tests.
- Local `_chunk_cumsum_fwd_kernel` stores `dt_out` with ordinary pointer
  arithmetic and has no `VLLM_TRITON_USE_TD` path.

Porting work:

- Low-to-medium effort if the PR applies cleanly.
- This is a narrow kernel optimization with tests, but it should not distract
  from larger MoE/spec blockers.

Validation:

- Run the associated Mamba SSD tests on XPU if available.
- Microbench the kernel device time and endpoint canaries.

### PR 44850: unified attention tile mask

- URL: https://github.com/vllm-project/vllm/pull/44850
- Status: open.
- Local status: appears present.
- Local file checked:
  - `/home/steve/src/vllm/vllm/v1/attention/ops/triton_unified_attention.py`

Why it matters:

- The PR fixes masked KV loads in the Triton unified attention tensor
  descriptor path.
- Local `triton_unified_attention.py` already has `tile_mask` used in K/V loads
  around the tiled loop. Treat as likely present unless a patch-level diff says
  otherwise.

## DFlash, MTP, And Spec Decode

### Local DFlash code is present but XPU readiness is not proven

Local files:

- `/home/steve/src/vllm/vllm/v1/spec_decode/dflash.py`
- `/home/steve/src/vllm/vllm/v1/spec_decode/utils.py`
- `/home/steve/src/vllm/vllm/model_executor/models/qwen3_dflash.py`

Local facts:

- `DFlashProposer` exists and calls `copy_and_expand_dflash_inputs_kernel`.
- `qwen3_dflash.py` exists and uses query-only draft attention after target
  context KV has been inserted.
- `copy_and_expand_dflash_inputs_kernel` is `@triton.jit`; `spec_decode/utils.py`
  contains multiple other Triton kernels.
- DFlash sets up non-causal attention metadata; XPU attention backend support
  for that exact contract must be proven.

Porting work:

- Build a DFlash XPU checklist before implementation:
  - DFlash input expansion kernel: Triton-XPU proof or torch/SYCL replacement.
  - DFlash non-causal attention metadata: backend compatibility.
  - GDN verifier partial-accept state: ReplaySSM or equivalent before trusting
    speed.
  - Graph-padded metadata: active-prefix handling from XPU-kernels issue 389,
    PR 391, and the Jason Boukheir fork commit.

### DFlash/spec upstream PRs worth tracking

- PR 43081, DFlash with FlashInfer:
  - URL: https://github.com/vllm-project/vllm/pull/43081
  - Status: open.
  - XPU value: pattern source. It shows required non-causal DFlash routing and
    FP8 KV interactions, but FlashInfer is not an XPU path.

- PR 45181, mixed KV page sizes for DFlash:
  - URL: https://github.com/vllm-project/vllm/pull/45181
  - Status: open.
  - XPU value: high if target and draft page sizes differ. The page-size and
    reshape handling is backend infrastructure, not just CUDA code.

- PR 44807, temporary DFlash SWA merge:
  - URL: https://github.com/vllm-project/vllm/pull/44807
  - Status: open draft.
  - XPU value: track only. Sliding-window behavior matters for DFlash drafters,
    but this is a temporary merge PR, not a final API.

- PR 45237, padding mixed speculative decode batches on D-node:
  - URL: https://github.com/vllm-project/vllm/pull/45237
  - Status: open draft.
  - XPU value: pattern source for preserving uniform graph shapes under spec
    decode and disaggregation. Not directly needed for local single-node TP4
    unless we adopt P/D or DP.

- PR 44336, adaptive K:
  - URL: https://github.com/vllm-project/vllm/pull/44336
  - Status: open.
  - XPU value: later-stage optimization. It only matters after spec decode is
    canary-clean on B70.

- Issue 46088, MTP KV dtype auto correctness:
  - URL: https://github.com/vllm-project/vllm/issues/46088
  - Status: open.
  - XPU value: caution flag. This is CUDA/Gemma, but cross-sequence
    contamination under batched MTP means any B70 spec path needs aggressive
    isolation/canary tests, especially with non-fp8 KV paths.

## MoE, Quant, And KV Cache Pattern Sources

### PR 46206: DeepSeek V4 EPLB across platforms

- URL: https://github.com/vllm-project/vllm/pull/46206
- Status: open.
- XPU value: medium pattern source.

This is not a Qwen3.6-A3B fix, but it shows upstream is actively standardizing
platform-specific MoE metadata and EPLB registration across NVIDIA/ROCm/XPU.
Keep it in the source list for EP/EPLB design and tests.

### PR 44389: Triton software NVFP4 KV cache

- URL: https://github.com/vllm-project/vllm/pull/44389
- Status: open.
- XPU value: medium-to-low until XPU-tested.

The PR reports about 3x KV capacity for Qwen3.6-35B-A3B with MRCR quality close
to auto KV, but the PR explicitly says validation was CUDA-only and XPU was not
tested. Also, the chriswagner B70 guide currently lists NVFP4 as not working on
that B70 stack. Treat as a future capacity lane, not a near-term speed lane.

### PR 45370: fused K-RoPE + static FP8 KV cache write

- URL: https://github.com/vllm-project/vllm/pull/45370
- Status: open.
- XPU value: pattern source.

This is CUDA/ROCm C++ work, not XPU, but the mechanism is relevant: fuse K
rotary embedding and static FP8 KV cache write to avoid an HBM round trip.
Local `xpu.py` currently disables `fuse_rope_kvcache` on XPU unless future work
adds support.

### PR 44891: push-based allreduce

- URL: https://github.com/vllm-project/vllm/pull/44891
- Status: open.
- XPU value: algorithmic pattern only.

This targets CUDA/NVLink small-message allreduce. B70 has no XeLink and no
NVLink, so it is not directly portable. The useful idea is to measure small
decode collectives separately and avoid assuming a single allreduce backend is
optimal across tensor sizes.

### XPU test-enablement PRs

- PR 45694: https://github.com/vllm-project/vllm/pull/45694
- PR 45382: https://github.com/vllm-project/vllm/pull/45382

These are high-value coverage sources, even when they are not performance
patches. They enable XPU tests for Triton kernels such as block int8/fp8,
scaled_mm, int8 quant, KDA, FLA layernorm guard, and per-token-group quant.

Use these test lists to decide whether a Triton kernel is mature enough to rely
on or should be rewritten in SYCL/native torch for B70.

## Local Platform Gaps In `/home/steve/src/vllm`

### XPU platform graph and fusion state

Local file: `/home/steve/src/vllm/vllm/platforms/xpu.py`

Observed behavior:

- XPU graph is disabled if `supports_xpu_graph()` is false or
  `VLLM_XPU_ENABLE_XPU_GRAPH` is false.
- Graph is disabled for `world_size_across_dp > 1` unless
  `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`.
- FlashAttention on XPU forces PIECEWISE graph mode.
- Many fusion passes are disabled on XPU by default:
  - `enable_sp`
  - `fuse_gemm_comms`
  - `fuse_allreduce_rms`
  - `fuse_norm_quant`
  - `fuse_act_quant`
  - `fuse_attn_quant`
  - `fuse_act_padding`
  - `fuse_rope_kvcache`

Actionable conclusion:

- Each disabled fusion pass is a port backlog item. For Qwen3.6 on B70, the
  most relevant are `fuse_gemm_comms`, `fuse_norm_quant`, `fuse_act_quant`, and
  `fuse_rope_kvcache`.
- Do not enable these flags blindly. Each needs backend support, canaries, and
  same-identity benchmarks.

### XPU model runner uses CUDA API monkeypatching

Local file: `/home/steve/src/vllm/vllm/v1/worker/xpu_model_runner.py`

Observed behavior:

- `XPUModelRunner` inherits CUDA/GPU model runner code and temporarily maps
  `torch.cuda.Stream`, `torch.cuda.current_stream`, `torch.cuda.graph`,
  `torch.cuda.CUDAGraph`, etc. to XPU equivalents.

Actionable conclusion:

- This is a fragile compatibility layer. When upstream adds cleaner XPU paths,
  especially around graph capture and stream/event semantics, they are worth
  reviewing even if they are not obvious performance PRs.

### Triton surface is broad

Local search found many `@triton.jit` kernels in relevant paths:

- spec decode: `vllm/v1/spec_decode/utils.py`
- attention: `vllm/v1/attention/ops/*`
- Mamba/GDN/SSD: `vllm/model_executor/layers/mamba/ops/*`
- quantization: `fp8_utils.py`, `int8_utils.py`, `triton_scaled_mm.py`,
  `awq_triton.py`, `nvfp4_emulation_utils.py`

Actionable conclusion:

- For B70, "port Triton to XPU" should be concrete, not generic. Start with
  kernels that directly gate Qwen3.6:
  1. DFlash/spec input expansion and rejection sampler kernels.
  2. Mamba/GDN SSD kernels with existing XPU PRs/tests.
  3. Quark W8A8/INT8 per-token/group quant kernels used by MoE paths.
  4. KV reshape/cache paths needed for prefix cache and long context.

## External B70 Sources From Issue Cross-Links

### chriswagner-ai B70 bare-metal multi-GPU guide

- URL: https://github.com/chriswagner-ai/intel-arc-b70-vllm-multi-gpu
- Status: newly added, high-value host-stack source.

Key claims to verify:

- 4x B70 bare-metal vLLM with TP=2/TP=4 working.
- Multi-GPU TP required both:
  - kernel >= 7.1.0-rc6 plus host NEO >= 26.14; and
  - Triton `init_devices` fix, via triton-xpu >= 3.7.0 or an in-tree patch on
    3.6.0.
- Qwen3-30B-A3B FP8 works in container-proven form.
- Quant support on that stack: FP8 and int4-AutoRound yes; AWQ/GPTQ/NVFP4 no.

Why it matters:

- This lines up with issue 41663 comments about Linux 7.1 driver fixes.
- It is not a kernel optimization source, but it is a strong host-stack
  bakeoff source for TP stability.

### Hal9000AIML B70 Ubuntu setup

- URL: https://github.com/Hal9000AIML/arc-pro-b70-inference-setup-ubuntu-server
- Status: already in source registry, keep as operational source.

Key claim:

- The repo headline says 140 tok/s on 2x B70 and 540 tok/s on 4x B70 for its
  setup, but it is not same-identity evidence for the local Qwen3.6 Quark W8A8
  lane without full workload/config matching.

Why it matters:

- It includes systemd/watchdog scripts, diagnostics, `xe_tuning.sh`, and links
  to B70 speedup patches. Use for environment and operational diagnostics.

## Recommended Next Work Queue

1. Build a vLLM upstream-delta matrix:
   - rows: PRs 46226, 46210, 41457, 45816, 41995/44511, 44850, 43081, 45181,
     45694, 45382;
   - columns: local status, files touched, B70 risk, validation gate, whether
     it needs a vllm-xpu-kernels counterpart.

2. Control-plane bakeoff before kernel invention:
   - per-worker `ZE_AFFINITY_MASK` from PR 46226;
   - torchcomms opt-in from PR 46210 if dependencies are available;
   - current kernel/runtime vs a clean kernel >= 7.1 / NEO >= 26.14 lane.

3. Narrow kernel bakeoffs:
   - PR 45816 tensor descriptor store for `_chunk_cumsum_fwd_kernel`;
   - PR 41457 GDN projection fusion, reconciled with local W8A8 work;
   - XPU test-enablement PRs as coverage sources.

4. DFlash readiness checklist:
   - local DFlash Triton kernels;
   - non-causal attention metadata;
   - mixed KV page handling from PR 45181;
   - graph-padded metadata handling from XPU-kernels issue 389/PR 391/fork
     commit;
   - ReplaySSM or equivalent GDN verifier state.

5. Keep CUDA/ROCm-only PRs in a pattern bucket:
   - PR 44389 NVFP4 KV;
   - PR 45370 fused K-RoPE + FP8 KV write;
   - PR 44891 push allreduce.

## Noise Filters

Do not spend implementation time on:

- PRs that only improve CUDA/HIP without a clear XPU dataflow analog.
- Spec decode features before the GDN verifier state problem is canary-clean.
- Benchmark claims missing model revision, quantization, graph mode, TP/PP,
  concurrency, prompt/output shape, and quality gate.
- Random oneCCL/Level Zero env flag sweeps without a source tying the flag to a
  specific failure mode.
