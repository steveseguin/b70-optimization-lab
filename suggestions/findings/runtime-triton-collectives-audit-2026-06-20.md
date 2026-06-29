# Runtime, Triton-XPU, and Collectives Audit

Created: 2026-06-20

Scope: deeper source pass for B70 multi-GPU stability, oneAPI/Level Zero
runtime deltas, Triton-XPU compiler/backend work, `llm-scaler` issue reports,
and adjacent engine patterns that could inform Qwen3.6-35B-A3B on 4x Arc Pro
B70. This file is research only; it does not propose implementing anything in
the current working tree.

## Executive Read

1. Treat the B70 runtime/topology stack as a performance prerequisite, not as
   generic environment noise. Several current failures are in Level Zero,
   Unified Runtime, oneCCL, XCCL, P2P, or worker device visibility before
   model kernels matter.
2. Kernel 7.1+ and compute-runtime `26.22.38646.4` plus IGC `v2.36.3` are
   high-priority stack candidates because multiple reports tie them to fixes
   for multi-device context and P2P/compression regressions. They need a
   controlled branch/container bakeoff, not an in-place production swap.
3. Consumer Intel cross-root-port P2P can be unsupported or worse: forced
   copies can return success while corrupting data. Any TP4 plan should prove
   P2P with a checksum test and should also measure host-staged fallback.
4. For MoE, the strongest Triton-XPU lead is not a direct CUDA gather port.
   Intel's Triton issue discussion points toward dense/pre-grouped expert
   layouts, 2D block IO, tensor descriptors where stride rules fit, or the
   SYCL-TLA path as an oracle.
5. For attention and FP8 KV, several small Triton-XPU PRs have measured vLLM
   benchmark wins. These are cheaper bakeoff candidates than inventing new
   local kernels.
6. Adjacent engines are useful pattern sources: llama.cpp SYCL is actively
   working through B70 topology, host-staged fallback, BF16-compressed
   allreduce, GDN recurrent state lifecycle, and MTP chaining.

## Runtime and Driver Lane

The `llm-scaler` and `compute-runtime` issue sets are now high-value sources
because they map to the exact class of failure that can make TP2/TP4 vLLM
results meaningless: worker startup passes, memory profiling starts, then the
first collective, IPC handle, broadcast, sample path, or P2P copy fails.

Before interpreting vLLM speed, collect this exact inventory:

- kernel version and whether it is xe or i915;
- compute-runtime, Level Zero, IGC, GMM, oneAPI runtime, oneCCL, PyTorch XPU,
  Triton-XPU, vLLM, and `vllm-xpu-kernels` versions;
- `xpu-smi topology -m`, `lspci -tv`, and PCIe root-port grouping;
- stale library check such as `LD_DEBUG=libs clinfo -l`, because issue reports
  show stale `/usr/local/lib` IGC can shadow distro/PPA packages;
- all Qwen benchmark identity flags from `/home/steve/AGENTS.md`.

Minimal low-level tests before endpoint vLLM:

- per-worker visibility test with `ZE_AFFINITY_MASK` and `torch.xpu`;
- multi-device SYCL/UR context allocation test;
- XCCL/oneCCL allreduce and broadcast on representative Qwen tensor sizes;
- Level Zero dev-to-dev copy checksum test for each B70 pair;
- host-staged dev-host-dev copy checksum test for each B70 pair;
- a one-request Qwen canary before throughput is recorded.

Candidate stack matrix:

- current local lane: keep as the control;
- configured PPA lane if it only moves from `26.18.38308.1` to
  `26.18.38308.4`;
- compute-runtime `26.22.38646.4` plus IGC `v2.36.3`;
- kernel 7.1+ lane where available;
- oneAPI 2026.x and PyTorch/Triton-XPU pair used by the target vLLM branch.

Debug toggles worth testing only inside this matrix:

- `NEOReadDebugKeys=1 RenderCompressedBuffersEnabled=0` for the compression
  path implicated in compute-runtime issue 921;
- `NEOReadDebugKeys=1 ForceZeDeviceCanAccessPerReturnValue=0` as a
  host-staged fallback for peer-access validation issues;
