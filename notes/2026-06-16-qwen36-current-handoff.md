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

2026-06-19 update: the latest decisive no-async TP2 PIECEWISE trace changed
the immediate priority. MoE is still the largest model-forward family, but the
accepted no-async decode path is also paying a large sampled-token
materialization cost after sampling.

Diagnostic identity:

```bash
TP_SIZE=2
ONEAPI_DEVICE_SELECTOR=level_zero:0,1
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill
VLLM_EXTRA_ARGS='--no-async-scheduling --uvicorn-log-level warning'
```

New diagnostic artifacts:

- `/home/steve/llm-optimizations/data/qwen36-stage-boundary-noasync-tp2-20260619stage1.log`
- `/home/steve/llm-optimizations/data/qwen36-stage-boundary-noasync-tp2-p512o128-20260619stage1.json`
- `/home/steve/llm-optimizations/data/qwen36-stage-boundary-noasync-tp2-timing-summary-20260619stage1.json`
- `/home/steve/llm-optimizations/data/qwen36-sync-to-list-noasync-tp2-p512o128-20260619tolist1.json`
- `/home/steve/llm-optimizations/data/qwen36-sync-to-list-nosync-noasync-tp2-p512o128-20260619tolist0.json`

Key finding:

- Diagnostic p512/o128 corrected decode: `83.80 tok/s`.
- Stage trace shows steady `forward_end` around `5.25 ms`.
- `bookkeeping_sync` is around `4.67 ms`.
- Almost all of that is `gpu_model_runner.bookkeeping_to_list`, around
  `4.62 ms`, where sampled token IDs are copied/materialized to CPU.
- Existing `_to_list` variants did not remove the wall:
  - `VLLM_XPU_SYNC_TO_LIST=1`, pre-copy sync on: `83.58 tok/s`.
  - `VLLM_XPU_SYNC_TO_LIST=1`, pre-copy sync off: `84.55 tok/s`.

Implication:

The next high-upside exact path is output materialization overlap/removal,
especially repairing async scheduling correctness or building a narrower
deferred sampled-token output path. Exact MoE/shared-expert work remains
important, but it cannot by itself reach the target while `_to_list` costs
about `4.6 ms/token` in the safe no-async path.

Async isolation results:

- `async-fast-outputids-tp2`, PIECEWISE, async, fast output-id repair:
  JSON failed at repeat `21`, color passed.
- `async-refresh-prev-sampled-tp2`, PIECEWISE, async, refreshed
  `prev_sampled_token_ids` tensor reference each step:
  JSON failed at repeat `21`, color passed.
- `async-gdn-decode-prefill-tp2`, PIECEWISE, async, native GDN for decode and
  prefill:
  JSON failed at repeat `31`, color passed.
- `async-sync-after-zero-tp2`, PIECEWISE, async, sync after fresh block zero:
  JSON failed at repeat `21`, color passed.
- `async-sync-output-copy-tp2`, PIECEWISE, async, synchronous output copy:
  JSON failed at repeat `21`, color passed.
- `async-sync-before-return-tp2`, PIECEWISE, async, full XPU sync before
  returning async output:
  JSON failed at repeat `21`, color passed.
- `async-graphnone-tp2`, graph-none, async:
  JSON passed `40/40`, color passed `8/8`.

Follow-up async/PIECEWISE replay isolation:

- `async-clear-on-prefill-tp2`, async, PIECEWISE, clear captured graphs on
  every new prefill:
  rejected. It crashed before a valid canary response with
  `beginAllocateToPool: already recording to mempool_id`.
- `async-initial4-eager-tp2`, async, PIECEWISE, first four decode forwards
  eager for each fresh request:
  rejected. JSON failed at repeat `60` with
  `{"answer":"42 widgets","unit":"widgets"}`; color passed `16/16`.
- `async-clone-sampled-ids-tp2`, async, PIECEWISE, clone sampled token IDs
  before async reuse:
  rejected. JSON failed at repeat `22`; color passed.
- `async-sync-replay-tp2`, async, PIECEWISE, synchronize around every graph
  replay:
  rejected. JSON failed at repeat `22`; color passed.
- `async-real-comm-capture-tp2`, async, PIECEWISE, forced comm graph with
  `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0`:
  rejected. Workers died during startup before readiness.
- `async-eager-every8req-tp2`, async, PIECEWISE, all decode replay eager for
  every eighth fresh request:
  accepted as a correctness workaround. JSON passed `96/96`; color passed
  `16/16`.
- `async-eager-every8req-tp2-metrics`, same identity as the passing `N=8`
  canary:
  corrected decode `83.35363772782296 tok/s`, decode
  `12.00305433894755 ms/token`.
- `async-eager-every16req-tp2`, async, PIECEWISE, all decode replay eager for
  every sixteenth fresh request:
  rejected. JSON passed `96/96`, but color failed at repeat `12`.

Interpretation:

- Async scheduler semantics can be correct: graph-none async passes the canary.
- The repeated JSON corruption requires async plus PIECEWISE replay.
- The first bad visible token is produced for the same prompt and same visible
  prefix immediately after `{"answer`, so output serialization and simple
  sampled-token CPU repair are not the root cause.
- Periodic full-request eager decode with `N=8` is the only passing
  async/PIECEWISE workaround found so far, but it does not improve the
  single-request decode lane versus the safe no-async baseline. It is useful
  as a correctness control and reliability fallback, not as the `>150 tok/s`
  path.
- Simple fences, sampled-token cloning, first-token eagering, graph clearing,
  and real communicator capture are closed for now.
- Next branch: return to exact structural speed work, especially graph-safe
  fused shared-expert/routed MoE boundaries or a larger persistent W8A8
  layerlet, with async `N=8` available only if a later endpoint patch needs a
  quality-safe async control.

Older context: before this trace, the work was focused on the fused W8A8 MoE
prologue path, because earlier family timing showed MoE/shared-expert work
dominating the single-request decode budget.

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

## 2026-06-18 Update: Spec Parity And EAGLE Data Path

The current credible path to `>150 tok/s` single-session decode without quality
loss is still trained EAGLE speculation. Other measured routes either failed
quality gates or lost too much speed. The verifier/spec-state work has moved:

- Correct controlled verifier path:
  `VLLM_XPU_SPEC_DECODE_DRAFT_ONLY=1`, serial-packed GDN, scheduler tail
  fallback, and accepted running conv/SSM state promotion.
- Oracle k=4 and k=8 are token-identical to the no-spec fixture with 100%
  oracle acceptance. k=8 artifact:
  `/home/steve/llm-optimizations/data/qwen36-oracle-k8-draftonly-serialgdnpacked-promoteconv-tailfallback-currentbaseline-eager-tp2-20260618cb-candidate.json`.
- The old real n-gram k=8 fast-lane attempt is rejected. It reached the server
  but serial GDN plus real n-gram acceptance was effectively unusable:
  roughly `0.6-3 tok/s` and only the first group accepted `5/8` draft tokens.
  Do not promote that route.

New EAGLE data export support was added in
`/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py` behind opt-in envs:

```bash
VLLM_XPU_EAGLE_DATA_DUMP_DIR=<dir>
VLLM_XPU_EAGLE_DATA_DUMP_RANK=0
VLLM_XPU_EAGLE_DATA_DUMP_MAX_STEPS=<n>
VLLM_XPU_EAGLE_DATA_DUMP_DTYPE=bfloat16
VLLM_XPU_EAGLE_DATA_DUMP_SINGLE_TOKEN_ONLY=1
```

Normal inference is unchanged when these envs are unset. Dump shards are
stitched by:

`/home/steve/llm-optimizations/scripts/build-qwen36-eagle-dataset-from-dump.py`

Smoke results:

- TP4 graph-none dump startup failed before readiness with a Level Zero
  device-lost error while creating an attention quant scale tensor, before the
  dump code ran. Log:
  `/home/steve/llm-optimizations/data/qwen36-eagle-hidden-dump-smoke-20260618d.log`.
- TP2 graph-none smoke on cards `0,1` succeeded. Dump dir:
  `/home/steve/llm-optimizations/data/qwen36-eagle-hidden-dump-smoke-tp2-20260618e`.
- TP2 smoke identity: Quark W8A8 INT8 target
  `cced56592e8c8935f8220836b4baa04dfd389118`, TP2, 32k max model length,
  `COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'`, no async, `MAX_NUM_SEQS=2`,
  `MAX_NUM_BATCHED_TOKENS=1024`, `GPU_MEMORY_UTILIZATION=0.82`.
- The TP2 smoke throughput is not a performance result because it was
  graph-none and first-request only. It was used only to validate EAGLE data
  export.
- Dataset summary:
  `/home/steve/llm-optimizations/data/qwen36-eagle-hidden-dataset-smoke-tp2-20260618e-summary.json`.
  It produced `64` usable rows, `63` continuity matches, `0` continuity breaks,
  and one stitched `.pt` sample.
- First stitched sample:
  `/home/steve/llm-optimizations/data/qwen36-eagle-hidden-dataset-smoke-tp2-20260618e/sample-000000-cmpl-911c7a5dc7a3503b-0-907523cf.pt`
  with hidden state shape `(64, 2048)` in BF16.

Current implementation direction:

1. Use vLLM's existing `method:"eagle"` path first, not EAGLE3. It wraps a
   plain Llama-style draft as `EagleLlamaForCausalLM`.
2. Draft config should use hidden size `2048`, vocab size `248320`, and a
   tiny one-layer Llama decoder. vLLM's simple EAGLE model consumes
   `[token_embedding, target_hidden_state]` through `model.fc`.
3. Build a loadable smoke checkpoint first, then train it from the dumped
   target hidden states. Only after it loads and produces non-trivial
   acceptance should we scale data generation and run PIECEWISE TP4 speed gates.

## 2026-06-18 Update: EAGLE-1 Loader Smoke

Created a reusable smoke-checkpoint generator:

`/home/steve/llm-optimizations/scripts/create-qwen36-eagle1-smoke-checkpoint.py`

Generated draft:

`/home/steve/llm-optimizations/data/qwen36-eagle1-smoke-draft-20260618a`

Checkpoint properties:

- one Llama-style EAGLE layer;
- `hidden_size=2048`, `intermediate_size=4096`;
- `num_attention_heads=16`, `num_key_value_heads=2`, `head_dim=128`;
- `vocab_size=248320`;
- about `43M` BF16 parameters;
- intentionally omits `embed_tokens` and `lm_head` so vLLM shares the target
  modules.

Loader/runtime smoke:

- First TP2 launch:
  `/home/steve/llm-optimizations/data/qwen36-eagle1-smoke-load-tp2-20260618a.log`
  failed before model/draft loading with a oneCCL/SYCL
  `PersistentDeviceCodeCache::getItemFromDisc` segfault during early TP2
  allreduce.
- Retry with `SYCL_CACHE_PERSISTENT=0`:
  `/home/steve/llm-optimizations/data/qwen36-eagle1-smoke-load-tp2-20260618b.log`
  reached readiness.
- vLLM loaded the target and drafter, and logged target sharing on both ranks:
  `Detected EAGLE model without its own embed_tokens...` and
  `Detected EAGLE model without its own lm_head...`.
- Short completion request succeeded through the EAGLE proposer/verifier path.
  Since the draft is random, metrics correctly showed `Drafted: 1 tokens`,
  `Accepted: 0 tokens`, acceptance `0.0%`.

Conclusion:

The local EAGLE-1 checkpoint format is loadable and executable on XPU. The next
required step is a real trainer that writes the same checkpoint format from the
Quark INT8 hidden-state dataset, then a TP2 acceptance smoke, then larger data
export/training before any TP4 PIECEWISE performance gate.

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

## 2026-06-18 Addendum — Restored Oracle Identity + Native Prefill State Failure

Important re-anchor:

- The token-exact oracle fixture is the **serial GDN identity**, not the
  generic/native-spec identity. The identity needs:
  `VLLM_XPU_SPEC_DECODE_DRAFT_ONLY=1`,
  `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`,
  `VLLM_XPU_GDN_SERIAL_SPEC_PACKED_DECODE=1`,
  `VLLM_XPU_GDN_SERIAL_SPEC_CONV=1`,
  `VLLM_XPU_GDN_SPEC_PROMOTE_RUNNING_AFTER_SPEC=1`, and
  `VLLM_XPU_GDN_SPEC_PROMOTE_CONV_STATE=1`.
- Reproduced on current tree:
  `qwen36-oracle-k8-draftonly-serial-restoredidentity-currenttree-eager-tp2-20260618b`
  has `baseline_match_all=true`, first diff `null`, 24/24 accepted, 100%
  full-accept rows. The parity gate still reports replay-accounting
  mismatches, but token output is exact.
- A misleading control without the serial flags
  (`qwen36-oracle-k8-draftonly-serialgdn-nopostprocess-control-currenttree-eager-tp2-20260618b`)
  failed at token 18 with 16/32 accepted. Do not use this as evidence against
  the serial oracle path; it was the wrong identity.

Failed native-prefill bridge attempts:

- `qwen36-oracle-k8-draftonly-nativeprefill-allornothing-rollback-currenttree-eager-tp2-20260618b`:
  all-or-nothing reduced the third partial row to 0 accepted and preempted,
  but output still diverged at token 17. Scheduler rollback alone cannot make
  native-prefill safe.
- `qwen36-oracle-k8-draftonly-nativeprefill-allornothing-finalpromote-currenttree-eager-tp2-20260618b`:
  enabling final promotion plus conv-state promotion did not help; same first
  diff at token 17.
- `qwen36-oracle-k8-draftonly-nativeprefill-replaycols-allornothing-finalpromote-currenttree-eager-tp2-20260618b`:
  replayed output state columns worsened acceptance (8/16) and still diverged
  at token 17.

Conclusion:

- The current native-prefill sequence is not serial-equivalent even after two
  full accepted groups when control returns to ordinary decode. It is not only
  a partial-accept commit issue; full accepted groups do not leave a safe
  running GDN state for later fallback/recovery decode.
- Do not spend more time on scheduler-only all-or-nothing workarounds for this
  path. The next viable correctness work is to repair native-prefill state
  generation/promotion itself, or to optimize the token-exact serial GDN path.

Postprocess experiment status:

- Added gated `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=1` helper in
  `vllm/v1/worker/mamba_utils.py` and runner hook in
  `vllm/v1/worker/gpu_model_runner.py`.
- The hook now skips full-accept rows by default and avoids globally clobbering
  accepted-token counts. It remains diagnostic only. Do not enable it in
  accepted benchmark identities until a serial-identity test with the hook also
  passes token parity.

## 2026-06-18 Addendum 2 — Gate Semantics Fixed, Native Verifier Still Unsafe

Serial correctness anchor:

- Current-tree serial GDN control
  `qwen36-oracle-k8-draftonly-serial-restoredidentity-currenttree-eager-tp2-20260618e`
  emitted the accepted no-spec token stream exactly (`first_diff=null`, 32/32
  output tokens match) with spec activity (`24/24` accepted, 100%, 3 rows).
- The original gate failed only because replay accounting reported 3 diagnostic
  mismatches. Generated tokens, suppressed follow-up schedule, and suppressed
  accept checks were clean.
- Added explicit checker option
  `--allow-replay-accounting-mismatch` and wrapper env
  `ALLOW_REPLAY_ACCOUNTING_MISMATCH=1`. Default behavior remains strict.
- Offline re-gate artifact:
  `data/qwen36-oracle-k8-draftonly-serial-restoredidentity-currenttree-eager-tp2-20260618e-allowacct-gate-summary.json`
  passed exact mode. Use this option only for known accounting-only trace noise,
  not for token or suppressed-follow-up failures.

Native verifier probes after the restored serial anchor:

- `qwen36-oracle-k8-draftonly-nativeprefill-exactstatereplay-offset1-manualconv-nofinalpromote-allornothing-postprocess-currenttree-eager-tp2-20260618e`:
  failed at token 17. All-or-nothing is not sufficient.
- `qwen36-oracle-k8-draftonly-nativeprefill-exactstatereplay-offset1-manualconv-nofinalpromote-nopreemptreject-postprocess-currenttree-eager-tp2-20260618e`:
  failed at token 24, immediately after accepting `... 271, 248068`.
- `qwen36-oracle-k8-draftonly-nativeprefill-exactstatereplay-offset1-manualconv-writeoutputs-nofinalpromote-postprocess-currenttree-eager-tp2-20260618e`:
  failed at token 17. Python/FLA replay outputs are not equivalent to the native
  safe output lane.
- `qwen36-oracle-k8-draftonly-nativeprefill-exactstatereplay-offset1-nativedecode-writeoutputs-nofinalpromote-postprocess-currenttree-eager-tp2-20260618e`:
  failed at token 17. Native per-position replay output write also worsened.
- `qwen36-oracle-k7-draftonly-nativeprefill-exactstatereplay-offset1-manualconv-nofinalpromote-postprocess-currenttree-eager-tp2-20260618e`:
  failed at token 24. The issue is not simply k=8 depth; it is a native
  verifier/state/logit boundary around the `248068` special token region.

Current interpretation:

- Do not enable the new output-write diagnostics in accepted identities:
  `VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_EXACT_REPLAY_WRITE_OUTPUTS=1` and
  `VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_EXACT_REPLAY_NATIVE_DECODE=1` both failed.
- The token-exact path is the serial GDN verifier path. The next performance
  work should either optimize that serial-correct verifier, or train/use a
  lightweight EAGLE draft with the serial verifier as the quality anchor.

Serial verifier speed check:

- `qwen36-ablation-serialgdn-oracle-k8-piecewise-tp2-metrics-20260618f`
  measured the serial-correct verifier under PIECEWISE graph on TP2.
- Summary:
  `data/qwen36-ablation-serialgdn-oracle-k8-piecewise-tp2-metrics-20260618f-summary-20260618192000.json`.
- Result: `14.03` corrected tok/s, `72.10` ms/token. This is not a viable
  speed lane. Keep serial GDN as a token-parity oracle only.

## 2026-06-18 Addendum 3 - EAGLE k5 Ceiling And Rollout Result

EAGLE speed ceiling:

- Synthetic k3 acceptance probe
  `qwen36-ablation-eagle2-tokenheavy-synthaccept4-piecewise-tp2-k3-ceiling-20260618h`
  measured `140.14` corrected tok/s, `7.20` ms/token. This is metrics-only,
  with canaries and quality skipped, so it is not promotable. It shows perfect
  k3 is still below the `>150 tok/s` target.
- Synthetic k5 acceptance probe
  `qwen36-ablation-eagle2-tokenheavy-synthaccept6-piecewise-tp2-k5-ceiling-20260618h`
  measured `181.91` corrected tok/s, `5.56` ms/token. This is also metrics-only
  and not promotable. It proves the serial EAGLE k5 path can structurally clear
  `>150 tok/s` if the draft acceptance is high enough.

Real EAGLE draft results:

