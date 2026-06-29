# Qwen 35B on 4x B70 Findings

Created: 2026-06-20

This folder is a research scratchpad for legitimate ways to improve
Qwen3.6-35B-A3B / Qwen 35B performance on 4x Intel Arc Pro B70 GPUs.

Scope:

- Identify high-value ideas before implementation.
- Tie each idea to primary sources or local benchmark evidence.
- Prefer porting proven upstream work over inventing new mechanisms.
- Preserve the Qwen benchmark identity rule from `/home/steve/AGENTS.md` and
  the repo workflow notes in `/home/steve/llm-optimizations/AGENTS.md`.

Files:

- `sources.md` - durable source registry and source-mining backlog.
- `qwen35-b70-options.md` - prioritized optimization options, expected value,
  porting work, risks, and suggested validation gates.
- `deep-dive-2026-06-20.md` - deeper source pass covering LocalMaxxing,
  B70 community repos, vLLM/vLLM-XPU PRs, forks, and driver/runtime gaps.
- `fork-audit-2026-06-20.md` - exhaustive public fork audit for
  `vllm-project/vllm-xpu-kernels`, including ahead-fork triage.
- `vllm-upstream-audit-2026-06-20.md` - upstream `vllm` issue/PR and local
  code audit, including B70 multi-GPU control-plane leads, GDN/DFlash gaps,
  and Triton/XPU port candidates.
- `runtime-triton-collectives-audit-2026-06-20.md` - deeper audit of
  oneAPI/Level Zero runtime reports, Triton-XPU grouped-GEMM and attention
  work, `llm-scaler` B70 failures, and adjacent engine collectives patterns.
- `pytorch-sglang-platform-audit-2026-06-20.md` - PyTorch XPU, XCCL,
  SGLang, vLLM-Omni, Intel LLVM, and Unified Runtime source pass for B70
  platform failures and adjacent XPU implementation patterns.
- `upstream-candidates.md` - local-only queue for bugs, docs, validation
  results, and small fixes that might be worth contributing upstream once they
  have enough evidence.
- `local-friction-fixes-2026-06-20.md` - local environment friction pass:
  `python` command fix, oneAPI sourcing traps, profiling-tool availability,
  Level Zero loader drift, and safe follow-up candidates.

Current read:

- The best current non-speculative speed path still points at XPU-native MoE
  and runtime overhead, not random launch flags.
- The cleanest near-term upstream bakeoff is vLLM-XPU-kernels v0.1.10 plus a
  small set of targeted PRs, especially MoE workspace/invalid-row work,
  GDN/DFlash graph-padding work, and B70 attention/KV fixes.
- An exhaustive `vllm-xpu-kernels` fork audit found 76 public forks: 6
  identical to upstream head, 60 stale/no-ahead default branches, and 10 ahead
  forks. The high-signal fork lead is Jason Boukheir's GDN metadata narrowing;
  several older forks are only medium-value pattern sources.
- The best correctness unlock for MTP/DFlash/EAGLE-style speculation is
  ReplaySSM-style GDN spec verification, ported to XPU without Triton.
- DFlash is now a legitimate Qwen3.6-35B source, but it is a proposer path.
  On B70 it still needs XPU-safe verifier state handling, DFlash metadata, and
  attention/backend compatibility before it is a performance path.
- The local stack is already on oneAPI 2026.0 and UMD 26.18.38308.1, but
  upstream and the configured PPA expose newer candidate runtime profiles that
  deserve a controlled bakeoff rather than an in-place upgrade.
- For `vllm-xpu-kernels`, the public fork audit is complete for the 76 public
  default-branch forks GitHub returned on 2026-06-20. For upstream `vllm`
  itself, use issue/PR search and local code presence checks rather than trying
  to enumerate the much larger fork network.
- The newest high-value upstream `vllm` leads are per-worker
  `ZE_AFFINITY_MASK` isolation, a draft torchcomms/XCCL communicator path,
  Qwen GDN `in_proj_ba` fusion, XPU tensor-descriptor stores in Mamba SSD, and
  DFlash/mixed-KV/spec-decode plumbing.
- The newest runtime read is that B70 TP/PP stability needs a low-level stack
  matrix before speed claims: kernel 7.1+ and compute-runtime
  `26.22.38646.4` plus IGC `2.36.3` are serious candidates, but P2P must be
  checksum-proven and host-staged fallback should be measured.
- The strongest Triton-XPU MoE lead is dense/pre-grouped expert layout with 2D
  block IO or SYCL-TLA as an oracle. A direct CUDA gather-style port is likely
  a low-value path on Xe2.
- PyTorch XPU itself now needs a first-class B70 stack gate:
  `get_device_properties`, `get_device_name`, `mem_get_info`, small
  `tensor.to("xpu")`, OOM recoverability, and loader/driver ABI matching can
  fail independently of vLLM kernels.
- XCCL/DeviceMesh split support is a likely platform blocker for EP/HSDP/FSDP
  or nested-mesh work. Probe it before interpreting any future expert-parallel
  layout result.
- SGLang is the best adjacent source for XPU graph, MoE tuning, disaggregation,
  and card-sharded harness patterns. It is not a drop-in replacement for this
  lane, but several PRs are strong implementation guides.
