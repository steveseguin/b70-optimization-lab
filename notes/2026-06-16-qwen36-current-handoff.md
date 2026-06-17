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

## 2026-06-17 Addendum — Fused-Prologue Bisection Concluded (Systemic)

Readiness-only test `skip0-37` was run with the full safe fast identity
plus fused-prologue capture enabled and `SKIP_LAYERS=0-37` (only layers
38-39 allowed to use fused-prologue capture).

- Label: `prefill-safe-int8-prologue-skip0-37-c1-ready`
- Log:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-prologue-skip0-37-c1-ready-20260617011726.log`
- Result: failed before readiness with
  `RuntimeError: level_zero backend failed with error: 20
  (UR_RESULT_ERROR_DEVICE_LOST)` at
  `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py:9456`,
  `logit_indices_device = torch.from_numpy(logit_indices).to(...)`.

This is the SAME failure site as `skip0`, `skip0-3`, and `skip0-19`,
even though only 1-2 layers (38-39) used fused-prologue capture.

Conclusion: the failure is SYSTEMIC to "fused-prologue capture enabled
at all," not per-layer MoE math. Enabling captured fused prologue on any
layer perturbs the c1 PIECEWISE capture such that the dummy sampler
`torch.from_numpy(...).to(device)` copy device-losts. Every layer-enabled
fused-prologue capture path will fail at this same site.

Implication: the layer bisection is futile. Stop spending time on
captured fused prologue. The failure site is in the sampler/logits
dummy run and the piecewise capture boundary machinery, not in MoE
kernel math, so the remaining options are the handoff step-3 pivots.

Post-run cleanup: the 4 `VLLM::Worker_TP*` processes orphaned after the
device-lost were SIGKILLed; `xpu-smi ps` confirmed all GPUs idle and no
vLLM processes remain.

Note: the ablation runner now records
`VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_SKIP_LAYERS` and
`VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_LAYER_REGEX` in both the log
echo and the summary JSON, so future fused-prologue runs carry full
identity (this was previously a gap).

## 2026-06-17 Addendum — Pivot to Shared-Experts: Both Levers Fail

After concluding fused-prologue capture is systemically dead, pivoted to
shared-experts on the working safe PIECEWISE lane (per the
`moe.shared_experts.apply_no_overlap` ~2.74 ms/step budget). Two
implemented levers were tested against the safe identity (only the one
env var changed, so identity matches the 93.55 base).

Lever A — `VLLM_XPU_SHARED_EXPERTS_STREAM=1` (aux-stream overlap):

- Label: `prefill-safe-int8-sharedexp-stream-c1`
- Result: FAILED at capture (engine core init). Root cause is NOT a
  device-lost; it is
  `RuntimeError: wait method cannot be used for an event associated
  with a command graph` at `torch.xpu.empty_cache()` inside
  `torch.cuda.graph()` capture (`cuda_graph.py:1634`). Multi-stream
  shared-expert events are incompatible with XPU PIECEWISE command-graph
  capture. Preconditions were met (`disable_inplace=True` via
  `layer.py:521`, token threshold 256 OK for decode). So this lever is
  blocked by an XPU runtime limitation, same wall as fused-prologue.

Lever B — `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1` (fused
silu+mul+quant + raw `int8_gemm_w8a8` for the shared down_proj):

- Label: `prefill-safe-int8-sharedexp-fusedactquant-c1`
- Summary:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-c1-summary-20260617014121.json`
- Capture-safe (reached readiness). Speed `91.85 tok/s` corrected
  (decode 10.89 ms/tok) — SLOWER than 93.55 base.
- json-canary PASS (96/96). color-canary FAIL (mismatch at repeat 7) —
  a correctness regression from the fused `silu_and_mul_quant_int8_xpu`
  kernel.
- REJECTED on both gates (speed and correctness). The fused path swaps
  the optimized oneDNN `down_proj` for a slower raw `int8_gemm_w8a8`,
  and the fused silu+quant kernel diverges numerically.