- Current token-heavy EAGLE k5 run
  `qwen36-ablation-eagle2-tokenheavy-fusedbatch-nosafety-fastpath-piecewise-tp2-k5-smoke-20260618h`
  measured `52.52` corrected tok/s, `18.95` ms/token, with mean acceptance
  length `2.02`, `107/525` accepted drafts, and per-position acceptance
  `0.543, 0.314, 0.124, 0.038, 0.000`.
- Added rollout training support to
  `scripts/train-qwen36-eagle1-draft.py` with `--rollout-steps`; default
  one-step behavior is unchanged.
- Rollout checkpoint:
  `data/qwen36-eagle2-corpus2-tokenheavy-rollout5-trained-20260618h`.
  Training used the token-heavy checkpoint as init, three epochs, lr `5e-6`,
  rollout steps `5`, and the same corpus/corpus2/pos datasets.
- Rollout k5 endpoint run
  `qwen36-ablation-eagle2-rollout5-piecewise-tp2-k5-smoke-20260618h`
  measured `55.70` corrected tok/s, `17.95` ms/token. Acceptance was worse
  than useful: mean acceptance length `1.90`, `80/445` accepted drafts, and
  per-position acceptance `0.494, 0.303, 0.101, 0.000, 0.000`.

Decision:

- Do not continue short rollout fine-tuning on this tiny dataset as a near-term
  performance path. It did not improve k5 acceptance and remains far below the
  acceptance needed to use the `181.91 tok/s` synthetic ceiling.
- The likely EAGLE blocker is draft quality/deeper-step training data, not the
  verifier's basic mechanics. A viable EAGLE path needs a much larger and more
  representative hidden-state dataset and an offline acceptance evaluator before
  more endpoint smoke runs.
- Near-term performance work should return to exact no-quality-loss fast path
  improvements: collectives/topology, XPU graph replay correctness, and MoE
  dispatch/GEMM overhead. Keep EAGLE as a possible larger-batch training track,
  not the next single-session speed lever unless a better draft is produced.

## 2026-06-18 Addendum 4 - TP4 Health Blocker And Traceability Fix

Cached PIECEWISE traceability fix:

- Patched `/home/steve/src/vllm/vllm/compilation/caching.py` so the cached
  `PiecewiseBackend` construction now passes `submod_name=submod_name`.
- Reason: cached PIECEWISE wrappers were losing their stable submodule labels,
  making `VLLM_XPU_CUDAGRAPH_DISABLE_SUBMOD_REGEX` and direct-sync isolation
  hard to audit.
- Validation: `py_compile` passed for `vllm/compilation/caching.py`.

Launcher health preflight:

- Patched
  `/home/steve/llm-optimizations/scripts/launch-qwen36-quark-int8-accepted.sh`
  with `QWEN36_XPU_PREFLIGHT`.
- Default behavior is `QWEN36_XPU_PREFLIGHT=auto`, which runs the XPU/XCCL
  preflight for `TP_SIZE>=4` before starting vLLM. Set
  `QWEN36_XPU_PREFLIGHT=0` only for explicitly labeled diagnostics.
- The preflight writes a separate log at
  `${LOG_PATH%.*}-xpu-health.log` unless `QWEN36_XPU_PREFLIGHT_LOG` is set.
- Validation: `bash -n` passed for the launcher and health script. A blocked
  launch smoke test refused to start TP4 and wrote
  `/home/steve/llm-optimizations/data/qwen36-preflight-blocked-launch-smoke-20260618-xpu-health.log`.

Fused-prologue isolation attempts:

- `qwen36-ablation-prologue-disable-submod2-c1capture-20260618proliso1.log`
  attempted to isolate `piecewise:2/` with
  `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET=1`,
  `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE=1`,
  `VLLM_XPU_CUDAGRAPH_DISABLE_SUBMOD_REGEX='piecewise:2/'`, and direct sync on
  the same submodule.
- `qwen36-ablation-prologue-disable-submod2-c1capture-gmem086-20260618proliso2.log`
  repeated the same probe at `GPU_MEMORY_UTILIZATION=0.86`.
- Both probes failed before model readiness, inside XPU/XCCL device
  initialization, so they are invalid as prologue evidence. Do not count either
  run as a model-speed or model-correctness result.

Hardware/runtime health finding:

- New preflight script:
  `/home/steve/llm-optimizations/scripts/check-qwen36-xpu-xccl-health.sh`.
- Failing TP4 artifact:
  `/home/steve/llm-optimizations/data/qwen36-xpu-health-device3-wedged-20260618.log`.
  Physical devices `0`, `1`, and `2` pass single-device XPU allocation; physical
  device `3` fails a small tensor allocation with
  `UR_RESULT_ERROR_OUT_OF_RESOURCES`. A 4-rank XCCL barrier/all-reduce over
  `0,1,2,3` then fails on rank 3 with the same error.
- Passing subset artifact:
  `/home/steve/llm-optimizations/data/qwen36-xpu-health-devices012-pass-20260618.log`.
  Physical devices `0,1,2` pass single-device allocation and 3-rank XCCL
  barrier/all-reduce.
- Device map from `xpu-smi discovery`: failed XPU id `3` is PCI
  `0000:47:00.0`, DRM `/dev/dri/card2`.
- No user process was holding `/dev/dri/card2` or the render nodes. `xpu-smi ps`
  showed only `xpu-smi` itself during inspection.
- Kernel logs show repeated `xe 0000:47:00.0` GT0 job timeouts, VM job
  timeouts, and driver reset attempts before the health check. This is a
  low-level card/driver recovery state, not an ordinary vLLM OOM.
- `xpu-smi config -d 3 --reset` reported `Fail to reset device`. Prior
  noninteractive sysfs reset also required sudo. A root-level PCI/SBR reset or
  host reboot is required before valid TP4 endpoint benchmarking can resume.

How to re-check health:

```bash
PHYSICAL_DEVICES=0,1,2,3 XCCL_DEVICES=0,1,2,3 \
  /home/steve/llm-optimizations/scripts/check-qwen36-xpu-xccl-health.sh
```

Healthy-subset check:

```bash
PHYSICAL_DEVICES=0,1,2 XCCL_DEVICES=0,1,2 \
  /home/steve/llm-optimizations/scripts/check-qwen36-xpu-xccl-health.sh
```

Current decision:

- Treat TP4 Qwen 3.6 endpoint runs as blocked until the 4-card health preflight
  passes.
- Continue only work that does not require a valid 4-card endpoint while the
  card is wedged: offline prologue/MoE replay, TP2/TP3 diagnostics clearly
  labeled as non-comparable, and code cleanup/traceability.
- Once TP4 health passes, rerun the fused-prologue `piecewise:2/` isolation
  probe with full benchmark identity before interpreting speed or quality.

## 2026-06-18 Addendum 5 - Healthy-Device W8A8 MoE Replay Floor

Because physical XPU 3 is still unhealthy, the following runs are offline
single-device replay diagnostics only. They are not endpoint speed results and
are not comparable to TP4 serving throughput. They use `ZE_AFFINITY_MASK=0` and
`ONEAPI_DEVICE_SELECTOR=level_zero:0` to avoid the wedged card.

Middle-layerlet correctness recheck:

- Command:
  `/home/steve/llm-optimizations/scripts/check-qwen36-w8a8-middle-layerlet.py --graph-replay --require-graph`
- JSON:
  `/home/steve/llm-optimizations/data/qwen36-w8a8-middle-layerlet-check-device0-20260618.json`
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-w8a8-middle-layerlet-check-device0-20260618.md`
- Result: overall passed. Eager and XPU graph replay passed for all synthetic
  cases, including `qwen36_decode_one_token_tp4_shape`.
- Interpretation: the existing middle-layerlet math and graph replay are still
  valid in isolation. The full endpoint blocker is integration/capture and the
  current TP4 hardware health issue, not this standalone math path.

Full route-exact MoE replay, current binary:

- JSON:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-current-device0-20260618.json`
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-current-device0-20260618.md`
- Result: best exact non-reference candidate was `preallocated_staged` at
  `191.159 us` best-row mean, `1.527x` versus current `xpu_fused_moe`.
- Aggregate means: `xpu_fused_moe` `308.363 us`, scratch `256.104 us`,
  preallocated staged `200.261 us`, fused-prologue staged `270.232 us`.
- Gate: failed. No rows met the `160 us/layerlet` target.

Offset/active-offset GEMM replay:

- JSON:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-offset-active-device0-20260618.json`
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-offset-active-device0-20260618.md`
- Result: exact. Best exact non-reference candidate was
  `fused_prologue_offset_gemm` at `186.619 us`, `1.581x` versus current
  `xpu_fused_moe`.
- Aggregate means: `xpu_fused_moe` `316.883 us`, scratch `262.541 us`,
  preallocated staged `203.542 us`, fused-prologue offset-GEMM `200.269 us`,
  active-offset-GEMM `201.639 us`.
- Gate: failed. This is the best offline diagnostic seen today, but still short
  of the `160 us/layerlet` target.

Hot-packed expert replay:

- JSON:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-hotpack-offset-active-device0-20260618.json`
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-hotpack-offset-active-device0-20260618.md`
- Result: exact in the synthetic remapped replay, but not a useful speed lever.
  Best exact candidate was `fused_prologue_offset_gemm` at `186.212 us`, with
  worse tail rows (`worst_best_exact_nonreference_us_mean=241.526 us`).
- Decision: do not prioritize expert hot-packing unless a later route-frequency
  model shows a stronger reason. It would require exact offline expert-weight
  permutation plus router-ID remap to preserve model outputs.

Fused SiLU+quant replay:

- JSON:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-fusedsilu-offset-active-device0-20260618.json`
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-fusedsilu-offset-active-device0-20260618.md`
- Result: exact in this replay, but slower than the plain offset-GEMM
  diagnostic. Best exact candidate was `fused_prologue_offset_gemm` at
  `189.774 us`.
- Decision: do not revive the previously rejected fused-SiLU endpoint path for
  speed. It remains a diagnostic-only lane unless a separate correctness fix
  explains the earlier endpoint canary failures.

Graph replay timing diagnostic:

- Script updated:
  `/home/steve/llm-optimizations/scripts/bench-qwen36-int8-moe-kernels.py`
  now supports `--graph-replay-timing`, `--graph-warmup`, and
  `--graph-iterations`.
- Syntax validation:
  `/home/steve/.venvs/vllm-xpu/bin/python -m py_compile scripts/bench-qwen36-int8-moe-kernels.py`
  passed.
- Multi-route artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-graph-offset-active-device0-20260618.json`
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-graph-offset-active-device0-20260618.md`
- Result: all graph captures executed, but candidate graph replay was not a
  stable shortcut. Aggregating graph rows by candidate produced:
  `xpu_fused_moe_with_scratch` mean `235.608 us`,
  `preallocated_staged` mean `238.654 us`,
  `fused_prologue_offset_gemm` mean `238.264 us`, and
  `fused_prologue_active_offset_gemm` mean `236.136 us`, with a wide
  `~145-331 us` range.
- A follow-up single-route graph run for route start `56` was rerun
  sequentially to avoid device contention:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-route-replay-graph-route56-sequential-device0-20260618.json`.
  It showed eager `fused_prologue_offset_gemm` at `185.661 us`, but graph
  replay around `331-340 us`, so the under-160 graph samples from the
  multi-route sweep are not trusted as promotion evidence.
- Invalid artifacts: `graph-route0-device0-20260618` and
  `graph-route56-device0-20260618` were accidentally launched in parallel on
  the same physical XPU. Do not use those two artifacts for performance
  conclusions.
- Decision: keep graph replay timing as a diagnostic only. It does not replace
  the need for a native one-dispatch/persistent MoE layerlet.

Updated target decision:

- The next exact no-quality-loss MoE speed path is not another Python scratch
  arrangement. The replay data says we need a true prologue-inclusive
  one-dispatch or persistent layerlet that keeps the offset-GEMM advantage and
  removes more fixed launch/dispatch overhead around activation/quant/GEMM2.
- A useful candidate must beat roughly `160 us` on this route replay before it
  deserves endpoint promotion work. For the `>150 tok/s` goal, the endpoint
  target will probably need this MoE layerlet plus restored healthy TP4 graph
  execution; current replay-only candidates are still not enough.

## 2026-06-18 Addendum 6 - Full W8A8 Layerlet Staged, Exact, Not Promoted

2025.3 binary staging:

- Rebuilt and staged the XPU extension with the oneAPI 2025.3-compatible
  runtime path. The earlier 2026-built extension pulled a `libsycl.so.9` ABI
  and caused native crashes against the current PyTorch/XPU runtime.
- Package binaries in `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/`
  were backed up with suffix `backup-20260618-full-layerlet-2025-precopy`
  before staging.
- Import check passed for both
  `torch.ops._xpu_C.qwen36_moe_w8a8_middle_layerlet` and
  `torch.ops._xpu_C.qwen36_moe_w8a8_full_layerlet`.

Full layerlet implementation:

- Kernel binding added in `/home/steve/src/vllm-xpu-kernels`:
  `csrc/xpu/moe_layerlet.cpp`, `csrc/xpu/ops.h`,
  `csrc/xpu/torch_bindings.cpp`, and `CMakeLists.txt`.
- Python integration added behind
  `VLLM_XPU_MOE_W8A8_FULL_LAYERLET=1` in
  `vllm_xpu_kernels/fused_moe_interface.py`.
- Accepted launcher explicitly unsets the full-layerlet flag unless
  `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`, so production/accepted runs cannot
  accidentally use the experimental path.
- Run-summary identity tracking now includes
  `VLLM_XPU_MOE_W8A8_FULL_LAYERLET`.

Exact replay result:

- Sweep JSON:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-sweep-device0-20260618.json`
- Sweep Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-sweep-device0-20260618.md`
- Result: 16 routed rows, all exact with
  `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0`.
- Full-layerlet timing: min `155.263 us`, mean `161.743 us`,
  max `171.005 us`, median `161.083 us`.
- Existing middle-layerlet timing on the same sweep: mean `167.315 us`.
- Current `xpu_fused_moe` reference timing on the same sweep:
  mean `304.637 us`.
- Gate: useful but not promoted. Half the rows are under `160 us`, but the
  sweep is single-device offline replay, not an endpoint or graph-quality
  result.

Live Python branch smoke:

- Direct live-path smoke:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-livepath-smoke-device0-20260618.json`
  was exact with `max_abs_diff = 0.0` and about `1.49x` over the local base
  call on that route.
- Preallocated-output live-path smoke:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-livepath-prealloc-smoke-device0-20260618.json`
  was exact with `max_abs_diff = 0.0`, but only about `1.20x` in that noisy
  wrapper test.
- Interpretation: the C++ op is exact and useful in offline replay, but live
  wrapper variance means it is not endpoint-promoted yet.

Next exact MoE work:

- The current full layerlet still calls separate prologue, quant1, GEMM1,
  activation/quant2, GEMM2, and gather launches.
- The next best no-quality-loss kernel target is a single-token/top-k=8
  prologue-plus-quant1 fused path. It should preserve the exact per-row INT8
  scale/round/clamp math while avoiding the BF16 remap write/read and deleting
  one dispatch.
- A smaller fallback target is a specialized single-token/top-k=8 gather, but
  gather is likely launch dominated and may not be enough by itself.
- Endpoint TP4 promotion remains blocked until the physical XPU 3 health check
  passes.

## 2026-06-18 Addendum 7 - Fused Quant1 Tried And Gated Off

Fused quant1 candidates:

- Added an opt-in C++ single-token/top-k=8 prologue+quant1 helper inside
  `csrc/xpu/moe_layerlet.cpp`, controlled by
  `VLLM_XPU_MOE_W8A8_FUSED_Q1=1`.
- The accepted launcher now unsets `VLLM_XPU_MOE_W8A8_FUSED_Q1` unless
  `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`.
- `run-qwen36-ablation-candidate.sh` records
  `VLLM_XPU_MOE_W8A8_FUSED_Q1` in the run-summary identity.

Results:

- Serial duplicate q1 variant:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-q1fused-sweep-device0-20260618.json`
  - Exact: max diff `0.0`.
  - Full-layerlet min/mean/median/max:
    `158.761 / 167.807 / 163.251 / 182.766 us`.
  - Only `1/16` rows under `160 us`.
  - Rejected for speed. It reduced quant parallelism too much.
- Eight-workgroup q1 variant:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-q1parallel-sweep-device0-20260618.json`
  - Exact: max diff `0.0`.
  - Full-layerlet min/mean/median/max:
    `160.385 / 178.733 / 176.648 / 202.214 us`.
  - `0/16` rows under `160 us`.
  - Rejected for speed. Preserving row parallelism still did not beat the
    existing prologue+quant sequence.

Restored guarded default:

- Default path with `VLLM_XPU_MOE_W8A8_FUSED_Q1` unset:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-q1guard-default-sweep-device0-20260618.json`
  - Exact: max diff `0.0`.
  - Full-layerlet min/mean/median/max:
    `154.587 / 160.819 / 159.294 / 178.277 us`.
  - `11/16` rows under `160 us`.
- Decision: keep the q1 code only as an opt-in diagnostic. Do not promote it
  or enable it by default.

Next exact MoE target:

- A standalone q1 fusion is not the missing win. The next worthwhile exact
  path is either a true persistent/one-dispatch MoE layerlet that moves the
  GEMM2/gather boundary, or a specialized gather/epilogue integration that
  avoids the final launch without reducing quant/GEMM parallelism.

## 2026-06-18 Addendum 8 - Fast Gather And Unchecked Middle Rejected

Fast gather:

- Added an opt-in single-token/top-k=8 gather helper controlled by
  `VLLM_XPU_MOE_W8A8_FAST_GATHER=1`.
- The helper preserves the generic gather accumulation order and was exact in
  replay, but it did not improve the route sweep enough:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-fastgather-sweep-device0-20260618.json`
  - Exact: max diff `0.0`.
  - Full-layerlet min/mean/median/max:
    `155.116 / 161.622 / 161.662 / 170.463 us`.
  - `5/16` rows under `160 us`.
- Same-lane comparison: the guarded default remains better than fast gather:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-q1guard-default-sweep-device0-20260618.json`
  had `154.587 / 160.819 / 159.294 / 178.277 us` and `11/16` rows under
  `160 us`.
- Decision: keep fast gather as an opt-in diagnostic only. Do not enable or
  promote it.

Unchecked-middle wrapper:

- Tried removing the duplicated middle-layerlet validation from inside the
  experimental full-layerlet wrapper. This does not change math, but the
  candidate was slower under the same rebuilt binary.
- Candidate artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-uncheckedmiddle-sweep-device0-20260618.json`
  - Exact: max diff `0.0`.
  - Full-layerlet min/mean/median/max:
    `163.327 / 177.125 / 173.131 / 210.363 us`.
  - `0/16` rows under `160 us`.
