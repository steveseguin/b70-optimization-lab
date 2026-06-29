# Source Registry

Created: 2026-06-20

Use this as the source list for future digging. Keep sources here even when a
lead is later rejected, but mark the status and reason.

## Local Sources Already Mined

### Benchmark identity and local context

- `/home/steve/AGENTS.md`
  - Status: mined.
  - Why it matters: forbids comparing Qwen 3.6 35B runs unless the full run
    identity matches. PIECEWISE graph mode, XPU graph flags, forced-comm graph,
    GDN fallback, sampler fallback, async args, and diagnostic flags must be
    recorded before interpreting speed.

- `/home/steve/llm-optimizations/AGENTS.md`
  - Status: mined.
  - Why it matters: repo-level workflow context. This project is a reproducible
    Intel XPU lab notebook/deployment guide, and runtime changes should be
    grounded in existing notes, scripts, and benchmark artifacts.

- `/home/steve/llm-optimizations/README.md`
  - Status: mined.
  - Why it matters: records historical B70 work, accepted baselines, known
    negative screens, DFlash stalls, oneCCL flag screens, and current Qwen
    artifacts.

- `/home/steve/llm-optimizations/docs/vllm-intel-upstream-candidates.md`
  - Status: mined.
  - Why it matters: local upstream candidate list. Strong recurring themes:
    XPU W8A8 MoE, MoE route capture, graph-cache provenance, XPU decode graph
    correctness, CPU KV/session cache, TurboQuant XPU, and modular builds.

- `/home/steve/llm-optimizations/notes/2026-06-16-qwen36-current-handoff.md`
  - Status: mined.
  - Why it matters: current safe fast identity, around 93.55 tok/s, plus
    active issues around async + PIECEWISE replay corruption and output
    materialization overhead.

- `/home/steve/llm-optimizations/notes/2026-06-20-research-plan-replayssm-and-speed.md`
  - Status: mined.
  - Why it matters: reframes the GDN speculative parity bug as a ReplaySSM
    porting gap, not a new-algorithm problem. Also notes ReplaySSM is mostly a
    correctness/spec-unlock for single-session B70 speed, not enough by itself.

- `/home/steve/llm-optimizations/notes/codex-gdn-parity-fix.md`
  - Status: mined.
  - Why it matters: documents failed local GDN spec parity attempts, including
    per-position Python loop, native spec-table path, and sequence-path trials.
    The narrow failure is partial-accept SSM/recurrent state publication.

- `/home/steve/llm-optimizations/notes/2026-06-12-qwen36-next-bigger-bets.md`
  - Status: mined.
  - Why it matters: earlier priority backlog: graph replay correctness,
    resident MoE layerlet, oracle parity repair, route timing, device-event
    graph audit, richer route digest, EP/TP layout, and warm artifact manager.

- `/home/steve/llm-optimizations/notes/2026-06-13-qwen36-moe-sidecar-readiness.md`
  - Status: mined.
  - Why it matters: oneDNN sidecar parity is strong as an oracle, but not a
    production speed path inside graph capture.

- `/home/steve/llm-optimizations/notes/2026-06-14-qwen36-recovery-implementation.md`
  - Status: mined.
  - Why it matters: graph-native W8A8 layerlet and resident-offset work showed
    synthetic promise, but endpoint gating/capture and route/offset overhead
    remain unresolved.

### Local code paths to inspect before implementing any idea

- `/home/steve/src/vllm/vllm/v1/spec_decode/dflash.py`
  - Status: mined.
  - Why it matters: local vLLM already has a DFlash proposer. It requires
    non-causal attention metadata and launches a DFlash input-expansion Triton
    kernel.

- `/home/steve/src/vllm/vllm/v1/spec_decode/utils.py`
  - Status: mined.
  - Why it matters: contains `copy_and_expand_dflash_inputs_kernel` and other
    `@triton.jit` spec-decode kernels. This is a concrete Triton-to-XPU port
    target for DFlash enablement.

- `/home/steve/src/vllm/vllm/model_executor/models/qwen3_dflash.py`
  - Status: mined.
  - Why it matters: local Qwen3 DFlash model code. It pre-inserts context KV,
    then runs query-only attention. Backend must support the metadata contract.

- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
  - Status: mined.
  - Why it matters: current XPU fused MoE wrapper and local W8A8 layerlet gates.
    It still allocates several scratch tensors in some paths and has endpoint
    gates that can prevent the C++ full-layerlet from being called.

- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/gdn_attn/gdn_attn_interface.cpp`
  - Status: mined.
  - Why it matters: native XPU GDN paths, including spec-decode shape checks
    and current scratch allocation patterns. Relevant to ReplaySSM, DFlash,
    and MTP verifier correctness.

- `/home/steve/src/llm-scaler`
  - Status: skimmed.
  - Why it matters: Intel multi-GPU/XPU serving stack. Useful for topology,
    oneCCL, quantization, and model-support comparisons.

## Primary External Sources Mined

### vLLM and vLLM-XPU

- vLLM XPU hardware/model support:
  - URL: https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/
  - Status: mined.
  - Key detail: Intel Arc Pro B-Series Graphics is the validated XPU hardware
    class; Qwen3 A3B models are listed in recommended model rows.

- vLLM Fused MoE kernel feature docs:
  - URL: https://docs.vllm.ai/en/latest/design/moe_kernel_features/
  - Status: mined.
  - Key detail: upstream vLLM treats MoE experts kernels, modular MoE methods,
    activation formats, quant formats, and all2all/EP backends as separable.
    This is the right map for EP and XPU MoE porting.

- vLLM XPU kernels repository:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels
  - Status: mined.
  - Key detail: repo provides SYCL/DPC++ and oneDNN custom kernels for Intel
    GPU dispatch into vLLM custom ops.

- vLLM XPU kernels v0.1.10 release:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/releases/tag/v0.1.10
  - Status: mined.
  - Key detail: includes GDN attention prefill optimization, fused quantization
    patterns, FP8/MXFP8 GEMM consolidation, rotary embedding kernel, memory
    information query, and PyTorch 2.12 update.

- vLLM XPU kernels issue 389, GDN graph-padded DFlash metadata:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/issues/389
  - Status: mined.
  - Key detail: DFlash/spec decode with graph-padded metadata on Arc Pro
    B60/B70 and TP4 needs metadata tensors accepted by active prefix, not exact
    captured-shape size.

- vLLM XPU kernels PR 391, accept graph-padded spec metadata:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/pull/391
  - Status: mined.
  - Key detail: proposed fix for issue 389. Important for DFlash/MTP under
    PIECEWISE graph capture.

- vLLM XPU kernels issue 390, XPU fused MoE allocates scratch every call:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/issues/390
  - Status: mined.
  - Key detail: `XpuFusedMoe.apply()` allocates temporary XPU tensors per call;
    decode-heavy MoE should reuse deterministic scratch buffers.

- vLLM XPU kernels PR 392, reusable fused MoE workspaces:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/pull/392
  - Status: mined.
  - Key detail: adds optional caller-provided workspaces for remap, GEMM1,
    activation, and GEMM2 scratch.

- vLLM XPU kernels issue 271, TurboQuant XPU feasibility:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/issues/271
  - Status: mined.
  - Key detail: TurboQuant can increase KV capacity but was much slower in
    reported Qwen3-30B XPU data because NVIDIA-tuned Triton kernels miss Xe2
    DPAS/XMX and use unfavorable tile/subgroup choices.

### Triton, grouped GEMM, and MoE

- Intel Triton backend grouped-GEMM tuning issue 6389:
  - URL: https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
  - Status: mined.
  - Key detail: MoE grouped GEMM performance depends on real routing
    distribution and tile configuration; decode route distributions are highly
    skewed. This supports route-window benchmarking rather than synthetic
    uniform expert loads.

### ReplaySSM and GDN speculative verification

- Dao AI Lab ReplaySSM blog:
  - URL: https://dao-lab.ai/blog/2026/replayssm/
  - Status: mined.
  - Key detail: caches recent SSM inputs instead of writing recurrent state
    every step; output can be reconstructed without materializing the full
    state on non-flush steps; rollback becomes a buffer operation.

- ReplaySSM reference repo:
  - URL: https://github.com/Johnny-Liou/ReplaySSM
  - Status: mined.
  - Key detail: reference vLLM-derived implementation source for ReplaySSM.
    Local path also exists at `/home/steve/src/ReplaySSM`.

- SGLang ReplaySSM RFC 28511:
  - URL: https://github.com/sgl-project/sglang/issues/28511
  - Status: mined.
  - Key detail: tracks porting ReplaySSM to SGLang, cites vLLM commit
    `3c85112`, and splits buffered decode from spec-verify.

- SGLang PR 28451, ReplaySSM buffered output-only decode:
  - URL: https://github.com/sgl-project/sglang/pull/28451
  - Status: mined.
  - Key detail: removes per-step full-state write for GDN/KDA decode behind a
    flag. Useful for understanding decode-buffer integration.

- SGLang PR 28695, ReplaySSM ring spec-verify:
  - URL: https://github.com/sgl-project/sglang/pull/28695
  - Status: mined.
  - Key detail: replaces per-draft full `[V,K]` recurrent-state snapshots with
    a circular `(d,k,g)` ring plus frozen checkpoint. It is the closest known
    match to the local GDN partial-accept correctness problem.

### DFlash and speculative decoding

- z-lab DFlash:
  - URL: https://github.com/z-lab/dflash
  - Status: mined.
  - Key detail: lists `z-lab/Qwen3.6-35B-A3B-DFlash` and says vLLM v0.20.1+
    includes core DFlash support. Published examples are CUDA/SGLang-oriented,
    so B70 still needs XPU backend work.

- vLLM speculators:
  - URL: https://github.com/vllm-project/speculators
  - Status: skimmed.
  - Key detail: library for building, evaluating, and storing speculative
    decoding algorithms for vLLM. Useful for EAGLE/P-EAGLE/draft training and
    evaluation flow.

- OpenVINO Model Server speculative decoding demo:
  - URL: https://docs.openvino.ai/2026/model-server/ovms_demos_continuous_batching_speculative_decoding.html
  - Status: skimmed.
  - Key detail: frames spec decoding as a latency reduction path with main and
    draft models while preserving main-model accuracy. Useful as an API and
    validation pattern, less likely as direct multi-B70 runtime for this model.

### Other XPU projects and stack sources

- Intel llm-scaler:
  - URL: https://github.com/intel/llm-scaler
  - Status: mined.
  - Key detail: `llm-scaler-vllm` lists CCL support, INT4/FP8 online serving,
    tensor/pipeline/data parallelism, and Qwen3.5/3.6-35B-A3B support.

- Intel Project Battlematrix software update:
  - URL: https://www.intel.com/content/www/us/en/developer/articles/technical/battlematrix-software-update-august2025.html
  - Status: mined.
  - Key detail: Intel positions the Arc Pro B-series stack around
    containerized Linux, multi-GPU scaling, PCIe P2P, vLLM/SGLang, by-layer
    quantization, pipeline parallelism, torch.compile, and speculative decode.

- Intel AI containers vLLM XPU BKC:
  - URL: https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md
  - Status: skimmed.
  - Key detail: records validated Arc Pro B-series container ingredients
    such as host OS, kernel driver, oneAPI, PyTorch, IPEX, and oneCCL. Useful
    for clean stack bakeoffs.

- SGLang XPU docs:
  - URL: https://github.com/sgl-project/sglang/blob/main/docs/platforms/xpu.md
  - Status: mined.
  - Key detail: SGLang has Intel GPU/XPU source-install docs and explicitly
    targets Intel Arc Pro B-Series, but current optimized model list is small.

- SGLang fused QK RMSNorm + mRoPE + KV-store PR 28700:
  - URL: https://github.com/sgl-project/sglang/pull/28700
  - Status: mined as transferable pattern.
  - Key detail: AMD/HIP specific, but the pattern matters: Qwen decode
    launch overhead can be reduced by fusing QK norm, rotary, and KV-store.

- IPEX-LLM:
  - URL: https://github.com/intel/ipex-llm
  - Status: skimmed, lower priority.
  - Key detail: archived by Intel and has known security/support warnings, but
    historical notes include low-bit Intel GPU work, FlashMoE, vLLM integration,
    pipeline parallel inference, and self-speculative decoding.

- IPEX-LLM vLLM quickstart:
  - URL: https://github.com/intel/ipex-llm/blob/main/docs/mddocs/Quickstart/vLLM_quickstart.md
  - Status: skimmed, lower priority.
  - Key detail: useful historical operational hints, including locking CPU/GPU
    frequencies for stable performance measurements.

- OpenVINO GenAI:
  - URL: https://github.com/openvinotoolkit/openvino.genai
  - Status: skimmed.
  - Key detail: continuous batching, prefix caching, sparse attention, and
    OpenVINO serving ideas. Direct fit depends on Qwen3.6/GDN/MoE support and
    multi-GPU status.

- llama.cpp SYCL backend:
  - URL: https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/SYCL.md
  - Status: skimmed.
  - Key detail: supports Intel Arc GPUs through SYCL. More useful for SYCL
    micro-optimization style and operational lessons than for current vLLM
    Quark W8A8 serving.

## 2026-06-20 Deeper Source Additions

### Local stack snapshot

- Active Python/XPU stack:
  - Status: mined.
  - Key detail: `/home/steve/.venvs/vllm-xpu` uses Python `3.12.13`,
    Torch `2.11.0+xpu`, `triton-xpu 3.7.0`, vLLM
    `0.20.2rc1.dev2+gc51df4300.d20260523.xpu`, and
    `vllm-xpu-kernels 0.1.9.dev27+g28e1f5e`.
  - Caveat: source trees are dirty in GDN/spec files; do not rebase or upgrade
    in place without preserving that work.

- Local oneAPI / UMD stack:
  - Status: mined.
  - Key detail: oneAPI DPC++ compiler is `2026.0.0`; SYCL reports four B70s
    on Level Zero UR `[1.15.38308+1]`; installed Compute Runtime packages are
    `26.18.38308.1`; configured PPA candidates are `26.18.38308.4`.
  - Why it matters: upstream vLLM already merged a 26.18/v0.1.10 bump and
    vLLM-XPU-kernels is staging 26.22/IGC 2.36.3. This is a stack bakeoff
    source, not permission for a blind upgrade.

### Benchmark and B70 community sources

- LocalMaxxing API, Quark W8A8 public B70 row:
  - URL: https://localmaxxing.com/api/benchmarks?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&limit=5
  - Status: mined.
  - Key detail: public row for `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
    on 4x B70, vLLM `0.20.2rc1...`, Quark W8A8 INT8, p512/n512,
    `99.428 tok/s` output and `196.325 tok/s` total, with quality gates
    recorded in notes.

