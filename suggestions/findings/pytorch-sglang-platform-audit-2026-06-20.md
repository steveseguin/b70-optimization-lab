# PyTorch, SGLang, and Platform Source Audit

Created: 2026-06-20

Scope: source mining for Qwen3.6-35B-A3B / Qwen 35B on 4x Intel Arc Pro B70,
focused on platform and adjacent-engine leads that can explain failures or
identify high-value work before implementation.

## Executive Read

- PyTorch XPU is now a first-order B70 source. Current issue reports include
  B70 `get_device_properties` segfaults, `mem_get_info` inaccuracies, fatal
  OOM/device-loss behavior, and Level Zero loader/driver ABI mismatches. These
  can invalidate vLLM memory profiling and worker startup before model kernels
  matter.
- XCCL/DeviceMesh is a likely blocker for future EP/HSDP/FSDP or more complex
  multi-dimensional layouts. Plain TP may avoid it, but any expert-parallel or
  sharded plan should probe `dist.split_group`/DeviceMesh support first.
- SGLang is not a drop-in answer for this B70/vLLM lane, but its open XPU PRs
  are high-value design sources: XPU graph capture, fused-MoE Triton tuning,
  disaggregated serving staging buffers, card-sharded CI launchers, and SYCL
  JIT/AOT kernel scaffolding.
- vLLM-Omni exposes Intel's broader XPU feature roadmap: XPU Graph, torch
  compile, sleep mode, prefix cache, FP8 KV cache, disaggregated serving,
  sequence parallelism, HSDP/FSDP, and EPLB. It also shows the risk: enabling
  XPU compile can enter code paths that still assume CUDA graphs.
- Intel LLVM and Unified Runtime reports show Battlemage correctness hazards
  beneath vLLM: ESIMD DPAS kernels can pass standalone tests but produce wrong
  answers inside a large SYCL project, Level Zero V2 adapter tests still fail
  on BMG, and BMG USM/memops tests hit sporadic device-loss or out-of-resource
  errors.

## PyTorch XPU Sources

### B70 device-property segfaults and ABI matching

Source:

- https://github.com/pytorch/pytorch/issues/179891
- https://github.com/pytorch/pytorch/issues/179030

Signal:

- `torch.xpu.is_available()`, `torch.xpu.device_count()`, and sometimes
  `torch.xpu.mem_get_info()` can work while `torch.xpu.get_device_name()` or
  `torch.xpu.get_device_properties()` segfaults on Intel Arc Pro B70.
- A later report on B70 said Level Zero init succeeded but the first compute
  kernel, such as `torch.tensor([1.0]).to("xpu:0")`, segfaulted. llama.cpp
  reportedly worked on the same host, pointing at a PyTorch/driver/ops stack
  interaction rather than a totally broken GPU.
- Maintainer comments point to driver-side and ABI issues. One specific
  warning is that `libze1` and `libze-intel-gpu1` must be upgraded together
  because newer driver DDI entries can be incompatible with an older loader.

Why it matters for Qwen/B70:

- vLLM worker startup, device property queries, memory profiling, and kernel
  dispatch may fail before any model-specific optimization is reached.
- A stack that passes `is_available()` is not sufficient evidence that it is
  valid for vLLM.

What to extract:

- Add a platform canary that runs these probes before vLLM endpoint tests:
  `torch.xpu.is_available()`, `torch.xpu.device_count()`,
  `torch.xpu.get_device_name(i)`, `torch.xpu.get_device_properties(i)`,
  `torch.xpu.mem_get_info(i)`, and a small `tensor.to("xpu:i")` compute test.
- Record `libze1`, `libze-intel-gpu1`, compute-runtime, IGC, GMM, oneAPI,
  PyTorch, Triton-XPU, kernel, and `torch.version.xpu` together. Treat loader
  and driver package skew as a real failure mode.

### Fatal OOM/device-loss instead of recoverable `OutOfMemoryError`

Source:

- https://github.com/pytorch/pytorch/issues/177714

Signal:

- PyTorch XPU can report fatal `UR_RESULT_ERROR_DEVICE_LOST`,
  `UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY`, or
  `UR_RESULT_ERROR_OUT_OF_RESOURCES` instead of recoverable
  `torch.OutOfMemoryError`.
- A reported workaround was `torch.xpu.set_per_process_memory_fraction(1.0)`.
  Maintainer comments describe a driver-side fix in a newer lane for at least
  some Battlemage cards, while B50-like behavior remained unresolved in later
  comments.