- `SYCL_UR_USE_LEVEL_ZERO_V2=0`, `SYCL_PI_LEVEL_ZERO_USM_RESIDENT=0`,
  `CCL_ENABLE_SYCL_KERNELS=0`, `CCL_ALLREDUCE=direct`, and
  `ONEAPI_DEVICE_SELECTOR=level_zero:0,1` only as a reproduced workaround
  lane from `llm-scaler` issue 463.

Do not do broad flag sweeps. Each toggle above has a narrow source-backed
failure mode and should be tested against low-level correctness first.

## P2P and Topology

`compute-runtime` issue 935 is an important warning. A user forced a consumer
Intel host bridge into the Linux P2PDMA whitelist, Level Zero reported success,
and the destination checksum still failed every time. Host-staged copy passed.
That makes blind P2P enablement unsafe as a performance strategy.

Actionable implications:

- Run a checksum P2P matrix before any TP4 benchmark is trusted.
- Record whether cards share a root port, share a PCIe switch, or sit behind
  separate consumer root ports.
- Test host-staged fallback even if it costs bandwidth. Correct, slower
  collectives are a better baseline than silent P2P corruption.
- If a hardware move is possible later, compare consumer Intel, AMD Zen,
  Xeon/whitelisted Intel, and shared-switch topologies. Linux P2PDMA policy
  is materially different across those host classes.

## Triton-XPU Porting Lane

### MoE Grouped GEMM

Intel Triton backend issue 6389 says vLLM MoE grouped GEMM performance depends
heavily on token routing distribution and tile config. The most important
technical point is that CUDA-style random row/gather loading of expert inputs
does not map cleanly to Xe2/Xe3P block IO. The SYCL-TLA path is faster for
several Qwen3-style shapes because it pre-groups into dense layouts.

High-value porting checklist:

- capture real Qwen3.6 route histograms from decode and small-batch prefill;
- run grouped-GEMM microbenchmarks against those histograms, not uniform
  synthetic experts;
- test Triton-XPU after PR 6974, because runtime row-stride support enables
  2D block loads for grouped GEMM cases that previously fell back to scalar
  gathers;
- compare against the SYCL-TLA provider as an oracle;
- if adding a local kernel, prefer a dense/pre-grouped expert layout over a
  direct CUDA gather port;
- use tensor descriptors only where the last dimension is dense and stride
  constraints fit. Tensor-descriptor migration PRs also call out cases such as
  GDN `beta`/`g` rank-1 tensors where pointer paths can be the right answer.

### Attention and FP8 KV

Several Triton-XPU PRs are narrow enough to bake off independently:

- PR 7192: vLLM unified attention `BLOCK_M` floor to 32, with reported BMG
  geomean gains for bf16 and fp8.
- PR 7193: reassociate `score_scale` into Q so LICM can hoist invariant work,
  with reported vLLM unified-attention gains.
- PR 7029: replace FP8E4M3FN-to-FP16 table lookup with a multiply-based
  conversion, reducing vLLM unified-attention latency in prefill/chunked/mixed
  and decode cases on PVC without BMG regression.
- PR 7040: analogous FP8E4M3FN-to-BF16 conversion, useful for FP8 KV cache to
  BF16 dot paths.

These are better first bakeoffs than local attention invention because they
are small, measured, and near vLLM's existing Triton path.

### Compiler and Tensor-Descriptor Follow-Ups

Track, but do not immediately depend on:

- runtime-base tensor-descriptor GEMM work;
- 3D tensor descriptor correctness/performance caveats;
- DPAS accumulator and reassociation compiler work;
- XPU Triton test enablement in upstream vLLM for block int8/fp8, MoE,
  quantization, attention, and sampling kernels;
- Triton-XPU startup/device-init fixes, because broken init can look like a
  vLLM worker or multi-GPU failure.

## llm-scaler Issue Matrix

The `llm-scaler` issue tracker is useful because it contains B70-specific
vLLM failure signatures and stack workarounds:

- Issue 486: dual B70 TP=2 fails around `zeMemOpenIpcHandle`; single-GPU
  sym_int4 works. Treat as a Level Zero/oneCCL IPC reproduction source.
- Issue 463: oneAPI 2025.3 Level Zero V2 multi-device context failures; reports
  a working rebuilt image using compute-runtime `26.22.38646.4`, GMM `22.10.0`,
  and IGC `2.36.3`, plus workaround environment variables.