- LocalMaxxing API, Intel Arc Pro B70 rows:
  - URL: https://localmaxxing.com/api/benchmarks?hardwareName=Intel%20Arc%20Pro%20B70&limit=80
  - Status: mined.
  - Key detail: useful B70 signals include XPUGraph un-gating taking custom
    vLLM decode from about `11 tok/s` eager to about `102 tok/s`, and
    llama.cpp B70 SYCL rows citing `dp4a fattn`, 16B V dequant, SYCL graph
    cache, activation Q8 cache, and gate/up handoff.

- LocalMaxxing API, Qwen3.6-35B FP8 rows:
  - URL: https://localmaxxing.com/api/benchmarks?hfId=Qwen%2FQwen3.6-35B-A3B-FP8&limit=10
  - Status: mined.
  - Key detail: CUDA reference rows show DFlash + CUDA graphs and prefix
    caching/torch.compile/CUDAGraphs as credible Qwen3.6-35B performance
    paths. Hardware and quantization differ, so treat as mechanism evidence.

- LocalMaxxing API, Qwen3.6-27B DFlash rows:
  - URL: https://localmaxxing.com/api/benchmarks?hfId=z-lab%2FQwen3.6-27B-DFlash&limit=12
  - Status: mined.
  - Key detail: includes B70 llama.cpp multi-GPU SYCL direct-allreduce tests
    with negative 4-GPU scaling and an RTX 5090 Lucebox DFlash row with
    acceptance length/rate. Good for DFlash and multi-GPU caution.

- Hal9000AIML B70 Ubuntu setup:
  - URL: https://github.com/Hal9000AIML/arc-pro-b70-inference-setup-ubuntu-server
  - Status: mined.
  - Key detail: operational B70 setup source: BIOS settings, topology,
    systemd/watchdog, independent per-card servers, and `xe_tuning.sh`. Useful
    for comparing host/driver setup, not as a direct vLLM kernel source.

- Hal9000AIML B70 speedup bugfix kit:
  - URL: https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes
  - Status: mined.
  - Key detail: lists 11 llama.cpp cherry-picks and measured B70/Xe2 lessons:
    BF16 `GET_ROWS`, fused MoE token-generation MMVQ, native Xe2 subgroup size
    for K-quant DMMV, oneMKL small-matmul routing, Q8_0 reorder fixes, Vulkan
    warptile tuning, and runtime rules such as relaxed allocation limits.

- PMZFX B70 benchmark corpus:
  - URL: https://github.com/PMZFX/intel-arc-pro-b70-benchmarks
  - Status: mined.
  - Key detail: commit-pinned llama.cpp SYCL/Vulkan benchmark corpus with
    power telemetry. Reports Qwen3.6-35B-A3B UD-Q4_K_M at `54.7 tg128 t/s`
    and Qwen3-Coder-Next 80B-A3B Q4_K_M at `43.4 tg128 t/s` on dual B70.

- Puget Systems B70 multi-GPU article:
  - URL: https://www.pugetsystems.com/labs/articles/intel-arc-pro-b70-multi-gpu-ai-inference-performance/
  - Status: mined.
  - Key detail: June 18, 2026 article using `intel/llm-scaler-vllm:0.14.0-b8.2.1`,
    Intel PPA 26.09.x, oneCCL, FP16, and GenAI-Perf streaming. Reports
    Qwen3.6-35B-A3B FP16 at `16.3 tok/s` single-user and `122 tok/s` at c8.
    Useful for clean-stack and multi-user behavior, not same-identity local
    comparison.

- Hugging Face Fast Gemma Challenge dashboard:
  - URL: https://huggingface.co/spaces/gemma-challenge/gemma-dashboard
  - Status: skimmed, low direct priority.
  - Key detail: benchmark dashboard source; no direct Qwen/B70 lead found in
    this pass.