Why it matters for Qwen/B70:

- vLLM memory profiling, KV cache sizing, warmup, and graph capture can
  intentionally probe memory limits. If the backend turns those probes into
  device-loss events, a speed experiment can look like a model or kernel bug
  when the underlying issue is recoverability.

What to extract:

- Add a controlled OOM/recoverability test to the stack gate. It should verify
  that a too-large allocation fails cleanly and that the next small XPU tensor
  operation still succeeds.
- Compare behavior with and without any memory-fraction workaround only in an
  isolated platform matrix. Do not mix it into Qwen benchmark identity without
  recording it.

### Inaccurate `mem_get_info`

Source:

- https://github.com/pytorch/pytorch/issues/161381

Signal:

- A BMG issue reports that `torch.xpu.mem_get_info()` returned unchanged free
  memory before and after a 1 GB allocation.

Why it matters for Qwen/B70:

- vLLM depends heavily on memory accounting. If PyTorch's free-memory view is
  stale or wrong, KV cache sizing and batch/concurrency decisions can be wrong.

What to extract:

- Cross-check `torch.xpu.mem_get_info()`, `torch.xpu.memory_allocated()`, and
  `xpu-smi` around a known allocation in the stack gate.
- Store the result with the runtime inventory before interpreting any memory
  utilization or concurrency result.

### XCCL `supportsSplitting` and DeviceMesh failures

Source:

- https://github.com/pytorch/pytorch/issues/186548

Signal:

- `ProcessGroupXCCL` does not override `Backend::supportsSplitting()`, so
  `dist.split_group`, nested DeviceMesh, and layouts that depend on process
  group splitting can fail before forward execution.
- The issue proposes a real `split()` implementation or fallback behavior and
  links a minimal repro in a TorchTitan-oriented setup.

Why it matters for Qwen/B70:

- Plain TP may not hit this path. Expert parallelism, FSDP/HSDP, nested meshes,
  and sparse expert layouts likely can.
- If we explore EP or hybrid TP/PP/DP layouts for 4x B70, this is a platform
  gate, not a model-kernel issue.

What to extract:

- Add a minimal DeviceMesh/XCCL split probe before any EP/HSDP/FSDP experiment.
- If it fails, keep the failure in the platform lane and avoid interpreting it
  as a Qwen MoE layout result.

### Multiprocessing tensor reduction and Triton package friction

Sources:

- https://github.com/pytorch/pytorch/issues/170636
- https://github.com/pytorch/pytorch/issues/186350

Signal:

- XPU multiprocessing tensor reduction is incomplete in at least one PyTorch
  issue, causing CPU sharing fallbacks to fail for XPU tensors.
- Packaging friction around `triton-xpu` versus `triton` can break downstream
  projects that assume one package name or dependency shape.

Why it matters for Qwen/B70:

- vLLM, tuning harnesses, TorchInductor, Ray workers, or autotuning jobs can
  cross multiprocessing boundaries even when the model path looks simple.
- A broken Triton package environment can make a kernel bakeoff fail before
  the kernel is tested.

What to extract:

- Include a small XPU tensor multiprocessing transfer check in any autotuning
  or Ray-based harness.
- Record Triton package identity (`triton`, `triton-xpu`, version, wheel
  source) next to vLLM and PyTorch versions.

## SGLang XPU Sources

### Fused MoE Triton tuning on XPU

Source:

- https://github.com/sgl-project/sglang/pull/28723

Signal:

- The PR makes fused-MoE Triton tuning more device-agnostic for XPU, CUDA, and
  HIP.
- It uses device abstraction for synchronize/events/graphs, selects XPUGraph
  when appropriate, places L2 flush tensors on the active device, and uses a
  torch-native top-k routing path on XPU where fused CUDA-only top-k is absent.
- Ray needs explicit `ray.init(num_gpus=get_device_count())` because bare
  `ray.init()` may not detect Intel XPU cards as GPU resources.
- Workers are pinned from Ray GPU IDs; Battlemage B580 configuration was added
  under Triton 3.7.0 configs.

Why it matters for Qwen/B70:

- This is a practical source for a B70 route-aware MoE tuning harness. It is
  more immediately useful than porting CUDA grouped-GEMM assumptions blindly.

What to extract:

- Adapt the harness concepts for local Qwen route histograms: device module
  abstraction, explicit Ray GPU counts, XPUGraph timing, XPU-safe top-k
  fallback, and BMG/B70 config files.
- Keep this as a microbench/tuning source first, not an endpoint change.