- Same-binary control without the unchecked path:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-uncheckedmiddle-control-device0-20260618.json`
  - Exact: max diff `0.0`.
  - Full-layerlet min/mean/median/max:
    `157.361 / 171.858 / 170.957 / 191.336 us`.
  - `2/16` rows under `160 us`.
- The absolute control run was slower than the older guarded-default artifact
  across reference and candidate timings, so do not compare it directly against
  the old artifact as a regression claim. Within the same rebuilt binary,
  unchecked-middle was clearly worse than its control.
- Decision: rejected and removed from source/scripts. Package binaries were
  restored from `backup-20260618-uncheckedmiddle-precopy`; the importable
  package is back to the previous fast-gather/full-layerlet staged binary.

Current best exact offline MoE artifact:

- The best exact offline full-layerlet result remains the guarded default:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-q1guard-default-sweep-device0-20260618.json`.
- The key blocker is still not a small wrapper or standalone gather tweak.
  The next serious exact/no-quality-loss path needs to remove a larger
  boundary: a true persistent or one-dispatch MoE layerlet, or an exact
  GEMM2/gather epilogue design that preserves the current BF16 row rounding
  before weighted accumulation.

## 2026-06-18 Addendum 9 - Real-Routing Oracle Fixed A Hidden Map/Binary Mismatch

Harness fixes:

- Added real-routing oracle checks to
  `/home/steve/llm-optimizations/scripts/bench-qwen36-int8-moe-kernels.py`.
  The oracle compares candidates against a forced rows-per-expert W8A8 path
  with offset/layerlet/prologue env paths disabled.
- Added hot-skew synthetic routing to catch multi-row/non-uniform expert maps.
- Fixed the benchmark report to store immediate scalar exactness diffs. The
  earlier report recomputed some diffs from tensors backed by scratch buffers
  after later timing loops had overwritten them.
- Graph replay now uses separate scratch buffers from the eager exactness path.

Correctness bug found:

- Hot-skew rows initially exposed large multi-row diffs in the fused-prologue
  paths.
- Root cause in source: `csrc/moe/fused_moe_prologue.hpp` wrote
  `unpermuted_row_to_permuted_row` in column-major expanded-token order
  (`k * rows + row`) while `moe_gather` expects row-major
  (`row * topk + k`).
- Patched `MergeExpertPrefixSumKernel` to keep
  `permuted_row_to_unpermuted_row` column-major for internal remap, but write
  `unpermuted_row_to_permuted_row[source_row * topk + source_k_rank]`.

Build lesson:

- Rebuilding only `_xpu_C.abi3.so` was insufficient. The Python benchmark path
  calls `torch.ops._moe_C.fused_moe_prologue`; that binary was still from
  2026-06-12 and kept the old map layout.
- Rebuilt and staged both binaries:
  - `_xpu_C.abi3.so`: `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so`
  - `_moe_C.abi3.so`: `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_moe_C.abi3.so`
- Backups:
  - `_xpu_C.abi3.so.backup-20260618174647-pre-rowmajor-prologue-fix`
  - `_moe_C.abi3.so.backup-20260618175726-pre-rowmajor-prologue-fix`

Corrected artifacts:

- Pre-`_moe_C` rebuild failing/contaminated graph diagnostic:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-rowmajorfix-graph-hot-skew-device0-20260618.json`
- Corrected rows=2 immediate-diff proof after `_moe_C` rebuild:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-immediatediff-after-moeC-rebuild-hot-skew-rows2-device0-20260618.json`
- Corrected hot-skew sweep after `_moe_C` rebuild:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-after-moeC-rebuild-hot-skew-sweep-device0-20260618.json`
- Corrected graph replay spot-check:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-after-moeC-rebuild-graph-hot-skew-rows2-device0-20260618.json`

Patch snapshots:

- `/home/steve/llm-optimizations/patches/vllm-xpu-kernels-qwen36-w8a8-layerlet-rowmajor-moeC-20260618.patch`
- `/home/steve/llm-optimizations/patches/llm-optimizations-qwen36-real-routing-oracle-immediatediff-20260618.patch`

Corrected hot-skew sweep summary:

| rows | xpu fused us | prealloc us | offset us | middle layerlet us | full layerlet us | max diff |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 392.893 | 255.456 | 243.029 | 211.361 | 228.176 | 0.0 |
| 2 | 319.131 | 199.030 | 200.844 | 182.169 | 166.017 | 0.0 |
| 4 | 342.726 | 224.809 | 218.783 | 188.799 | 181.233 | 0.0 |
| 8 | 322.517 | 200.850 | 200.811 | 177.496 | 169.169 | 0.0 |
| 16 | 317.837 | 204.380 | 194.935 | 173.069 | 166.498 | 0.0 |

Current interpretation:

- The real-routing correctness problem is fixed for the offline replay paths:
  current reference, rows oracle, offset oracle, fused-prologue, middle
  layerlet, and full layerlet all report `max_abs_diff = 0.0` on hot-skew
  multi-row replay after both extensions are rebuilt.
- The best exact offline candidate is still short of the `160 us` gate on this
  sweep. Rows 2/8/16 are close (`166-169 us` for full layerlet), but rows 1 is
  still too slow (`211 us` middle, `228 us` full).
- XPU graph replay remains a blocker for endpoint promotion: the corrected
  rows=2 graph spot-check is exact but replay is about `320-330 us`, slower
  than eager replay.

Next exact/no-quality-loss performance targets:

- Re-test active-offset GEMM with the corrected `_moe_C` binary. It was not
  included in the corrected sweep and may help hot-skew paths with many zero
  experts.
- Attack rows=1 specifically. The single-token decode shape is still the
  largest layerlet miss; revisit the opt-in q1/fast-gather code only under the
  corrected oracle harness, and keep anything that does not beat the default
  gated off.
- Find why isolated graph replay is slower than eager. Do not promote endpoint
  graph wiring until replay timing is credible or proven irrelevant to the live
  graph lane.
- Once XPU physical device 3 is recovered, run TP4 accepted-lane quality and
  endpoint A/B with full benchmark identity recorded before interpreting any
  tok/s result.

## 2026-06-18 Addendum 10 - Active Offset, Q1, And Fast Gather Retested

Corrected active-offset sweep:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-after-moeC-rebuild-activeoffset-hot-skew-sweep-device0-20260618.json`
- Exactness: all enabled paths reported `max_abs_diff = 0.0`.
- Active-offset GEMM was not a speed win versus plain offset:

| rows | active offset us | plain offset us | middle layerlet us | full layerlet us |
|---:|---:|---:|---:|---:|
| 1 | 200.102 | 198.386 | 168.792 | 187.122 |
| 2 | 200.772 | 199.823 | 167.921 | 163.722 |
| 4 | 195.026 | 197.106 | 167.212 | 164.606 |
| 8 | 200.824 | 199.621 | 171.210 | 163.241 |
| 16 | 201.019 | 197.892 | 167.576 | 160.979 |

Decision: keep active-offset as a diagnostic only. It is exact, but not
faster enough to promote.

Corrected q1/fast-gather retests:

- q1 only:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-after-moeC-q1only-hot-skew-rows1-2-device0-20260618.json`
  - Exact: `0.0`.
  - Rows 1: middle `190.957 us`, full `201.240 us`.
  - Rows 2: middle `173.546 us`, full `176.384 us`.
  - Decision: rejected for speed.
- fast-gather only:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-after-moeC-fastgatheronly-hot-skew-rows1-2-device0-20260618.json`
  - Exact: `0.0`.
  - Rows 1: middle `162.288 us`, full `172.371 us`.
  - Rows 2: middle `168.064 us`, full `158.136 us`.
  - Decision: not a default. It gives a rows=2 pass in this noisy microbench,
    but it does not solve rows=1 and only applies to single-token gather.
- q1 + fast-gather:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-after-moeC-q1-fastgather-hot-skew-rows1-2-device0-20260618.json`
  - Exact: `0.0`.
  - Rows 1: middle `163.146 us`, full `170.599 us`.
  - Rows 2: middle `161.330 us`, full `158.470 us`.
  - Decision: do not promote. q1 hurts, and the rows=2 pass does not address
    the rows=1 bottleneck.

Current next target:

- The corrected oracle gates show the shape to attack is rows=1. The fastest
  exact rows=1 candidate in the corrected retests is the Python-dispatched
  middle-layerlet path around `162-169 us`, while full C++ layerlet is still
  slower on rows=1. A useful next patch should reduce full-layerlet rows=1
  overhead without changing math, or add a genuinely faster single-token
  full-layerlet path.

## 2026-06-18 Addendum 11 - Real Rows=1 Scan, Q1/Fast-Gather Rejected Again

Stable real-route baseline:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-default-firstdecode-routes-row1-stable-device0-20260618.json`
- Same-lane rerun after adding runtime identity and sourcing full oneAPI
  `setvars.sh`:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-default-setvars-firstdecode-routes-row1-stable-device0-20260618.json`
- Identity: single-device offline replay on device 0, Quark W8A8 INT8 config,
  TP4-shaped per-rank tensors, rows=1, captured first-decode routes from
  `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl`,
  route starts `0:120:5`, 30 measured iterations, 5 warmup iterations,
  real-routing oracle enabled, q1 and fast-gather envs unset.
- Exactness: all promoted candidates reported `max_abs_diff = 0.0`.

Stable real-route rows=1 summary:

| path | min us | mean us | median us | p90 us | max us | <=160 us rows |
|---|---:|---:|---:|---:|---:|---:|
| xpu scratch | 248.525 | 262.639 | 257.973 | 275.888 | 292.490 | 0/24 |
| plain offset | 189.216 | 203.241 | 200.009 | 212.507 | 233.532 | 0/24 |
| active offset | 189.769 | 204.650 | 202.847 | 213.597 | 226.699 | 0/24 |
| middle layerlet | 161.001 | 173.428 | 171.181 | 180.944 | 193.764 | 0/24 |
| full layerlet | 157.215 | 169.210 | 166.545 | 177.622 | 188.859 | 2/24 |

Decision: the corrected full layerlet is the best current exact MoE replay
path, but it is not enough for endpoint promotion. It clears the `160 us` gate
on only 2 of 24 real routes and still has a `188.859 us` tail.

Same-env confirmation after runtime identity patch:

- Default/setvars full layerlet min/mean/median/p90/max:
  `158.326 / 169.172 / 164.374 / 182.699 / 205.267 us`, with 5 of 24 rows
  under `160 us`.
- Route-pack/setvars full layerlet min/mean/median/p90/max:
  `156.054 / 170.198 / 167.456 / 175.876 / 207.490 us`, with 3 of 24 rows
  under `160 us`.
- This confirms the original direction: default remains the safer baseline
  despite the route-pack best-case win.

Rejected real-route q1 and gather variants:

- Fast gather only:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-fastgather-firstdecode-routes-row1-stable-device0-20260618.json`
  - Exact: `0.0`.
  - Full layerlet min/mean/median/p90/max:
    `157.106 / 171.433 / 169.913 / 182.596 / 200.772 us`.
  - It improves some routes but worsens others badly. Do not enable globally.
- Optimized q1 only:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-q1opt-firstdecode-routes-row1-stable-device0-20260618.json`
  - Exact: `0.0`.
  - Full layerlet min/mean/median/p90/max:
    `159.356 / 171.950 / 167.073 / 190.830 / 199.455 us`.
  - This is slower than the stable default mean and tail. Keep q1 gated off.

Hot-expert physical packing simulation:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-routepack-firstdecode-routes-row1-stable-device0-20260618.json`
- This remaps hot logical experts to dense physical IDs. A real model could
  preserve quality by permuting expert weights and remapping top-k IDs
  together, so this was worth testing.
- Exact: `0.0` within the remapped replay.
- Full layerlet min/mean/median/p90/max:
  `156.054 / 170.198 / 167.456 / 175.876 / 207.490 us`.
- It helped routes 95 and 20 by about `25 us` and `21 us`, but hurt routes 80
  and 5 by about `39 us` and `31 us`.

Decision: physical expert packing is not a safe global speed lever from this
fixture. Keep it as an idea for per-layer/per-rank adaptive layouts only if a
future trace shows a stable route distribution with a smaller tail.

Runtime environment lesson:

- In this shell, sourcing only
  `/opt/intel/oneapi/compiler/2025.3/env/vars.sh` made `xpu-smi` see all B70s
  but made PyTorch report `torch.xpu.device_count() == 0`.
- Sourcing `/opt/intel/oneapi/setvars.sh --force` restored PyTorch XPU
  visibility (`device_count == 4`), and with `ONEAPI_DEVICE_SELECTOR=level_zero:0`
  the replay saw one selected device.
- The replay harness now records `runtime_identity`, including device selector
  env, q1/fast-gather envs, torch version, selected XPU device names, Python
  path, and loaded `vllm_xpu_kernels` extension paths. It also records the
  selected expert rows directly in each result.

Immediate command-list real-route check:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-immediate-firstdecode-routes-row1-stable-device0-20260618.json`
- Environment delta from the default/setvars replay:
  `SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=1` and
  `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`.
- Exact: `0.0`.
- Full layerlet min/mean/median/p90/max:
  `157.265 / 169.618 / 169.510 / 178.733 / 188.032 us`, with 2 of 24 rows
  under `160 us`.
- Compared with the same-env default/setvars replay
  (`158.326 / 169.172 / 164.374 / 182.699 / 205.267 us`), immediate lists
  smooth the worst tail but worsen median and do not improve mean.

Decision: keep immediate command lists as a possible endpoint stability/tail
lever to retest only after TP4 health is restored. It is quality-neutral in
offline replay, but it is not a standalone rows=1 MoE win and should not be
combined into accepted endpoint manifests without full quality and reliability
gates.

W8A8 grouped GEMM m8 policy checks:

- Code change: exposed `w8a16_policy_m_8` through
  `VLLM_XPU_W8A8_GROUPED_GEMM_POLICY=m8`, plus diagnostic shape-specific
  overrides:
  `VLLM_XPU_W8A8_GROUPED_GEMM_N_LT_K_POLICY` and
  `VLLM_XPU_W8A8_GROUPED_GEMM_N_GT_K_POLICY`.
- The replay harness now records all three policy envs in `runtime_identity`.
- All completed policy runs were exact (`max_abs_diff = 0.0`).

Artifacts and results:

| policy | artifact | full layerlet min/mean/median/p90/max us | <=160 rows | decision |
|---|---|---:|---:|---|
| rebuilt default | `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-default-rebuilt-firstdecode-routes-row1-device0-20260618.json` | `154.045 / 163.868 / 159.998 / 175.859 / 203.502` | 12/24 | current rebuilt control |
| generic m8 run 1 | `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-m8policy-firstdecode-routes-row1-stable-device0-20260618.json` | `155.153 / 163.253 / 160.339 / 172.203 / 179.175` | 9/24 | promising tail, not repeatable |
| generic m8 run 2 | `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-m8policy-repeat-firstdecode-routes-row1-device0-20260618.json` | `154.458 / 170.817 / 170.447 / 178.564 / 195.076` | 2/24 | rejected for repeatability |
| generic m8 + immediate | `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-m8-immediate-firstdecode-routes-row1-device0-20260618.json` | `154.731 / 167.267 / 164.970 / 174.000 / 212.484` | 6/24 | rejected |
| m8 only when `N<K` | `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-m8-nltk-firstdecode-routes-row1-device0-20260618.json` | `155.290 / 175.271 / 173.277 / 192.108 / 202.766` | 3/24 | rejected |
| m8 only when `N>K` | `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-m8-ngtk-firstdecode-routes-row1-device0-20260618.log` | crashed before JSON flush | n/a | rejected, unsafe |

Decision: do not promote m8 policy. Generic m8 can reduce a single-run tail,
but the improvement is not stable across repeats. GEMM1-only m8 is slower.
GEMM2-only m8 segfaulted, although device 0 survived a post-crash XPU smoke
test. Keep the m8 code path as a diagnostic only; do not set any m8 policy env
in accepted endpoint launchers.

Next exact/no-quality-loss work:

- Stop spending time on standalone q1, standalone gather, active-offset, and
  global expert packing. Also stop spending time on m8 grouped-GEMM policy
  variants. All completed variants are exact, but none gives a repeatable
  real rows=1 win.
- The next useful patch needs to remove a larger boundary inside the rows=1
  MoE path: either a persistent/one-dispatch MoE layerlet, a GEMM2+gather
  epilogue that preserves the current BF16 weighted accumulation behavior, or a
  row1/top-k=8 direct expert path that avoids the generic grouped-GEMM launch
  shape without changing W8A8 math.

## 2026-06-18 Addendum 5 - Offline EAGLE Acceptance Gate

Purpose:

- The serial EAGLE k5 synthetic path already proved the endpoint can
  structurally clear the `>150 tok/s` target (`181.91 tok/s`) if draft
  acceptance is high enough, but current real draft acceptance is too weak.
- To avoid slow endpoint iterations, add a cheap offline draft-quality gate
  before spending time on vLLM launch/measurement.

New script:

- `/home/steve/llm-optimizations/scripts/evaluate-qwen36-eagle-draft-offline.py`
- It loads a local EAGLE draft checkpoint plus the target model
  `embed_tokens`/`lm_head`, reads hidden-state dataset `.pt` files, rolls out
  greedy draft proposals, compares token IDs against the recorded target greedy
  continuation, and reports:
  - mean accepted draft length;
  - per-position exact and top-k rates;
  - acceptance histogram;
  - concrete mismatch examples.

Offline acceptance results:

| checkpoint | eval set | artifact | mean accepted | decision |
|---|---|---|---:|---|
| token-heavy EAGLE2 | capped corpus2+pos | `data/qwen36-eagle2-tokenheavy-offline-accept-capped-20260618.json` | `1.640625` | baseline |
| rollout5 EAGLE2 | capped corpus2+pos | `data/qwen36-eagle2-rollout5-offline-accept-capped-20260618.json` | `1.9296875` | best offline signal |
| token-focused rollout5 | capped corpus2+pos | `data/qwen36-eagle2-tokenfocused-rollout5-offline-accept-capped-20260618i.json` | `1.828125` | rejected |
| token-heavy EAGLE2 | smoke held-out | `data/qwen36-eagle2-tokenheavy-offline-accept-smoke-20260618.json` | `1.5689655` | baseline |
| rollout5 EAGLE2 | smoke held-out | `data/qwen36-eagle2-rollout5-offline-accept-smoke-20260618.json` | `1.7413793` | best offline signal |
| token-focused rollout5 | smoke held-out | `data/qwen36-eagle2-tokenfocused-rollout5-offline-accept-smoke-20260618i.json` | `1.6724138` | rejected |

Rollout5 details:

- Checkpoint:
  `/home/steve/llm-optimizations/data/qwen36-eagle2-corpus2-tokenheavy-rollout5-trained-20260618h`
- Capped corpus2+pos conditional exact by step:
  `0.90625, 0.6121, 0.4225, 0.5667, 0.7647`.
