# Qwen 35B on 4x B70 Optimization Options

Created: 2026-06-20

Target context: Qwen3.6-35B-A3B / Qwen 35B on 4x Intel Arc Pro B70, currently
using vLLM-XPU and local XPU kernel work. No implementation is proposed here;
this is a prioritized research-to-implementation menu.

## Ground Rules

- Do not compare benchmark numbers unless the full Qwen run identity matches:
  model path/revision, quantization, TP/PP/concurrency, graph config,
  memory-utilization, XPU graph flags, forced-comm flags, GDN fallback,
  sampler fallbacks, async args, and diagnostic flags.
- Keep graph-none results separate from PIECEWISE forced-comm graph results.
- For speculative decoding, the target verifier owns correctness. Draft output
  is never trusted unless token-identical canaries and quality gates pass.
- Port proven mechanisms first. Avoid new state machinery when upstream has
  already solved the same problem.

## Latest Deep-Dive Additions

The June 20 deeper pass changed the priority order in three ways:

- The local XPU kernel package is behind upstream. Local
  `vllm-xpu-kernels` is `0.1.9.dev27+g28e1f5e`; upstream released `v0.1.10`,
  and vLLM PR 40367 already merged the bump plus a newer UMD baseline.
- The local driver/runtime lane is not the freshest available lane. This host
  has `26.18.38308.1`; the configured PPA offers `26.18.38308.4`, and
  upstream kernel PR 424 is staging `26.22.38646.4` plus newer IGC.
- LocalMaxxing and community B70 repos point to graph replay, B70-specific
  dequant/attention kernels, activation caching, MoE gate/up handoff, and
  collective/topology handling as the recurring high-value areas.
- Upstream `vllm` itself has several fresh XPU/B70 leads that map directly to
  local gaps: per-worker `ZE_AFFINITY_MASK`, a draft torchcomms/XCCL
  communicator, Qwen GDN projection fusion, Mamba SSD tensor-descriptor stores,
  DFlash/mixed-KV support, and XPU Triton test enablement.
- Current runtime and Triton-XPU reports make stack/topology validation a
  prerequisite for TP4 speed work. B70 multi-GPU failures are often Level Zero,
  Unified Runtime, oneCCL/XCCL, or P2P problems before model kernels matter.
- PyTorch XPU, XCCL, and adjacent SGLang/vLLM-Omni work add a new platform
  lesson: validate PyTorch device properties, memory APIs, OOM recovery,
  DeviceMesh splitting, and compile/graph CUDA assumptions before interpreting
  any Qwen TP4 speed result.

The immediate implication: before deeper local kernel invention, do a
controlled upstream-delta bakeoff and cherry-pick review. It is likely cheaper
than rediscovering fixes already landing upstream.

## Priority 0 - Highest-Value Leads

### 0. Bake off upstream XPU kernel/runtime deltas before new local tuning

Why it can help:

- Upstream `vllm-xpu-kernels v0.1.10` landed after the local package and
  includes GDN prefill optimization, fused quantization patterns, FP8/MXFP8
  GEMM consolidation, rotary embedding, memory info, and PyTorch 2.12 work.
- Open upstream PRs map directly to local bottlenecks: reusable MoE
  workspaces, invalid-row MoE guards, graph-padded GDN/DFlash metadata, fused
  qknorm/RoPE/KV insert, stride-aware flash cache writes, and newer UMD/IGC.
- A community fork has a unique GDN cudagraph-padded metadata narrowing commit
  that is not obviously present in the local tree. The full fork audit also
  found older medium-value pattern leads for W4A16 grouped GEMM, fused
  SiLU/block quant, MoE benchmarking, RMSNorm/layernorm, and index hardening.

What is involved:

- Create a clean comparison lane with the same launcher identity, canaries,
  PIECEWISE graph settings, Quark W8A8 model, TP4, and B70 driver inventory.
- Compare local `0.1.9.dev27+g28e1f5e` against upstream `v0.1.10` without
  carrying local dirty changes unless the run cannot start.
- Review/cherry-pick one upstream candidate at a time: PR 392, PR 401,
  PR 422, PR 429, PR 424, and Jason Boukheir's GDN metadata commit.
- Keep runtime changes out of the working lane until a separate stack bakeoff
  proves correctness and speed.