### XPU graph runner

Source:

- https://github.com/sgl-project/sglang/pull/25853

Signal:

- Adds an `XPUGraphRunner` using `torch.xpu.XPUGraph`,
  `torch.xpu.graph(xpu_graph=...)`, XPU profiler activity, fixed metadata
  buffers, cache seqlens, and page-table handling.
- The PR explicitly guards out several features: TP/DP/PP greater than 1,
  LoRA, speculative inference, two-batch overlap, MLP TP gather/sync, and
  encoder-decoder.
- Review feedback asks for XPU-native CLI naming and clarity around attention
  backend support.

Why it matters for Qwen/B70:

- It is a good pattern source for graph metadata ownership and capture API use.
  It is not sufficient for our target because the guarded-out features overlap
  the interesting Qwen/B70 lanes: TP and speculation.

What to extract:

- Mine buffer ownership, metadata fixup, and graph capture scaffolding.
- Treat every guard as a checklist item for why direct adoption will not solve
  TP4 or DFlash/MTP by itself.

### XPU disaggregated serving support

Source:

- https://github.com/sgl-project/sglang/pull/26501

Signal:

- Adds XPU handling for disaggregated serving staging buffers, streams, events,
  and tensor transport.
- Mentions NIXL/UCX/ZE transport and current XPU defaults around allocator and
  staging behavior. XPU IPC remains a future item in the PR context.

Why it matters for Qwen/B70:

- If TP4 memory pressure or prefill/decode imbalance remains severe, this is a
  source for staging-buffer and transport design. It is lower priority than
  local TP/graph/MoE work, but a real adjacent path.

What to extract:

- Track XPU event/stream abstractions, staging-buffer lifetimes, and ZE
  transport test shape.
- Do not treat it as a near-term endpoint speed fix unless we choose a
  disaggregated architecture deliberately.

### XPU SYCL JIT kernel support

Source:

- https://github.com/sgl-project/sglang/pull/28716

Signal:

- Adds SYCL JIT kernel support with BMG/Battlemage AOT flags and cache
  handling.
- Implements examples such as RMSNorm, QKNorm, RoPE, RoPE plus KV store, and
  timestep embedding.

Why it matters for Qwen/B70:

- This is a source for building maintainable XPU kernel scaffolding outside
  pure Triton, especially for small fused ops around attention and norm paths.

What to extract:

- Reuse the JIT/AOT architecture, cache layout, and BMG target flags as a
  pattern if local SYCL kernels become necessary.
- Require endpoint correctness canaries, because Intel LLVM reports below show
  standalone SYCL success is not enough.

### Card-sharded XPU CI and launch harness

Source:

- https://github.com/sgl-project/sglang/pull/28329

Signal:

- Adds an XPU card-level launcher that detects `torch.xpu.device_count()` and
  runs one subprocess per card pinned by `ZE_AFFINITY_MASK`.
- Isolates Hugging Face, Triton, and TorchInductor caches and master ports.
- Uses a conservative default concurrency ramp for XPU.

Why it matters for Qwen/B70:

- This is a useful harness pattern for B70 microbench sweeps and per-card
  diagnostics, even if we keep vLLM as the serving stack.

What to extract:

- Per-card `ZE_AFFINITY_MASK` process isolation, cache isolation, and
  concurrency-ramp structure.
- Use it for low-level bakeoffs where vLLM's full distributed launcher would
  hide which card or process failed.

### Additional SGLang XPU pattern sources

Sources:

- https://github.com/sgl-project/sglang/pull/26679
- https://github.com/sgl-project/sglang/pull/23534
- https://github.com/sgl-project/sglang/pull/28646
- https://github.com/sgl-project/sglang/pull/25936
- https://github.com/sgl-project/sglang/pull/27544

Signals:

- FP8 quantization fallbacks on XPU, tested in a multi-XPU TP=4 setting for a
  different model.
- LMCache/radix cache XPU support by replacing hardcoded CUDA streams with
  device helpers.
- BMG Triton MLA memory-safety changes such as limiting `max_kv_splits`.
- DeepSeek V4 XPU paths and env/TP examples.
- XPU fallback handling for CUDA-assumed Mamba dependencies.

Why it matters for Qwen/B70:

- These are lower-direct-value sources, but they expose the same repeated
  pattern: replace CUDA hard-codes with device helpers, add XPU fallbacks first,
  then only optimize the hot path once correctness and dispatch are stable.

## vLLM-Omni Sources

### XPU 2026 Q2 roadmap