- Smoke conditional exact by step is lower but still better than token-heavy.
- The earlier endpoint rollout5 k5 run was slower/worse than expected, so this
  offline score is not an endpoint speed claim. Treat it as a draft-training
  selector only.

Rejected token-focused fine-tune:

- Checkpoint:
  `/home/steve/llm-optimizations/data/qwen36-eagle2-tokenfocused-rollout5-trained-20260618i`
- Training command initialized from token-heavy and used
  `--rollout-steps 5 --feature-loss-weight 0.25 --token-loss-weight 1.0`
  for 4 epochs.
- Final training metrics regressed (`top1 = 0.3156`, `top3 = 0.4508`,
  `token_loss = 2.0299`), and offline acceptance landed below rollout5 on both
  capped and smoke gates.
- Decision: do not promote this checkpoint; keep the run as evidence that
  simply increasing token-loss weight is not enough.

EAGLE data coverage status:

- Existing usable datasets:
  - `data/qwen36-eagle-hidden-dataset-corpus-tp2-20260618a` (`48` samples)
  - `data/qwen36-eagle-hidden-dataset-corpus2-tp2-20260618a` (`254` samples)
  - `data/qwen36-eagle-hidden-dataset-pos-tp2-20260618a` (`54` samples)
  - `data/qwen36-eagle-hidden-dataset-smoke-tp2-20260618e` (`1` sample)
- The collector previously had only a narrow prompt mix. It now includes
  additional families in
  `/home/steve/llm-optimizations/scripts/collect-qwen36-eagle-hidden-corpus.py`:
  `debug-log`, `python-patch`, `sql-analysis`, `shell-runbook`,
  `api-contract`, `longform-summary`, `test-plan`, `algorithm`,
  `comparison`, and `user-support`.

Next EAGLE work:

- Collect a larger TP2 hidden-state dump on healthy devices only; do not use
  TP4 until the XPU/XCCL health preflight passes.
- Build an expanded dataset with the existing dump builder, train a rollout
  EAGLE2 checkpoint, and accept it for endpoint testing only if offline
  acceptance clearly beats rollout5 on both the capped corpus and smoke gates.
- If offline acceptance reaches the needed band, run endpoint k5 with the
  accepted identity and full quality/reliability gates.

## 2026-06-18 Addendum 6 - m8 Guard

The shape-specific diagnostic `VLLM_XPU_W8A8_GROUPED_GEMM_N_GT_K_POLICY=m8`
previously segfaulted before JSON flush. The grouped-GEMM policy override now
ignores `m8` when `gemm_n > gemm_k`, both for generic and `N>K` overrides:

- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp`

This guard is not a performance win and does not change the accepted endpoint
identity. It exists to keep future diagnostic sweeps from selecting the unsafe
GEMM2 shape. Rebuild/stage `_xpu_C` after this edit before running any policy
sweeps that import `vllm_xpu_kernels._xpu_C`.

## 2026-06-18 Addendum 7 - Expanded EAGLE Data Collection And Rejected Fine-Tunes

Expanded TP2 hidden-state export:

- Failed attempt:
  `data/qwen36-eagle-hidden-dump-expanded-tp2-20260618j.log` failed during
  sampler profiling because Triton loaded
  `/opt/intel/oneapi/compiler/2026.0/lib/libsycl.so.9`, which mismatched the
  active UR loader:
  `undefined symbol: urDeviceWaitExp, version LIBUR_LOADER_0.12`.
- Fix for this environment:
  source oneAPI normally, then pin
  `LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2025.3/lib:$LD_LIBRARY_PATH`
  and `PATH=/opt/intel/oneapi/compiler/2025.3/bin:$PATH`. A direct Triton
  target smoke passed with that ordering and still saw `torch.xpu.device_count()
  == 4`.
- Successful run:
  `data/qwen36-eagle-hidden-dump-expanded-tp2-20260618k.log`
  on TP2 cards `0,1`, graph-none, no async, Quark W8A8 INT8 target, 32k max
  model length, `GPU_MEMORY_UTILIZATION=0.82`,
  `MAX_NUM_BATCHED_TOKENS=1024`, `MAX_NUM_SEQS=8`, and hidden dump envs set.
- Request manifest:
  `data/qwen36-eagle-hidden-expanded-tp2-20260618k-requests.json`
  with `64` prompts over the expanded prompt families.
- Dataset summary:
  `data/qwen36-eagle-hidden-dataset-expanded-tp2-20260618k-summary.json`
  produced `6144` rows, `64` saved samples, `6080` continuity matches,
  `0` continuity breaks, `0` position breaks, and `0` bad files.

Expanded-data offline acceptance controls:

| checkpoint | expanded mean accepted | decision |
|---|---:|---|
| token-heavy control | `1.046875` | weak |
| rollout5 control | `1.132812` | current control |

The new expanded set is substantially harder than the old capped corpus2+pos
gate where rollout5 gets `1.929688`. This explains why endpoint acceptance is
still far below the synthetic k5 ceiling.

Fine-tune attempts against expanded data:

| checkpoint | capped corpus2+pos | smoke | expanded | decision |
|---|---:|---:|---:|---|
| rollout5 control | `1.929688` | `1.741379` | `1.132812` | keep as best current control |
| expanded low-LR mixed | `1.914062` | `1.741379` | `1.125000` | reject |
| expanded-only | `1.875000` | not run | `1.226562` | reject; improves expanded but hurts established gate |
| expanded oversample4 | `1.882812` | `1.793103` | `1.156250` | reject; improves smoke/expanded slightly but hurts capped gate |

Artifacts:

- Low-LR mixed checkpoint:
  `data/qwen36-eagle2-rollout5-expanded-lowlr-trained-20260618k`.
- Expanded-only checkpoint:
  `data/qwen36-eagle2-rollout5-expanded-only-trained-20260618l`.
- Oversample4 checkpoint:
  `data/qwen36-eagle2-rollout5-expanded-oversample4-trained-20260618m`.
- Corresponding offline acceptance JSON files:
  `data/qwen36-eagle2-rollout5-expanded-*-offline-accept-*.json`.

Decision:

- Do not promote any expanded-data fine-tune to endpoint testing.
- The current 2-layer draft can partially learn the expanded data, but not
  enough, and the improvements trade off against the established capped gate.
- Next draft-quality work should change the draft/training strategy instead of
  just reweighting this 2-layer rollout checkpoint: larger/deeper draft, better
  train/validation split with held-out expanded prompts, scheduled rollout
  targets, or richer hidden features. Keep using the offline acceptance gate
  before any endpoint run.

## 2026-06-18 Addendum 8 - Deeper EAGLE Draft Attempts

Offline eval identity correction:

- `start_stride` is part of the offline EAGLE acceptance identity.
- The historical capped control used `start_stride=4`; the historical smoke
  control used `start_stride=1`; the expanded control used `start_stride=4`.
- A default `start_stride=1` capped rerun of the same 2-layer rollout5 control
  measured only `1.273438` mean accepted, while the historical stride-4 capped
  identity measures `1.929688`. Do not compare offline acceptance artifacts
  without matching `dataset_dir`, `max_steps`, `max_starts`, `start_stride`,
  `dtype`, draft checkpoint, target checkpoint, and evaluator script revision.

Trainer changes:

- Added deeper-draft initialization controls in
  `scripts/train-qwen36-eagle1-draft.py`:
  - `--repeat-last-init-layer`: copy the last checkpoint layer into added
    layers. This was tested and rejected.
  - `--zero-extra-init-layer`: zero added layer matrices. This preserves output
    but is mostly dead for training because zeroing every matrix removes useful
    gradients through the added layer.
  - `--residual-extra-init-layer`: copy the last checkpoint layer into added
    layers, then zero only `self_attn.o_proj.weight` and
    `mlp.down_proj.weight`. This starts as a residual no-op while preserving
    trainable q/k/v and gate/up features.
  - `--freeze-init-base-layers`: freeze `fc` and checkpoint-loaded layers so
    only added residual layers train.
- A zero-step 3-layer residual-extra checkpoint exactly preserved the capped
  stride-4 control (`1.929688`) and froze the two loaded base layers, so this
  is the correct initializer for future deeper-draft work.

Results:

| checkpoint | capped stride-4 | smoke stride-1 | expanded stride-4 | decision |
|---|---:|---:|---:|---|
| 2-layer rollout5 control | `1.929688` | `1.741379` | `1.132812` | current control |
| 3-layer repeat-init expanded2 | `1.921875` | `1.793103` | `1.132812` | reject; capped regression |
| 3-layer repeat-init old-only | `1.898438` | `1.793103` | `1.117188` | reject; capped regression |
| 3-layer residual-init expanded2, base frozen | `1.890625` | `1.758621` | `1.125000` | reject; capped and expanded regression |
| 3-layer residual-init old-only, base frozen | `1.929688` | `1.741379` | `1.109375` | reject; neutral on accepted gates, worse expanded |

Decision:

- Do not promote any 3-layer EAGLE checkpoint from this batch to endpoint
  testing.
- Deeper capacity is not enough under the current objective. Repeat-init
  changes the function and damages the accepted gate. Residual-init is the
  right way to add trainable depth, but training only a third residual layer
  did not improve acceptance.
- Future EAGLE work should change the objective/data loop before further
  endpoint tests: use explicit train/validation splits, checkpoint selection by
  offline acceptance instead of final batch metrics, scheduled rollout training,
  and possibly token-margin or top-k-distillation losses. Any future offline
  report must record `start_stride`.
- Since EAGLE acceptance remains far below the synthetic k5 ceiling, the next
  no-quality-loss performance branch should return to exact MoE work unless a
  stronger draft-training objective is implemented.

Checkpoint-selection follow-up:

- Added `--checkpoint-every` to `scripts/train-qwen36-eagle1-draft.py` so
  intermediate draft checkpoints can be selected by offline acceptance instead
  of final batch metrics.
- Reran the residual-extra old-only setup with checkpoints every 50 steps:
  `data/qwen36-eagle3-rollout5-residualextra-oldonly-ckpt-trained-20260618s`.
- Capped stride-4 sweep artifact:
  `data/qwen36-eagle3-residualextra-oldonly-checkpoint-capped-sweep-20260618s.jsonl`.
- Best checkpoints were `step-000050`, `step-000100`, `step-000500`, and
  `final`, all tied the control at `1.929688`. No checkpoint exceeded the
  accepted 2-layer rollout5 control.
- Decision: checkpoint selection is useful infrastructure, but this residual
  old-domain objective still produces no EAGLE acceptance win.

## 2026-06-19 Addendum - Direct GEMM2+Gather Epilogue Rejected

User asked to pursue exact MoE optimization first, with GEMM2+gather epilogue
fusion before escalating to a persistent one-dispatch layerlet.

Implementation:

- Added an opt-in diagnostic path in
  `/home/steve/src/vllm-xpu-kernels/csrc/xpu/moe_layerlet.cpp`.
- Env flag:
  `VLLM_XPU_MOE_W8A8_DIRECT_GEMM2_GATHER=1`.
- The path is only used for single-token, top-k=8, BF16/FP16 output shapes.
- It preserves the current exact math boundary by:
  - keeping prologue/quant1, GEMM1, and activation/quant2 unchanged;
  - computing each selected GEMM2 expert row directly from W8A8 int32 sums;
  - applying the same activation scale and per-expert output-channel weight
    scale;
  - casting each GEMM2 row value to BF16/FP16 before weighted gather, matching
    the accepted materialized GEMM2 row semantics.
- Added the flag to route replay runtime identity in
  `/home/steve/llm-optimizations/scripts/bench-qwen36-int8-moe-kernels.py`.
- Rebuilt and staged:
  `/home/steve/src/vllm-xpu-kernels/build/xpu-c-only-2025/_xpu_C.abi3.so`
  copied to
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so`.

Smoke replay:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-directgemm2gather-route0-smoke-device0-20260619.json`.
- Identity:
  `ONEAPI_DEVICE_SELECTOR=level_zero:0`, `ZE_AFFINITY_MASK=0`,
  route fixture
  `qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl`,
  rows=1, route start 0, direct flag enabled.
- Exactness:
  `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0` and
  `full_layerlet_vs_rows_oracle_max_abs_diff = 0.0`.
- Timing:
  direct full layerlet `200.595 us`; same-run middle layerlet `169.842 us`.

Multi-route replay:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-directgemm2gather-routes7-device0-20260619.json`.
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-directgemm2gather-routes7-device0-20260619.md`.
- Routes:
  `0,40,80,85,95,100,115`.
- Exactness:
  all rows `max_abs_diff = 0.0` versus both `xpu_fused_moe` and rows-oracle.
- Direct full-layerlet timing:
  min/mean/max `168.969 / 190.527 / 200.715 us`, `0/7` rows under
  `160 us`.
- Same-run middle-layerlet timing:
  min/mean/max `171.844 / 198.937 / 228.868 us`, `0/7` rows under
  `160 us`.

Decision:

- Reject the simple direct GEMM2+gather replacement for speed.
- It proves the direct math can be exact, but it gives up the optimized DPAS
  grouped-GEMM execution and is slower despite removing the separate gather
  launch.
- Do not wire this path into the endpoint or benchmark it as a candidate.
- Keep it as a disabled diagnostic only unless we later need a correctness
  oracle for a true fused epilogue.

Next exact MoE work:

- Stop small wrapper/fast-gather/q1/policy knobs.
- The next patch should be a true larger boundary:
  1. persistent/one-dispatch W8A8 MoE layerlet that keeps descriptors,
     expert pointers, route buffers, scratch, and output buffers resident; or
  2. a real grouped-GEMM epilogue modification that accumulates weighted GEMM2
     output inside the DPAS GEMM store path while preserving BF16 row rounding.
- Gate remains offline first: route replay exactness `max_abs_diff = 0.0`,
  repeated timing, target below the current `160-180 us` layerlet band before
  any endpoint work.

## 2026-06-19 Addendum - DPAS TopK8 GEMM2+Gather Prototype Rejected

Follow-up to the direct GEMM2+gather diagnostic above. The direct scalar
kernel was exact but slow because it abandoned the optimized DPAS grouped-GEMM
path. I prototyped a narrower DPAS-backed top-k8 GEMM2+gather path to test the
best plausible version of "GEMM2 + gather epilogue first" before escalating to
the persistent layerlet.

Implementation:

- Added a new opt-in XE2 diagnostic path:
  `VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER=1`.
- Added follow-up column tile selectors for this diagnostic path:
  `VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER_NTILE=32` and
  `VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER_NTILE=16`. Unset/default remains the
  original N64 policy.
- Main code paths touched:
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.hpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/gemm_xe2_policy.hpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.cpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.h`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/grouped_gemm_interface.cpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/grouped_gemm_interface.h`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/moe_layerlet.cpp`
  - `/home/steve/llm-optimizations/scripts/bench-qwen36-int8-moe-kernels.py`
- The kernel shape is one workgroup per output column tile. Each workgroup
  loops the 8 routed experts in top-k order, uses DPAS for each selected expert
  row, casts each expert row value to BF16/FP16 before route weighting, then
  stores the final accumulated token output.
- This avoids atomics and preserves the accepted deterministic gather order.
- The path remains disabled by default and is not wired into endpoint launch
  identity.

Build/import:

- Build command:
  `cmake --build /home/steve/src/vllm-xpu-kernels/build/xpu-c-only-2025 -j 8`.
- Build completed successfully.
- Rebuilt modules copied into:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so` and
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_moe_C.abi3.so`.
- Import check confirmed `torch.ops._xpu_C.qwen36_moe_w8a8_full_layerlet` is
  available.

Smoke replay:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-dpasgemm2gather-route0-smoke-device0-20260619.json`.
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-dpasgemm2gather-route0-smoke-device0-20260619.md`.
- Exactness:
  `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0`.
- Timing:
  full layerlet `176.817 us`, above the `160 us` promotion gate.

Multi-route replay:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-dpasgemm2gather-routes7-device0-20260619.json`.
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-dpasgemm2gather-routes7-device0-20260619.md`.
- Identity:
  `ZE_AFFINITY_MASK=0`, `VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER=1`,
  route fixture
  `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`,
  layer regex `layers[.]9[.]`, rows=1, route starts
  `0,40,80,85,95,100,115`, warmup=20, iterations=100.
- Exactness:
  all 7 rows have `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0`.
- Timing:
  full-layerlet min/mean/max `161.554 / 172.244 / 178.651 us`.
- Gate:
  `0/7` rows under `160 us`;
  status `exact_nonreference_candidates_exist_but_gate_not_met`.

N-tile replay follow-up:

- Purpose:
  test whether the DPAS prototype was underparallelized by the default N64
  output tile.
- N32 artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-dpasgemm2gather-ntile32-routes7-device0-20260619.json`.
- N32 markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-dpasgemm2gather-ntile32-routes7-device0-20260619.md`.
- N32 identity adds:
  `VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER_NTILE=32`.
- N32 exactness:
  all 7 rows have `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0`.
- N32 timing:
  full-layerlet min/mean/median/p90/max
  `170.550 / 176.388 / 173.695 / 191.394 / 189.810 us`; `0/7` rows under
  `160 us`.
- N16 artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-dpasgemm2gather-ntile16-routes7-device0-20260619.json`.
- N16 markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-dpasgemm2gather-ntile16-routes7-device0-20260619.md`.
- N16 identity adds:
  `VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER_NTILE=16`.
- N16 exactness:
  all 7 rows have `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0`.
- N16 timing:
  full-layerlet min/mean/median/p90/max
  `164.743 / 182.092 / 177.334 / 214.518 / 211.275 us`; `0/7` rows under
  `160 us`.

Decision:

- Reject the DPAS top-k8 GEMM2+gather prototype as a speed candidate.
- It is exact and improves on the scalar direct diagnostic in the default N64
  form, but it still does not beat the existing full-layerlet enough to justify
  endpoint integration.
- N32 and N16 remain exact but are slower, so changing the column tile is not
  the missing lever.
- Likely reason: one-workgroup-per-column-tile preserves exact order but reduces
  useful parallelism across the 8 experts; the saved gather launch/memory
  traffic does not compensate.
- Keep the prototype disabled and recorded as an offline diagnostic. Do not
  include it in accepted endpoint benchmarks.

Updated next move:

- The GEMM2+gather epilogue branch has now been tested in both simple scalar
  and DPAS-backed deterministic forms. Both preserve quality but miss speed.
- Escalate to the larger exact boundary: persistent/one-dispatch W8A8 MoE
  layerlet or an equivalent deterministic kernel that keeps the existing DPAS
  parallelism while reducing launch/host/descriptor overhead.
- Any next candidate must still pass route replay exactness at
  `max_abs_diff = 0.0` before endpoint or quality-gate work.

## 2026-06-19 Addendum - Workspace Atomic Reuse Rejected