Validation gate:

- Same canaries as the accepted Quark row, then same-identity p512/n512.
- Record vLLM commit, `vllm-xpu-kernels` commit, runtime packages, oneAPI,
  `torch.version.xpu`, graph flags, and launcher log.

Main sources:

- https://github.com/vllm-project/vllm-xpu-kernels/releases/tag/v0.1.10
- https://github.com/vllm-project/vllm/pull/40367
- https://github.com/vllm-project/vllm-xpu-kernels/pull/392
- https://github.com/vllm-project/vllm-xpu-kernels/pull/401
- https://github.com/vllm-project/vllm-xpu-kernels/pull/422
- https://github.com/vllm-project/vllm-xpu-kernels/pull/429
- https://github.com/vllm-project/vllm-xpu-kernels/pull/424
- `/home/steve/llm-optimizations/suggestions/findings/fork-audit-2026-06-20.md`
- https://github.com/jasonboukheir/vllm-xpu-kernels/commit/63c50713578d55a349610797788c7f3da133b2ff

Risk:

- Upstream movement can invalidate local dirty GDN/spec work. This should be a
  branch/container bakeoff, not an in-place upgrade of the current lane.

### 0b. Bake off upstream vLLM XPU control-plane deltas

Why it can help:

- The local XPU worker maps `local_rank` to `xpu:<index>` inside the worker,
  but upstream PR 46226 isolates each worker process before startup with a
  per-worker `ZE_AFFINITY_MASK`. That is a direct fit for B70 TP/PP device
  visibility and memory-profiling instability.
- Local XPU communication always routes through `XpuCommunicator`, which has
  XPU-specific workarounds for compile-time allreduce, uneven allgatherv, and
  gather. Upstream draft PR 46210 adds a torchcomms-backed communicator path.
- B70 issue reports show multi-GPU failures are often in vLLM worker-init,
  ProcessGroupXCCL, `dist.broadcast`, or Level Zero/oneCCL device-loss paths,
  not only in model kernels.

What is involved:

- Port/test PR 46226 on a branch first; do not mix it with kernel changes.
- If dependencies are available, add PR 46210 as an opt-in communicator path
  and run standalone collective sweeps before endpoint tests.
- Compare against the host-stack guidance from the B70 issue thread and the
  chriswagner bare-metal guide: kernel >= 7.1 / NEO >= 26.14 plus triton-xpu
  3.7.0 or equivalent `init_devices` fix.
- Keep this as a controlled bakeoff. The goal is to determine whether worker
  isolation and communicator changes stabilize TP4/PP paths or change
  throughput.

Validation gate:

- Each worker logs only one visible XPU with its own `ZE_AFFINITY_MASK` and
  internal `xpu:0`.
- Standalone XCCL/torchcomms collectives pass for the exact tensor shapes used
  by Qwen TP.
- JSON/color canaries pass before speed is interpreted.
- Same Qwen benchmark identity only: no graph-none versus PIECEWISE mixing.

Main sources:

- `/home/steve/llm-optimizations/suggestions/findings/vllm-upstream-audit-2026-06-20.md`
- https://github.com/vllm-project/vllm/pull/46226
- https://github.com/vllm-project/vllm/pull/46210
- https://github.com/vllm-project/vllm/issues/41663
- https://github.com/vllm-project/vllm/issues/46072
- https://github.com/chriswagner-ai/intel-arc-b70-vllm-multi-gpu

Risk:

- This may improve stability rather than speed. It still matters because an
  unstable TP/PP path prevents meaningful kernel comparisons.

### 0c. Stabilize and fingerprint B70 runtime/topology before TP4 speed work

Why it can help:

- B70 issue reports show TP/PP failures in `zeMemOpenIpcHandle`, Unified
  Runtime multi-device contexts, `UR_RESULT_ERROR_DEVICE_LOST`, XCCL/oneCCL
  collectives, and device-to-device copies. Those failures can make kernel
  benchmarks and vLLM speed comparisons misleading.
- Compute-runtime issue reports point to fixes and regressions around
  multi-device contexts, BMG internal engines, compression, peer access, and
  P2P. Kernel 7.1+ and compute-runtime `26.22.38646.4` plus IGC `2.36.3` are
  concrete candidate lanes to bake off.
