# Upstream Contribution Candidates

Created: 2026-06-20

Purpose: track bug fixes, validation results, docs, and optimization ideas that
could be useful upstream without creating extra repository-management chores.
This file is local-only until an item is explicitly promoted.

## Low-Overhead Rules

- Do not maintain long-lived forks as research artifacts.
- Do not open upstream issues from hunches. Require a repro, exact stack
  identity, or a concrete docs gap first.
- Prefer existing issue comments when an upstream thread already matches the
  failure.
- Prefer docs PRs or issue comments before code PRs unless the patch is small,
  isolated, and already validated locally.
- Use short-lived PR branches only when a single contribution is ready.
- Link any upstream action back here so this file remains the local source of
  truth.

## Promotion Bar

An item should not leave this folder unless it has:

- exact project and version or commit;
- exact hardware and stack identity;
- model, quantization, TP/PP, graph mode, and launch identity when performance
  is involved;
- expected versus actual behavior;
- minimal repro or exact benchmark artifact;
- correctness/canary result;
- suggested upstream action: issue, issue comment, docs PR, or code PR.

Statuses:

- `local-only`: keep as internal research or implementation guidance.
- `needs-repro`: likely useful, but not ready for upstream.
- `issue-ready`: evidence is enough to open or comment on an upstream issue.
- `doc-pr-ready`: evidence is enough for a small docs PR.
- `code-pr-ready`: patch is small, isolated, and locally validated.
- `submitted`: upstream action exists; link it here.
- `closed`: no longer worth pursuing upstream.

## Candidate Queue

### 1. B70 PyTorch/XPU Stack Canary

Target upstream:

- PyTorch XPU
- Possibly vLLM XPU docs if the canary becomes a practical serving checklist

Status: `needs-repro`

Likely action:

- Existing issue comment if our host reproduces a known failure.
- New issue only if the exact failure is not already covered.
- Docs PR only after the canary becomes stable and concise.

Why it may help upstream:

- Current B70 reports show `torch.xpu.is_available()` can pass while
  `get_device_properties`, `get_device_name`, `mem_get_info`, first compute,
  or OOM recovery fails.
- A small canary would help distinguish PyTorch/runtime stack problems from
  vLLM or model-kernel problems.

Evidence needed:

- Output from every B70 visible to the host:
  `is_available`, `device_count`, `get_device_name`,
  `get_device_properties`, `mem_get_info` before/after allocation,
  `memory_allocated`, small `tensor.to("xpu")` compute, controlled OOM
  recovery, and `xpu-smi` cross-check.
- Package inventory for kernel, compute-runtime, `libze1`,
  `libze-intel-gpu1`, IGC, GMM, oneAPI, PyTorch, Triton-XPU, vLLM, and
  `vllm-xpu-kernels`.

Local sources:

- `pytorch-sglang-platform-audit-2026-06-20.md`
- https://github.com/pytorch/pytorch/issues/179891
- https://github.com/pytorch/pytorch/issues/177714
- https://github.com/pytorch/pytorch/issues/161381
- https://github.com/pytorch/pytorch/issues/179030

### 2. Qwen/B70 Benchmark Identity Pitfall

Target upstream:

- vLLM docs or XPU docs
- Possibly vLLM issue comments when benchmark comparisons are misleading

Status: `local-only`

Likely action:

- Keep local unless we produce a concise, generalizable XPU benchmarking note.
- Promote to docs PR only if it avoids a recurring upstream confusion.

Why it may help upstream:

- Missing `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'` can silently
  put a run on a graph-none lane and make speed comparisons meaningless.
- The same class of problem can affect any XPU graph benchmark, not just this
  model.

Evidence needed:

- One clean local example with full benchmark identity showing the graph-none
  versus PIECEWISE distinction without making a loose speed comparison.
- Exact launcher log and run summary.

Local sources:

- `/home/steve/AGENTS.md`
- `qwen35-b70-options.md`
- local Qwen run summaries and launcher logs when selected.

### 3. vLLM Per-Worker `ZE_AFFINITY_MASK` Validation On B70

Target upstream:

- vLLM PR 46226 or related vLLM XPU issues

Status: `needs-repro`

Likely action:

- Comment on the relevant upstream PR/issue with exact 4x B70 validation.
- Code PR only if we find a small local fix beyond the upstream PR.

Why it may help upstream:

- Per-worker device visibility is directly relevant to B70 TP/PP stability.
- Upstream maintainers benefit from validation on real 4x Arc Pro B70 systems.

Evidence needed:

- Worker logs proving each process sees only one expected XPU.
- Same-identity Qwen canaries before and after the change.
- XCCL/oneCCL collective sanity output for representative tensor shapes.

Local sources:

- `vllm-upstream-audit-2026-06-20.md`
- https://github.com/vllm-project/vllm/pull/46226
- https://github.com/vllm-project/vllm/issues/41663

### 4. XCCL/DeviceMesh Split Probe

Target upstream:

- PyTorch distributed/XCCL

Status: `needs-repro`

Likely action:

- Comment on the existing PyTorch issue if our stack reproduces it.
- New issue only if our failure differs materially.

Why it may help upstream:

- EP, HSDP/FSDP, and nested DeviceMesh experiments can fail before model
  execution if `ProcessGroupXCCL` lacks group-splitting support.
- A small B70 repro would make the serving impact clearer.

Evidence needed:

- Minimal `dist.split_group` or DeviceMesh repro on the local B70 stack.
- Confirmation whether plain TP avoids the failure.
- Stack inventory and exact PyTorch commit/version.

Local sources:

- `pytorch-sglang-platform-audit-2026-06-20.md`
- https://github.com/pytorch/pytorch/issues/186548