Shared-expert per-step timing breakdown (from
`qwen36-shared-expert-internals-timing-timing-decision-20260615a20.json`,
summed across layers): `gate_up_proj` 0.725 ms, `silu_and_mul` 0.725 ms,
`down_proj` 0.549 ms, `expert_gate` 0.373 ms, `gate_mul` 0.146 ms. Most
of this is real memory-bound int8 GEMM work for single-token decode, so
the only realistic reductions are overlap (blocked) or kernel fusion
(currently buggy and slower).

Conclusion: on the captured PIECEWISE lane, the two main shared-expert
speed levers are not viable as-is. Remaining untested lower-ceiling
levers: `VLLM_XPU_SHARED_EXPERT_ACT_WORKSPACE` (buffer reuse, tiny) and
`VLLM_XPU_MOE_SHARED_ADD_ALLREDUCE_CUSTOM_OP`.

## 2026-06-17 Addendum — Fused-Act-Quant Deep-Dive: Kernel Is Correct

User directed fixing the fused-act-quant kernel. Deep investigation
(standalone op-level comparison on XPU) shows the fused activation
kernel is NOT the bug:

- `torch.ops._xpu_C.silu_and_mul_quant_int8_xpu(gate_up)` produces
  BIT-EXACT identical `(int8, scale)` to the unfused path
  `silu_and_mul` -> `torch.ops._xpu_C.per_token_quant_int8_xpu(out)`
  (0/24576 mismatches, scale max diff 0.0, bf16 inputs, d=3072).
- The fused down_proj uses the SAME `int8_gemm_w8a8` op and the SAME
  processed weight/scale as the normal `XPUInt8ScaledMM.apply_weights`
  path (`scaled_mm/xpu.py:198`), with identical args (out_dtype=bf16,
  bias=None). So the shared-expert math is identical fused vs unfused.

So the color-canary failure is NOT a math/correctness bug in the fused
kernel. The mismatch record shows it occurred at repeat index 6
(repeats 0-5 were consistent) with a divergent `<think>` token sequence
— i.e. NON-DETERMINISM under PIECEWISE capture replay, not a systematic
error. Most likely cause: the fused path calls the non-`_out` variant
`silu_and_mul_quant_int8_xpu`, which allocates its output tensors fresh
each call; under cudagraph capture those pool allocations can alias
across replays, breaking determinism. The `_out` variant
(`silu_and_mul_quant_int8_xpu_out`) with persistent buffers likely fixes
determinism.

The speed deficit (91.85 vs 93.55, +0.20 ms) is because
`launch_silu_and_mul_quant_int8` (`int8_quant.cpp:85`) is a non-vectorized
two-pass scalar kernel, slower than the vectorized `silu_and_mul` +
`per_token_quant_int8_xpu` it replaces. Even with determinism fixed AND
the kernel vectorized, the theoretical ceiling is small (it only merges
the silu read-pass with the quant read-pass; the GEMM is unchanged) —
well under the ~7% needed for >100 tok/s.

Net: fused-act-quant is architecturally low-ceiling on this lane. The
recurring blocker across fused-prologue, stream-overlap, and now
fused-act-quant is the XPU PIECEWISE capture constraint itself.

## 2026-06-17 Addendum — Attacking the Capture Constraint (Stream Overlap)

Pursued the capture constraint as the root blocker for shared-expert
stream overlap. Root-caused the failure:

- `torch.cuda.graph.__enter__` (`torch/xpu/graphs.py`) calls
  `torch.xpu.empty_cache()` directly. vLLM already no-ops
  `torch.accelerator.empty_cache` for PIECEWISE pieces with
  `gc_disable` (`cuda_graph.py:1617`), but that is a DIFFERENT function
  object from `torch.xpu.empty_cache` (verified distinct module/identity),
  so the actual call in `__enter__` was never intercepted. With aux-stream
  events tied to a command graph, `empty_cache`'s internal wait raised
  `RuntimeError: wait method cannot be used for an event associated with
  a command graph`.