After rejecting GEMM2+gather epilogue variants, I tested one smaller
fixed-overhead cut before escalating to a true persistent layerlet: remove the
tiny per-GEMM `atomic_buffer = at::empty({1}, int32)` allocation inside the
grouped GEMM offsets launcher when called from the full layerlet.

Implementation:

- Added an opt-in diagnostic flag:
  `VLLM_XPU_MOE_W8A8_WORKSPACE_ATOMIC=1`.
- Added internal C++ wrappers to pass a raw `int*` atomic buffer into the XE2
  W8A8 INT8 offsets grouped GEMM path:
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/grouped_gemm_interface.h`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/grouped_gemm_interface.cpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.h`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.cpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/moe_layerlet.cpp`
- The full layerlet reuses the first `int` slot of the existing uint8 prologue
  workspace after prologue/quant1 completes. This keeps the current optimized
  DPAS GEMM kernels and output order unchanged.
- The path is disabled by default and was not wired into endpoint launches.

Build/import:

- Targeted build:
  `cmake --build /home/steve/src/vllm-xpu-kernels/build/xpu-c-only-2025 --target _xpu_C -j 4`.
- Build completed successfully after the heavy XE2 grouped-GEMM translation
  unit compiled.
- Rebuilt modules copied into:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so` and
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_moe_C.abi3.so`.
- Import check confirmed `torch.ops._xpu_C.qwen36_moe_w8a8_full_layerlet` is
  available.

Route replay:

- Candidate artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-workspaceatomic-routes7-device0-20260619.json`.
- Candidate markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-workspaceatomic-routes7-device0-20260619.md`.
- Adjacent control artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-workspaceatomic-control-routes7-device0-20260619.json`.
- Adjacent control markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-workspaceatomic-control-routes7-device0-20260619.md`.
- Shared identity:
  `ZE_AFFINITY_MASK=0`, route fixture
  `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`,
  layer regex `layers[.]9[.]`, rows=1, route starts
  `0,40,80,85,95,100,115`, warmup=20, iterations=100.
- Candidate adds:
  `VLLM_XPU_MOE_W8A8_WORKSPACE_ATOMIC=1`.
- Exactness:
  candidate and adjacent control both have
  `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0` on all 7 rows.
- Candidate full-layerlet min/mean/median/p90/max:
  `168.110 / 174.518 / 173.856 / 183.004 / 182.163 us`; `0/7` rows under
  `160 us`.
- Adjacent control full-layerlet min/mean/median/p90/max:
  `161.697 / 166.446 / 166.044 / 177.249 / 175.779 us`; `0/7` rows under
  `160 us`.

Decision:

- Reject workspace atomic reuse as a speed candidate.
- It is exact, but adjacent control is materially faster in this replay.
- This confirms that the next serious work should not spend more time on tiny
  allocation cleanup inside the current staged layerlet. Move to the larger
  persistent/one-dispatch W8A8 MoE boundary, or an equivalent deterministic
  kernel that keeps route state, descriptors, scratch, and DPAS work resident.

## 2026-06-19 Addendum - Route-Known GEMM1 Diagnostic Rejected

After the GEMM2+gather and workspace-atomic branches missed the promotion gate,
I tested the symmetric GEMM1-side question: whether the c1/top-k8 route-known
shape can bypass the generic grouped-GEMM scheduler for GEMM1 and directly
launch one DPAS workgroup family per routed expert row.

Implementation:

- Added a disabled-by-default diagnostic flag:
  `VLLM_XPU_MOE_W8A8_ROUTE_GEMM1=1`.
- Added tile selector:
  `VLLM_XPU_MOE_W8A8_ROUTE_GEMM1_MTILE=8|32`; unset/default uses M16.
- The diagnostic path is gated to the exact single-token Qwen 3.6 MoE shape:
  top-k 8, one token, contiguous route rows, grouped GEMM1 output layout, and
  the existing W8A8 INT8 weight/scales format.
- Main code paths touched:
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.hpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.cpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.h`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/grouped_gemm_interface.cpp`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/grouped_gemm_interface.h`
  - `/home/steve/src/vllm-xpu-kernels/csrc/xpu/moe_layerlet.cpp`
  - `/home/steve/llm-optimizations/scripts/bench-qwen36-int8-moe-kernels.py`
- The full layerlet falls back to the accepted grouped-GEMM path unless the
  diagnostic flag and shape gate both pass.
- The path remains offline-only and is not an endpoint candidate.

Build/import:

- Targeted build:
  `cmake --build /home/steve/src/vllm-xpu-kernels/build/xpu-c-only-2025 --target _xpu_C -j 4`.
- Build completed successfully.
- Rebuilt extension copied into:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so`.
- Import check confirmed `torch.ops._xpu_C.qwen36_moe_w8a8_full_layerlet` is
  available.

Route replay:

- Shared identity:
  `ZE_AFFINITY_MASK=0`, route fixture
  `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`,
  layer regex `layers[.]9[.]`, rows=1, route starts
  `0,40,80,85,95,100,115`, warmup=20, iterations=100,
  target `160 us`.
- Adjacent control artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-routegemm1-control-routes7-device0-20260619.json`.
- Adjacent control markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-routegemm1-control-routes7-device0-20260619.md`.
- M16 artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-routegemm1-m16-routes7-device0-20260619.json`.
- M16 markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-routegemm1-m16-routes7-device0-20260619.md`.
- M8 artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-routegemm1-m8-routes7-device0-20260619.json`.
- M8 markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-routegemm1-m8-routes7-device0-20260619.md`.
- M32 artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-routegemm1-m32-routes7-device0-20260619.json`.
- M32 markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-routegemm1-m32-routes7-device0-20260619.md`.
- Exactness:
  control, M16, M8, and M32 all have
  `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0` on all 7 rows.

Timing:

- Adjacent control route/full_us:
  `0:162.311`, `40:166.755`, `80:170.076`, `85:166.611`,
  `95:167.100`, `100:165.555`, `115:161.335`.
- Adjacent control min/mean/median/p90/max:
  `161.335 / 165.677 / 166.611 / 170.671 / 170.076 us`; `0/7` rows under
  `160 us`.
- M16 route/full_us:
  `0:173.424`, `40:167.312`, `80:162.484`, `85:163.872`,
  `95:163.861`, `100:164.664`, `115:161.763`.
- M16 min/mean/median/p90/max:
  `161.763 / 165.340 / 163.872 / 174.647 / 173.424 us`; `0/7` rows under
  `160 us`.
- M8 min/mean/median/p90/max:
  `167.183 / 176.882 / 177.742 / 190.124 / 188.642 us`; `0/7` rows under
  `160 us`.
- M32 min/mean/median/p90/max:
  `162.336 / 175.938 / 171.121 / 200.497 / 198.761 us`; `0/7` rows under
  `160 us`.

Decision:

- Reject route-known GEMM1 as a speed candidate.
- M16 is exact and marginally lower mean than this adjacent control, but the
  improvement is too small, the worst row regresses, and no row passes the
  `160 us` target.
- M8 and M32 are exact but clearly slower.
- This result closes another small-wrapper branch. The missing speed is not in
  isolated GEMM1 wrapper selection. The next serious branch remains a true
  larger exact MoE boundary: one-dispatch/resident layerlet, fused activation
  plus GEMM2, or an equivalent deterministic DPAS pipeline that removes launch
  and descriptor overhead without changing output order or BF16 accumulation.

## 2026-06-19 Addendum - TP4 Health Still Blocked; Route-Class AOT Not Broad Enough

After closing route-known GEMM1, I refreshed the two decision gates that decide
whether to keep working TP4 endpoint timing or route-class-specific kernels.

TP4 XPU/XCCL health:

- TP4 health log:
  `/home/steve/llm-optimizations/data/qwen36-xpu-health-tp4-20260619-routegemm1-followup.log`.
- Result:
  physical devices 0, 1, and 2 pass the single-device XPU smoke.
- Physical device 3 fails standalone allocation:
  `RuntimeError: level_zero backend failed with error: 40 (UR_RESULT_ERROR_OUT_OF_RESOURCES)`.
- XCCL TP4 then fails at rank 3 in `dist.barrier(...)` with the same
  Level Zero out-of-resources error.
- `xpu-smi ps` showed no long-running vLLM/Python model workers holding VRAM;
  only transient `xpu-smi` processes appeared.
- `xpu-smi diag -d 3 -l 1 -j` aborts with
  `terminate called without an active exception`.
- `xpu-smi config -d 3 --reset` is available but failed as the current user.
  Noninteractive sudo is not available, and `/sys/bus/pci/devices/0000:47:00.0/reset`
  is root-only.
- Healthy subset log:
  `/home/steve/llm-optimizations/data/qwen36-xpu-health-devices012-20260619-routegemm1-followup.log`.
- Devices 0, 1, and 2 pass single-device XPU smoke and XCCL all-reduce.

Decision:

- Do not trust TP4 endpoint results until device 3 is reset externally or after
  reboot and the TP4 preflight passes.
- The accepted launcher already has the correct fail-closed guard:
  `QWEN36_XPU_PREFLIGHT=auto` runs
  `/home/steve/llm-optimizations/scripts/check-qwen36-xpu-xccl-health.sh` for
  `TP_SIZE >= 4` and refuses to start if the health gate fails.
- While device 3 is wedged, exact offline kernel replay on device 0 is still
  useful, and endpoint experiments should use only healthy subsets or be marked
  blocked for TP4.

Route-class AOT/cache refresh:

- Route-class AOT JSON:
  `/home/steve/llm-optimizations/data/qwen36-routeclass-aot-routecapture6-20260619.json`.
- Route-class AOT markdown:
  `/home/steve/llm-optimizations/data/qwen36-routeclass-aot-routecapture6-20260619.md`.
- Route signature cache JSON:
  `/home/steve/llm-optimizations/data/qwen36-route-signature-cache-routecapture6-20260619.json`.
- Route signature cache markdown:
  `/home/steve/llm-optimizations/data/qwen36-route-signature-cache-routecapture6-20260619.md`.
- Routecapture6 has 285 records across 3 layers, and all 285 ordered top-k
  route classes are unique in this sample.
- Status:
  `needs_more_route_windows_before_aot_commit`.
- Coverage is weak for exact route-class kernels:
  top 32 classes per layer cover only `0.337` of the layer records, and every
  top-k class count is 1 in this fixture.

Decision:

- Do not spend the next implementation cycle on exact ordered top-k route-class
  AOT kernels from this fixture. The observed route reuse is too low.
- A broad speed win still needs a generic one-dispatch/resident MoE layerlet,
  a lower-latency TP/collective layout after hardware health is fixed, or a
  token-verified speculation path with exact verifier parity.

## 2026-06-19 Addendum - Full Layerlet Graph Replay Rejected

I tested whether graph replay of the current exact full MoE layerlet removes
enough launch/dispatch overhead to make the existing boundary worth promoting.

Artifacts:

- JSON:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-graphreplay-control-routes7-device0-20260619.json`.
- Markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-graphreplay-control-routes7-device0-20260619.md`.

Run identity:

- Device-local offline replay, `ZE_AFFINITY_MASK=0`.
- `rows=1`, `warmup=20`, `iterations=80`.
- Route source:
  `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Layer regex `layers[.]9[.]`.
- Route starts `0,40,80,85,95,100,115`.
- Current exact full layerlet, no route-GEMM1 env enabled.

Normal full layerlet timing:

- Route/full_us:
  `0:163.709`, `40:170.123`, `80:164.201`, `85:161.504`,
  `95:167.763`, `100:167.834`, `115:167.326`.
- Min/mean/median/max:
  `161.504 / 166.066 / 167.326 / 170.123 us`.
- Exactness:
  all rows have `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0`.

Graph replay timing:

- `full_layerlet` graph replay route/us:
  `0:181.851`, `40:195.768`, `80:179.414`, `85:179.286`,
  `95:186.839`, `100:181.281`, `115:177.510`.
- Min/mean/median/max:
  `177.510 / 183.136 / 181.281 / 195.768 us`.
- Other graph replay boundaries were also slower or unstable in this fixture:
  `xpu_fused_moe_with_scratch` mean `313.858 us`,
  `preallocated_staged` mean `253.763 us`, and
  `fused_prologue_staged` mean `229.347 us`.

Decision:

- Reject graph replay of the current full layerlet as a speed candidate.
- The current full layerlet is exact but remains in the `~161-170 us` route band,
  while graph replay makes this fixture slower rather than faster.
- The next exact/no-quality-loss work should not be another wrapper replay of
  the same boundary. It should either reshape the MoE compute boundary itself
  with a resident one-dispatch layerlet, repair speculation verifier parity to
  create verified multi-token work, or use a healthy-card endpoint layout that
  reduces TP/collective latency without changing outputs.

## 2026-06-19 Addendum - q1 + Route-GEMM1 Combo Is Exact But Unstable

Before starting a larger rewrite, I checked whether already-rejected exact
subpaths stack into a stable win. The only interesting combo was
`VLLM_XPU_MOE_W8A8_FUSED_Q1=1` plus
`VLLM_XPU_MOE_W8A8_ROUTE_GEMM1=1`.

Initial combo sweep:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-combo-q1-routegemm1-routes7-device0-20260619.json`.
- Route/full_us:
  `0:158.337`, `40:158.479`, `80:171.398`, `85:157.696`,
  `95:157.323`, `100:157.864`, `115:157.953`.
- Min/mean/median/max:
  `157.323 / 159.864 / 157.953 / 171.398 us`.
- Exactness:
  all rows have `full_layerlet_vs_xpu_fused_moe_max_abs_diff = 0.0`.

Repeat gate:

- Adjacent control:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-control-repeat100-a-routes7-device0-20260619.json`.
- q1 + route-GEMM1 repeat A:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-q1-routegemm1-repeat100-a-routes7-device0-20260619.json`.
- q1 + route-GEMM1 repeat B:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-q1-routegemm1-repeat100-b-routes7-device0-20260619.json`.
- q1 + route-GEMM1 M8:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-q1-routegemm1-repeat100-m8-routes7-device0-20260619.json`.
- q1 + route-GEMM1 M32:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-q1-routegemm1-repeat100-m32-routes7-device0-20260619.json`.

Repeat timing:

- Control min/mean/median/max:
  `162.568 / 169.427 / 167.591 / 177.143 us`; `0/7` rows under `160 us`.
- q1 + route-GEMM1 repeat A:
  `158.042 / 168.391 / 164.461 / 187.160 us`; `3/7` rows under `160 us`.
- q1 + route-GEMM1 repeat B:
  `158.862 / 170.901 / 167.939 / 186.982 us`; `1/7` rows under `160 us`.
- q1 + route-GEMM1 M8:
  `165.230 / 177.547 / 169.780 / 205.600 us`; `0/7` rows under `160 us`.
- q1 + route-GEMM1 M32:
  `165.580 / 174.773 / 177.906 / 185.706 us`; `0/7` rows under `160 us`.

Decision:

- Reject q1 + route-GEMM1 as an endpoint promotion candidate for now.
- It is exact, and the first sweep showed it can hit the target band, but the
  repeated route distribution is not stable enough and the mean does not
  reliably beat adjacent control.
- M8 and M32 route-GEMM1 tiles are clearly worse in combination.
- Keep this result as evidence that q1 and route-local GEMM1 interact, but do
  not enable it in the accepted launcher without a stronger resident/persistent
  implementation and full endpoint quality gates.

## 2026-06-19 Addendum - DFlash Draft Is Active But Native Verifier Still Fails

I tested the public DFlash draft model as a possible no-quality-loss route to
verified multi-token decode, but only as a quality/parity smoke. This was not a
speed promotion.

Draft model:

- HF repo:
  `z-lab/Qwen3.6-35B-A3B-DFlash`.
- Revision:
  `42d3b34d588423cdae7ba8f53a8cf7789346a719`.
- Local snapshot:
  `/mnt/fast-ai/llm-cache/hf/models--z-lab--Qwen3.6-35B-A3B-DFlash/snapshots/42d3b34d588423cdae7ba8f53a8cf7789346a719`.
- Cache size:
  `905M`.
- Config:
  `architectures=["DFlashDraftModel"]`, `num_hidden_layers=8`,
  `block_size=16`, `dflash_config.mask_token_id=248070`,
  `dflash_config.target_layer_ids=[1,10,19,28,37]`.

Kernel/runtime prerequisite fixed:

- The first DFlash smoke failed before model load because the local
  `vllm_xpu_kernels._xpu_C` extension could not import:
  `libgrouped_gemm_xe_2.so` was stale and missing the new route-GEMM1 symbols.
- I rebuilt and reinstalled `_xpu_C` and copied the rebuilt grouped GEMM/GDN
  shared libraries into `vllm_xpu_kernels/`.
- Import and XPU platform detection now work again:
  `_xpu_C import ok`, `current_platform.device_type == "xpu"`.

Parity runner/tooling:

- Added reusable runner:
  `/home/steve/llm-optimizations/scripts/run-qwen36-spec-parity-candidate.sh`.
- Hardened replay decoding in:
  `/home/steve/llm-optimizations/scripts/replay-qwen36-spec-trace.py`.
- Reason:
  DFlash trace rows use `scheduled_spec_token_ids=[-1,...]`, and the replay
  report should preserve those placeholders instead of crashing during
  tokenizer decode.

Smoke run:

- Label:
  `qwen36-dflash-k15-eager-tp2-smoke-20260619b`.
- Launch identity:
  TP2 on XPUs `0,1`, eager, XPU graph off, GPU memory utilization `0.82`,
  prompt `512`, output `32`,
  speculative config
  `{"method":"dflash","model":"...Qwen3.6-35B-A3B-DFlash/...42d3b34d...","num_speculative_tokens":15}`.
- Server log:
  `/home/steve/llm-optimizations/data/qwen36-dflash-k15-eager-tp2-smoke-20260619b-20260619dflashsmoke2.log`.
- Candidate output:
  `/home/steve/llm-optimizations/data/qwen36-dflash-k15-eager-tp2-smoke-20260619b-20260619dflashsmoke2-candidate.json`.
- Spec trace:
  `/home/steve/llm-optimizations/data/qwen36-dflash-k15-eager-tp2-smoke-20260619b-20260619dflashsmoke2-spec-trace.jsonl`.

Result:

- DFlash was active:
  `draft_tokens=90`, `accepted=35`, `rejected=55`,
  accept rate `38.888888888888886%`.
- Replay after the tooling fix:
  `/home/steve/llm-optimizations/data/qwen36-dflash-k15-eager-tp2-smoke-20260619b-20260619dflashsmoke2-replay-rerun.json`.
- Replay accounting:
  `accounting_mismatch_count=0`, `generated mismatches=0`,
  `schedule mismatches=0`, `accept mismatches=0`.
- Exact quality gate:
  `/home/steve/llm-optimizations/data/qwen36-dflash-k15-eager-tp2-smoke-20260619b-20260619dflashsmoke2-gate-summary-rerun.json`.
- Gate status:
  `pass=false`, `mismatch_count=1`.