Source:

- https://github.com/vllm-project/vllm-omni/issues/2570

Signal:

- Intel XPU roadmap items include Sequence Parallel, HSDP/FSDP, torch compile,
  XPU Graph, sleep mode, LoRA, disaggregated serving, EPLB, Prefix Cache, FP8
  KV cache, and sparse attention.
- The roadmap excludes models that cannot fit in 8x B70 or require CUDA
  hard-coded packages.

Why it matters for Qwen/B70:

- This gives a useful map of where Intel/vLLM-Omni expects XPU platform work
  to land. Several items overlap our likely needs: graph, prefix cache, FP8 KV,
  disaggregation, EPLB, and distributed layouts.

What to extract:

- Use roadmap items as a source-mining checklist for vLLM core and
  vLLM-XPU-kernels parity, not as proof any feature is production-ready for
  Qwen/B70.

### XPU torch inductor enablement

Source:

- https://github.com/vllm-project/vllm-omni/pull/3113

Signal:

- Enables `supports_torch_inductor=True` for an XPU path and reports a modest
  end-to-end improvement on a non-Qwen workload.
- Review discussion flags a CUDA-graph assumption risk inside compile-related
  code when graph use is enabled.

Why it matters for Qwen/B70:

- XPU compile can be useful, but enabling it globally can route through CUDA
  graph assumptions. That is a direct warning for any local attempt to turn on
  TorchInductor or compile flags in vLLM-XPU.

What to extract:

- Audit graph/compile paths for `torch.cuda` assumptions before enabling XPU
  compile in a serving lane.
- Treat compile as an isolated bakeoff with canaries and exact benchmark
  identity, not a background flag.

### Sleep mode and memory telemetry

Source:

- https://github.com/vllm-project/vllm-omni/issues/2545

Signal:

- XPU/NPU sleep-mode follow-up work includes VRAM audit telemetry parity once
  newer PyTorch is stable.

Why it matters for Qwen/B70:

- Sleep/offload is not a primary speed path, but memory accounting and
  telemetry parity overlap the `mem_get_info` and vLLM memory-profile risks
  above.

## Intel LLVM and Unified Runtime Sources

### ESIMD DPAS correctness inside large SYCL projects

Source:

- https://github.com/intel/llvm/issues/21741

Signal:

- On Battlemage/B70, an ESIMD DPAS flash-attention kernel can produce correct
  results in a standalone or small shared-library test but wrong results when
  compiled as part of a larger SYCL project.
- The report says work-item 0 can be correct while later work-items are wrong.
  It also notes that the `joint_matrix` path did not expose expected matrix
  hardware, forcing an ESIMD workaround.

Why it matters for Qwen/B70:

- Any local ESIMD/SYCL attention or MoE kernel must pass endpoint-style
  canaries inside the real build. A standalone microbench is necessary but not
  sufficient.

What to extract:

- Add an "integrated build canary" rule for any SYCL/ESIMD kernel. The kernel
  must be validated inside the real vLLM/vllm-xpu-kernels shared-library
  context, not only in a toy binary.

### Level Zero V2 and BMG runtime failures

Sources:

- https://github.com/intel/llvm/issues/22025
- https://github.com/intel/llvm/issues/21873
- https://github.com/intel/llvm/issues/17847

Signal:

- Level Zero V2 conformance tests have reported BMG failures around native
  handles and selectors.
- BMG USM/memops and matrix tests can fail sporadically with
  `UR_RESULT_ERROR_OUT_OF_RESOURCES`, `UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY`,
  or `UR_RESULT_ERROR_DEVICE_LOST`.
- Graph/native-command tests have timed out in Level Zero V2 adapter paths.

Why it matters for Qwen/B70:

- These are the same error classes showing up in higher-level PyTorch, vLLM,
  and llm-scaler reports. Treat Level Zero V2 and graph/native-command choices
  as explicit stack variables.

What to extract:

- Record L0 V1/V2 adapter mode and any UR/L0 workaround flags in every stack
  bakeoff.
- Do not combine Level Zero V2 changes with model/kernel changes in the same
  experiment.

### BF16 feature detection and builtins

Sources:

- https://github.com/oneapi-src/unified-runtime/issues/2669
- https://github.com/intel/llvm/issues/22054

Signal:

- Unified Runtime reports that the bfloat16 conversion extension could not be
  queried on DG2/BMG/Lunar Lake even where native BF16 conversions should
  exist.
- Intel LLVM reports BF16 builtin failures across several GPU generations,
  including BMG, in at least one driver lane.