### 5. vLLM-XPU-Kernels GDN/DFlash Metadata And Graph Padding

Target upstream:

- `vllm-project/vllm-xpu-kernels`
- Possibly vLLM spec-decode/GDN code if the fix lives outside the kernel repo

Status: `needs-repro`

Likely action:

- Issue or PR only after local endpoint canaries prove the change.
- If the value is just a pattern from another fork, keep it local.

Why it may help upstream:

- Qwen3.6 GDN and DFlash-style speculation need graph-padded metadata and safe
  verifier-state handling.
- Public fork audit found a high-signal GDN metadata narrowing lead that may
  not be upstreamed.

Evidence needed:

- Exact diff or cherry-pick candidate.
- Token-identical canaries for partial-accept/reject speculation.
- Same-identity benchmark only after correctness passes.

Local sources:

- `fork-audit-2026-06-20.md`
- `vllm-upstream-audit-2026-06-20.md`
- `qwen35-b70-options.md`
- https://github.com/jasonboukheir/vllm-xpu-kernels/commit/63c50713578d55a349610797788c7f3da133b2ff

### 6. Route-Aware MoE Tuning Harness For XPU

Target upstream:

- vLLM-XPU-kernels
- Intel Triton-XPU grouped-GEMM issue threads
- Possibly SGLang if we find a cross-project harness improvement

Status: `local-only`

Likely action:

- Keep local until we have captured Qwen route histograms and a reusable
  microbench.
- Comment upstream with route-distribution data if it materially informs
  grouped-GEMM tuning.

Why it may help upstream:

- Intel Triton grouped-GEMM work says real route distribution matters.
- SGLang's XPU fused-MoE tuning PR has useful harness patterns that could be
  adapted to vLLM/XPU.

Evidence needed:

- Captured Qwen route histograms for representative prompts and concurrency.
- Microbench comparing current path, Triton-XPU candidate, and SYCL/native
  oracle under the same route fixtures.

Local sources:

- `runtime-triton-collectives-audit-2026-06-20.md`
- `pytorch-sglang-platform-audit-2026-06-20.md`
- https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
- https://github.com/sgl-project/sglang/pull/28723

### 7. B70 P2P, IPC, And Host-Staged Copy Validation

Target upstream:

- Intel compute-runtime
- llm-scaler
- vLLM XPU issue threads, if vLLM is where the failure appears

Status: `needs-repro`

Likely action:

- Existing issue comment with exact checksum results.
- New issue only if we produce a minimal reproducer for a novel corruption or
  device-loss case.

Why it may help upstream:

- Multiple B70 reports fail around `zeMemOpenIpcHandle`, P2P, cross-root-port
  behavior, or device-to-device copies.
- A checksum-proven B70 matrix is more useful than endpoint-only failure logs.

Evidence needed:

- Pairwise B70 P2P checksum results.
- Host-staged fallback checksum results.
- Topology and kernel/runtime inventory.
- Clear mapping from low-level failure to vLLM or llm-scaler symptom.

Local sources:

- `runtime-triton-collectives-audit-2026-06-20.md`
- https://github.com/intel/compute-runtime/issues/935
- https://github.com/intel/llm-scaler/issues/486
- https://github.com/intel/llm-scaler/issues/489
- https://github.com/TSUMUGI-XE/b70-dual-tp2

### 8. ESIMD/SYCL Integrated-Build Correctness Rule

Target upstream:

- vLLM-XPU-kernels docs or test notes
- Intel LLVM issue comments if we reproduce a compiler/runtime behavior

Status: `local-only`

Likely action:

- Keep as local validation policy unless a local SYCL/ESIMD kernel reproduces
  standalone-pass/integrated-fail behavior.

Why it may help upstream:

- Intel LLVM reports B70 ESIMD DPAS kernels can pass standalone tests but fail
  when compiled into a large SYCL project.
- That is directly relevant to any future local attention/MoE SYCL kernel.

Evidence needed:

- Standalone microbench result.
- Integrated vLLM/vllm-xpu-kernels canary result.
- If they diverge, minimal reproduction or compiler invocation delta.

Local sources:

- `pytorch-sglang-platform-audit-2026-06-20.md`
- https://github.com/intel/llvm/issues/21741

### 9. XPU Compile/Graph CUDA-Assumption Audit

Target upstream:

- vLLM or vLLM-Omni, depending on where the assumption is found

Status: `local-only`

Likely action:

- Docs issue or small code PR only if we hit a concrete CUDA hard-code while
  enabling XPU compile or graph paths.

Why it may help upstream:

- vLLM-Omni's XPU torch-inductor work shows compile paths can still fall into
  CUDA graph assumptions.
- vLLM-XPU graph and PIECEWISE work is already sensitive to graph-mode identity
  and correctness.

Evidence needed:

- Exact stack trace or source location.
- Minimal repro independent of the full Qwen serving path if possible.
- Confirmation that an XPU-specific guard or device helper fixes it.

Local sources:

- `pytorch-sglang-platform-audit-2026-06-20.md`
- https://github.com/vllm-project/vllm-omni/pull/3113

## Suggested Contribution Flow

1. Keep the item in this file until it reaches `issue-ready`,
   `doc-pr-ready`, or `code-pr-ready`.
2. Before external action, copy the relevant evidence into a short upstream
   draft under this item.
3. If it is an issue/comment, submit directly and add the URL here.
4. If it is a PR, create a short-lived branch named for one contribution only,
   submit the PR, then avoid using that fork/branch for unrelated research.
5. If maintainers ask for follow-up that would turn into ongoing maintenance,
   decide explicitly whether it is worth doing. Default is to keep research
   moving locally.