First mismatch:

- Fixture:
  `/home/steve/llm-optimizations/data/qwen36-dflash-k15-eager-tp2-smoke-20260619b-20260619dflashsmoke2-fixture-rerun.json`.
- Output index:
  `24`.
- Accepted/no-spec token:
  `271` (`\n\n`).
- DFlash/native-verifier candidate token:
  `198` (`\n`).
- Accepted window:
  `[11,321,874,4131,4557,13,271,248068,271,248069,271,16,13,2972,10886,38563]`.
- Candidate window:
  `[11,321,874,4131,4557,13,271,248068,198,90700,8340,25,271,16,13,220]`.
- Replay mapping:
  trace row `4`, emission role `replacement_after_reject`,
  `num_accepted=0`, `num_rejected=15`,
  `scheduled_spec_token_ids=[-1 x 15]`, `generated_token_ids=[198]`.

Decision:

- Reject DFlash as a promotion candidate until native verifier parity is fixed.
- The draft model is useful because it is active and has nonzero acceptance,
  but it exposes the same verifier/recovery correctness failure around the
  `248068` region seen in prior native verifier probes.
- Next highest-leverage correctness work is to repair the normal native
  verifier/GDN state transaction around rejected speculative rows, then rerun
  this DFlash fixture and the existing oracle fixtures before making any speed
  claim.

Follow-up DFlash recovery flag tests:

- Full preempt replacement recovery:
  `qwen36-dflash-k15-eager-tp2-recover-replacement-20260619a-20260619dflashrecover1`.
  Flags:
  `VLLM_XPU_SPEC_DECODE_SUPPRESS_REPLACEMENT=1`,
  `VLLM_XPU_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT=1`,
  `VLLM_XPU_SPEC_DECODE_RESUME_AFTER_RECOVERY_PREEMPT=1`,
  `VLLM_XPU_SPEC_DECODE_RECOVERY_FORCE_SINGLE_STEPS=16`.
  Result:
  `pass=false`, accept rate `11.666666666666666%`.
  First mismatch moved earlier to output index `2`; the candidate duplicated
  token `440` (`with`) where baseline expected token `27044` (` dense`).
  Fixture:
  `/home/steve/llm-optimizations/data/qwen36-dflash-k15-eager-tp2-recover-replacement-20260619a-20260619dflashrecover1-fixture.json`.

- No-preempt replacement suppression:
  `qwen36-dflash-k15-eager-tp2-no-preempt-replacement-20260619a-20260619dflashnopreempt1`.
  Flags:
  `VLLM_XPU_SPEC_DECODE_SUPPRESS_REPLACEMENT=1`,
  `VLLM_XPU_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT=1`,
  `VLLM_XPU_SPEC_DECODE_NO_PREEMPT_SUPPRESSED_REPLACEMENT=1`.
  Result:
  `pass=false`, accept rate `32.38095238095238%`.
  First mismatch at output index `4`; the candidate repeated the accepted
  prefix `[440,27044,47193]` before continuing.
  Fixture:
  `/home/steve/llm-optimizations/data/qwen36-dflash-k15-eager-tp2-no-preempt-replacement-20260619a-20260619dflashnopreempt1-fixture.json`.

Decision:

- Simple flag-only DFlash replacement recovery is rejected.
- Full-preempt recovery replays from too early a boundary.
- No-preempt replacement suppression repeats the accepted prefix.
- DFlash remains useful as a verifier bug reproducer, but it is not the next
  promotion lane until the GDN/KV transaction is fixed in code.

Additional DFlash follow-up on 2026-06-19:

- Tried a scheduler-side deferred-placeholder guard so forced recovery steps
  would not refill `scheduled_spec_decode_tokens` in
  `update_draft_token_ids_in_output`.
  Run:
  `qwen36-dflash-k15-eager-tp2-no-preempt-replacement-20260619b-20260619dflashnopreempt2`.
  Result:
  still `pass=false`, accept rate `32.38095238095238%`, first mismatch at
  output index `4`, same repeated accepted prefix
  `[440,27044,47193]`. I reverted the guard because it was ineffective.
- Tried replaying the accepted prefix plus suppressed replacement as ordinary
  recovery decode:
  `VLLM_XPU_SPEC_DECODE_REPLAY_SUPPRESSED_REPLACEMENT_ACCEPTED=1`,
  `VLLM_XPU_SPEC_DECODE_EAGER_REPLACEMENT_RECOVERY=1`,
  `VLLM_XPU_SPEC_DECODE_EAGER_ALL_RECOVERY_STEPS=1`.
  Run:
  `qwen36-dflash-k15-eager-tp2-replay-accepted-replacement-20260619a-20260619dflashreplayaccepted1`.
  Result:
  endpoint failed before producing a candidate with
  `UR_RESULT_ERROR_DEVICE_LOST` in rotary embedding after a scheduler output
  still contained `num_scheduled_tokens=16` and placeholder
  `scheduled_spec_decode_tokens=[-1 x 15]` during a forced recovery phase.
  Reject this flag stack as unstable.
- Scoped post-crash health check for the actual TP2 cards passed:
  `/home/steve/llm-optimizations/data/qwen36-xpu-health-devices01-after-dflash-replayaccepted-scoped-20260619.log`.
- Full physical/XCCL health still shows device `3` unhealthy:
  `/home/steve/llm-optimizations/data/qwen36-xpu-health-devices01-after-dflash-replayaccepted-20260619.log`.

Updated decision:

- Stop flag-level DFlash recovery work for now. The remaining issue is not a
  one-line scheduler suppression policy; forced recovery can still be paired
  with stale placeholder speculative rows and/or mismatched worker request
  state. A real code fix would need to make recovery scheduling atomic across
  scheduler output, drafter output, worker local token cache, and GDN/KV state.
- For the speed goal, return to exact MoE structural work unless/until the
  verifier transaction gets a dedicated implementation window.

Additional DFlash follow-up on 2026-06-19, later:

- Added diagnostic
  `VLLM_XPU_SPEC_DECODE_REPLAY_ROW_STATEFUL_RECOVERY=1` for
  `VLLM_XPU_SPEC_DECODE_REPLAY_ROW_AFTER_TOKEN_IDS`.  Instead of calling
  `_preempt_request()` and resetting `num_computed_tokens` to zero, it keeps
  the request running, clears speculative IDs/placeholders, sets the replay
  boundary to `visible_tokens - 1`, and forces single-token recovery steps.
  Syntax gate passed:
  `/home/steve/.venvs/vllm-xpu/bin/python -m py_compile ...`.
- Async scheduler run:
  `qwen36-dflash-k15-eager-tp2-stateful-replay-think-20260619b-20260619dflashstateful2`
  crashed with `AsyncScheduler._update_request_with_output` placeholder
  underflow after the stateful row.  The spec trace confirms the row normalized
  to `num_computed_tokens=521`, `num_output_placeholders=0`, `spec_len=0`,
  and did not preempt.  This means async still needs a separate stale in-flight
  scheduler-output transaction if this path is ever revived.
- Synchronous scheduler run:
  `qwen36-dflash-k15-eager-tp2-stateful-replay-think-sync-20260619a-20260619dflashstatefulsync1`
  completed but failed parity.  First diff remained at output index `24`
  after `<think>`: baseline token `271` vs candidate token `198`.  Avoiding
  the long prefill replay is not enough; the native packed verifier rows
  before the recovery point already leave recurrent state non-identical.
- Serial GDN anchor with DFlash:
  `qwen36-dflash-k15-eager-tp2-serial-gdn-sync-20260619a-20260619dflashserial1`
  also failed parity, though it moved the first diff to output index `25`.
  Gate role was `replacement_after_reject`, accept rate was about `25.71%`.
  This shows DFlash is not a near-term promotion lane even with serial GDN;
  it needs a larger verifier/replacement transaction fix, not another
  scheduler-only replay knob.
- Current DFlash conclusion: keep the stateful replay flag only as a diagnostic
  artifact.  Do not claim speed or quality from DFlash.  Return to exact MoE
  layerlet work for the no-quality-loss >150 tok/s goal.

## 2026-06-19 Addendum - Full Layerlet Endpoint Smoke Is Exact But Small

I ran a same-identity TP2 endpoint smoke to check whether the exact C++
`qwen36_moe_w8a8_full_layerlet` route-replay gain survives real endpoint
execution. This used devices `0,1` because physical device `3` is still not
TP4-safe.

Shared identity:

- model:
  `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- `TP_SIZE=2`, `ONEAPI_DEVICE_SELECTOR=level_zero:0,1`,
  `ZE_AFFINITY_MASK=0,1`, `QWEN36_XPU_PREFLIGHT=1`.
- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'`.
- `XPU_GRAPH=1`, `VLLM_XPU_ENABLE_XPU_GRAPH=1`,
  `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`,
  `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`.
- `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`,
  `VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1`,
  `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`,
  `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`,
  `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`.
- `VLLM_EXTRA_ARGS='--uvicorn-log-level warning'`.
- short smoke only: one `512/256` metrics run plus 8-repeat JSON/color
  canaries; quality suite skipped.

Control artifact:

- `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-tp2-control-smoke-20260619a-summary-20260619tp2control1.json`
- corrected decode throughput: `83.68628063307641 tok/s`.
- vLLM histogram decode: `11.948150581702066 ms/token`.
- JSON/color canaries: passed `8/8` each.

Full-layerlet artifact:

- `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-full-layerlet-tp2-smoke-20260619a-summary-20260619fulltp2smoke1.json`
- extra flags: `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`,
  `VLLM_XPU_MOE_W8A8_FULL_LAYERLET=1`.
- corrected decode throughput: `85.45754293668266 tok/s`.
- vLLM histogram decode: `11.702753504323482 ms/token`.
- JSON/color canaries: passed `8/8` each.

Decision:

- The full layerlet is a real but small endpoint improvement in this TP2 smoke:
  about `+1.77 tok/s`, `+2.1%`, or `0.245 ms/token`.
- This is not remotely enough for the `>150 tok/s` goal, and it does not
  justify a production promotion by itself.
- The route replay showed a much larger isolated MoE reduction, so the missing
  gain is likely being absorbed by graph/dispatcher boundaries, collectives,
  GDN/attention, logits/sampling, or other all-rank forward overhead.
- Next step: run decisive live decode timing on the same TP2 identity, comparing
  control versus full-layerlet if possible, then target the largest remaining
  live family rather than adding another tiny MoE wrapper flag.

## 2026-06-19 Addendum - TP2 Decisive Timing Reframes The MoE Target

I ran decisive live decode timing on the same TP2 PIECEWISE identity used by
the full-layerlet smoke above.

Control timing artifacts:

- `/home/steve/llm-optimizations/data/qwen36-prefill-safe-int8-tp2-control-decisive-20260619a-p512o256-20260619tp2timingctl1.json`
- `/home/steve/llm-optimizations/data/qwen36-prefill-safe-int8-tp2-control-decisive-20260619a-timing-decision-20260619tp2timingctl1.json`
- Corrected decode throughput: `84.30754286685192 tok/s`.
- Decode time: `11.861692133606994 ms/token`.

Full-layerlet timing artifacts:

- `/home/steve/llm-optimizations/data/qwen36-prefill-safe-int8-full-layerlet-tp2-decisive-20260619a-p512o256-20260619tp2timingfull1.json`
- `/home/steve/llm-optimizations/data/qwen36-prefill-safe-int8-full-layerlet-tp2-decisive-20260619a-timing-decision-20260619tp2timingfull1.json`
- Extra flags: `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`,
  `VLLM_XPU_MOE_W8A8_FULL_LAYERLET=1`.
- Corrected decode throughput: `84.4112340056149 tok/s`.
- Decode time: `11.845327250739501 ms/token`.

Key timing result:

- Both decisions still label the largest family as `moe`, but the dominant
  live label is `moe_forward_shared.custom_op`, not the routed W8A8 layerlet.
- Control: `moe_forward_shared.custom_op` max `8.841024 ms`,
  `moe.shared_experts.apply_no_overlap` max `5.772847 ms`,
  `qwen2_moe.shared.silu_and_mul` max `3.394437 ms`,
  `xpu_moe.fused_moe_call` max only `1.318158 ms`.
- Full-layerlet: `moe_forward_shared.custom_op` max `8.720514 ms`,
  `moe.shared_experts.apply_no_overlap` max `5.635415 ms`,
  `qwen2_moe.shared.silu_and_mul` max `3.311749 ms`,
  `xpu_moe.fused_moe_call` max `1.342872 ms`.

Decision:

- The exact C++ routed full-layerlet is still useful as a small building block,
  but it is no longer the highest-probability path to `>150 tok/s`.
- The current live wall is the shared-expert path and/or the graph boundary
  around `moe_forward_shared`, so another routed expert micro-kernel is likely
  to produce only sub-percent endpoint gains.
- Rejected shared-expert paths from earlier remain rejected:
  `VLLM_XPU_SHARED_EXPERTS_STREAM=1` + graph no-empty-cache was quality-clean
  but slowed to `73.7749 tok/s`; `VLLM_XPU_SHARED_EXPERT_ACT_WORKSPACE=1`
  failed canaries under PIECEWISE; `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1`
  was slower and/or replay-nondeterministic; `VLLM_XPU_MOE_SHARED_ADD_ALLREDUCE_CUSTOM_OP=1`
  was quality-clean but slower.
- Next exact candidates should therefore be:
  1. Restore TP4 health first, because TP2 is not the target production shape.
  2. Build an offline shared-expert replay harness that isolates
     `gate_up_proj`, `silu_and_mul`, `down_proj`, `expert_gate`, and `gate_mul`
     under the current INT8 path and tests exact fused/persistent variants
     outside the endpoint before any canary run.
  3. If the shared-expert harness does not show a large exact win, shift back
     to no-quality-loss speculation parity rather than spending more time on
     low-ceiling shared-expert wrappers.

## 2026-06-19 Addendum - Shared-Expert Fused Act/Quant `_out` Is Not Graph-Safe

I tested a narrower shared-expert optimization that reuses preallocated
activation-quantization outputs instead of letting
`silu_and_mul_quant_int8_xpu` allocate fresh tensors. The endpoint flag stack
was:

- `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1`
- `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT_OUT=1`

Microbench result:

- `_xpu_C.silu_and_mul_quant_int8_xpu_out` is mathematically exact against
  separate `silu_and_mul` plus INT8 quantization for the tested shared-expert
  shapes.
- It saves roughly `6-7 us` versus the separate two-op path for
  rows `1..32`, `d=512`.

Endpoint shallow smoke, TP2 PIECEWISE identity:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-tp2-smoke-20260619a-summary-20260619175320.json`
- Corrected decode throughput: `85.47207810078443 tok/s`.
- Decode time: `11.700355452376243 ms/token`.
- JSON/color canaries: passed `8/8` each.

Deep canary under normal PIECEWISE decode replay:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-tp2-deep-canary-20260619a-summary-20260619175659.json`
- JSON failed at repeat index `31`.
- Expected `{"answer":"42","unit":"widgets"}`, got
  `{"answer":"12","unit":"widgets"}`.
- Color passed `96/96`.

Diagnostic replay bypass:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-tp2-eager-everyreq-canary-20260619a-summary-20260619180050.json`
- Extra flag:
  `VLLM_XPU_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS=1`.
- JSON/color both passed `96/96`.
- This points away from arithmetic error and toward graph replay buffer
  ownership/lifetime.

Strong-output replay mitigation:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-tp2-strong-output-canary-20260619a-summary-20260619180502.json`
- Extra flag: `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1`.
- JSON still failed at repeat index `31` with the same `42 -> 12` mismatch.
- Color passed `96/96`.

Decision:

- Reject `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT_OUT=1` for endpoint use.
- The math is exact and the shallow speed signal is real, but reusable
  Python-owned q/scale workspace is unsafe under PIECEWISE decode replay.
- Do not use eager-every-request as a performance workaround; it is a
  correctness diagnostic only.
- Next shared-expert work must make the fused boundary graph-safe. Viable
  directions are:
  1. move the temporary q/scale ownership inside a single custom op or captured
     graph-owned boundary so Python does not reuse graph-visible scratch;
  2. add capture-aware workspace ownership keyed by graph wrapper/static input
     slot, with a replay alias trace proving no stale scratch reuse;
  3. isolate only the corrupting PIECEWISE submodule in eager mode if its
     submod index can be mapped and if the speed loss is small.

The fastest exact path is still shared-expert structural work, but promotion
requires deep canaries under normal PIECEWISE replay, not only eager replay.

## 2026-06-19 Addendum - Async Scheduling Was A Separate Correctness Poison

I retested the current TP2 PIECEWISE forced/noop-comm graph lane after
separating async scheduling from GDN/shared-expert graph replay issues.

Clean TP2/no-async identity:

- `TP_SIZE=2`, devices `0,1`.
- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'`.
- `XPU_GRAPH=1`, `VLLM_XPU_ENABLE_XPU_GRAPH=1`,
  `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`,
  `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`.
- `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`.
- `VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1`.
- `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`.
- `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`.
- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`.
- `VLLM_EXTRA_ARGS='--no-async-scheduling --uvicorn-log-level warning'`.

Control results:

- Canary artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-tp2-control-noasync-canary-20260619a-summary-20260619prefillnoasynca.json`
- Metrics artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-tp2-control-noasync-metrics-20260619a-summary-20260619prefillnoasyncmetricsa.json`
- JSON canary passed `64/64`.
- Color canary passed `16/16`.
- Corrected decode throughput: `82.06149961234053 tok/s`.
- Decode time: `12.19165415864154 ms/token`.

Async separation:

- With async scheduling left enabled, current-code JSON canaries still failed
  around repeat index `21` or `31` with the characteristic `42 -> 12`
  corruption.
- Native GDN decode fallback for layer `0`, layers `0..2`, and even full
  `decode,prefill` GDN fallback did not fix the async failure.
- Full `decode,prefill` GDN fallback plus `--no-async-scheduling` passed
  JSON `64/64` and color `16/16`.
- Therefore, current async scheduling is an independent correctness blocker
  for this endpoint identity. Do not promote async-path speed until the
  repeated canaries pass on the same run identity.

Shared-expert fused `_out` retest under the clean no-async identity:

- Canary artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-noasync-tp2-canary-20260619a-summary-20260619sharedoutnoasync1.json`
- Metrics artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-noasync-tp2-metrics-20260619a-summary-20260619sharedoutnoasyncmetrics1.json`
- Extra flags:
  `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1`,
  `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT_OUT=1`.
- JSON canary passed `64/64`.
- Color canary passed `16/16`.
- Corrected decode throughput: `83.61311830066423 tok/s`.
- Decode time: `11.960592332457054 ms/token`.
- Decision: keep as a small candidate win on the no-async lane
  (`+1.5516186883237 tok/s`, about `+1.9%` versus the clean baseline), but it
  is far too small to explain a path to `>150 tok/s` by itself and still needs
  full quality/reliability gates before production use.

Routed full-layerlet retest under the clean no-async identity:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-full-layerlet-noasync-tp2-candidate-20260619a-summary-20260619fulllayerletnoasync1.json`
- Extra flags:
  `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`,
  `VLLM_XPU_MOE_W8A8_FULL_LAYERLET=1`.
