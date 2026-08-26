# Qwen3.8 Flash-Next XPU overlay and preload gates

Date: 2026-08-26

## Outcome

The checkpoint and TP4 model topology are ready for a first real load, but the
load remains fail-closed until a coherent MoE-enabled XPU extension has been
built and tested. This is a runtime-package gate, not a model-fit failure.

The older Qwen matrix and DeepSeek lane remain paused. None of their launch
identities, binaries, patches, or promoted speeds were modified.

## vLLM overlay

The local vLLM `main` overlay is six commits above upstream base
`76cfe1cd88`:

- `3fd193010b`: pinned Qwen4Exp model implementation from PR 53896;
- `a6d6d48a1b`: pinned PLE offload implementation from PR 53899;
- `25482e7979`: eager, blocking shared-host PLE transport for XPU;
- `a1fa0b1bbf`: Qwen4Exp XPU registry/model dispatch;
- `b1b3a68da0`: XPU HyperConnection reference fallbacks;
- `48a350bcf6`: QSA XPU kernel enablement.

CUDA and ROCm paths were not replaced. The XPU path is correctness-first and
keeps graph disabled for initial bring-up.

Targeted validation passed:

- 22 PLE transport/worker tests passed, with one CUDA-only skip;
- 46 Qwen/config tests passed, with four hardware skips;
- real B70 HyperConnection microtests were exact for all six operations;
- real B70 QSA compressed-index, sparse-paged-attention, MQA-score, top-k,
  group-compression, and cache-store tests passed;
- QSA sparse attention had maximum absolute error `0.0078125`, below the
  upstream `0.02` tolerance;
- PLE FP8-to-BF16 dequantization with the checkpoint's global scale was exact.

## Correct TP4 memory accounting

`tools/meta_tp_construct.py` uses the real checkpoint configuration,
`initialize_model`, the real FP8 quantization mapper, BF16 default dtype, and
four distributed ranks while allocating tensors on `meta`.

The earlier direct-constructor failure was not a checkpoint defect. Directly
calling the model class bypassed vLLM's quantization name mapper and produced a
false shared-expert block-divisibility error. The production initialization
path passes.

The earlier 33.81-GiB estimate was also false: the dry constructor had not
entered vLLM's BF16 default-dtype context, so ordinary parameters became FP32.
The corrected figures are:

| Shape | Per-rank parameters | FP8 bytes | BF16 bytes | FP32 bytes |
| --- | ---: | ---: | ---: | ---: |
| TP4 | 31.631803 GiB | 30,198,988,800 | 3,647,434,592 | 117,966,528 |
| TP4 + EP4 | 31.528806 GiB | 30,198,988,800 | 3,647,434,592 | 7,374,528 |

EP4 does not materially reduce bytes per rank, but it preserves the native
checkpoint expert block layout: 128 local experts with intermediate dimension
1280, instead of refining the non-EP layout into 512 experts by 320. EP4 is
therefore the preferred first correctness load.

Each B70 exposes 31.890625 GiB. The first load will use a 12-GiB/rank selective
UVA allowance for only `ple_embedding.ngram_embedding.weight`, plus
`gpu_memory_utilization=0.92`. The allowance covers the approximately
11.92-GiB TP-local PLE shard while leaving all other weights resident; it is
not general-weight offload. Real B70 microtests proved both BF16 matrix
multiplication and FP8 `scaled_mm` can consume pinned host-USM views exactly.
Prefetch offload is not allowed yet because the current implementation
constructs CUDA streams and events directly.

## Kernel-package blocker found before load

The live `_xpu_C.abi3.so` was built with MoE disabled. It therefore lacked the
grouped-GEMM operator needed by Qwen4Exp. It also lacked the `is_xe2_arch` and
`is_xe3_arch` Python operators expected by current vLLM.

This was traced to local merge damage in the maintained kernel stack:

- upstream commit `2e2d56e` added the architecture probes, but a later local
  packed-verifier commit replaced the affected files and dropped those hunks;