- Consumer Intel cross-root-port P2P can be unsupported or silently corrupt if
  forced. TP4 needs a checksum-proven topology, not just a successful startup.

What is involved:

- Build a stack inventory script/runbook: kernel, xe/i915, compute-runtime,
  Level Zero, IGC, GMM, oneAPI, oneCCL, PyTorch XPU, Triton-XPU, vLLM, and
  `vllm-xpu-kernels`.
- Add low-level gates before vLLM endpoint speed: per-worker
  `ZE_AFFINITY_MASK` visibility, multi-device SYCL/UR context allocation,
  XCCL/oneCCL collectives, P2P checksum for every B70 pair, and host-staged
  checksum fallback.
- Bake off the current stack against candidate runtime lanes without mixing in
  model/kernel changes.
- Treat `RenderCompressedBuffersEnabled=0`,
  `ForceZeDeviceCanAccessPerReturnValue=0`, and the `llm-scaler` Level Zero V2
  workaround variables as narrow reproduced lanes, not general tuning flags.

Validation gate:

- Low-level P2P and host-staged copy checksums pass before endpoint throughput
  is interpreted.
- Collectives pass on representative Qwen TP tensor shapes.
- Qwen canaries pass before speed is recorded.
- Same benchmark identity only; stack changes must be recorded next to model,
  graph, quantization, TP/PP, and launch flags.

Main sources:

- `/home/steve/llm-optimizations/suggestions/findings/runtime-triton-collectives-audit-2026-06-20.md`
- https://github.com/intel/compute-runtime/issues/921
- https://github.com/intel/compute-runtime/issues/916
- https://github.com/intel/compute-runtime/issues/935
- https://github.com/intel/llm-scaler/issues/463
- https://github.com/intel/llm-scaler/issues/486
- https://github.com/intel/llm-scaler/issues/489
- https://github.com/TSUMUGI-XE/b70-dual-tp2

Risk:

- This lane may mostly buy correctness and stability. That is still high value
  because invalid or unstable collectives make all later speed work suspect.

### 0d. Bake off Triton-XPU attention, FP8, and grouped-GEMM backend deltas

Why it can help:

- Triton-XPU PR 6974 enables 2D block loads for grouped GEMM cases with
  runtime row strides, which is directly relevant to vLLM MoE.
- PRs 7192 and 7193 report vLLM unified-attention gains on BMG from a
  `BLOCK_M` floor and reassociating `score_scale` into Q.
- PRs 7029 and 7040 simplify FP8E4M3FN conversion paths, which matters for FP8
  KV cache and attention dot paths.
- Intel's grouped-GEMM issue says CUDA-style random expert-row gather is a bad
  fit for Xe2 block IO. Dense/pre-grouped expert layout or SYCL-TLA comparison
  is a better source of ideas than a naive CUDA/Triton port.

What is involved:

- Check whether the active Triton-XPU build includes these PRs; if not, create
  a branch/container bakeoff.
- Run vLLM unified-attention microbenchmarks and Qwen canaries before endpoint
  speed tests.
- Capture real Qwen MoE route histograms and benchmark current grouped GEMM,
  post-PR-6974 Triton-XPU, and SYCL-TLA/oracle paths against those histograms.
- For local MoE work, bias toward pre-grouped dense inputs and tensor
  descriptors only where stride rules fit.

Validation gate:

- Attention and FP8 microbench improvements reproduce without canary drift.
- MoE microbench uses captured route distributions, not uniform synthetic
  loads.
- Endpoint speed is interpreted only under the unchanged Qwen identity.

Main sources:

- https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
- https://github.com/intel/intel-xpu-backend-for-triton/pull/6974
- https://github.com/intel/intel-xpu-backend-for-triton/pull/7192
- https://github.com/intel/intel-xpu-backend-for-triton/pull/7193
- https://github.com/intel/intel-xpu-backend-for-triton/pull/7029
- https://github.com/intel/intel-xpu-backend-for-triton/pull/7040

Risk:

- Triton-XPU deltas can change compiler behavior broadly. Keep this as an
  isolated backend bakeoff before combining it with vLLM or kernel patches.

### 0e. Add PyTorch XPU and XCCL canaries to the B70 stack gate

Why it can help:

- PyTorch XPU issue reports show B70 can pass `is_available()` and
  `device_count()` while `get_device_properties`, `get_device_name`, or first
  compute still segfaults.
- `torch.xpu.mem_get_info()` can be stale or wrong on BMG, and XPU OOM can
  surface as fatal Unified Runtime device-loss instead of recoverable
  `torch.OutOfMemoryError`.
- `ProcessGroupXCCL` missing group-splitting support can block DeviceMesh,
  nested meshes, EP, HSDP, or FSDP before a model forward pass.
- SGLang's XPU PRs show the same recurring control-plane fixes: explicit XPU
  resource declaration, per-card `ZE_AFFINITY_MASK`, device-helper APIs, XPU
  graph metadata ownership, and CUDA-hardcode removal.

What is involved:

- Add a platform canary before endpoint benchmarks: XPU availability, device
  count, device name/properties, `mem_get_info` before/after allocation,
  `memory_allocated`, small `tensor.to("xpu")` compute, `xpu-smi` cross-check,
  and controlled OOM recoverability.
- Record Level Zero loader and driver versions together: `libze1`,
  `libze-intel-gpu1`, compute-runtime, IGC, GMM, oneAPI, PyTorch, Triton-XPU,
  vLLM, and `vllm-xpu-kernels`.
- Add a minimal XCCL/DeviceMesh split probe before EP/HSDP/FSDP or nested-mesh
  experiments.
- Check XPU tensor multiprocessing and Triton package identity before using
  Ray or autotuning harnesses.
- Mine SGLang PR 28723 for a B70 route-aware MoE tuning harness and PR 25853
  for graph metadata patterns, but keep both as source material until their
  TP/speculation gaps are resolved locally.

Validation gate:

- The canary must pass on every B70 visible to the run before Qwen speed is
  interpreted.
- A controlled OOM must leave the device usable for a subsequent small tensor
  operation.
- DeviceMesh split failure is recorded as a platform blocker, not a model
  layout result.
- Any compile or graph flag must be audited for `torch.cuda` assumptions before
  enabling it in an XPU serving lane.

Main sources:

- `/home/steve/llm-optimizations/suggestions/findings/pytorch-sglang-platform-audit-2026-06-20.md`
- https://github.com/pytorch/pytorch/issues/179891
- https://github.com/pytorch/pytorch/issues/177714
- https://github.com/pytorch/pytorch/issues/161381
- https://github.com/pytorch/pytorch/issues/186548
- https://github.com/sgl-project/sglang/pull/28723
- https://github.com/sgl-project/sglang/pull/25853
- https://github.com/vllm-project/vllm-omni/issues/2570
- https://github.com/intel/llvm/issues/21741

Risk:

- This lane is mostly a correctness and experiment-quality gate. It will not
  create speed by itself, but it prevents false model/kernel conclusions from
  broken platform behavior.

### 1. Port ReplaySSM GDN spec verification to XPU

Why it can help:

- The current MTP/DFlash/EAGLE path is blocked by GDN recurrent-state parity
  after partial acceptance. Local attempts that used slot-copy, Python
  per-position loops, native spec tables, or sequence-path variants did not
  pass the endpoint canary at useful speed.
- ReplaySSM directly targets the same failure mode: avoid per-draft full-state
  snapshots and make rejected draft rollback a ring-buffer pointer operation.
- This is the likely correctness unlock for using MTP, EAGLE, or DFlash without
  quality loss.

What is involved:

- Mine upstream vLLM commit `3c85112`, local `/home/steve/src/ReplaySSM`, and
  SGLang RFC/PRs for exact algorithm behavior.
- Do not copy Triton kernels; Triton FLA kernels are known to fail on this XPU.
  Reimplement the reconstruction math with vectorized torch XPU ops or a later
  SYCL op.
- Maintain the early-flush invariant and partial-accept state publication.
- Gate behind an opt-in env such as `VLLM_XPU_GDN_REPLAYSSM_SPEC=1`.

Validation gate:

- Endpoint canary, not synthetic tests: JSON 96/96 and color 96/96 against the
  no-spec target, with full benchmark identity recorded.
- Then measure MTP k=1/k=3, EAGLE, and DFlash acceptance/speed.

Main sources:

- `/home/steve/llm-optimizations/notes/2026-06-20-research-plan-replayssm-and-speed.md`
- `/home/steve/llm-optimizations/notes/codex-gdn-parity-fix.md`
- https://dao-lab.ai/blog/2026/replayssm/
- https://github.com/sgl-project/sglang/issues/28511
- https://github.com/sgl-project/sglang/pull/28695
- https://github.com/Johnny-Liou/ReplaySSM

Risk:

- ReplaySSM is a spec/correctness unlock and high-batch bandwidth win; by
  itself it may not improve single-request no-spec speed. The payoff comes when
  it lets a high-acceptance draft amortize MoE/weight traffic.

### 2. Make the W8A8 MoE layerlet/workspace path real on endpoint

Why it can help:

- Local timing keeps pointing at MoE/shared-expert structure and per-step
  overhead as the non-speculative speed ceiling.
- Upstream XPU issue 390 and PR 392 confirm that `XpuFusedMoe.apply()` can
  allocate scratch every call and that caller-provided workspaces are a
  legitimate optimization path.
- Local 2026-06-20 notes show the endpoint did not actually enter the C++
  full-layerlet path even when layerlet flags were set. That means the next
  work is not kernel tuning; it is exposing and satisfying the Python gate.

What is involved:

- Finish the gate trace for `VLLM_XPU_MOE_W8A8_FULL_LAYERLET_GATE_TRACE_FILE`.
- Determine whether the blocker is missing scratch, `num_rows` shape, capture
  state, fused-offset prerequisites, or another false gate.
- Once the C++ trace proves `qwen36_moe_w8a8_full_layerlet` is called, run a
  canary-clean endpoint A/B.
- Align with upstream reusable-workspace API shape where possible.

Validation gate:

- C++ trace proves real full-layerlet calls.
- JSON/color canaries pass.
- Compare only against a same-identity PIECEWISE control.

Main sources:

- `/home/steve/llm-optimizations/notes/2026-06-16-qwen36-current-handoff.md`
- `/home/steve/llm-optimizations/notes/2026-06-14-qwen36-recovery-implementation.md`
- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
- https://github.com/vllm-project/vllm-xpu-kernels/issues/390
- https://github.com/vllm-project/vllm-xpu-kernels/pull/392

Risk:

- The first endpoint flag A/B was not a real layerlet test. Do not attribute
  speed deltas to C++ layerlets until trace evidence shows the op executed.

### 3. Port DFlash support as an XPU verifier-proposer path, not as a shortcut

Why it can help:

- DFlash now has a Qwen3.6-35B-A3B drafter and vLLM core support upstream.
  If verifier-safe, it could amortize target model work by proposing larger
  token blocks than simple n-gram.
- Local vLLM already contains DFlash proposer code and a Qwen3 DFlash model,
  so this is mostly backend compatibility and correctness work.
- LocalMaxxing and Lucebox show DFlash/DDTree/PFlash are real performance
  mechanisms when acceptance and graph execution are healthy. Treat those as
  evidence for the mechanism, not proof that the CUDA/HIP path ports directly.

What is involved:

- Port or replace `copy_and_expand_dflash_inputs_kernel` and adjacent
  `@triton.jit` spec-decode kernels with XPU-compatible torch/SYCL paths.
- Ensure XPU attention backend supports DFlash non-causal metadata.
- Carry graph-padded DFlash/spec metadata through GDN/XPU ops using active
  prefixes, matching the intent of vllm-xpu-kernels issue 389 / PR 391.
- Do not trust DFlash until the target verifier path has ReplaySSM or another
  canary-safe partial-accept state solution.

Validation gate:

- DFlash starts and produces target-verified outputs on B70.
- JSON/color canaries pass with `num_speculative_tokens` sweep.
- Acceptance rate and corrected tok/s are recorded with same benchmark identity.

Main sources:

- `/home/steve/src/vllm/vllm/v1/spec_decode/dflash.py`
- `/home/steve/src/vllm/vllm/v1/spec_decode/utils.py`
- `/home/steve/src/vllm/vllm/model_executor/models/qwen3_dflash.py`
- https://github.com/z-lab/dflash
- https://github.com/Luce-Org/lucebox-hub
- https://github.com/vllm-project/vllm-xpu-kernels/issues/389
- https://github.com/vllm-project/vllm-xpu-kernels/pull/391
- https://github.com/jasonboukheir/vllm-xpu-kernels/commit/63c50713578d55a349610797788c7f3da133b2ff