- JSON canary passed `64/64`.
- Color canary passed `16/16`.
- Corrected decode throughput: `82.18196711720888 tok/s`.
- Decode time: `12.17378463775276 ms/token`.
- Decision: reject as an endpoint speed candidate on the clean no-async lane.
  It is quality-clean in this focused gate but essentially baseline speed.

Updated immediate plan:

1. Keep the no-async TP2 identity as the current safe benchmark lane.
2. Try stacking the small shared-expert `_out` candidate only after any larger
   candidate passes; it is not enough to chase alone.
3. Restore TP4/device health next. TP2 clean speed in the low `80 tok/s` range
   is too far from the `>150 tok/s` target without either healthy four-card
   execution or a no-quality-loss multi-token path.
4. If TP4 remains blocked, build the offline shared-expert replay harness and
   pursue a larger fused/persistent shared-expert boundary instead of more
   routed-expert layerlet variants.

## 2026-06-19 Addendum - TP4 Still Blocked, Routed+Shared Stack Does Not Matter

Device/topology health:

- Device `3` still fails a trivial single-device allocation:
  `/home/steve/llm-optimizations/data/qwen36-xpu-health-device3-single-20260619195006.log`
- Error:
  `RuntimeError: level_zero backend failed with error: 40 (UR_RESULT_ERROR_OUT_OF_RESOURCES)`.
- `xpu-smi stats -d 3` reports only `34 MiB` GPU memory used and
  `0%` memory utilization, and `xpu-smi ps -d 3` shows no model process.
- The exposed PCI reset path exists at
  `/sys/bus/pci/devices/0000:47:00.0/reset`, with reset methods `flr bus`,
  but it is root-only and this shell does not have non-interactive sudo.
- Devices `0,1,2` pass fresh single-device and XCCL all-reduce health:
  `/home/steve/llm-optimizations/data/qwen36-xpu-health-devices012-fresh-20260619195121.log`
- TP3 is not a usable fallback for this model: `hidden_size=2048`,
  `num_attention_heads=16`, `num_key_value_heads=2`, `num_experts=256`,
  `num_experts_per_tok=8`, and `vocab_size=248320` are not divisible by `3`.

Conclusion:

- TP4 remains blocked in this session by physical device `3` health.
- TP3 is architecturally incompatible.
- The only reliable exact endpoint topology available right now is TP2 on
  devices `0,1`.

Stacked routed+shared candidate:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedout-full-layerlet-noasync-tp2-candidate-20260619a-summary-20260619sharedoutfulllayerletnoasync1.json`
- Extra flags:
  `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1`,
  `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT_OUT=1`,
  `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`,
  `VLLM_XPU_MOE_W8A8_FULL_LAYERLET=1`.
- JSON canary passed `64/64`.
- Color canary passed `16/16`.
- Corrected decode throughput: `83.64920085436258 tok/s`.
- Decode time: `11.955750166180223 ms/token`.

Decision:

- The routed full-layerlet adds essentially nothing when stacked with the
  shared-expert `_out` candidate (`+0.036 tok/s` over shared `_out` alone).
- Stop spending endpoint runs on routed layerlet variants unless a new offline
  replay result shows a much larger exact win.
- Next engineering target is a shared-expert replay harness that isolates
  `gate_up_proj`, activation/quantization, `down_proj`, `expert_gate`, and
  final multiply/add. The endpoint timing says this is the live TP2 wall.

## 2026-06-19 Addendum - Shared-Expert C++ Boundary Is Correct But Small

Implemented a larger exact shared-expert W8A8 boundary:

- Kernel/binding patch in `/home/steve/src/vllm-xpu-kernels`:
  - `int8_gemm_w8a8_out`.
  - `qwen36_shared_expert_w8a8_out`.
  - Gate weight accepts both replay layout `[hidden, 1]` and live
    `ReplicatedLinear` layout `[1, hidden]` without Python-side contiguous
    transpose.
- Endpoint wiring in
  `/home/steve/src/vllm/vllm/model_executor/models/qwen2_moe.py` behind:
  `VLLM_XPU_SHARED_EXPERT_BOUNDARY_OUT=1`.
- Replay harness:
  `/home/steve/llm-optimizations/scripts/bench-qwen36-shared-expert-replay.py`.

Build lesson:

- Do not use full `pip install -e . --no-build-isolation` for every
  `_xpu_C` kernel iteration; it rebuilds broad attention targets first and
  took too long.
- Use the direct target instead:
  `cmake --build /home/steve/src/vllm-xpu-kernels/build/temp -j=8 --target=_xpu_C`,
  then copy `_xpu_C.abi3.so` and sibling `.so` files into
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/`.

Offline replay:

- Smoke artifact:
  `/home/steve/llm-optimizations/data/qwen36-shared-expert-replay-cppbound-smoke-20260619.md`
- Stable artifact:
  `/home/steve/llm-optimizations/data/qwen36-shared-expert-replay-cppbound-tp2-20260619.md`
- Exact parity: `max_abs_diff = 0` for rows `1,2,4,8,16,32`.
- Stable replay mean C++ boundary timings:
  - rows `1`: `216.180 us` vs baseline `264.540 us`.
  - rows `2`: `206.868 us` vs baseline `250.995 us`.
  - rows `4`: `260.857 us` vs baseline `247.807 us` (slower).
  - rows `8`: `273.691 us` vs baseline `248.311 us` (slower).
  - rows `16`: `208.777 us` vs baseline `283.551 us`.
  - rows `32`: `215.368 us` vs baseline `311.497 us`.

Endpoint canary, same clean TP2/no-async identity:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedboundary-out-noasync-tp2-canary-20260619a-summary-20260619sharedboundarycanary1.json`
- Extra flag: `VLLM_XPU_SHARED_EXPERT_BOUNDARY_OUT=1`.
- JSON canary passed `64/64`.
- Color canary passed `16/16`.

Endpoint metrics, same clean TP2/no-async identity:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedboundary-out-noasync-tp2-metrics-20260619a-summary-20260619sharedboundarymetrics1.json`
- Corrected decode throughput: `83.6714304189521 tok/s`.
- Decode time: `11.952609020454474 ms/token`.

Decision:

- Keep as a correct, opt-in, small candidate.
- It is only about `+1.61 tok/s` over the clean TP2/no-async baseline and
  essentially tied with the previous shared `_out` candidate.
- This does not materially move the `>150 tok/s` target. The next larger work
  must attack routed MoE fixed costs, collectives/topology, or exact
  speculation parity.

## 2026-06-19 Addendum - Shared Boundary Timing and Next Branch

Decisive timing after the shared-expert C++ boundary:

- Run summary:
  `/home/steve/llm-optimizations/data/qwen36-sharedboundary-noasync-tp2-decisive-20260619a-run-summary-20260619sharedboundarytiming1.json`
- Timing decision:
  `/home/steve/llm-optimizations/data/qwen36-sharedboundary-noasync-tp2-decisive-20260619a-timing-decision-20260619sharedboundarytiming1.md`
- Same clean TP2/no-async identity as the accepted current safe lane, plus
  `VLLM_XPU_SHARED_EXPERT_BOUNDARY_OUT=1`.
- Corrected decode throughput on the timing probe:
  `84.10955623702061 tok/s`.
- Main visible labels:
  - `gpu_model_runner.model_forward`: mean `5.363407 ms`.
  - `gpu_model_runner.bookkeeping_sync`: mean `4.679359 ms`.
  - `gdn_attention_core_xpu.native`: mean `1.506388 ms`.
  - `qwen2_moe.shared.boundary_int8_cpp`: mean `1.548210 ms`.

Interpretation:

- The shared-expert boundary is active and exact, but it does not move the
  endpoint enough.
- The routed MoE offline branches already closed today:
  - direct GEMM2+gather: exact, rejected for speed.
  - DPAS GEMM2+gather and N-tile variants: exact, rejected for speed.
  - workspace atomic reuse: exact, rejected for speed.
  - route-known GEMM1: exact, rejected for speed.
  - q1 + route-GEMM1: exact but not stable enough across repeats.
- Do not spend more endpoint time on those small exact MoE flags unless a new
  offline artifact shows a stable sub-`160 us` layerlet across the route set.

Runner hygiene:

- Patched `scripts/run-qwen36-ablation-candidate.sh` and
  `scripts/run-qwen36-decisive-timing.sh` so future summaries record the newer
  W8A8 route flags, DPAS gather flags, workspace-atomic flag, route-GEMM1
  tile flag, shared-expert boundary flag, `VLLM_EXTRA_ARGS`, and
  `GPU_MEMORY_UTILIZATION`.
- `bash -n` passed for both scripts.

Next active plan:

1. Recover a quality-safe fast lane before more endpoint speed claims.
   - Current no-async TP2 safe lane is only `~82-84 tok/s`.
   - TP2 async shallow smoke can pass, but deeper notes show async canary
     corruption; do not promote async until repeated canaries and the quality
     suite pass in the exact identity.
2. Resume oracle/spec parity repair as the largest no-quality-loss path to
   `>150 tok/s`.
   - First target: oracle `k=1` must be token-identical to no-spec on the same
     no-async/PIECEWISE identity.
   - Trace token IDs, positions, slot IDs, KV block state, hidden-state digest,
     and top-k logits at the first divergence.
   - Only after parity, test DFlash/EAGLE/ngram acceptance or wider
     target-verified multi-token decode.
3. Keep TP4 blocked until device `3` XPU/XCCL health is repaired externally.
   TP3 is incompatible with this model, and TP2 is the only healthy exact
   topology available in this shell.

## 2026-06-19 Addendum - Fused Shared Gate/Mul Increment

Implemented an opt-in C++/SYCL epilogue inside the existing shared-expert
W8A8 boundary:

- Kernel source:
  `/home/steve/src/vllm-xpu-kernels/csrc/xpu/moe_layerlet.cpp`
- Runtime flag:
  `VLLM_XPU_SHARED_EXPERT_FUSED_GATE_MUL=1`
- Required surrounding flag:
  `VLLM_XPU_SHARED_EXPERT_BOUNDARY_OUT=1`
- The default path is unchanged when the new flag is unset.
- The ablation wrapper now records the new flag in both the printed guard
  line and summary JSON identity:
  `/home/steve/llm-optimizations/scripts/run-qwen36-ablation-candidate.sh`

Implementation details:

- Replaces only the final shared-expert gate/multiply epilogue:
  `matmul(hidden_states, expert_gate_w) -> sigmoid -> multiply down_out`.
- Keeps the accepted W8A8 quant/GEMM path unchanged.
- Tries to preserve dtype staging by rounding the gate and sigmoid through
  the output dtype before multiplying `down_out`.
- This is exact enough for the current canary and quality gates, but it is
  still gated because its dot-product reduction order differs from the PyTorch
  matmul path.

Build/install:

```bash
JOBS=4 /home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh
cp /tmp/vllm-xpu-xpu-c-only-2025/vllm_xpu_kernels/_xpu_C.abi3.so \
  /home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so
```

Import sanity:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib \
/home/steve/.venvs/vllm-xpu/bin/python -c 'import torch, vllm_xpu_kernels._xpu_C; print(hasattr(torch.ops._xpu_C, "qwen36_shared_expert_w8a8_out"))'
```

Validation identity:

```bash
TP_SIZE=2
ONEAPI_DEVICE_SELECTOR=level_zero:0,1
ZE_AFFINITY_MASK=0,1
QWEN36_XPU_PREFLIGHT=0
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill
VLLM_EXTRA_ARGS='--no-async-scheduling --uvicorn-log-level warning'
VLLM_XPU_SHARED_EXPERT_BOUNDARY_OUT=1
VLLM_XPU_SHARED_EXPERT_FUSED_GATE_MUL=1
GPU_MEMORY_UTILIZATION=0.90
```

Quality/canary artifacts:

- Canary summary:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedgate-mul-noasync-tp2-canary-summary-20260619sharedgatemulcanary1.json`
- JSON canary: passed `64/64`.
- Color canary: passed `16/16`.
- Quality summary:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedgate-mul-noasync-tp2-quality-summary-20260619sharedgatemulquality1.json`
- Quality suite: `pass_all=true`, `baseline_match_all=true`,
  exact arithmetic/copy/json cases passed, repeat passed, long-context passed.

Metrics artifact:

- Summary:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-sharedgate-mul-noasync-tp2-metrics-summary-20260619sharedgatemulmetrics1.json`
- Corrected decode throughput: `84.9100565680358 tok/s`.
- Decode time: `11.777681041849064 ms/token`.
- TTFT: `269.54865898005664 ms`.

Comparable TP2/no-async controls:

- Plain TP2/no-async control:
  `82.06149961234053 tok/s`, `12.19165415864154 ms/token`.
- Shared boundary only:
  `83.6714304189521 tok/s`, `11.952609020454474 ms/token`.
- Fused gate/mul over shared boundary:
  `84.9100565680358 tok/s`, `11.777681041849064 ms/token`.

Decision:

- Keep this as a validated opt-in incremental exact improvement.
- It is about `+2.85 tok/s` over the plain TP2/no-async control and
  `+1.24 tok/s` over the shared-boundary-only endpoint.
- It still does not materially approach the `>150 tok/s` goal.
- Do not spend much more time on tiny shared-expert epilogues. The next win
  needs to remove a larger fixed cost.

Next best branches after this increment:

1. Routed MoE persistent one-dispatch layerlet:
   keep route buffers, descriptors, scales, scratch, GEMM workspaces, and
   output buffers resident; fuse route/remap, quant, GEMM1, activation/quant,
   GEMM2, and gather/combine. Gate offline first with exact replay parity.
2. Exact speculation/oracle parity:
   repair k=1 token identity before attempting wider EAGLE/ngram acceptance.
   This remains the largest plausible no-quality-loss jump to `>150 tok/s`.
3. Async/PIECEWISE replay correctness:
   graph-none async is correct, but async+PIECEWISE corrupts canaries. The
   `N=8` eager workaround is correct but not faster. Treat this as a
   correctness branch, not a speed branch, unless a new replay ownership fix
   appears.
4. TP4 only after hardware health:
   device `3`/XCCL remains a blocker. Do not interpret TP4 endpoint speed
   until the preflight passes cleanly.

## 2026-06-19 Addendum - Real Full-Layerlet Endpoint Gate

Important correction:

- The endpoint full-layerlet path is not enabled by
  `VLLM_XPU_MOE_W8A8_FULL_LAYERLET=1` alone.
- It also requires the fused prologue offset gate:
  `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET=1`.
- Under graph capture, it should also use
  `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE=1`.
- The accepted launcher clears experimental W8A8 flags unless
  `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`.

Corrected endpoint identity tested:

```bash
TP_SIZE=2
ONEAPI_DEVICE_SELECTOR=level_zero:0,1
ZE_AFFINITY_MASK=0,1
QWEN36_XPU_PREFLIGHT=0
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill
VLLM_EXTRA_ARGS='--no-async-scheduling --uvicorn-log-level warning'
GPU_MEMORY_UTILIZATION=0.90
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET=1
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE=1
VLLM_XPU_MOE_W8A8_FULL_LAYERLET=1
VLLM_XPU_MOE_W8A8_FUSED_Q1=1
VLLM_XPU_MOE_W8A8_ROUTE_GEMM1=1
VLLM_XPU_SHARED_EXPERT_BOUNDARY_OUT=1
VLLM_XPU_SHARED_EXPERT_FUSED_GATE_MUL=1
```

Operational lesson:

- Killing the launcher can leave `VLLM::EngineCore` and `VLLM::Worker_TP*`
  processes alive, holding XPU memory.
- Check those process names before interpreting a low-free-memory launch
  failure as a model/config problem.

Corrected run artifact:

- Summary:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-q1-routefull-sharedgate-real-noasync-tp2-summary-20260619q1routefullshared3.json`
- Log:
  `/home/steve/llm-optimizations/data/qwen36-ablation-prefill-safe-int8-q1-routefull-sharedgate-real-noasync-tp2-20260619q1routefullshared3.log`
- JSON canary: passed `24/24`.
- Color canary: passed `24/24`.
- Corrected decode throughput: `82.4576360185309 tok/s`.
- Decode time: `12.135906462845014 ms/token`.
- TTFT: `268.7872141832486 ms`.

Decision:

- Reject this endpoint combination as a speed branch.
- It is correct under the canaries but slower than the validated shared gate/mul
  increment (`84.9100565680358 tok/s`) and only about equal to the plain
  TP2/no-async control.
- Do not promote full-layerlet + q1 + route-GEMM1 to endpoint default in this
  form.
- Continue with larger routed-MoE fixed-overhead work rather than more small
  q1/route/full-layerlet combinations.

## 2026-06-19 Addendum - Sorted Active Helper And Q1 Direct Full-Layerlet Rejected

Current installed XPU extension state after the latest rebuild:

- Installed `_xpu_C.abi3.so` SHA256:
  `6201eb3b6088344f69faf215815bf34172d1f0a3b2454f3a2a764cfc4dff9b75`
- The temporary `128` local-size direct GEMM2/gather binary was reverted.
- Import sanity confirmed these symbols exist:
  `qwen36_topk_ids_to_active_expert_ids_int32_out`,
  `cutlass_grouped_gemm_w8a8_int8_active_offsets_interface`,
  `qwen36_moe_w8a8_full_layerlet`, and
  `qwen36_shared_expert_w8a8_out`.

Sorted active-helper replay:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-active-offset-runtime-sortedactive-routes7-device0-20260619activepath5.json`
- Identity:
  real route capture from
  `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`,
  route starts `0,40,80,85,95,100,115`, device `0`,
  `VLLM_XPU_INT8_MOE_ACTIVE_OFFSET_GEMM=1`,
  `VLLM_XPU_MOE_W8A8_FUSED_Q1=1`,
  `VLLM_XPU_MOE_W8A8_ROUTE_GEMM1=1`.
- Exactness: active-offset and offset candidates had `0.0` max diff against
  the XPU fused-MoE oracle on all checked routes.
- Promotion gate: failed.
  `rows_ready_for_endpoint_gate=0/7`,
  `worst_best_exact_nonreference_us_mean=222.65256`,
  target `160 us`.
- Route active-offset graph means were around `147.62-175.06 us`, but
  full prologue-inclusive host means remained around `202.87-223.79 us`.
- Decision: keep sorted active-helper as a correct diagnostic building block.
  Do not promote active-offset GEMM to the endpoint.