Why it matters for Qwen/B70:

- Incorrect BF16 feature detection can push kernels into slow fallback paths or
  unsafe assumptions. Qwen/B70 uses BF16-adjacent attention, norm, and
  quantization paths even when weights are quantized.

What to extract:

- Include BF16 feature/probe output in the stack inventory.
- Watch for feature-detection-based fallbacks when comparing Triton-XPU,
  SYCL, and torch-native paths.

## High-Value Next Actions

1. Add a PyTorch/XPU stack canary before vLLM endpoint tests:
   `is_available`, `device_count`, `get_device_name`, `get_device_properties`,
   `mem_get_info` before/after allocation, `memory_allocated`, a small
   `tensor.to("xpu")` compute test, controlled OOM recoverability, and
   `xpu-smi` cross-check.
2. Add an XCCL/DeviceMesh split probe before any EP/HSDP/FSDP or nested-mesh
   layout experiment. If it fails, keep the result in the platform lane.
3. Mine SGLang PR 28723 for a route-aware B70 MoE tuning harness: device
   module abstraction, explicit Ray XPU resource declaration, XPU top-k
   fallback, XPUGraph timing, and BMG config format.
4. Mine SGLang PR 25853 for XPU graph metadata and buffer-ownership patterns,
   but treat its TP/speculation guards as unresolved gaps for our target.
5. Treat every new SYCL/ESIMD kernel as requiring two validations: standalone
   microbench and integrated vLLM/vllm-xpu-kernels endpoint canary.
6. Add BMG runtime feature detection to the stack inventory: BF16 conversion
   extension, matrix/DPAS availability, ESIMD path, L0 adapter mode, and
   Triton package identity.

## Source Links

- PyTorch B70 device-property segfault:
  https://github.com/pytorch/pytorch/issues/179891
- PyTorch newer-driver XPU segfault:
  https://github.com/pytorch/pytorch/issues/179030
- PyTorch fatal XPU OOM/device-loss:
  https://github.com/pytorch/pytorch/issues/177714
- PyTorch incorrect `mem_get_info`:
  https://github.com/pytorch/pytorch/issues/161381
- PyTorch XCCL `supportsSplitting`:
  https://github.com/pytorch/pytorch/issues/186548
- PyTorch XPU multiprocessing reduction:
  https://github.com/pytorch/pytorch/issues/170636
- PyTorch Triton-XPU packaging friction:
  https://github.com/pytorch/pytorch/issues/186350
- SGLang fused MoE Triton tuning on XPU:
  https://github.com/sgl-project/sglang/pull/28723
- SGLang XPUGraph runner:
  https://github.com/sgl-project/sglang/pull/25853
- SGLang XPU disaggregation:
  https://github.com/sgl-project/sglang/pull/26501
- SGLang XPU JIT kernel support:
  https://github.com/sgl-project/sglang/pull/28716
- SGLang card-sharded XPU launch:
  https://github.com/sgl-project/sglang/pull/28329
- SGLang FP8 XPU fallback:
  https://github.com/sgl-project/sglang/pull/26679
- SGLang LMCache/radix XPU support:
  https://github.com/sgl-project/sglang/pull/23534
- SGLang BMG MLA memory safety:
  https://github.com/sgl-project/sglang/pull/28646
- SGLang DeepSeek V4 XPU:
  https://github.com/sgl-project/sglang/pull/25936
- SGLang Mamba XPU fallback:
  https://github.com/sgl-project/sglang/pull/27544
- vLLM-Omni XPU roadmap:
  https://github.com/vllm-project/vllm-omni/issues/2570
- vLLM-Omni XPU torch inductor:
  https://github.com/vllm-project/vllm-omni/pull/3113
- vLLM-Omni sleep-mode follow-up:
  https://github.com/vllm-project/vllm-omni/issues/2545
- Intel LLVM ESIMD DPAS BMG correctness:
  https://github.com/intel/llvm/issues/21741
- Intel LLVM L0v2 BMG failures:
  https://github.com/intel/llvm/issues/22025
- Intel LLVM BMG USM/memops failures:
  https://github.com/intel/llvm/issues/21873
- Intel LLVM L0v2 graph/native command timeout:
  https://github.com/intel/llvm/issues/17847
- Intel LLVM BF16 builtin failures:
  https://github.com/intel/llvm/issues/22054
- Unified Runtime BF16 conversion query:
  https://github.com/oneapi-src/unified-runtime/issues/2669