### Speculative decode and alternate engines

- Lucebox Hub:
  - URL: https://github.com/Luce-Org/lucebox-hub
  - Status: mined.
  - Key detail: custom speculative inference server with DFlash, PFlash,
    DDTree, KVFlash, and model-specific kernels. Reports Qwen3.6-27B + PFlash
    around `5.6x` and Qwen3.6-27B + DDTree around `4.84x` versus its vendored
    llama.cpp baseline. CUDA/HIP source, no XPU path found.

- Anna release 2026.4.17:
  - URL: https://github.com/funkpopo/Anna/releases/tag/2026.4.17
  - Status: mined as breadcrumb index.
  - Key detail: release notes mention fused op naming/dispatch changes,
    decode op interfaces, MoE dispatch/scatter/grouped INT4 MLP ops, Qwen3.5
    quant/config handling, and engine alignment with fused ops. Follow primary
    upstream PRs before using.

### Upstream vLLM / vLLM-XPU sources added

- vLLM PR 40367, vLLM-XPU-kernels v0.1.10 and UMD 26.18:
  - URL: https://github.com/vllm-project/vllm/pull/40367
  - Status: mined.
  - Key detail: merged June 19, 2026; bumps vLLM to `vllm-xpu-kernels v0.1.10`
    and points at Compute Runtime `26.18.38308.1`.

- vLLM-XPU-kernels PR 424, UMD 26.22 profile:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/pull/424
  - Status: mined.
  - Key detail: open profile update from `igc-2.34.4-cr-26.18` to
    `igc-2.36.3-cr-26.22`, Compute Runtime `26.22.38646.4`, Level Zero
    `1.28.6`.

- vLLM-XPU-kernels PR 321, oneAPI 2026.0 stack:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/pull/321
  - Status: mined.
  - Key detail: upgrades build/CI environment toward oneAPI 2026.0, Torch XPU
    nightly, Triton-XPU pins, and AOT device list.

- vLLM-XPU-kernels PR 401, MoE invalid-row activation skip:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/pull/401
  - Status: mined.
  - Key detail: device-side `valid_rows` guard for MoE activation kernels so
    padded/invalid routed rows do not run activation work and no Python
    `.item()` synchronization is needed.

- vLLM-XPU-kernels PR 422, fused qknorm/RoPE/KV insert on BMG:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/pull/422
  - Status: mined.
  - Key detail: SYCL port and profile-guided optimization of a fused
    attention-preprocessing kernel; removes private-memory spill and uses
    cooperative sub-groups, improving measured device time about 3.3x in the
    PR notes.

- vLLM-XPU-kernels PR 429, stride-aware flash cache writes:
  - URL: https://github.com/vllm-project/vllm-xpu-kernels/pull/429
  - Status: mined.
  - Key detail: preserves vectorized compact K/V cache writes but adds
    per-head indexing for strided packed K/V views.

- vLLM PR 46226, per-worker XPU device visibility:
  - URL: https://github.com/vllm-project/vllm/pull/46226
  - Status: mined.
  - Key detail: assigns `ZE_AFFINITY_MASK` per XPU worker so each TP worker
    sees only its physical XPU and uses worker-visible `xpu:0`.

- vLLM PR 46210, torchcomms backend for XPU:
  - URL: https://github.com/vllm-project/vllm/pull/46210
  - Status: mined, draft.
  - Key detail: adds torchcomms/XCCL communicator path while preserving the
    existing XPU communicator as default.

- vLLM issue 41663, dual-B70 TP=2 GP fault / BCS reset:
  - URL: https://github.com/vllm-project/vllm/issues/41663
  - Status: mined including comments.
  - Key detail: detailed dual Arc Pro B70 TP=2 failure matrix. Later comments
    add working-stack clues: vLLM CI XPU image, Level Zero/oneCCL versions,
    `UR_L0_USE_IMMEDIATE_COMMANDLISTS=0`, and a pointer toward kernel 7.1 /
    newer NEO for multi-root B70 TP.

- vLLM issue 46072, Battlemage PP=2 device loss / worker wedge:
  - URL: https://github.com/vllm-project/vllm/issues/46072
  - Status: mined including comments.
  - Key detail: PP=2 on B70+B580 can load and answer briefly, then fail around
    sampling/cross-worker communication. Comments clarify that a pending fix
    targets faster wedged-worker detection, not the Level Zero/oneCCL root
    crash.

- vLLM PR 41457, Qwen3.5/3.6 GDN projection fusion:
  - URL: https://github.com/vllm-project/vllm/pull/41457
  - Status: mined.
  - Key detail: fuses `in_proj_ba` into a 6-way `MergedColumnParallelLinear`
    for the Qwen3.5/3.6 non-LoRA path, removing a separate small GEMM.

- vLLM PR 45816, XPU Triton tensor-descriptor store for Mamba chunk cumsum:
  - URL: https://github.com/vllm-project/vllm/pull/45816
  - Status: mined.
  - Key detail: adds optional `VLLM_TRITON_USE_TD` tensor-descriptor store for
    `_chunk_cumsum_fwd_kernel`, reporting about 5-7% XPU kernel device-time
    reduction.

- vLLM issue 41817 and PRs 41995/44511, XPU high-bit Mamba copy pointers:
  - URLs:
    - https://github.com/vllm-project/vllm/issues/41817
    - https://github.com/vllm-project/vllm/pull/41995
    - https://github.com/vllm-project/vllm/pull/44511
  - Status: mined.
  - Key detail: XPU device pointers can have the high bit set; signed int64
    host assignment breaks align-mode prefix-cache copy metadata. Local branch
    already appears to use `torch.uint64` pointer buffers.

- vLLM PR 43081, DFlash with FlashInfer:
  - URL: https://github.com/vllm-project/vllm/pull/43081
  - Status: mined as DFlash backend pattern.
  - Key detail: routes non-causal DFlash attention through FlashInfer and
    documents FP8 KV interactions. Pattern source only for XPU.

- vLLM PR 45181, mixed KV page sizes for DFlash:
  - URL: https://github.com/vllm-project/vllm/pull/45181
  - Status: mined.
  - Key detail: generic KV-cache infrastructure for target/draft models with
    different physical page sizes, including padded layout/stride handling.