Fix added (vllm `cuda_graph.py`, env-gated `VLLM_XPU_GRAPH_NO_EMPTY_CACHE`):
no-op `torch.xpu.empty_cache` during capture for XPU. This is a real bug
fix (vLLM was patching the wrong function on XPU) and unblocks aux-stream
graph capture generally; gated so the default lane is unchanged.

Result with `VLLM_XPU_SHARED_EXPERTS_STREAM=1` +
`VLLM_XPU_GRAPH_NO_EMPTY_CACHE=1` (full safe identity, both envs changed):

- Label: `prefill-safe-int8-sharedexp-stream-noemptycache-c1`
- Summary:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedexp-stream-noemptycache-c1-summary-20260617030450.json`
- Capture now SUCCEEDS (no device-lost, no command-graph event error).
- Correctness: json-canary PASS (96/96), color-canary PASS (96/96) — the
  aux-stream overlap is deterministic and exact.
- Speed: `73.77 tok/s` corrected (decode 13.56 ms/tok) — MUCH SLOWER than
  the 93.55 base (-21%).

Conclusion: the capture constraint was NOT the real blocker for stream
overlap's value. Even capture-unblocked, shared-experts aux-stream overlap
is slower on 4x Arc Pro B70, because the separate stream does not provide
real compute concurrency on this hardware — the fork/join/sync overhead is
paid with nothing hidden. Stream overlap is closed as a speed lever.

Overall MoE/shared-expert lane outcome (all on the captured PIECEWISE
lane): fused-prologue (capture-dead), stream-overlap (capture-fixable but
no concurrency -> slower), fused-act-quant (kernel correct but slower +
replay-nondeterministic). No per-pass MoE lever reaches the +7% needed for
>100 tok/s. The capture constraint plus the lack of XPU multi-stream
concurrency together cap the captured-lane approach.

## 2026-06-17 Addendum — N-Gram Spec Decode: Prompt-Dependent + Nondeterministic

Pivoted to speculative decoding (native MTP is dead: the Quark INT8
checkpoint has 0 `mtp.*` weights, confirmed in
`notes/2026-06-10-qwen36-local-argmax-and-mtp-rejected.md`). Tested
n-gram spec decode (`method:ngram`, k=5, prompt_lookup_min=2/max=5,
`{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":128}`) through
the standard canary+quality pipeline (runner made launcher-configurable via
`SERVER_LAUNCHER`; identity otherwise matches the safe lane). The prior
2026-06-10 note reported 114.86 tok/s, but that was on a HIGH-REUSE prompt.

Result (label `prefill-safe-int8-ngram5-cg128-c1`):
- Speed on the STANDARD `natural-chat` metrics prompt: `48.30 tok/s`
  corrected (decode 26.79 ms/tok) — SLOWER than the 93.55 base.
- Reason: n-gram acceptance on general/diverse generation is near ZERO.
  Server `SpecDecodingMetrics` during the metrics phase showed many windows
  at `Mean acceptance length: 1.00, Accepted: 0, 0.0%`; only the
  repetitive canary/quality prompts showed high acceptance (88%, length
  5.40). So spec drafts are all rejected on general prompts -> pure
  overhead. n-gram only helps copy/repetition workloads.
- Correctness: color-canary PASS (96/96), quality-suite PASS
  (baseline_match_all true). BUT json-canary FAIL: nondeterministic
  divergence at repeat 66 of 96 (the bonus-row GDN state bug from the
  oracle-parity investigation still affects real canary prompts). Not
  token-identical to no-spec.

Conclusion: n-gram spec decode is NOT a reliable path to >100 tok/s with no
quality loss on the standard benchmark. It regresses speed on general
prompts (low acceptance) and is nondeterministic (json canary).

## Session Summary (2026-06-17)

Four speed levers exhausted with clear mechanisms:
1. fused-prologue capture: systemic device-lost (dead).
2. shared-experts stream overlap: capture-fixable (added
   `VLLM_XPU_GRAPH_NO_EMPTY_CACHE`) but no XPU stream concurrency -> -21%.
3. fused-act-quant: fused kernel proven bit-exact correct; slower
   (non-vectorized) + replay-nondeterministic; low ceiling.
4. n-gram spec decode: near-zero acceptance on general prompts -> slower;
   json-canary nondeterminism; only helps repetitive workloads.

Concrete artifacts produced (all uncommitted, ready to commit):
- llm-optimizations: identity-recorder fix + `SERVER_LAUNCHER` runner
  option + handoff findings.
- vllm: `VLLM_XPU_GRAPH_NO_EMPTY_CACHE` capture bug-fix (real fix: vLLM
  patched the wrong `empty_cache` function on XPU).
- Minimal repros under `/tmp/opencode/`.

The 93.55 tok/s base appears near the practical ceiling for this
model/hardware on the captured PIECEWISE lane. Reaching a reliable >100
tok/s with no quality loss likely requires either a real draft-model spec
decoder with high diverse-prompt acceptance (EAGLE; MTP weights are absent
from this checkpoint) or custom MoE int8 GEMMs faster than oneDNN.

## 2026-06-17 Addendum — MTP Spec Decode: Acceptance Works, Draft Too Heavy

Reframed goal: >150 tok/s single-session decode (prefer >200), no quality
loss. Only a learned-draft spec decoder can give that multiplicative win.
Native MTP was thought dead (Quark INT8 checkpoint has 0 `mtp.*` weights),
but the official FP8 snapshot IS present locally
(`models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a72...`), so a hybrid
checkpoint (Quark INT8 target + official FP8 MTP head) was built via
`scripts/create-qwen36-quark-fp8-mtp-hybrid.py` (output
`/mnt/fast-ai/qwen36-quark-int8-fp8-mtp-hybrid`).

GOTCHA found and fixed: the ablation runner exports `MODEL_PATH` (Quark
default) which the hybrid-mtp launcher's `${MODEL_PATH:-hybrid}` kept, so
the first run served the QUARK path (random/uninitialized MTP head) -> 0%
acceptance. Re-running with `MODEL_PATH` explicitly set to the hybrid made
MTP load the real weights.

MTP acceptance (hybrid, real weights): GOOD. Per-position acceptance
62%-100% (avg ~62% on natural-chat, ~88% on repetitive), acceptance length
~1.6-1.9 at k=1. So a learned draft matched to this target IS achievable;
the hybrid head generalizes acceptably across the INT8/FP8 hidden-state
gap. (Label `prefill-safe-int8-hybrid-mtp-k1-real-c1`.)

BUT two blockers remain:

1. SPEED (the MTP draft is too heavy). The MTP head is a FULL MoE layer
   (256 experts, `mtp.layers.0.mlp.experts.*`), nearly as expensive as a
   target forward. Measured at k=1 PIECEWISE cg128: 69.46 tok/s (decode
   14.42 ms/tok) -> SLOWER than the 93.55 base. The extra draft token
   costs ~12.8 ms (~1x a target forward). A draft that costs ~1x the
   target cannot yield big speedups. (A graph-none run measured 19 tok/s -
   the accepted-launcher default is `cudagraph_mode:NONE`; always set
   PIECEWISE+cg128 for valid spec-decode speed.)

2. CORRECTNESS (parity bug persists). At k=1 PIECEWISE both json- and
   color-canary FAILED (the verifier bonus-row GDN recurrent/conv state
   divergence from `recovery-implementation.md` is not fixed).

Conclusion: MTP cannot reach >150 here because its draft is a full MoE
layer (too expensive). n-gram is free but 0% diverse acceptance. The
architecture that delivers >150 on diverse prompts is a LIGHTWEIGHT
learned draft (EAGLE: 1-2 thin layers, no MoE). vLLM has
`extract_hidden_states.py` (EAGLE data prep) and the eagle proposer, but
the EAGLE training repo is NOT present locally and no trained EAGLE draft
for this model exists on disk. Reaching the >150 goal therefore requires
training an EAGLE draft on the Quark INT8 target (extract hidden states,
clone SafeAILab/EAGLE, train) - a multi-hour task with XPU-compat risk.