Q1 + direct GEMM2/gather full-layerlet:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-q1direct-routes7-device0-20260619.json`
- Identity:
  same real route capture and route starts, device `0`,
  `VLLM_XPU_MOE_W8A8_FUSED_Q1=1`,
  `VLLM_XPU_MOE_W8A8_DIRECT_GEMM2_GATHER=1`.
- Exactness: `full_layerlet_vs_xpu_fused_moe_max_abs_diff=0.0` and
  `full_layerlet_vs_rows_oracle_max_abs_diff=0.0` on all seven routes.
- Route full-layerlet host means:
  `193.65164, 169.30628, 181.80136, 162.99816, 188.18748, 175.80628,
  173.56040 us`.
- Promotion gate: failed.
  `rows_ready_for_endpoint_gate=0/7`,
  `worst_best_exact_nonreference_us_mean=193.65164`,
  target `160 us`.
- Decision: exact, but not fast enough; do not promote to endpoint.

Direct GEMM2/gather local-size `128` diagnostic:

- Artifact:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-full-layerlet-q1direct128-routes7-device0-20260619.json`
- Exactness: still `0.0` max diff on all seven routes.
- Promotion gate: failed.
  `rows_ready_for_endpoint_gate=0/7`,
  `worst_best_exact_nonreference_us_mean=193.2268`,
  target `160 us`.
- Route full-layerlet host means:
  `174.18024, 189.54988, 184.99260, 182.28184, 184.12160, 187.88224,
  193.22680 us`.
- Decision: rejected for speed and reverted. The installed binary is back to
  the `6201eb...` SHA above.

Reviewed `/home/steve/suggestions.md` again:

- Its highest-value live items still agree with the current direction:
  persistent/one-dispatch routed W8A8 MoE, exact oracle/spec parity, and TP4
  only after XPU/XCCL health.
- Several speed anchors in that file refer to the older TP4 async fast
  research base. Current endpoint comparisons should continue to use the
  safe TP2/no-async identity unless device `3` health is restored and the full
  benchmark identity matches.

Current conclusion:

- Small exact W8A8 MoE knobs are now closed for this cycle:
  active-offset, q1-only, fast gather, route-GEMM1, direct GEMM2/gather,
  DPAS GEMM2/gather, workspace atomic, route-class ordering, shared boundary,
  shared fused gate/mul, and the corrected endpoint full-layerlet combination.
- The next exact/no-quality-loss MoE branch must remove a larger boundary:
  a persistent/one-dispatch layerlet with resident descriptors/scratch/route
  buffers, or an equivalent deterministic DPAS pipeline that fuses route,
  quant, GEMM1, activation/quant2, GEMM2, and gather/combine under one
  replayable boundary.
- Endpoint work should resume only after the offline route gate consistently
  beats the current `~160-180 us` layerlet band with exact parity.

## 2026-06-19 Addendum - oneDNN Sidecar Route Replay Rejected As Endpoint Path

Harness update:

- `scripts/bench-qwen36-int8-moe-kernels.py` now has an explicit
  `--enable-onednn-sidecar` diagnostic path.
- The wrapper runs fused prologue, quantizes the remapped hidden states, builds
  the oneDNN int32 end-only offsets, calls
  `qwen36_moe_onednn_sidecar_probe`, and then runs the normal weighted gather.
- The sidecar ABI has a legacy argument named `remapped_hidden_states`, but the
  C++ diagnostic validates it as the int8 GEMM1 input buffer; the Python wrapper
  now passes `gemm1_a` there and leaves the regular BF16 remap path unchanged.
- The sidecar is included in exactness checks, rows-oracle checks, timing JSON,
  markdown output, runtime identity, and the prologue-inclusive promotion gate.

Artifacts:

- Mode `23` smoke:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-onednn-sidecar-smoke-device0-20260619.json`
- Mode `33` smoke:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-onednn-sidecar-mode33-smoke-device0-20260619.json`
- Seven-route mode `33` replay:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-onednn-sidecar-mode33-routes7-device0-20260619.json`
- Seven-route markdown:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-onednn-sidecar-mode33-routes7-device0-20260619.md`

Seven-route identity:

- Route capture:
  `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`
- Route starts: `0,40,80,85,95,100,115`
- Device: `ONEAPI_DEVICE_SELECTOR=level_zero:0`, `ZE_AFFINITY_MASK=0`
- TP-size in replay math: `4`
- Iterations/warmup: `80/20`
- oneDNN sidecar mode: `33`
- `--real-routing-oracle` enabled

Results:

- Exactness: oneDNN sidecar had `0.0` max abs diff versus `xpu_fused_moe`
  and `0.0` max abs diff versus the rows-per-expert oracle on all seven routes.
- Promotion gate: failed.
  `rows_ready_for_endpoint_gate=0/7`,
  `status=exact_nonreference_candidates_exist_but_gate_not_met`,
  target `160 us`.
- Best exact non-reference stayed the current `full_layerlet`.
  Best route: `162.21985 us`; worst route: `174.2182 us`.
- oneDNN sidecar total means by route:
  `299.754, 314.4245, 303.52465, 305.75675, 306.969, 321.3886,
  319.8897 us`.
- oneDNN sidecar internal middle-wall means by route:
  `45.575, 47.725, 45.0625, 45.45, 45.975, 48.5125, 48.9625 us`.

Decision:

- Reject the current Python/C++ oneDNN sidecar wrapper as an endpoint path. It
  is exact, but the prologue-inclusive total is far slower than the current
  exact full-layerlet replay.
- Keep the `~45-49 us` internal middle-wall number as a diagnostic hint only.
  It says oneDNN's cached GEMM middle can be fast in isolation, but the current
  boundary does not remove enough fixed route/prologue/quant/gather overhead.
- Do not spend more time on this sidecar wrapper unless the next design makes it
  a single resident, graph-safe/persistent boundary rather than a Python-level
  chain with offset conversion and separate gather.

Next best branch:

- Return to the larger exact boundary: persistent/one-dispatch W8A8 MoE
  layerlet, or equivalent deterministic DPAS pipeline, where descriptors,
  scratch, route buffers, offsets, expert pointers, and output buffers stay
  resident and the per-token submission is one small route command.
- Secondary branch remains oracle/spec parity, but MoE still looks like the
  highest-probability no-quality-loss path.

## 2026-06-20 Addendum - Unchecked Full-Layerlet Validation Bypass Rejected

Diagnostic implementation:

- Added guarded env flag
  `VLLM_XPU_MOE_W8A8_UNCHECKED_FULL_LAYERLET=1` in
  `/home/steve/src/vllm-xpu-kernels/csrc/xpu/moe_layerlet.cpp`.
- The flag bypasses the initial host-side dtype/device/shape validation inside
  `qwen36_moe_w8a8_full_layerlet`.
- Default behavior is unchanged when the flag is unset.
- Rebuilt and installed active `_xpu_C.abi3.so` with SHA:
  `c585bbb150720ff5d210205004f56f8e200f9d1f164192a042e329a8c5b22d06`.

Artifacts:

- Unchecked route-80 smoke:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-unchecked-q1-routegemm1-smoke-route80-device0-20260620.json`
- Same-binary checked route-80 control:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-checked-q1-routegemm1-smoke-route80-device0-20260620.json`

Identity:

- Device: `ONEAPI_DEVICE_SELECTOR=level_zero:0`, `ZE_AFFINITY_MASK=0`
- Route capture:
  `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`
- Route start: `80`
- TP-size in replay math: `4`
- Real-routing oracle enabled
- `VLLM_XPU_MOE_W8A8_FUSED_Q1=1`
- `VLLM_XPU_MOE_W8A8_ROUTE_GEMM1=1`

Results:

- Unchecked path exactness:
  `full_layerlet_vs_xpu_fused_moe_max_abs_diff=0.0`,
  `full_layerlet_vs_rows_oracle_max_abs_diff=0.0`.
- Checked control exactness:
  `full_layerlet_vs_xpu_fused_moe_max_abs_diff=0.0`,
  `full_layerlet_vs_rows_oracle_max_abs_diff=0.0`.
- Unchecked route-80 full-layerlet host mean: `204.1338 us`.
- Checked route-80 full-layerlet host mean on the same active binary:
  `167.8508 us`.
- Both failed the `160 us` prologue-inclusive promotion target.

Decision:

- Reject unchecked host validation bypass as a speed path. It is exact, but it
  is slower than the checked control on the same route and binary.
- Keep the flag off by default. It can remain as a diagnostic guard, but it is
  not endpoint-promotable and should not be used in accepted benchmark
  identities.
- This closes another small-boundary branch. The next MoE optimization must
  remove actual kernel/queue/device-boundary work, not only host validation.

Next branch:

- Add a decisive internal timing trace for the current exact full-layerlet
  route-GEMM1/Q1 path, then use that to choose one larger fusion boundary.
- If the trace confirms GEMM2/gather or activation/quant2 launch overhead is
  the main local wall, prototype a resident one-dispatch layerlet around that
  boundary.
- If the trace says full-layerlet local work is already near the floor and the
  endpoint wall is elsewhere, pivot back to async/PIECEWISE correctness or
  exact verifier/spec parity rather than adding more MoE micro-knobs.

## 2026-06-20 Addendum - Route-GEMM1 B-Layout Fixed, Endpoint Gate Still Not Active

Root cause fixed:

- The routed topk8 GEMM1/GEMM2-gather kernels in
  `/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.hpp`
  used the wrong B tensor layout.
- The existing offsets grouped GEMM path is launched through
  `MoEGEMMLauncherOffsets<'R','R',...>`, but internally flips B to
  column-major (`actual_layout_of_B='C'`).
- The routed topk8 kernels hardcoded B as row-major. Changing the B tensor
  construction to `'C'` made routed GEMM1 exact.

Direct GEMM1 proof:

- Before fix:
  `/home/steve/llm-optimizations/data/qwen36-route-gemm1-direct-compare-route80-20260620.json`
  had `overall_max_abs_diff=16.75`.
- After B-layout fix:
  `/home/steve/llm-optimizations/data/qwen36-route-gemm1-direct-compare-route80-blayoutfix-20260620.json`
  had `overall_max_abs_diff=0.0`.
- After restoring the hand-written routed body:
  `/home/steve/llm-optimizations/data/qwen36-route-gemm1-direct-compare-route80-blayoutfix-handbody-20260620.json`
  also had `overall_max_abs_diff=0.0`.

Replay results:

- Route-80 full layerlet with B-layout fix, Q1, route-GEMM1 hand body:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-blayoutfix-handbody-q1-routegemm1-smoke-route80-device0-20260620.json`
  exact, `full_layerlet_total_us_mean=138.69128`.
- Seven-route replay with the same path:
  `/home/steve/llm-optimizations/data/qwen36-int8-moe-layerlet-blayoutfix-handbody-q1-routegemm1-routes7-device0-20260620.json`
  all exact. Route means:
  `0=139.78`, `40=141.45`, `80=139.00`, `85=136.67`,
  `95=138.02`, `100=160.80`, `115=148.58 us`.
- MTILE=8 was mixed: route-100 alone improved to `143.38 us`, but the seven
  route set still had a `165.67 us` worst row. Do not promote MTILE=8 yet.

Endpoint A/B results:

- TP2 graph-none control:
  `/home/steve/llm-optimizations/data/qwen36-ablation-tp2-control-blayoutfix-summary-20260620tp2ctlblayout1.json`
  passed JSON/color canaries, `13.95497 tok/s`.
- TP2 graph-none layerlet flags:
  `/home/steve/llm-optimizations/data/qwen36-ablation-tp2-fulllayerlet-q1-routegemm1-blayoutfix-summary-20260620tp2fulllayerlet1.json`
  passed JSON/color canaries, `13.89789 tok/s`.
- TP2 PIECEWISE forced-comm control:
  `/home/steve/llm-optimizations/data/qwen36-ablation-tp2-piecewise-control-blayoutfix-summary-20260620tp2piecewisectl1.json`
  passed JSON/color canaries, `83.56112 tok/s`.
- TP2 PIECEWISE layerlet flags:
  `/home/steve/llm-optimizations/data/qwen36-ablation-tp2-piecewise-fulllayerlet-q1-routegemm1-blayoutfix-summary-20260620tp2piecewisefulllayerlet1.json`
  passed JSON/color canaries, `82.32790 tok/s`.

Important correction:

- The endpoint layerlet-flag runs above did **not** actually prove the C++
  full-layerlet path was active.
- A C++ opt-in trace was added in
  `/home/steve/src/vllm-xpu-kernels/csrc/xpu/moe_layerlet.cpp`:
  `VLLM_XPU_MOE_W8A8_FULL_LAYERLET_TRACE_FILE`.
- Trace run without fused-prologue offset gate:
  `/home/steve/llm-optimizations/data/qwen36-ablation-tp2-piecewise-fulllayerlet-trace-blayoutfix-summary-20260620tp2piecewisefulllayerlettrace1.json`
  produced no C++ trace file, meaning `qwen36_moe_w8a8_full_layerlet` was not
  entered.
- Trace run with:
  `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET=1` and
  `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE=1`
  also produced no C++ trace file:
  `/home/steve/llm-optimizations/data/qwen36-ablation-tp2-piecewise-fulllayerlet-offset-trace-blayoutfix-summary-20260620tp2piecewisefulllayerlettraceoffset1.json`.
- Therefore the current endpoint is failing a higher-level Python gate before
  the C++ op. Do not interpret the endpoint layerlet A/B as a real full-layerlet
  speed test until the Python gate reason is captured.

Interrupted loose end:

- A Python gate-reason trace was added in
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`:
  `VLLM_XPU_MOE_W8A8_FULL_LAYERLET_GATE_TRACE_FILE`.
- The first gate-reason trace run was interrupted before it reached metrics:
  label `tp2-piecewise-fulllayerlet-gatetrace-blayoutfix`,
  stamp `20260620tp2piecewisefulllayerletgatetrace1`.
- It had not yet produced:
  `/home/steve/llm-optimizations/data/qwen36-full-layerlet-gate-trace-tp2-piecewise-20260620.jsonl`
  or
  `/home/steve/llm-optimizations/data/qwen36-full-layerlet-trace-tp2-piecewise-gatereason-20260620.jsonl`
  before the stop.

Current active library hashes after trace instrumentation:

- `_xpu_C.abi3.so`:
  `1797dca305004d09fe89d76f071766b290ecb356adf188faf1b2931a9742fa33`
- `libgrouped_gemm_xe_2.so`:
  `d7ac20974b96f7429350ddb0319384386cf2433442bdda1e878537eca60b0be1`

Saved patches:

- Kernel repo patch:
  `/home/steve/llm-optimizations/patches/vllm-xpu-kernels-qwen36-routegemm1-blayoutfix-20260620.patch`
- Lab repo patch:
  `/home/steve/llm-optimizations/patches/llm-optimizations-qwen36-routegemm1-blayoutfix-results-20260620.patch`

Immediate next command to resume:

```bash
TRACE=/home/steve/llm-optimizations/data/qwen36-full-layerlet-trace-tp2-piecewise-gatereason-20260620.jsonl
GATE=/home/steve/llm-optimizations/data/qwen36-full-layerlet-gate-trace-tp2-piecewise-20260620.jsonl
rm -f "$TRACE" "$GATE"
STAMP=20260620tp2piecewisefulllayerletgatetrace2 \
PORT=18184 \
TP_SIZE=2 \
ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
ZE_AFFINITY_MASK=0,1 \
QWEN36_XPU_PREFLIGHT=0 \
METRICS_REPEATS=1 \
METRICS_PROMPT_TOKENS=128 \
METRICS_OUTPUT_TOKENS=64 \
METRICS_WARMUP_OUTPUT_TOKENS=16 \
ABLATION_SKIP_CANARIES=1 \
ABLATION_RUN_QUALITY=0 \
ABLATION_SKIP_METRICS=0 \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
XPU_GRAPH=1 \
VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET=1 \
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE=1 \
VLLM_XPU_MOE_W8A8_FULL_LAYERLET=1 \
VLLM_XPU_MOE_W8A8_FUSED_Q1=1 \
VLLM_XPU_MOE_W8A8_ROUTE_GEMM1=1 \
VLLM_XPU_MOE_W8A8_FULL_LAYERLET_TRACE_FILE="$TRACE" \
VLLM_XPU_MOE_W8A8_FULL_LAYERLET_TRACE_MAX_LINES=512 \
VLLM_XPU_MOE_W8A8_FULL_LAYERLET_GATE_TRACE_FILE="$GATE" \
VLLM_XPU_MOE_W8A8_FULL_LAYERLET_GATE_TRACE_MAX_LINES=512 \
/home/steve/llm-optimizations/scripts/run-qwen36-ablation-candidate.sh \
  tp2-piecewise-fulllayerlet-gatetrace-blayoutfix
```

Decision tree when resuming:

- If the Python gate trace says missing scratch keys, fix scratch allocation in
  the endpoint path before benchmarking again.
- If it says `num_rows != 1`, the PIECEWISE bucket is not exercising the
  single-token layerlet path; add a compatible decode-only gate or layerlet
  variant for that shape.
- If it says `stream_capture_active` blocks the fused offset gate, keep
  `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE=1` and find the next
  false prerequisite.
- Only after the C++ trace shows real calls to
  `qwen36_moe_w8a8_full_layerlet` should a full canary-clean endpoint A/B be
  treated as a real layerlet result.

## 2026-06-21 Follow-Up - Full-Layerlet Gate Trace

The gate trace follow-up produced two useful artifacts:

- TP2 PIECEWISE forced-comm:
  `/home/steve/llm-optimizations/data/qwen36-ablation-tp2-piecewise-fulllayerlet-gatetrace-blayoutfix-summary-20260621tp2piecewisefulllayerletgatetrace1.json`
  and
  `/home/steve/llm-optimizations/data/qwen36-full-layerlet-gate-trace-tp2-piecewise-20260621.jsonl`.
- TP2 graph-none with mixed workspace:
  `/home/steve/llm-optimizations/data/qwen36-ablation-tp2-graphnone-fulllayerlet-mixedws-gatetrace-summary-20260621tp2graphnonefulllayerletmixedws1.json`
  and
  `/home/steve/llm-optimizations/data/qwen36-full-layerlet-gate-trace-tp2-graphnone-mixedws-20260621.jsonl`.

The PIECEWISE trace repeatedly had no scratch keys or W8A8 offset scratch and
never enabled the full-layerlet op (`use_w8a8_full_layerlet=false`). The
graph-none mixed-workspace run had scratch keys, W8A8 offsets, and finally
`num_rows=1` with `prologue_workspace=true` and
`use_w8a8_full_layerlet=true`.

Interpretation:

- The endpoint gate issue is not the C++ route-GEMM1 B-layout fix itself.
- PIECEWISE is still missing or not preserving the required per-layer scratch
  state at the point where the MoE path asks for the full-layerlet op.
- Graph-none can reach the intended rows=1 layerlet gate when the workspace
  shape is compatible, so the next useful patch should target PIECEWISE scratch
  lifetime/allocation or the capture-compatible path that supplies those keys.