- the local CMake list retained `csrc/moe/fused_moe_prologue.cpp`, while the
  file itself was dropped during a later upstream merge even though the
  preserved Qwen layerlet still calls it.

Both source pieces were restored on kernel `main` as focused commits. An
isolated build uses oneAPI 2025.3 to preserve the runtime's `libsycl.so.8` ABI,
MoE and GDN enabled, B70-only AOT, one compile job, and external-drive build
storage. No live binary will be replaced until import, operator-registration,
architecture, grouped-GEMM, GDN, and MoE numerical gates pass.

### Superseding native-build decision

A deeper interface audit stopped that grouped-GEMM build before its expensive
compile. The maintained tree currently mixes the old local 11-argument grouped
GEMM Python/binding ABI with the newer 10-argument C++ interface. More
importantly, a later local performance overlay displaced upstream's explicit
block-FP8 128x128 scale path. Merely making the mixed source compile could
therefore silently execute this checkpoint with the wrong scale semantics.

The first-load path now preserves the accepted existing `_xpu_C`, grouped-GEMM,
GDN, FA2, and optimization binaries and explicitly selects
`--moe-backend triton`. Only `_C` and `_moe_C` are rebuilt from current source
to update their stale operator schemas. That narrow build disables SYCL-TLA,
FA2, GDN, MQA, `_xpu_C`, and the allocator, so it cannot overwrite or dilute
the accepted performance stack. A resident plus UVA block-FP8 Triton
numerical gate is mandatory before the full checkpoint load.

Native grouped MoE is now a later optimization task: reconcile the ABI,
reapply the upstream block-FP8 scale path onto the local INT8/INT4/MXFP4
optimizations, build in isolation, and prove numerical parity before promotion.

Structured evidence is in `data/20260826-preload-gates.json`.

## Frozen first-load identity

After the native package gate passes:

- local checkpoint only, pinned revision and tree hash;
- language-only;
- TP4 + EP4, `allgather_reducescatter`;
- target-only / MTP0;
- eager, no graph, no compilation, no prefix cache;
- 512-token model length, one sequence, 512 batched tokens;
- dedicated PLE CPU-process transport disabled: `VLLM_PLE_CPU_OFFLOAD` is
  unset;
- selective PLE UVA only: `--offload-backend uva`, `--cpu-offload-gb 12`, and
  `--cpu-offload-params ple_embedding.ngram_embedding.weight`;
- Triton MoE backend (native grouped MoE is not correctness-qualified);
- GPU memory utilization 0.92;
- external cache, temp, and log roots;
- exact-token and semantic canaries before any performance claim.

Context, MTP, graph, and speed expansion remain downstream of that exact
correctness gate.

## First real TP4 load: bounded constructor failure and repair

Attempt 4 passed every frozen launcher gate, including four-rank XCCL barrier
and all-reduce, and brought up all four TP4/EP4 workers. It selected Triton for
both GDN decode and block-FP8 MoE. It then stopped in the PLE constructor before
checkpoint weight loading; this was not a hang, OOM, collective failure, model
fit failure, or throughput result.

`PleOffloadLayer.get_target_device()` combined the accelerator-aware current
device index with a literal `cuda` device type. The surrounding default-device
context consequently sent ordinary PLE constructor tensors through
`torch.cuda._lazy_init()` on the XPU-only PyTorch build. All four ranks failed
the same way. The full external log is retained at:

```text
/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-512-r1-attempt4/server.log
```

The focused repair is vLLM commit `240899082e`: select the active PyTorch
accelerator's device type while retaining the existing current-device index
and CPU-offload early return. It does not change kernels, quantization,
topology, memory policy, graph mode, or benchmark settings. The worker unit
suite passes `21/21`, covering XPU, CUDA, and CPU-offload selection, and a real
B70 probe proves that the same PLE constructor device context creates ordinary
tensors on `xpu:0`. Patch artifact `vllm/0007` preserves the repair.

Structured attempt evidence is in
`data/20260826-tp4-first-load-attempt4.json`. The next action is an unchanged
attempt 5 with only the source repair and launcher source-head pin advanced.