- vLLM PR 44807, temporary DFlash SWA merge:
  - URL: https://github.com/vllm-project/vllm/pull/44807
  - Status: mined as tracker only.
  - Key detail: temporary mergeability PR for DFlash sliding-window attention.
    Useful to track, but not a final API source.

- vLLM PR 45237, speculative decode padding on D-node:
  - URL: https://github.com/vllm-project/vllm/pull/45237
  - Status: mined as graph-shape pattern.
  - Key detail: pads transferred decode requests with dummy spec tokens to
    preserve uniform spec-decode graph shapes in P/D disaggregation.

- vLLM PR 44336, adaptive speculation length:
  - URL: https://github.com/vllm-project/vllm/pull/44336
  - Status: mined, later-stage.
  - Key detail: adjusts speculative K from acceptance-rate EMAs. Relevant only
    after B70 spec decode is canary-clean.

- vLLM issue 46088, MTP KV dtype auto cross-sequence corruption:
  - URL: https://github.com/vllm-project/vllm/issues/46088
  - Status: mined as caution.
  - Key detail: CUDA/Gemma report, but cross-sequence contamination under
    batched MTP is a warning that any B70 spec path needs strict canaries.

- vLLM PR 46206, DeepSeek V4 EPLB across platforms:
  - URL: https://github.com/vllm-project/vllm/pull/46206
  - Status: mined as MoE control-plane pattern.
  - Key detail: standardizes platform-specific DeepSeek V4 MoE/EPLB metadata
    registration across NVIDIA, ROCm, and XPU.

- vLLM PR 44389, Triton software NVFP4 KV cache:
  - URL: https://github.com/vllm-project/vllm/pull/44389
  - Status: mined as future capacity lane.
  - Key detail: reports about 3x KV capacity for Qwen3.6 models, but validation
    is CUDA-only and XPU was not tested.

- vLLM PR 45370, fused K-RoPE + static FP8 KV cache write:
  - URL: https://github.com/vllm-project/vllm/pull/45370
  - Status: mined as pattern source.
  - Key detail: fuses K rotary embedding and FP8 KV cache write to avoid an HBM
    round trip on CUDA/ROCm. XPU analog would need a native/SYCL path.

- vLLM PR 44891, push-based allreduce:
  - URL: https://github.com/vllm-project/vllm/pull/44891
  - Status: mined as algorithmic pattern only.
  - Key detail: CUDA/NVLink small-message allreduce. Not directly portable to
    B70, but reinforces measuring decode collective size classes.

- vLLM PRs 45694 and 45382, XPU Triton kernel test enablement:
  - URLs:
    - https://github.com/vllm-project/vllm/pull/45694
    - https://github.com/vllm-project/vllm/pull/45382
  - Status: mined.
  - Key detail: enable XPU coverage for Triton kernels including block int8/fp8,
    scaled_mm, int8 quant, KDA, FLA layernorm guard, and per-token-group quant.

- Local vLLM upstream audit:
  - Path: `/home/steve/llm-optimizations/suggestions/findings/vllm-upstream-audit-2026-06-20.md`
  - Status: current working summary.
  - Key detail: maps the upstream issue/PR list to local code status in
    `/home/steve/src/vllm`.

- vLLM-XPU-kernels fork audit:
  - URLs:
    - https://github.com/draghan/vllm-xpu-kernels
    - https://github.com/LucasWilkinson/vllm-xpu-kernels
    - https://github.com/tianyuan0211/vllm-xpu-kernels-fork
    - https://github.com/kfojcik-intel/vllm-xpu-kernels
    - https://github.com/jasonboukheir/vllm-xpu-kernels
    - https://github.com/jasonboukheir/vllm-xpu-nix
  - Status: exhaustive for the 76 public default-branch forks returned by
    GitHub on 2026-06-20.
  - Local audit file:
    `/home/steve/llm-optimizations/suggestions/findings/fork-audit-2026-06-20.md`
  - Key detail: 6 forks were identical to upstream head, 60 had no unique
    default-branch commits ahead of upstream, and 10 were ahead. The
    high-signal fork lead remains `jasonboukheir/vllm-xpu-kernels`, but
    additional medium-value pattern leads were found in forks by
    `PershingSquare`, `chaojun-zhang`, `Wei-Lin-Intel`, `nc-BobLee`, and
    `jikunshang`.

- Jason Bou Kheir GDN metadata narrowing commit:
  - URL: https://github.com/jasonboukheir/vllm-xpu-kernels/commit/63c50713578d55a349610797788c7f3da133b2ff
  - Status: mined.
  - Key detail: narrows cudagraph-padded GDN spec metadata tensors to active
    prefixes inside the kernel wrapper so existing size checks and launchers
    see unpadded views.

- PershingSquare oneDNN W4A16 grouped GEMM commit:
  - URL: https://github.com/PershingSquare/vllm-xpu-kernels/commit/dbe6ec4aee54a8091954da5a8c92d64b613adf71
  - Status: mined.
  - Key detail: old-base fork commit adding oneDNN W4A16 grouped GEMM. Not a
    direct Quark W8A8 fix, but a concrete XPU quantized grouped-GEMM pattern.

- Chaojun Zhang fused SiLU + per-block quant commit:
  - URL: https://github.com/chaojun-zhang/vllm-xpu-kernels/commit/c3af52c1047e707ce8826a87a4f2253999711e07
  - Status: mined.
  - Key detail: old-base fused activation plus block quantization op. Compare
    against upstream `v0.1.10` fused quant work before spending time.

- Wei-Lin Intel MoE benchmark/reference scripts:
  - URL: https://github.com/Wei-Lin-Intel/vllm-xpu-kernels
  - Status: mined.
  - Key detail: ahead fork adds `tests/fused_moe/optimized_triton_moe.py` and
    `tests/fused_moe/moe_compare.py`. Useful as benchmark/reference material,
    not as a direct runtime patch.

- nc-BobLee IPEX-derived RMSNorm/layernorm fork:
  - URL: https://github.com/nc-BobLee/vllm-xpu-kernels
  - Status: mined.
  - Key detail: old-base fork adds a head RMSNorm kernel, ports IPEX layernorm
    logic, and optimizes fused add RMSNorm. Useful only if profiling shows
    norm overhead.