- Issue 489: PP=2 B70+B580 crash/hang with `UR_RESULT_ERROR_DEVICE_LOST` or
  worker communication timeouts after an initial request.
- Issue 407: older sym_int4 Qwen3.6-35B-A3B GDN issue resolved in a later
  `llm-scaler-vllm` image; useful for GDN max-vthread and image-version clues.
- Issue 439: FP8 KV and custom ESIMD MoE dtype gaps; `page_attn_decode`
  rejected FP8 KV in that image.
- Issue 479: GPTQ INT4 MoE hits `UR_RESULT_ERROR_OUT_OF_RESOURCES`; dense INT4
  works, and later comments point to future GPTQ/MTP/vLLM 0.22 work. Treat
  GPTQ claims as leads only until model, quantization, TP, workload, and
  correctness identity match.

## Adjacent Engine Patterns

llama.cpp SYCL is not a vLLM drop-in, but it is a valuable B70 topology and
collectives lab.

Useful patterns:

- PR 24152: backend-specific SYCL allreduce for tensor split. The design uses
  a small-tensor direct path and a large-tensor BF16-compressed cross-device
  path to cut PCIe bytes. It reports large gains on dual B70 for some tensor
  split workloads, with mixed results on B60/B580 and MoE. The size-class
  design is the reusable idea.
- PR 24476: SYCL dev2dev memcpy via SYCL API plus host-staged fallback because
  Level Zero direct copies could produce abnormal output in multi-GPU cases.
  This lines up with compute-runtime topology concerns.
- PR 17374: Vulkan Xe2 subgroup/block-size experiments. Not directly usable,
  but a reminder that Xe2 subgroup shape can move prompt-processing speed by
  large factors and can also trigger correctness/device-loss failures.
- PR 24785: Qwen3.6 Gated DeltaNet recurrent state shrink/expand for prompt
  cache. This is ROCm-oriented but algorithmically relevant to GDN state
  lifecycle and agent-turn prompt caching.
- PR 24340: MTP chaining for Step3.5/3.7. Useful for hidden-state and per-head
  MTP state mechanics, not as a B70 kernel source.

## Next Source Targets

Mine these next only if the stack and Triton leads above leave open questions:

- `TSUMUGI-XE/b70-dual-tp2`, especially `repro/b70_p2p_copy_probe.cpp`, for a
  small B70 P2P checksum harness.
- llama.cpp PR 24152 implementation files, for the BF16-compressed allreduce
  thresholding and buffer lifecycle.
- oneCCL and torchcomms PRs around XPU/XCCL to see whether vLLM PR 46210 can
  become a safe opt-in communicator path.
- Linux `pci_p2pdma` and xe driver commits around peer access and BMG
  compression, only where they map to a reproduced B70 issue.
- SYCL-TLA provider code used by Triton-XPU benchmarks, to see whether it can
  serve as an oracle for MoE grouped GEMM and attention microbenchmarks.

## Source Links

- https://github.com/intel/llm-scaler/issues/486
- https://github.com/intel/llm-scaler/issues/463
- https://github.com/intel/llm-scaler/issues/489
- https://github.com/intel/llm-scaler/issues/407
- https://github.com/intel/llm-scaler/issues/439
- https://github.com/intel/llm-scaler/issues/479
- https://github.com/intel/compute-runtime/issues/921
- https://github.com/intel/compute-runtime/issues/916
- https://github.com/intel/compute-runtime/issues/935
- https://github.com/intel/compute-runtime/issues/922
- https://github.com/intel/compute-runtime/pull/930
- https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
- https://github.com/intel/intel-xpu-backend-for-triton/pull/6974
- https://github.com/intel/intel-xpu-backend-for-triton/pull/7192
- https://github.com/intel/intel-xpu-backend-for-triton/pull/7193
- https://github.com/intel/intel-xpu-backend-for-triton/pull/7029
- https://github.com/intel/intel-xpu-backend-for-triton/pull/7040
- https://github.com/ggml-org/llama.cpp/pull/24152
- https://github.com/ggml-org/llama.cpp/pull/24476
- https://github.com/ggml-org/llama.cpp/pull/17374
- https://github.com/ggml-org/llama.cpp/pull/24785
- https://github.com/ggml-org/llama.cpp/pull/24340
- https://github.com/TSUMUGI-XE/b70-dual-tp2
