# Qwen 3.6 35B INT8 XPU Optimization Handoff

Date: 2026-06-16

## Current Goal

Get `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` on 4x Intel Arc Pro B70
well above `100 tok/s` single-request decode with no quality loss.

Quality loss is not acceptable. Any promoted change must be token/canary/quality
validated against the current safe fast identity before being treated as a win.

## Benchmark Identity Rule

Do not compare runs unless the full run identity matches.

Critical identity fields:

- model path and revision
- quantization
- TP/PP/concurrency
- `COMPILATION_CONFIG`
- `GPU_MEMORY_UTILIZATION`
- `XPU_GRAPH`, `VLLM_XPU_ENABLE_XPU_GRAPH`
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM`, `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE`
- `VLLM_XPU_GDN_NATIVE_FALLBACK`
- sampler/top-k fallback flags
- async scheduling / `VLLM_EXTRA_ARGS`
- diagnostic flags

Previous mistake to avoid: a run missing
`COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'` defaulted to graph-none
and measured around `15 tok/s`, which was incorrectly compared against the fast
PIECEWISE forced-comm lane.

Known fast-but-unsafe historical baseline: PIECEWISE forced-comm graph lane at
about `93.45 tok/s`.

Current validated safe research base:

- Summary:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-summary-20260615a13deep2.json`
- Corrected output speed: `93.55054235558917 tok/s`
- Decode time: `10.689885 ms/token`
- TTFT: `187.3366 ms`
- Gates passed: metrics, JSON `128/128`, color `256/256`, quality suite,
  baseline match, long-context pass.

## Current Safe Fast Identity

Model:

`/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`

Core settings:

```bash
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1
GPU_MEMORY_UTILIZATION=0.90
VLLM_EXTRA_ARGS='--uvicorn-log-level warning'
```

## Where I Am Right Now

The latest work is focused on the fused W8A8 MoE prologue path, because timing
shows MoE/shared-expert work dominates the single-request decode budget.

Important timing artifact:

- `/home/steve/llm-optimizations/data/qwen36-shared-expert-internals-timing-timing-decision-20260615a20.json`

Timing conclusion from that artifact:

- `forward_total` roughly `5.53 ms`
- `model_forward` roughly `5.48 ms`
- `moe.quant_method_total` roughly `4.75 ms`
- `moe.shared_experts.apply_no_overlap` roughly `2.74 ms`
- `moe.apply` roughly `1.60 ms`
- `xpu_moe.fused_moe_call` roughly `1.02 ms`
- Collectives are not the main wall for the current c1 path.

So the current high-upside branch is still MoE/shared-expert structural work,
not TP topology or sampler-only work.

## Latest Fused-Prologue Findings

I added a layer skip/include gate for fused prologue capture so we can bisect
which layers poison PIECEWISE graph capture.

Code changed:

- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
- `/home/steve/src/vllm/vllm/model_executor/layers/quantization/quark/quark_moe.py`

New env vars:

```bash
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_SKIP_LAYERS
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_LAYER_REGEX
```

Syntax checks passed before the latest endpoint tests:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile /home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile /home/steve/src/vllm/vllm/model_executor/layers/quantization/quark/quark_moe.py
```

Latest endpoint readiness tests:

1. `skip0`
   - Label: `prefill-safe-int8-prologue-skip0-c1-ready`
   - Log:
     `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-prologue-skip0-c1-ready-20260616prolskip0ready1.log`
   - Result: failed before readiness with `UR_RESULT_ERROR_DEVICE_LOST`
   - Failure site:
     `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py:9456`
     copying `logit_indices_device = torch.from_numpy(logit_indices).to(...)`
     during c1 PIECEWISE graph capture.

2. `skip0-3`
   - Label: `prefill-safe-int8-prologue-skip0-3-c1-ready`
   - Log:
     `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-prologue-skip0-3-c1-ready-20260616prolskip03ready1.log`
   - Result: failed before readiness with the same `UR_RESULT_ERROR_DEVICE_LOST`
     at the same dummy `logit_indices` copy during c1 graph capture.
   - Failed run left workers alive; I killed those exact orphaned PIDs. A later
     `xpu-smi ps` showed no vLLM workers left.

3. `skip0-39`
   - Label: `prefill-safe-int8-prologue-skipall-c1-ready`
   - Summary:
     `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-prologue-skipall-c1-ready-summary-20260616prolskipallready1.json`
   - Log:
     `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-prologue-skipall-c1-ready-20260616prolskipallready1.log`
   - Result: passed readiness-only run.
   - Meaning: the layer gate works, and the surrounding W8A8/middle-layerlet
     flags are not enough by themselves to crash capture.

4. `skip0-19`
   - Label: `prefill-safe-int8-prologue-skip0-19-c1-ready`
   - Log:
     `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-prologue-skip0-19-c1-ready-20260616prolskip019ready1.log`
   - Result: failed with `UR_RESULT_ERROR_DEVICE_LOST`, then the API server
     timed out waiting for engine core startup.
   - No summary file was emitted.
   - Latest `xpu-smi ps` after failure showed only `xpu-smi`, no vLLM workers.

Interpretation:

- Fused prologue graph capture is still unsafe if any tested upper-half layer
  remains enabled.
- Skipping all layers passes, so the failure is tied to captured fused-prologue
  usage, not the launch identity as a whole.
- Current evidence points to graph-captured prologue state or capture-time
  driver/runtime interaction, not standalone MoE math.

## Reduced Reproducer State

Main reproducer:

- `/home/steve/llm-optimizations/scripts/repro-qwen36-prologue-tp4-capture.py`

Recently added features:

- `--endpoint-context`
- `--compile-wrapper`
- `--workspace-manager`
- `--custom-op-wrapper`
- endpoint-like workspace allocation using vLLM `WorkspaceManager`
- local opaque custom op via `direct_register_custom_op`

Passing reduced artifacts:

- `/home/steve/llm-optimizations/data/qwen36-prologue-endpoint-context-workspace-r1-20260616b.json`
- `/home/steve/llm-optimizations/data/qwen36-prologue-endpoint-context-workspace-tp4-l1-20260616a.json`
- `/home/steve/llm-optimizations/data/qwen36-prologue-endpoint-context-workspace-tp4-l40-prewarm8192-20260616a.json`
- `/home/steve/llm-optimizations/data/qwen36-prologue-endpoint-context-workspace-compile-tp4-l1-20260616a.json`
- `/home/steve/llm-optimizations/data/qwen36-prologue-endpoint-context-workspace-compile-tp4-l40-prewarm8192-20260616a.json`
- `/home/steve/llm-optimizations/data/qwen36-prologue-customop-workspace-r1-20260616b.json`
- `/home/steve/llm-optimizations/data/qwen36-prologue-customop-workspace-tp4-l1-20260616a.json`
- `/home/steve/llm-optimizations/data/qwen36-prologue-customop-workspace-tp4-l40-prewarm8192-20260616a.json`
- `/home/steve/llm-optimizations/data/qwen36-prologue-customop-workspace-compile-tp4-l40-prewarm8192-20260616a.json`

Meaning:

- The reduced replay covers kernel sequence, TP4, prewarm allocator,
  endpoint-like ops, WorkspaceManager, opaque custom op, and `torch.compile`.
- It still passes.
- The full endpoint failure is likely due to full-model graph capture state,
  graph runtime state, or interaction with surrounding endpoint capture logic.

## Files I Am Actively Using

Optimization notes and plans:

- `/home/steve/llm-optimizations/notes/2026-06-14-qwen36-recovery-implementation.md`
- `/home/steve/suggestions.md`
- `/home/steve/AGENTS.md`
- `/home/steve/llm-optimizations/AGENTS.md`

Runners and launchers:

- `/home/steve/llm-optimizations/scripts/run-qwen36-ablation-candidate.sh`
- `/home/steve/llm-optimizations/scripts/launch-qwen36-quark-int8-accepted.sh`
- `/home/steve/llm-optimizations/scripts/run-qwen36-decisive-timing.sh`
- `/home/steve/llm-optimizations/scripts/qwen36-timing-family-decision.py`
- `/home/steve/llm-optimizations/scripts/qwen36-ablation-report.py`
- `/home/steve/llm-optimizations/scripts/run-qwen36-oracle-parity-gate.sh`

Current reproducer:

- `/home/steve/llm-optimizations/scripts/repro-qwen36-prologue-tp4-capture.py`

vLLM Python code:

- `/home/steve/src/vllm/vllm/model_executor/layers/quantization/quark/quark_moe.py`
- `/home/steve/src/vllm/vllm/model_executor/layers/fused_moe/experts/xpu_moe.py`
- `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`
- `/home/steve/src/vllm/vllm/compilation/cuda_graph.py`

XPU kernel bridge and native code:

- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/moe_layerlet.cpp`
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/ops.h`
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/torch_bindings.cpp`
- `/home/steve/src/vllm-xpu-kernels/CMakeLists.txt`

Important patch directory:

- `/home/steve/llm-optimizations/patches/`

## What I Intend To Do Next

Immediate next steps:

1. Finish bisection of fused prologue capture safety.
   - Since `skip0-19` failed and `skip0-39` passed, next likely tests are
     ranges that keep progressively fewer high layers enabled:
     `skip0-29`, `skip0-34`, `skip0-37`, then single-layer enables if needed.
   - These are readiness-only tests first.
   - If a non-all skip range reaches readiness, promote it to metrics and
     canaries before making any speed claim.

2. Add live ABI/context logging only if bisection is ambiguous.
   - Candidate envs:
     `VLLM_XPU_MOE_LIVE_ABI_FILE=/home/steve/llm-optimizations/data/...jsonl`
     and `VLLM_XPU_MOE_LIVE_ABI_MAX_LINES=2000`.
   - Use this only when necessary because it adds overhead.

3. If every layer-enabled fused-prologue capture path fails, stop spending
   time on captured fused prologue and pivot to one of:
   - persistent MoE layerlet that avoids graph-captured prologue state
   - exact oracle k=1/k2 speculation parity repair
   - graph capture alias/lifetime tracing in `cuda_graph.py`

4. Keep notes and patches current.
   - Save diffs for the reproducer update.
   - Save diffs for the fused-prologue layer gate.
   - Update `/home/steve/suggestions.md` and
     `/home/steve/llm-optimizations/notes/2026-06-14-qwen36-recovery-implementation.md`
     after each meaningful result.

Promotion rules:

- Do not promote readiness-only tests.
- Do not promote metrics-only tests.
- A candidate has to beat the current `93.55 tok/s` base and pass canaries and
  quality gates before it matters.
- If speed changes unexpectedly, first diff run identity and launcher logs
  against the safe base.

## Current Process State

After the latest failed `skip0-19` run, I checked `xpu-smi ps`.

Observed state:

- no vLLM API server
- no EngineCore
- no VLLM worker processes
- only `xpu-smi` appeared while checking

So the machine was clean at the time this file was written.