- Jikunshang integer-width/index hardening fork:
  - URL: https://github.com/jikunshang/vllm-xpu-kernels
  - Status: mined.
  - Key detail: broad `int` to `size_t` hardening and MoE remap edits. Treat as
    large-shape correctness material, not a speed path.

- Chris Wagner Arc B70 vLLM multi-GPU guide:
  - URL: https://github.com/chriswagner-ai/intel-arc-b70-vllm-multi-gpu
  - Status: mined as host-stack source.
  - Key detail: field-tested 4x B70 bare-metal guide claiming TP=2/TP=4
    serving after two fixes: kernel >= 7.1.0-rc6 plus host NEO >= 26.14, and
    the Triton `init_devices` fix via triton-xpu >= 3.7.0 or patch. Useful for
    stack bakeoff, not as a direct kernel patch.

## Sources Still Worth Mining

- Upstream vLLM commit `3c85112`
  - Target files: `fused_recurrent_replayssm.py`,
    `gdn_replayssm_spec_decode.py`.
  - Goal: compare the exact algorithm against local XPU GDN data layout.

- Local `/home/steve/src/ReplaySSM`
  - Target files:
    `/home/steve/src/ReplaySSM/vllm/model_executor/layers/fla/ops/gdn_replayssm_spec_decode.py`
    and
    `/home/steve/src/ReplaySSM/vllm/model_executor/layers/mamba/ops/selective_state_update_replayssm_spec.py`.
  - Goal: produce a line-by-line XPU port checklist without copying Triton.

- vLLM PRs/issues around DFlash and hidden states:
  - Examples to inspect: DFlash speculators parsing, hidden-state extraction,
    async scheduling/spec decode, Qwen3.6 DFlash/MTP recipes.
  - Goal: find scheduler, rollback, hidden-state, and graph-capture contracts
    that the XPU fork may be missing.

- SGLang DFlash and SpecForge:
  - URLs: https://docs.sglang.ai/ and https://sgl-project.github.io/SpecForge/
  - Goal: study draft-model training/evaluation and server-side spec decode
    contracts, especially for Qwen/GDN models.

- Intel XPU backend for Triton issues and PRs:
  - URL: https://github.com/intel/intel-xpu-backend-for-triton/issues
  - Goal: track grouped GEMM, block scaling, DPAS/XMX tiling, and Triton
    language gaps that decide whether to port a Triton kernel or rewrite in
    SYCL/torch XPU.

- oneCCL, Level Zero, and Unified Runtime docs:
  - Goal: only mine for graph/event/command-list correctness and stable BKC
    settings. Avoid random flag sweeps unless a source ties the flag to a
    measured issue.

- PyTorch XPU Inductor/Triton integration docs and issues:
  - Goal: understand which upstream vLLM `torch.compile` assumptions now work
    on Intel XPU and which custom ops need fake/meta kernels.