Risk:

- Published DFlash examples are CUDA/SGLang-oriented. B70 work is likely
  backend and state-correctness plumbing before speed is visible.

## Priority 1 - Strong Follow-Ups

### 4. Fix async + PIECEWISE graph replay correctness

Why it can help:

- Local notes show graph-none async can pass, while async + PIECEWISE corrupts
  JSON. If fixed, async scheduling may hide host/runtime overhead and may make
  speculation practical.

What is involved:

- First-divergence instrumentation around graph replay state, logits, sampled
  tokens, and GDN state without CPU reads that mask timing.
- Audit static input buffers, event dependencies, and state writes during graph
  replay.
- Keep every test on explicit PIECEWISE graph identity.

Main sources:

- `/home/steve/llm-optimizations/notes/2026-06-16-qwen36-current-handoff.md`
- `/home/steve/llm-optimizations/notes/2026-06-12-qwen36-next-bigger-bets.md`

Risk:

- Prior traces showed CPU tensor reads can mask the failure. Instrumentation has
  to avoid changing the execution ordering.

### 5. Remove or overlap sampled-token output materialization

Why it can help:

- No-async TP2 diagnostics showed a large `bookkeeping_to_list` wall, roughly
  comparable to forward time. This is not a GPU kernel issue; it is runtime
  output materialization and synchronization.

What is involved:

- Identify where sampled token IDs are copied to CPU/list form.
- Defer, batch, or overlap that transfer while preserving OpenAI-compatible
  streaming behavior and stop-condition correctness.
- Consider a device-resident sampled-token path for canary/benchmark harnesses
  first, then production API behavior later.

Main sources:

- `/home/steve/llm-optimizations/notes/2026-06-16-qwen36-current-handoff.md`

Risk:

- Easy to break streaming semantics or stop-token handling. Needs focused API
  boundary tests, not just tok/s.

### 6. Route-aware grouped GEMM and B70-specific MoE autotune

Why it can help:

- Intel Triton backend issue 6389 says MoE grouped GEMM performance depends
  strongly on real routing distribution and tile config, especially skewed
  decode routes.
- Local config searches suggest B70 configs exist for some shapes, but not all
  current Qwen W8A8 INT8 route shapes.
- llama.cpp B70 reports show practical wins from B70-specific dequant layout,
  activation caching, and MoE gate/up handoff. Those are not drop-in vLLM
  kernels, but they are concrete dataflow hypotheses for the W8A8 path.

What is involved:

- Capture exact Qwen route windows for c1 decode and small batches.
- Benchmark current vLLM Quark MoE, XPU grouped GEMM, oneDNN sidecar oracle,
  and Triton-XPU candidates against the same route histograms.
- Generate B70-specific configs only after route-window microbenchmarks show a
  win.

Main sources:

- https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
- https://docs.vllm.ai/en/latest/design/moe_kernel_features/
- https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes
- https://github.com/PMZFX/intel-arc-pro-b70-benchmarks
- `/home/steve/llm-optimizations/notes/2026-06-13-qwen36-moe-sidecar-readiness.md`

Risk:

- Uniform synthetic expert loads can give the wrong answer. Use captured route
  windows.

### 6b. Port narrow upstream vLLM GDN/Mamba performance patches

Why it can help:

- Upstream PR 41457 fuses Qwen3.5/3.6 GDN `in_proj_ba` into the main
  projection, replacing two GEMMs with one for the non-LoRA path.
- Upstream PR 45816 adds a Triton tensor-descriptor store path for
  `_chunk_cumsum_fwd_kernel`, reporting about 5-7% XPU kernel device-time
  reduction.
- The local tree still shows separate `in_proj_ba` logic and lacks the
  `VLLM_TRITON_USE_TD` chunk-cumsum path.

What is involved:

- Compare PR 41457 against local dirty W8A8 projection code before attempting a
  port; this one touches weight loading and quantized projection behavior.
- PR 45816 is narrower and should be tested as a small kernel-level branch.
- Add upstream XPU test-enablement PRs 45694 and 45382 as coverage sources.

Validation gate:

- Weight-load and deterministic generation tests on the exact Qwen3.6 model.
- Endpoint canaries.
- Kernel microbench only after functional parity; endpoint speed only with
  identical run identity.

Main sources:

- https://github.com/vllm-project/vllm/pull/41457
- https://github.com/vllm-project/vllm/pull/45816
- https://github.com/vllm-project/vllm/pull/45694
- https://github.com/vllm-project/vllm/pull/45382

Risk:

- Projection fusion may conflict with local W8A8 native int8 experiments.
  Treat it as a merge/reconciliation task, not a one-line cherry-pick.

### 7. Re-evaluate TP, EP, PP, and data-parallel layouts for c1 decode

Why it can help:

- Four B70s are not automatically faster for single-request decode if TP4 adds
  synchronization and small collectives at every layer.
- vLLM MoE docs, llm-scaler, and SGLang all expose multiple parallelism axes.
  For MoE, EP-style movement of routed activations may beat synchronizing every
  dense boundary in some cases.
- LocalMaxxing B70 DFlash rows show 2x/3x B70 llama.cpp direct allreduce work
  can help, but 4x direct peer allreduce can regress. TP4 needs topology and
  collective proof, not assumptions.

What is involved:

- Run controlled same-identity TP2 vs TP4 PIECEWISE comparisons.
- Evaluate EP only with correct XPU all2all/AgRs backend support and exact
  Qwen route placement.
- Separate single-session latency goals from multi-user throughput goals.

Main sources:

- https://github.com/intel/llm-scaler
- https://docs.vllm.ai/en/latest/design/moe_kernel_features/
- https://github.com/sgl-project/sglang/blob/main/docs/platforms/xpu.md
- https://localmaxxing.com/api/benchmarks?hfId=z-lab%2FQwen3.6-27B-DFlash&limit=12
- `/home/steve/llm-optimizations/notes/2026-06-12-qwen36-next-bigger-bets.md`

Risk:

- EP/PP may improve capacity or multi-user throughput while hurting c1 latency.
  Keep the metric explicit.

### 8. Fix worker-to-device visibility and XPU communicator path

Why it can help:

- vLLM has open XPU PRs for per-worker `ZE_AFFINITY_MASK` and torchcomms XPU
  support. Both are directly relevant to TP4 process/device assignment,
  collectives, hangs, and peer-device failures.
- The current environment does not have `oneccl_bind_pt` installed in the
  active venv, so communicator behavior should be treated as an explicit stack
  variable rather than background plumbing.

What is involved:

- Review vLLM PR 46226 for per-worker visibility and compare it to the local
  launcher/process model.
- Review vLLM PR 46210 for torchcomms XPU backend maturity and required
  package/runtime dependencies.
- Add communicator identity to benchmark summaries before interpreting TP2/TP4
  speed or stability.

Main sources:

- https://github.com/vllm-project/vllm/pull/46226
- https://github.com/vllm-project/vllm/pull/46210
- https://github.com/vllm-project/vllm/issues/46195
- https://www.pugetsystems.com/labs/articles/intel-arc-pro-b70-multi-gpu-ai-inference-performance/

Risk:

- Communicator changes can fix hangs while hurting c1 latency, or vice versa.
  Keep stability, c1 latency, and multi-user throughput as separate outcomes.

## Priority 2 - Useful, But Not Current Lead

### 9. Clean stack/BKC bakeoff

Why it can help:

- Intel is moving fast on B70 software: vLLM-XPU kernels, PyTorch XPU,
  oneAPI, oneCCL, AI containers, and Battlematrix images. Some local gaps may
  already be fixed in a newer stack.
- The current host has Compute Runtime/OpenCL/Level Zero GPU packages
  `26.18.38308.1`; candidate packages include `26.18.38308.4`, while upstream
  PR 424 is staging `26.22.38646.4` plus IGC `2.36.3`.

What is involved:

- Boot/test a clean container or spare environment with Intel AI container BKC.
- Record full driver/kernel/oneAPI/PyTorch/IPEX/oneCCL/vLLM identities.
- Run the same canary and baseline harness before adopting any component.
- Compare at least three lanes if practical: current host, PPA `26.18.38308.4`,
  and upstream/preview `26.22.38646.4` profile.

Main sources:

- https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md
- https://www.intel.com/content/www/us/en/developer/articles/technical/battlematrix-software-update-august2025.html
- https://github.com/vllm-project/vllm-xpu-kernels/releases/tag/v0.1.10
- https://github.com/vllm-project/vllm-xpu-kernels/pull/424
- https://github.com/vllm-project/vllm-xpu-kernels/pull/321

Risk:

- Stack movement can hide regressions. This is a controlled bakeoff, not an
  in-place upgrade of the working lane.

### 10. OpenVINO GenAI, llama.cpp SYCL, and archived IPEX-LLM as pattern sources

Why it can help:

- These projects show Intel GPU-specific operational and kernel ideas:
  continuous batching, prefix caching, low-bit kernels, frequency locking,
  SYCL build patterns, and alternate serving APIs.

What is involved:

- Mine for transferable mechanisms, not direct replacement of vLLM-XPU.
- Treat IPEX-LLM carefully because the repo is archived and marked unsupported.
- Treat OpenVINO GenAI as a possible single-device/draft-pattern source unless
  current multi-GPU Qwen3.6/GDN/MoE support is proven.
- Add LocalMaxxing, Hal9000AIML, and PMZFX as B70-specific pattern sources:
  kernel shape, dequant layout, SYCL graph cache, host tuning, and driver
  handling are useful even when the runtime is not.

Main sources:

- https://github.com/openvinotoolkit/openvino.genai
- https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/SYCL.md
- https://github.com/intel/ipex-llm
- https://github.com/Hal9000AIML/arc-pro-b70-inference-setup-ubuntu-server
- https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes
- https://github.com/PMZFX/intel-arc-pro-b70-benchmarks

Risk:

- Direct migration cost is high and may lose current Quark/vLLM functionality.

### 11. TurboQuant or quantized KV cache

Why it can help:

- Mostly capacity and long-context headroom, not current c1 decode speed.

What is involved:

- Only revisit if context length or KV capacity becomes the bottleneck.
- If revisited, avoid NVIDIA-tuned Triton kernels as-is; B70 needs Xe2-aware
  tiling and DPAS/XMX use.

Main sources:

- https://github.com/vllm-project/vllm-xpu-kernels/issues/271

Risk:

- Existing XPU data shows large slowdown despite capacity gains.

## Known Low-Value Or Already-Screened Directions

- Blind oneCCL / UR / Level Zero flag sweeps without a source-tied hypothesis.
- Graph-none speed comparisons against PIECEWISE forced-comm baselines.
- Generic CPU n-gram speculation as a production speed path for this model.
- oneDNN sidecar as a captured production path. Keep it as a parity oracle.
- DFlash direct enablement without fixing verifier state rollback first.

## Suggested Next Research Actions

1. Produce a ReplaySSM XPU port checklist from local `/home/steve/src/ReplaySSM`
   and SGLang PR 28695. Output should list tensors, shapes, state ownership,
   and which parts become torch XPU vs SYCL later.
2. Build the upstream-delta matrix: local `vllm-xpu-kernels`, upstream
   `v0.1.10`, PR 392, PR 401, PR 422, PR 429, PR 424, and the Jason
   graph-padded metadata commit. Add the medium-value fork leads from
   `fork-audit-2026-06-20.md`. Mark each as already present, cleanly
   cherry-pickable, conflicting, superseded, pattern-only, or runtime-only.
3. Finish the W8A8 full-layerlet gate trace and prove whether the endpoint can
   call `qwen36_moe_w8a8_full_layerlet`.
4. Make a DFlash XPU port checklist: Triton kernels, non-causal attention,
   graph-padded metadata, hidden-state transfer, GDN verifier, and canary plan.
5. Capture route-window fixtures that can feed grouped GEMM/route-aware MoE
   microbenchmarks.
6. Build a clean-stack comparison table from Intel AI containers, local stack,
   LocalMaxxing public rows, Puget's B70 article, and upstream vLLM-XPU kernel
   release notes.
7. Add the PyTorch/XPU stack canary and XCCL/DeviceMesh split probe from
   `pytorch-sglang-platform-audit-2026-06-20.md` before the next TP4 stack
   comparison.
8. Mine SGLang PR 28723 into a concrete MoE tuning harness checklist using
   captured Qwen route histograms, explicit XPU resources, and XPUGraph timing.