- Hugging Face model cards for:
  - `z-lab/Qwen3.6-35B-A3B-DFlash`
  - `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
  - Qwen3.6 MTP/draft variants
  - Goal: verify model revisions, draft compatibility, context limits, and
    license/format details before any benchmark.

- LocalMaxxing API rows:
  - Goal: collect public performance clues only. Do not compare directly to
    local runs unless model, quantization, TP/PP, graph identity, flags, and
    workload match.

## Runtime, Triton-XPU, and Adjacent Engine Sources Added

- Runtime/Triton/collectives audit:
  - Path: `/home/steve/llm-optimizations/suggestions/findings/runtime-triton-collectives-audit-2026-06-20.md`
  - Status: written.
  - Key detail: current B70 multi-GPU research should split stack/topology
    correctness from model/kernel speed. P2P and collectives need checksum and
    low-level gates before endpoint speed is trusted.

- Intel compute-runtime issue 921, BMG multi-device regressions:
  - URL: https://github.com/intel/compute-runtime/issues/921
  - Status: mined.
  - Key detail: reports multi-BMG enumeration and compression/P2P regressions.
    Relevant fixes/commits include internal BCS initialization, peer-access
    validation, and decompression for P2P source allocations. Kernel 7.1+ and
    newer compute-runtime lanes are important candidates.

- Intel compute-runtime issue 916, multi-device USM allocation:
  - URL: https://github.com/intel/compute-runtime/issues/916
  - Status: mined.
  - Key detail: multi-device Level Zero/UR allocation failures; reports kernel
    and compute-runtime fixes plus a host-staged fallback debug key. Treat as a
    low-level context/allocation gate before vLLM TP/PP testing.

- Intel compute-runtime issue 935, B70 cross-root-port P2P:
  - URL: https://github.com/intel/compute-runtime/issues/935
  - Status: mined.
  - Key detail: forced consumer Intel cross-root P2P can return success while
    corrupting destination data; host-staged copy passes. This makes checksum
    P2P validation mandatory before trusting TP4 collectives.

- Intel compute-runtime issue 922, multi-rank BMG Level Zero abort:
  - URL: https://github.com/intel/compute-runtime/issues/922
  - Status: mined.
  - Key detail: B70/BMG multi-rank Level Zero failures after compute-runtime
    changes; stale `/usr/local/lib` IGC can shadow package libraries, and
    maintainers request testing compute-runtime `26.22.38646.4` plus IGC
    `v2.36.3`.

- Intel compute-runtime PR 930, USM compression/P2P:
  - URL: https://github.com/intel/compute-runtime/pull/930
  - Status: mined.
  - Key detail: proposed disabling USM compression for multi-device contexts
    and was closed after a narrower decompression fix. Useful for understanding
    the compression failure mode, not as a current patch target.

- `TSUMUGI-XE/b70-dual-tp2`:
  - URL: https://github.com/TSUMUGI-XE/b70-dual-tp2
  - Status: queued as a next source.
  - Key detail: referenced by compute-runtime issue 935 as a small B70 P2P
    reproduction repository. The likely high-value file is
    `repro/b70_p2p_copy_probe.cpp`.

- `llm-scaler` issue 486, dual B70 TP=2 IPC failure:
  - URL: https://github.com/intel/llm-scaler/issues/486
  - Status: mined.
  - Key detail: single-GPU works but TP=2 fails around
    `zeMemOpenIpcHandle`. Useful as an IPC/oneCCL failure signature.

- `llm-scaler` issue 463, Level Zero V2 multi-device failures:
  - URL: https://github.com/intel/llm-scaler/issues/463
  - Status: mined.
  - Key detail: reports a failing oneAPI 2025.3 Level Zero V2 lane and a
    working rebuilt image using compute-runtime `26.22.38646.4`, GMM `22.10.0`,
    and IGC `2.36.3`. Also lists workaround variables to test only in a
    controlled matrix.

- `llm-scaler` issue 489, PP=2 B70+B580 device loss:
  - URL: https://github.com/intel/llm-scaler/issues/489
  - Status: mined.
  - Key detail: pipeline-parallel serving can load and even answer once before
    `UR_RESULT_ERROR_DEVICE_LOST` or worker communication timeout. Useful for
    long-running canary and second-request stability tests.

- `llm-scaler` issue 407, Qwen3.6 sym_int4 GDN failure:
  - URL: https://github.com/intel/llm-scaler/issues/407
  - Status: mined.
  - Key detail: older image failed a GDN v-thread-slot constraint for
    Qwen3.6-35B-A3B sym_int4; later image reportedly fixed it. Useful for
    GDN image-version and model-shape clues.

- `llm-scaler` issue 439, FP8 KV and ESIMD MoE dtype gaps:
  - URL: https://github.com/intel/llm-scaler/issues/439
  - Status: mined.
  - Key detail: image-specific custom ESIMD MoE and FP8 KV decode gaps. Treat
    as a compatibility checklist before relying on FP8 KV claims.

- `llm-scaler` issue 479, GPTQ INT4 MoE out-of-resources:
  - URL: https://github.com/intel/llm-scaler/issues/479
  - Status: mined.
  - Key detail: INT4 GPTQ MoE hits XPU out-of-resources while dense INT4 works.
    Later GPTQ/MTP claims are leads only until benchmark identity matches.

- Intel Triton backend issue 6389, vLLM grouped GEMM:
  - URL: https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
  - Status: mined deeper.
  - Key detail: MoE grouped GEMM performance depends on real route distribution
    and tile config. The important insight is to avoid blindly porting
    CUDA-style random expert-row gather to Xe2; dense/pre-grouped layouts and
    SYCL-TLA comparison are more promising.

- Intel Triton backend PR 6974, runtime row-stride 2D block load:
  - URL: https://github.com/intel/intel-xpu-backend-for-triton/pull/6974
  - Status: mined.
  - Key detail: enables 2D block loads for grouped GEMM cases with runtime row
    strides, which directly affects vLLM MoE candidates.

- Intel Triton backend PRs 7192 and 7193, vLLM unified attention:
  - URLs:
    - https://github.com/intel/intel-xpu-backend-for-triton/pull/7192
    - https://github.com/intel/intel-xpu-backend-for-triton/pull/7193
  - Status: mined.
  - Key detail: small source/backend changes with reported BMG vLLM
    unified-attention gains. Good branch bakeoff candidates before local
    attention work.

- Intel Triton backend PRs 7029 and 7040, FP8 conversion:
  - URLs:
    - https://github.com/intel/intel-xpu-backend-for-triton/pull/7029
    - https://github.com/intel/intel-xpu-backend-for-triton/pull/7040
  - Status: mined.
  - Key detail: replace FP8E4M3FN table-lookup conversion paths with
    multiply-based conversions for FP16/BF16 paths. Relevant to FP8 KV cache
    and attention dot paths.

- llama.cpp PR 24152, SYCL tensor-split allreduce:
  - URL: https://github.com/ggml-org/llama.cpp/pull/24152
  - Status: mined as adjacent-engine pattern.
  - Key detail: B70-oriented tensor-split allreduce with size-class behavior,
    including BF16-compressed cross-device large transfers. Useful as a
    collectives design source, not as a vLLM drop-in.

- llama.cpp PR 24476, SYCL dev2dev memcpy fallback:
  - URL: https://github.com/ggml-org/llama.cpp/pull/24476
  - Status: mined as adjacent-engine pattern.
  - Key detail: moves away from risky Level Zero direct dev2dev copy and keeps
    host-staged fallback because multi-GPU copies can produce abnormal output.

- llama.cpp PR 17374, Vulkan Xe2 subgroup/block-size experiments:
  - URL: https://github.com/ggml-org/llama.cpp/pull/17374
  - Status: mined as low-direct-value pattern.
  - Key detail: subgroup/block size can move Xe2 prompt-processing speed, but
    correctness/device-loss risk is real. Treat as a reminder to benchmark
    subgroup shapes carefully.

- llama.cpp PR 24785, Qwen3.6 GDN recurrent state prompt-cache lifecycle:
  - URL: https://github.com/ggml-org/llama.cpp/pull/24785
  - Status: mined as algorithmic source.
  - Key detail: ROCm-oriented shrink/expand recurrent-state work for Qwen3.6
    Gated DeltaNet; useful for state lifecycle ideas around prompt cache and
    rejected speculative drafts.

- llama.cpp PR 24340, MTP chaining:
  - URL: https://github.com/ggml-org/llama.cpp/pull/24340
  - Status: mined as algorithmic source.
  - Key detail: multi-head MTP hidden-state and KV mechanics can inform Qwen
    MTP/DFlash verifier integration, but it is not a B70 kernel source.

## PyTorch, SGLang, vLLM-Omni, and Platform Sources Added

- PyTorch issue 179891, B70 `get_device_properties` segfault:
  - URL: https://github.com/pytorch/pytorch/issues/179891
  - Status: mined.
  - Key detail: B70 can pass `is_available` and `device_count` while device
    properties/name or first compute can segfault. Loader/driver ABI matching
    between `libze1` and `libze-intel-gpu1` is a concrete stack gate.

- PyTorch issue 179030, newer-driver XPU segfault:
  - URL: https://github.com/pytorch/pytorch/issues/179030
  - Status: mined.
  - Key detail: reinforces that compute-runtime, Level Zero loader, and
    PyTorch XPU versions must be recorded as a matched lane.

- PyTorch issue 177714, fatal XPU OOM/device-loss:
  - URL: https://github.com/pytorch/pytorch/issues/177714
  - Status: mined.
  - Key detail: XPU can return fatal UR device-loss or out-of-resource errors
    instead of recoverable `torch.OutOfMemoryError`. Add OOM recoverability to
    the stack gate.

- PyTorch issue 161381, incorrect `mem_get_info`:
  - URL: https://github.com/pytorch/pytorch/issues/161381
  - Status: mined.
  - Key detail: `mem_get_info` can fail to reflect allocations on BMG. Compare
    PyTorch memory APIs and `xpu-smi` before trusting vLLM KV sizing.

- PyTorch issue 186548, XCCL `supportsSplitting` missing:
  - URL: https://github.com/pytorch/pytorch/issues/186548
  - Status: mined.
  - Key detail: `ProcessGroupXCCL` can block `dist.split_group` and nested
    DeviceMesh layouts before forward execution. Probe before EP/HSDP/FSDP
    experiments.

- PyTorch issues 170636 and 186350, XPU multiprocessing and Triton packaging:
  - URLs:
    - https://github.com/pytorch/pytorch/issues/170636
    - https://github.com/pytorch/pytorch/issues/186350
  - Status: mined as harness risks.
  - Key detail: XPU tensor multiprocessing reduction and `triton-xpu` package
    assumptions can break tuning or worker harnesses before model code runs.

- SGLang PR 28723, fused MoE Triton tuning on XPU:
  - URL: https://github.com/sgl-project/sglang/pull/28723
  - Status: mined.
  - Key detail: high-value source for B70 route-aware MoE tuning harnesses:
    device abstraction, explicit Ray XPU resources, XPUGraph timing, torch
    top-k fallback, and Battlemage Triton config shape.

- SGLang PR 25853, XPUGraph runner:
  - URL: https://github.com/sgl-project/sglang/pull/25853
  - Status: mined.
  - Key detail: useful graph metadata/buffer ownership pattern, but guards out
    TP/DP/PP greater than 1 and speculative inference, so it is not a direct
    Qwen TP4/DFlash fix.

- SGLang PR 26501, XPU disaggregated serving:
  - URL: https://github.com/sgl-project/sglang/pull/26501
  - Status: mined as medium-term source.
  - Key detail: staging buffers, XPU events/streams, NIXL/UCX/ZE transport,
    and current XPU IPC gaps are useful if prefill/decode disaggregation
    becomes a deliberate architecture path.

- SGLang PR 28716, XPU SYCL JIT kernels:
  - URL: https://github.com/sgl-project/sglang/pull/28716
  - Status: mined.
  - Key detail: source for BMG AOT flags, JIT cache layout, and small fused
    XPU kernels such as RMSNorm, QKNorm, RoPE, and RoPE plus KV store.

- SGLang PR 28329, XPU card-sharded harness:
  - URL: https://github.com/sgl-project/sglang/pull/28329
  - Status: mined.
  - Key detail: one process per card with `ZE_AFFINITY_MASK`, isolated caches,
    and conservative XPU concurrency ramp. Good pattern for B70 microbench CI.

- Additional SGLang XPU pattern PRs:
  - URLs:
    - https://github.com/sgl-project/sglang/pull/26679
    - https://github.com/sgl-project/sglang/pull/23534
    - https://github.com/sgl-project/sglang/pull/28646
    - https://github.com/sgl-project/sglang/pull/25936
    - https://github.com/sgl-project/sglang/pull/27544
  - Status: mined as lower-direct-value patterns.
  - Key detail: FP8 XPU fallbacks, radix-cache device helpers, BMG MLA memory
    limits, DeepSeek V4 XPU examples, and Mamba fallback handling.

- vLLM-Omni issue 2570, XPU 2026 Q2 roadmap:
  - URL: https://github.com/vllm-project/vllm-omni/issues/2570
  - Status: mined.
  - Key detail: roadmap source for XPU Graph, torch compile, sleep mode,
    prefix cache, FP8 KV, disaggregation, sequence parallel, HSDP/FSDP, and
    EPLB.

- vLLM-Omni PR 3113, XPU torch inductor:
  - URL: https://github.com/vllm-project/vllm-omni/pull/3113
  - Status: mined.
  - Key detail: XPU compile can help in an adjacent workload, but review notes
    show compile paths can still assume CUDA graph APIs.

- vLLM-Omni issue 2545, sleep-mode follow-up:
  - URL: https://github.com/vllm-project/vllm-omni/issues/2545
  - Status: mined as memory-telemetry source.
  - Key detail: XPU/NPU VRAM audit parity overlaps with B70 memory accounting
    and sleep/offload research.

- Intel LLVM issue 21741, ESIMD DPAS wrong results in large SYCL project:
  - URL: https://github.com/intel/llvm/issues/21741
  - Status: mined.
  - Key detail: B70 ESIMD DPAS flash-attention kernel can pass standalone
    tests but produce wrong answers inside a larger SYCL project. Integrated
    endpoint canaries are mandatory for local SYCL/ESIMD kernels.

- Intel LLVM issues 22025, 21873, and 17847, BMG L0/UR failures:
  - URLs:
    - https://github.com/intel/llvm/issues/22025
    - https://github.com/intel/llvm/issues/21873
    - https://github.com/intel/llvm/issues/17847
  - Status: mined.
  - Key detail: Level Zero V2, USM/memops, matrix, and graph/native-command
    failures on BMG match the error classes seen in higher-level B70 reports.

- Unified Runtime issue 2669 and Intel LLVM issue 22054, BF16 feature gaps:
  - URLs:
    - https://github.com/oneapi-src/unified-runtime/issues/2669
    - https://github.com/intel/llvm/issues/22054
  - Status: mined.
  - Key detail: BF16 conversion extension query and builtin failures can push
    B70 paths into wrong or slow fallbacks. Add BF16 feature detection to stack
    inventory.

## Source Hygiene Rules

- Prefer GitHub repos, PRs/issues, official docs, and local benchmark artifacts.
- Record exact file paths, URLs, commit IDs, and model revisions when known.
- For any performance claim, record batch/concurrency, prompt/output shape,
  quantization, hardware, graph mode, and whether correctness gates passed.
- Treat CUDA/HIP/Triton code as a pattern source, not a drop-in XPU solution.
