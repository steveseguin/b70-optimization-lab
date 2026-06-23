# Qwen3.6 Recovery Implementation

Date: 2026-06-14

## Implemented

- Added `scripts/run-qwen36-decisive-timing.sh`.
  - Launches the accepted graph-disabled W8A8 lane.
  - Enables opt-in XPU decode timing without changing accepted defaults.
  - Runs a c1 endpoint metric pass.
  - Summarizes the timing log.
  - Emits a fresh bottleneck-family decision JSON and Markdown.
- Added `scripts/qwen36-timing-family-decision.py`.
  - Classifies timing labels into MoE, GDN, full attention, collectives,
    logits/sampler, runtime, and other.
  - Uses top visible family labels and rank skew as routing evidence.
  - Explicitly warns that timing labels are nested and non-exclusive.
- Added `scripts/run-qwen36-graph-replay-matrix.sh`.
  - Reuses the current `cuda_graph.py` compare/trace hooks.
  - Runs a reproducible PIECEWISE prefix-0 matrix:
    control, sync replay, compare-direct, and return-direct.
  - Keeps graph candidates rejected unless canaries pass.

## Operational Defaults

- The accepted launcher remains graph-disabled and production-safe.
- Timing stays opt-in through `VLLM_XPU_DECODE_TIMING_ALLOW=1`.
- The decisive timing runner defaults to `p512/o256`, one measured repeat, and
  no canaries. Set `RUN_CANARIES=1` for a heavier timing-plus-correctness pass.
- The replay matrix defaults to 64 JSON and color repeats per variant.

## Next Execution

1. Run one fresh accepted-lane timing pass:

```bash
cd /home/steve/llm-optimizations
bash scripts/run-qwen36-decisive-timing.sh accepted-c1-decisive-20260614
```

2. Use the generated timing decision to choose the next engineering branch:
   persistent W8A8 MoE layerlet, GDN/dense fusion, collectives/topology, or
   runtime/static c1 work.

3. If graph replay remains under investigation, run:

```bash
cd /home/steve/llm-optimizations
bash scripts/run-qwen36-graph-replay-matrix.sh
```

4. Promote no candidate until JSON/color canaries, quality suite, token checks,
   and repeated p512/o512 metrics all pass.

## Fresh Accepted-Lane Timing Run

Command:

```bash
cd /home/steve/llm-optimizations
PROMPT_TOKENS=512 OUTPUT_TOKENS=128 METRICS_REPEATS=1 \
  VLLM_XPU_DECODE_TIMING_SKIP_FIRST=16 \
  VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST=16 \
  VLLM_XPU_DECODE_TIMING_STEP_EVERY=16 \
  RUN_CANARIES=0 \
  bash scripts/run-qwen36-decisive-timing.sh accepted-c1-decisive-20260614-impl
```

Artifacts:

- Metrics:
  `data/qwen36-accepted-c1-decisive-20260614-impl-p512o128-20260614162746.json`
- Timing summary:
  `data/qwen36-accepted-c1-decisive-20260614-impl-timing-summary-20260614162746.json`
- Timing decision:
  `data/qwen36-accepted-c1-decisive-20260614-impl-timing-decision-20260614162746.json`
- Run summary:
  `data/qwen36-accepted-c1-decisive-20260614-impl-run-summary-20260614162746.json`

Result:

- Diagnostic timing-on corrected output rate: `13.38 tok/s`.
- vLLM decode histogram: `74.73 ms/generated token`.
- Client TTFT: `284.98 ms`; vLLM TTFT: `209.78 ms`.
- Available KV cache memory after profiling: `19.07 GiB`.
- vLLM maximum 32K concurrency estimate: `57.80x`.

Decision:

- Leading family: MoE.
- Top visible label after per-step normalization:
  `moe.quant_method_total` at `38.34 ms/step`.
- Runner-up: collectives,
  `all_reduce:(1, 2048):torch.bfloat16:bytes=4096` at `6.51 ms/step`.
- Next target remains the persistent/resident W8A8 MoE layerlet path.

Note: this is a diagnostic timing run, not a promoted speed row. Canaries were
not requested for this pass.

## Implementation Checkpoint: Guardrails And Gates

Added a fail-closed guard in
`/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
for the rejected oneDNN sidecar-inside-XPU-graph path.

- Default behavior now skips oneDNN sidecar execution when the current XPU
  stream is being captured.
- The only way to re-enter this path is to explicitly set
  `VLLM_XPU_MOE_ONEDNN_SIDECAR_ALLOW_GRAPH_CAPTURE=1` for an isolated
  diagnostic run.
- Rationale: mode 123 with wait-in-capture fell back because waits cannot be
  issued while recording a command graph; mode 133/no-wait captured but the
  first real vLLM request hit `UR_RESULT_ERROR_DEVICE_LOST`. This path is not a
  candidate for production or unattended benchmarking.

Added `scripts/qwen36-ablation-report.py`.

- Normalizes ablation summaries and decisive timing run summaries.
- Reports corrected output tok/s, decode ms/token, JSON canary status, color
  canary status, quality-suite status, and first failure.
- Treats missing quality validation as missing, not as passed.
- Separates `quality_validated` from `promotion_ready`.
- Supports `--min-tok-s`; `promotion_ready=true` requires quality validation
  plus the requested speed floor.

Generated current min-98 report:

- JSON: `data/qwen36-ablation-report-min98-20260614164151.json`
- Markdown: `data/qwen36-ablation-report-min98-20260614164151.md`
- Rows summarized: 29.
- `promotion_ready`: 0.
- `quality_validated`: 1.
- The only quality-validated row in this set is the graph-disabled packed gate
  at about `13.98 tok/s`, so it is not useful for the speed goal.

Added `scripts/run-qwen36-oracle-parity-gate.sh`.

- Consumes accepted and candidate token-trace artifacts.
- Optionally replays speculative scheduler JSONL traces.
- Reduces accepted-vs-candidate drift into a compact fixture.
- Runs `check-qwen36-oracle-fixture.py` in exact or known-drift mode.
- Default exact mode requires speculative activity and request-id joinability,
  so a future oracle/spec patch must prove both "spec ran" and "tokens match".

Known-drift smoke:

```bash
cd /home/steve/llm-optimizations
MODE=known-drift \
EXPECTED_MISMATCHES=2 \
EXPECTED_ROLES=verifier_bonus_after_full_accept,replacement_after_reject \
ACCEPTED_TRACE_JSON=data/qwen36-quark-int8-tp4-oracle-k1-short-accepted-graph-20260611.json \
CANDIDATE_TRACE_JSON=data/qwen36-quark-int8-tp4-oracle1-workertrace-completions-20260611a.json \
SPEC_SUMMARY_JSON=data/qwen36-quark-int8-tp4-oracle1-workertrace-spec-summary-20260611a.json \
REPLAY_JSON=data/qwen36-quark-int8-tp4-oracle1-workertrace-replay-20260611a.json \
./scripts/run-qwen36-oracle-parity-gate.sh workertrace-known-drift-smoke-v2
```

Result:

- Summary:
  `data/qwen36-oracle-workertrace-known-drift-smoke-v2-gate-summary-20260614164300.json`
- Check result: pass in `known-drift` mode.
- Mismatch roles: `verifier_bonus_after_full_accept`,
  `replacement_after_reject`.
- Spec activity: 15 draft tokens, 14 accepted, 1 rejected,
  93.33% accept rate.
- The reducer returned rc=2 because this fixture intentionally drifts; the gate
  pass is based on the checker rc=0 in known-drift mode.

Current rejected paths to avoid re-testing without new evidence:

- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`: slightly slower than accepted and
  costs KV headroom.
- Direct oneDNN sidecar capture inside vLLM XPU graphs: falls back or device
  loss.
- PIECEWISE prefix-0 decode graph replay variants tested on 2026-06-14:
  compare-direct short passed, but deeper return-direct/sync/zero-empty and
  standard prefix-0 canaries still failed.

Current primary engineering branches:

1. Graph-native or persistent SYCL W8A8 MoE layerlet.
   Use the oneDNN sidecar as the exact oracle, but do not capture oneDNN engine
   stream work inside vLLM graphs.
2. Oracle k=1 speculative parity repair.
   Use the new oracle parity gate before any speed claim. The first required
   milestone is token-identical output with speculative verifier activity
   proven active.
3. Selective graph replay bypass only if a fresh trace proves a narrow replay
   family can be disabled while preserving enough speed. Current broad prefix-0
   replay is not clean.

## Implementation Checkpoint: Graph-Native W8A8 MoE Middle Layerlet

Implemented an opt-in graph-native W8A8 MoE middle layerlet in
`/home/steve/src/vllm-xpu-kernels`.

Files changed:

- `csrc/xpu/moe_layerlet.cpp`
- `csrc/xpu/ops.h`
- `csrc/xpu/torch_bindings.cpp`
- `CMakeLists.txt`
- `vllm_xpu_kernels/fused_moe_interface.py`
- `/home/steve/src/vllm/vllm/model_executor/layers/fused_moe/experts/xpu_moe.py`
- `scripts/check-qwen36-w8a8-middle-layerlet.py`
- `scripts/launch-qwen36-quark-int8-accepted.sh`
- `scripts/run-qwen36-ablation-candidate.sh`
- `scripts/run-qwen36-decisive-timing.sh`

Behavior:

- New XPU op:
  `_xpu_C::qwen36_moe_w8a8_middle_layerlet`.
- It runs the middle MoE sequence as one native extension boundary:
  offsets W8A8 GEMM1 -> exact SiLU/mul INT8 quant -> offsets W8A8 GEMM2.
- It remains fail-closed by default.
- The accepted launcher now strips the experimental flags unless
  `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1` is set.
- The vLLM path only uses it when:
  `VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1`,
  `VLLM_XPU_W8A8_USE_OFFSETS=1`,
  activation is SiLU, INT8 scratch is available, and the oneDNN sidecar is not
  selected.

Build/deploy status:

- `python3 -m py_compile vllm_xpu_kernels/fused_moe_interface.py`: pass.
- `_xpu_C` rebuild: pass.
- Live binary backup:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so.backup-before-w8a8-middle-layerlet-20260614-170538`
- Live op registration check: pass.

Synthetic parity harness:

```bash
cd /home/steve/llm-optimizations
python3 scripts/check-qwen36-w8a8-middle-layerlet.py --graph-replay --require-graph
```

Latest artifact:

- JSON: `data/qwen36-w8a8-middle-layerlet-check-20260614T171738Z.json`
- Markdown: `data/qwen36-w8a8-middle-layerlet-check-20260614T171738Z.md`

Result:

- Overall: pass.
- XPU graph replay requested and required: pass.
- Cases: `tiny_sparse`, `single_hot_expert`, `decode_like_sparse`,
  `dense_small`.
- Eager max diff: `0.0`.
- Graph replay max diff: `0.0`.
- Graph replay mutates inputs after capture, so this proves the op replays with
  live buffers instead of stale captured values.

Endpoint smoke, layerlet with graph disabled:

```bash
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1 \
PROMPT_TOKENS=64 OUTPUT_TOKENS=64 WARMUP_OUTPUT_TOKENS=16 \
METRICS_REPEATS=1 RUN_CANARIES=0 \
bash scripts/run-qwen36-decisive-timing.sh middle-layerlet-eager-smoke
```

Artifacts:

- Log: `data/qwen36-middle-layerlet-eager-smoke-20260614171249.log`
- Metrics:
  `data/qwen36-middle-layerlet-eager-smoke-p64o64-20260614171249.json`
- Timing decision:
  `data/qwen36-middle-layerlet-eager-smoke-timing-decision-20260614171249.json`

Result:

- Corrected output rate: `13.2529 tok/s`.
- vLLM decode time: `75.4752 ms/token`.
- Client TTFT: `192.48 ms`.
- vLLM TTFT: `114.45 ms`.
- Top visible MoE label: `xpu_moe.w8a8_offsets`.
- `xpu_moe.w8a8_offsets`: max `0.099079 ms`, mean `0.095973 ms`.
- `xpu_moe.w8a8_middle_layerlet`: max `0.060602 ms`, mean
  `0.059367 ms`.
- `xpu_moe.gemm1_quant`: max `0.027884 ms`, mean `0.027227 ms`.

Interpretation:

- The layerlet is active and endpoint-safe in graph-disabled smoke.
- The fixed per-token offsets construction became the top visible MoE cost.

## Implementation Checkpoint: Resident Offsets Scratch

Added resident offsets scratch on the mixed INT8 workspace path.

Behavior:

- When `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`, the XPU MoE workspace manager
  also allocates `w8a8_offsets` as an `int64` tensor of shape
  `num_local_experts + 1`.
- `_make_w8a8_grouped_gemm_offsets` now reuses this buffer when available and
  performs `torch.cumsum(..., dtype=torch.int64, out=offsets[1:])`.
- This avoids a per-layer offsets allocation and the extra int64 intermediate.

Validation:

- The synthetic layerlet harness still passed with graph replay required after
  this change:
  `data/qwen36-w8a8-middle-layerlet-check-20260614T171738Z.json`.

Endpoint smoke, layerlet plus resident offsets:

```bash
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
PROMPT_TOKENS=64 OUTPUT_TOKENS=64 WARMUP_OUTPUT_TOKENS=16 \
METRICS_REPEATS=1 RUN_CANARIES=0 \
bash scripts/run-qwen36-decisive-timing.sh middle-layerlet-resident-offset-smoke
```

Artifacts:

- Log:
  `data/qwen36-middle-layerlet-resident-offset-smoke-20260614171754.log`
- Metrics:
  `data/qwen36-middle-layerlet-resident-offset-smoke-p64o64-20260614171754.json`
- Timing decision:
  `data/qwen36-middle-layerlet-resident-offset-smoke-timing-decision-20260614171754.json`

Result:

- Corrected output rate: `13.7112 tok/s`.
- vLLM decode time: `73.0055 ms/token`.
- Client TTFT: `190.69 ms`.
- vLLM TTFT: `111.75 ms`.
- Top visible MoE label remains `xpu_moe.w8a8_offsets`.
- `xpu_moe.w8a8_offsets`: max `0.073370 ms`, mean `0.0723868 ms`.
- `xpu_moe.w8a8_middle_layerlet`: max `0.059415 ms`, mean
  `0.0576678 ms`.
- `xpu_moe.gemm1_quant`: max `0.019098 ms`, mean `0.0188165 ms`.

Delta versus layerlet without resident offsets:

- Corrected output rate: `+0.4583 tok/s`, about `+3.46%`.
- vLLM decode time: `75.4752 -> 73.0055 ms/token`.
- Offsets max cost: `0.099079 -> 0.073370 ms`.
- Graph-native layerlet cost stayed roughly flat, so the improvement is from
  resident offsets and workspace reuse rather than a changed math path.

Status:

- Promising but not promoted.
- This is one short p64/o64 smoke with canaries disabled.
- Before adoption, run JSON/color canaries, quality suite, at least four
  measured repeats, and an adjacent accepted-control A/B.

Canary-only quality smoke:

```bash
PORT=18083 BASE_URL=http://127.0.0.1:18083 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
ABLATION_SKIP_METRICS=1 JSON_REPEATS=8 COLOR_REPEATS=8 \
bash scripts/run-qwen36-ablation-candidate.sh middle-layerlet-resident-offset-canary8
```

Artifacts:

- Summary:
  `data/qwen36-ablation-middle-layerlet-resident-offset-canary8-summary-20260614172409.json`
- JSON canary:
  `data/qwen36-ablation-middle-layerlet-resident-offset-canary8-json-repeat8-20260614172409.json`
- Color canary:
  `data/qwen36-ablation-middle-layerlet-resident-offset-canary8-color-repeat8-20260614172409.json`
- Log:
  `data/qwen36-ablation-middle-layerlet-resident-offset-canary8-20260614172409.log`

Result:

- JSON canary: pass, `8/8`, `0` mismatches.
- Color canary: pass, `8/8`, `0` mismatches.
- Metrics: skipped.
- Quality suite: skipped.
- This upgrades the candidate from "endpoint smoke only" to "endpoint smoke
  plus short deterministic canary pass", but it is still not promotion-ready.

Harness fix:

- Patched `scripts/run-qwen36-ablation-candidate.sh` so future summaries record
  per-step status as `passed`, `failed`, `skipped`, or `missing_artifact`.
- Added `artifact_exists` to the summary JSON.
- Added `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE` to the recorded environment.
- Corrected the current canary summary to mark metrics and quality as skipped
  because those artifacts were intentionally not generated.

## Implementation Checkpoint: Prefix Offset XPU Op

Implemented the next target from the resident-offset checkpoint: a tiny
graph-native prefix-offset XPU op.

Files changed:

- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/moe_layerlet.cpp`
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/ops.h`
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/torch_bindings.cpp`
- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
- `scripts/check-qwen36-w8a8-middle-layerlet.py`
- `scripts/launch-qwen36-quark-int8-accepted.sh`
- `scripts/run-qwen36-ablation-candidate.sh`
- `scripts/run-qwen36-decisive-timing.sh`

Behavior:

- New op:
  `_xpu_C::qwen36_rows_per_expert_offsets_int64_out`.
- It writes `offsets[0] = 0` and the inclusive prefix of int32
  `rows_per_expert` into the resident int64 offsets buffer.
- It is opt-in via `VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1`.
- It is also stripped by the accepted launcher unless
  `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`.
- Added nested timing labels:
  `xpu_moe.w8a8_offsets_prefix_op` and
  `xpu_moe.w8a8_offsets_torch_cumsum`.

Build/deploy status:

- `_xpu_C` rebuild: pass.
- Live binary backup:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so.backup-before-prefix-offset-20260614-173259`
- Direct XPU parity check against `torch.cumsum`: pass.

Updated synthetic harness:

```bash
cd /home/steve/llm-optimizations
ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  /home/steve/.venvs/vllm-xpu/bin/python \
  scripts/check-qwen36-w8a8-middle-layerlet.py --graph-replay --require-graph
```

Artifacts:

- JSON: `data/qwen36-w8a8-middle-layerlet-check-20260614T173603Z.json`
- Markdown: `data/qwen36-w8a8-middle-layerlet-check-20260614T173603Z.md`

Result:

- Overall: pass.
- Prefix eager: pass for all four cases.
- Prefix graph replay: pass for all four cases, including mutated
  `rows_per_expert` after capture.
- Layerlet eager: pass for all four cases.
- Layerlet graph replay: pass for all four cases.

Endpoint smoke, layerlet plus resident prefix offsets:

```bash
PORT=18084 BASE_URL=http://127.0.0.1:18084 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1 \
VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_XPU_DECODE_TIMING_LABEL_REGEX='xpu_moe\.w8a8_offsets|xpu_moe\.w8a8_offsets_prefix_op|xpu_moe\.w8a8_offsets_torch_cumsum|xpu_moe\.w8a8_middle_layerlet|xpu_moe\.gemm1_quant' \
PROMPT_TOKENS=64 OUTPUT_TOKENS=64 WARMUP_OUTPUT_TOKENS=16 \
METRICS_REPEATS=1 RUN_CANARIES=0 \
bash scripts/run-qwen36-decisive-timing.sh middle-layerlet-prefix-offset-smoke
```

Artifacts:

- Log: `data/qwen36-middle-layerlet-prefix-offset-smoke-20260614173632.log`
- Metrics:
  `data/qwen36-middle-layerlet-prefix-offset-smoke-p64o64-20260614173632.json`
- Timing decision:
  `data/qwen36-middle-layerlet-prefix-offset-smoke-timing-decision-20260614173632.json`
- Run summary:
  `data/qwen36-middle-layerlet-prefix-offset-smoke-run-summary-20260614173632.json`

Result:

- Corrected output rate: `14.2056 tok/s`.
- vLLM decode time: `70.4096 ms/token`.
- Client TTFT: `184.92 ms`.
- vLLM TTFT: `112.45 ms`.
- Top visible MoE label is now `xpu_moe.w8a8_middle_layerlet`, not offsets.
- `xpu_moe.w8a8_middle_layerlet`: max `0.049362 ms`, mean
  `0.0485178 ms`.
- `xpu_moe.w8a8_offsets`: max `0.022380 ms`, mean `0.0221915 ms`.
- `xpu_moe.w8a8_offsets_prefix_op`: max `0.013010 ms`, mean
  `0.0128663 ms`.
- `xpu_moe.gemm1_quant`: max `0.014299 ms`, mean `0.0141435 ms`.

Delta versus resident-offset cumsum candidate:

- Corrected output rate: `13.7112 -> 14.2056 tok/s`, about `+3.61%`.
- vLLM decode time: `73.0055 -> 70.4096 ms/token`.
- Offsets max cost: `0.073370 -> 0.022380 ms`.

Delta versus first layerlet smoke without resident offsets:

- Corrected output rate: `13.2529 -> 14.2056 tok/s`, about `+7.19%`.
- vLLM decode time: `75.4752 -> 70.4096 ms/token`.
- Offsets max cost: `0.099079 -> 0.022380 ms`.

Canary-only quality smoke:

```bash
PORT=18085 BASE_URL=http://127.0.0.1:18085 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1 \
VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
ABLATION_SKIP_METRICS=1 JSON_REPEATS=8 COLOR_REPEATS=8 \
bash scripts/run-qwen36-ablation-candidate.sh middle-layerlet-prefix-offset-canary8
```

Artifacts:

- Summary:
  `data/qwen36-ablation-middle-layerlet-prefix-offset-canary8-summary-20260614173934.json`
- JSON canary:
  `data/qwen36-ablation-middle-layerlet-prefix-offset-canary8-json-repeat8-20260614173934.json`
- Color canary:
  `data/qwen36-ablation-middle-layerlet-prefix-offset-canary8-color-repeat8-20260614173934.json`
- Log:
  `data/qwen36-ablation-middle-layerlet-prefix-offset-canary8-20260614173934.log`

Result:

- JSON canary: pass, `8/8`, `0` mismatches.
- Color canary: pass, `8/8`, `0` mismatches.
- Metrics: skipped.
- Quality suite: skipped.
- Status: promising short candidate, not promoted.

Longer candidate gate:

```bash
PORT=18086 BASE_URL=http://127.0.0.1:18086 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1 \
VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
METRICS_REPEATS=2 JSON_REPEATS=32 COLOR_REPEATS=32 \
ABLATION_RUN_QUALITY=1 QUALITY_REPEAT_RUNS=4 QUALITY_LONG_CONTEXT_TOKENS=2048 \
bash scripts/run-qwen36-ablation-candidate.sh middle-layerlet-prefix-offset-gate32-quality
```

Artifacts:

- Summary:
  `data/qwen36-ablation-middle-layerlet-prefix-offset-gate32-quality-summary-20260614174351.json`
- Metrics:
  `data/qwen36-ablation-middle-layerlet-prefix-offset-gate32-quality-p512o512-20260614174351.json`
- JSON canary:
  `data/qwen36-ablation-middle-layerlet-prefix-offset-gate32-quality-json-repeat32-20260614174351.json`
- Color canary:
  `data/qwen36-ablation-middle-layerlet-prefix-offset-gate32-quality-color-repeat32-20260614174351.json`
- Quality suite:
  `data/qwen36-ablation-middle-layerlet-prefix-offset-gate32-quality-quality-suite-20260614174351.json`

Result:

- Metrics: pass.
- p512/o512 corrected output rate: `14.1911 tok/s` mean over two repeats.
- p512/o512 vLLM decode time: `70.4677 ms/token` mean over two repeats.
- JSON canary: pass, `32/32`, `0` mismatches.
- Color canary: pass, `32/32`, `0` mismatches.
- Text quality suite: pass.
- Quality suite details:
  baseline match all: pass;
  exact cases `exact_ok`, `copy_phrase`, `arithmetic`, `json_schema`: pass;
  repeat case: pass;
  long-context case at `2048` tokens: pass.

Adjacent accepted-control A/B:

```bash
PORT=18087 BASE_URL=http://127.0.0.1:18087 \
METRICS_REPEATS=2 ABLATION_SKIP_CANARIES=1 \
bash scripts/run-qwen36-ablation-candidate.sh accepted-control-adjacent-p512o512
```

Artifacts:

- Summary:
  `data/qwen36-ablation-accepted-control-adjacent-p512o512-summary-20260614174908.json`
- Metrics:
  `data/qwen36-ablation-accepted-control-adjacent-p512o512-p512o512-20260614174908.json`

Result:

- Accepted-control p512/o512 corrected output rate:
  `13.9929 tok/s` mean over two repeats.
- Accepted-control p512/o512 vLLM decode time:
  `71.4661 ms/token` mean over two repeats.
- Candidate versus adjacent accepted-control:
  `14.1911 / 13.9929 = 1.0142`, about `+1.42%`.
- Decode time improvement:
  `71.4661 -> 70.4677 ms/token`, about `+1.40%`.

Interpretation:

- The short timing smoke showed a larger local MoE/offset improvement; the
  longer p512/o512 A/B shows a real but smaller end-to-end decode improvement.
- This candidate has now passed synthetic parity, XPU graph replay parity, a
  short canary smoke, a longer 32-repeat canary gate, and a reduced text
  quality suite.
- It is still not a production default until full 96/128+ canaries, 4+ metric
  repeats, a full-length quality suite, and stability soak are done.

Saved patch snapshots:

- Kernel extension:
  `patches/vllm-xpu-kernels-qwen36-w8a8-layerlet-prefix-offset-20260614.patch`
- vLLM resident scratch wiring:
  `patches/vllm-qwen36-w8a8-resident-offset-scratch-20260614.patch`
- Scripts, notes, and harness:
  `patches/llm-optimizations-qwen36-w8a8-layerlet-prefix-offset-results-20260614.patch`

Next best implementation target:

1. Run full-strength validation for the prefix-offset candidate:
   4+ p512/o512 metric repeats, 96/128+ JSON/color canaries, full quality
   settings, and a short stability soak.
2. If the speed signal survives full validation, look inside
   `xpu_moe.w8a8_middle_layerlet`; it is now the top visible MoE label.
3. Candidate layerlet follow-ups:
   fuse prefix-offset generation into the middle layerlet call boundary,
   reduce Python/custom-op boundary count around `gemm1_quant`, or move toward
   a persistent per-layer descriptor/scratch object so each decode token submits
   fewer independent commands.

## 2026-06-15 Exact Layerlet Activation/Quant Repair

Context:

- The earlier synthetic W8A8 middle-layerlet checker was too weak. Its
  reference path used `_xpu_C.silu_and_mul_quant_int8_xpu_out`, which is the
  same fused shortcut used inside the candidate layerlet. That allowed the
  checker to pass even when the layerlet did not match the accepted vLLM
  endpoint path.
- The corrected reference path is:
  offsets W8A8 GEMM1 -> `fused_moe_activation(..., "silu")` BF16 output ->
  `_xpu_C.per_token_quant_int8_xpu_out` -> offsets W8A8 GEMM2.
- This is the no-quality-loss reference that matters for promotion.

Patches:

- Updated `scripts/check-qwen36-w8a8-middle-layerlet.py` to use the accepted
  two-step activation/quant reference and record
  `reference_activation_quant="vllm_silu_then_xpu_per_token_quant"`.
- Updated the experimental XPU SiLU+INT8 quant op in
  `/home/steve/src/vllm-xpu-kernels/csrc/xpu/quantization/int8_quant.cpp`
  to cast SiLU to BF16 before multiply and cast the product to BF16 before
  INT8 quantization.
- Rebuilt `_xpu_C` with GDN kernels enabled:
  `BUILD_DIR=/home/steve/src/vllm-xpu-kernels/build/xpu-c-only-exact-siluq-20260615a2`,
  `INSTALL_PREFIX=/tmp/vllm-xpu-xpu-c-only-exact-siluq-20260615a2`.
- Live extension backup:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so.backup-before-exact-siluq-layerlet-20260615a2`.

Corrected synthetic checker before the C++ repair:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/check-qwen36-w8a8-middle-layerlet.py \
  --graph-replay --require-graph \
  --json-out data/qwen36-w8a8-middle-layerlet-check-accepted-ref-20260615a2.json \
  --md-out data/qwen36-w8a8-middle-layerlet-check-accepted-ref-20260615a2.md
```

Result:

- Failed as expected.
- Prefix offsets matched in eager and graph replay.
- GEMM1 matched exactly.
- `gemm2_a` and scales diverged in every case, confirming the activation/quant
  step was the real layerlet math mismatch.

Corrected synthetic checker after the C++ repair:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/check-qwen36-w8a8-middle-layerlet.py \
  --graph-replay --require-graph \
  --json-out data/qwen36-w8a8-middle-layerlet-check-exact-siluq-20260615a3.json \
  --md-out data/qwen36-w8a8-middle-layerlet-check-exact-siluq-20260615a3.md
```

Result:

- Overall pass.
- Eager and XPU graph replay passed all four synthetic cases.
- GEMM1 diff: `0.0`.
- `gemm2_a` mismatches: `0`.
- scale diff: `0.0`.
- GEMM2 output diff: `0.0`.

Offset-only endpoint isolation:

```bash
PORT=18092 BASE_URL=http://127.0.0.1:18092 STAMP=20260615a1 \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
METRICS_REPEATS=2 JSON_REPEATS=32 COLOR_REPEATS=32 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  fastgraph-offsets-prefix-no-layerlet-smoke
```

Artifacts:

- Summary:
  `data/qwen36-ablation-fastgraph-offsets-prefix-no-layerlet-smoke-summary-20260615a1.json`
- Log:
  `data/qwen36-ablation-fastgraph-offsets-prefix-no-layerlet-smoke-20260615a1.log`

Result:

- Rejected.
- First metrics request hit HTTP 500, then the engine exited.
- Worker error:
  `RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)`.
- Because the middle layerlet was disabled, this implicates the endpoint
  offset/prefix/mixed-workspace route itself, not only the layerlet math.
- Do not retry offset-only endpoint runs as a performance candidate.

Exact layerlet endpoint smoke:

```bash
PORT=18093 BASE_URL=http://127.0.0.1:18093 STAMP=20260615a4 \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1 \
VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
METRICS_REPEATS=2 JSON_REPEATS=32 COLOR_REPEATS=32 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh fastgraph-exact-layerlet-smoke
```

Artifacts:

- Summary:
  `data/qwen36-ablation-fastgraph-exact-layerlet-smoke-summary-20260615a4.json`
- Metrics:
  `data/qwen36-ablation-fastgraph-exact-layerlet-smoke-p512o512-20260615a4.json`
- JSON canary:
  `data/qwen36-ablation-fastgraph-exact-layerlet-smoke-json-repeat32-20260615a4.json`
- Color canary:
  `data/qwen36-ablation-fastgraph-exact-layerlet-smoke-color-repeat32-20260615a4.json`

Result:

- Metrics: pass.
- Corrected output rate: `88.2832 tok/s`.
- vLLM decode time: `11.3280 ms/token`.
- JSON canary: pass, `32/32`.
- Color canary: pass, `32/32`.
- Quality suite skipped because the speed gate failed.

Decision:

- Keep the exact SiLU/quant repair as a correctness fix for experimental
  layerlet diagnostics.
- Do not promote the current W8A8 middle-layerlet endpoint path. It is now
  canary-clean in the short gate, but it is slower than the clean forced-graph
  lane around `93.3 tok/s`.
- This path will not get us above `100 tok/s` unless it is redesigned to remove
  more command/launch overhead. The current fused boundary is not enough.

Next best >100 tok/s route:

1. Restore or re-run a short accepted-control smoke after the extension rebuild
   to prove the production lane is unchanged by the experimental quant repair.
2. Use decisive timing on the clean `~93.3 tok/s` forced-graph lane, not the
   rejected layerlet, to rank MoE, collectives, GDN, activation/quant, logits,
   and scheduler overhead.
3. If collectives dominate, work on a graph-safe communication path that avoids
   no-op comm capture corruption and custom-allreduce clone overhead.
4. If MoE dominates, skip the current offset-only route and build the next
   resident layerlet around persistent per-layer descriptors, resident route
   buffers, resident scratch, and a single graph-safe command boundary. The
   prefix-offset op and mixed-workspace endpoint route are not acceptable as
   currently implemented.
5. Continue oracle `k=1` spec parity as the other no-quality-loss path to a
   large single-request speedup. No speed claim until token parity is exact.

Post-rebuild accepted-control check:

```bash
PORT=18094 BASE_URL=http://127.0.0.1:18094 STAMP=20260615a5 \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
METRICS_REPEATS=2 JSON_REPEATS=16 COLOR_REPEATS=16 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  fastgraph-control-post-exactsiluq-smoke
```

Artifacts:

- Summary:
  `data/qwen36-ablation-fastgraph-control-post-exactsiluq-smoke-summary-20260615a5.json`
- Metrics:
  `data/qwen36-ablation-fastgraph-control-post-exactsiluq-smoke-p512o512-20260615a5.json`
- JSON canary:
  `data/qwen36-ablation-fastgraph-control-post-exactsiluq-smoke-json-repeat16-20260615a5.json`
- Color canary:
  `data/qwen36-ablation-fastgraph-control-post-exactsiluq-smoke-color-repeat16-20260615a5.json`

Result:

- JSON/color canaries passed, but corrected output rate was only
  `87.2888 tok/s`.
- This is slower than the pre-rebuild clean forced-graph lane around
  `93.3 tok/s`.

Decision:

- Do not leave the rebuilt 54 MB extension installed as the active binary.
- Restored the pre-rebuild live extension from:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so.backup-before-exact-siluq-layerlet-20260615a2`.
- Keep the exact SiLU/quant source change and synthetic parity artifacts as a
  useful correctness repair, but the active endpoint binary is restored to
  avoid a production-lane speed regression.

## 2026-06-15 Packed Oracle Verifier Hidden-State Evidence

Goal:

- Stop guessing about the oracle k=1 mismatch and decide whether the failure is
  sampler/logits, visible token bookkeeping, attention/GDN state, or scheduler
  state commit.

Implementation:

- Added row labeling to the opt-in
  `VLLM_XPU_REPLAY_MICROSCOPE_FILE` trace in
  `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`.
- The trace now labels sampled rows as `sample`, `target`, or `bonus`, records
  input ids, positions, draft ids, request ids, and top-k logits, and emits a
  compact per-row final hidden-state digest before `lm_head`.
- Added launcher passthrough for `REPLAY_MICROSCOPE_FILE`,
  `REPLAY_MICROSCOPE_MAX_LINES`, `REPLAY_MICROSCOPE_RANK`,
  `REPLAY_MICROSCOPE_TENSOR_LIMIT`, and `REPLAY_MICROSCOPE_TOPK`.

Control:

- No-spec eager/no-XPU-graph focused run:
  `data/qwen36-nospec-hiddenrow-eager-repetitive-20260615g42-completion.json`.
- Trace:
  `data/qwen36-nospec-hiddenrow-eager-repetitive-20260615g42-replay-microscope-r0.jsonl`.
- It reproduced the established g20 token sequence exactly, including tail
  `[4581,2468,1345,28043,7072,3817,17856,13]`.

Oracle run:

- Oracle k=1 unsuppressed eager/no-XPU-graph focused run:
  `data/qwen36-oracle1-unsuppressed-hiddenrow-eager-repetitive-20260615g43-completion.json`.
- Trace:
  `data/qwen36-oracle1-unsuppressed-hiddenrow-eager-repetitive-20260615g43-replay-microscope-r0.jsonl`.
- It still drifted only at output index 30: no-spec `17856` (`timing`),
  oracle `22188` (`verification`).

Key evidence:

- The failing oracle verifier pass feeds packed tokens `[7072,3817]` at
  positions `[516,517]`.
- Row 1 is the full-accept bonus row for input token `3817` at position `517`.
- No-spec at the same input/position ranks `17856` above `22188`:
  top ids `[17856,22188,271,248046,9191,198,13,1358,19039,81873,8240,248044]`,
  top values `[21.875,18.125,17.125,15.25,14.375,14.3125,13.5625,13.5,13.25,12.5,12.4375,12.3125]`.
- Oracle packed bonus row ranks `22188` above `17856`:
  top ids `[22188,17856,271,248046,2652,159676,198,9845,181505,10206,174657,695]`,
  top values `[22.625,20.5,17.375,16.75,15.75,15.25,15.1875,14.125,14.125,13.375,13.3125,13.25]`.
- The final hidden state already differs before `lm_head`:
  - no-spec row position `517`: mean `-0.1280970275402069`, sum
    `-262.34271240234375`, l2 `109.96859741210938`, head
    `[2.1875,-1.8125,-0.296875,1.1875,2.578125,-2.875,-0.515625,-4.21875]`.
  - oracle packed row position `517`: mean `-0.1013849526643753`, sum
    `-207.63638305664062`, l2 `109.91653442382812`, head
    `[1.65625,-2.890625,0.0130615234375,-0.5625,3.703125,-3.390625,-1.625,-2.4375]`.

Decision:

- The drift is not a sampler bug and not an `lm_head`/top-k artifact.
- The packed speculative verification path is producing a different model
  hidden state before logits.
- Next target is the hybrid GDN/Mamba speculative state transaction and packed
  verifier metadata: `mamba_utils.preprocess_mamba/postprocess_mamba`,
  `gdn_attn.py` metadata construction, and `gdn_linear_attn.py` spec-state
  usage.
- Low-cost next diagnostic: test `VLLM_XPU_NGRAM_NO_MAMBA_SPEC_BLOCKS=1` with
  the same hidden-row trace. If the mismatch changes or disappears, the fault
  is in speculative Mamba/GDN block allocation/state commit. If not, add
  layer-level hidden digests to find the first layer where packed and sequential
  decode diverge.

## 2026-06-15 Restored Binary Control And Fresh Timing

Restored-binary control smoke:

```bash
PORT=18095 BASE_URL=http://127.0.0.1:18095 STAMP=20260615a6 \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
METRICS_REPEATS=2 JSON_REPEATS=8 COLOR_REPEATS=8 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  fastgraph-control-restored-binary-smoke
```

Artifacts:

- Summary:
  `data/qwen36-ablation-fastgraph-control-restored-binary-smoke-summary-20260615a6.json`
- Metrics:
  `data/qwen36-ablation-fastgraph-control-restored-binary-smoke-p512o512-20260615a6.json`
- JSON canary:
  `data/qwen36-ablation-fastgraph-control-restored-binary-smoke-json-repeat8-20260615a6.json`
- Color canary:
  `data/qwen36-ablation-fastgraph-control-restored-binary-smoke-color-repeat8-20260615a6.json`

Result:

- Metrics: pass.
- Corrected output rate: `89.9613 tok/s`.
- Decode time: `11.1167 ms/token`.
- Client TTFT: `190.25 ms`.
- JSON canary: pass, `8/8`.
- Color canary: pass, `8/8`.
- Quality suite skipped.

Interpretation:

- This validates that the restored binary is canary-clean, but it does not
  recreate the prior `93.3137 tok/s` control from
  `qwen36-ablation-native-decode-safe-prefill-graph-summary-20260614f1.json`.
- Treat this as a short clean control, not a speed improvement.
- Any future unexpected speed move must first diff full run identity against
  the prior accepted forced-graph PIECEWISE lane before interpreting it.

Fresh decisive timing on the accepted cache label:

```bash
STAMP=20260615a7 PORT=18096 BASE_URL=http://127.0.0.1:18096 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
PROMPT_TOKENS=512 OUTPUT_TOKENS=256 METRICS_REPEATS=1 \
WARMUP_OUTPUT_TOKENS=64 RUN_CANARIES=0 \
VLLM_XPU_DECODE_TIMING_SKIP_FIRST=32 \
VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST=32 \
VLLM_XPU_DECODE_TIMING_STEP_EVERY=16 \
bash scripts/run-qwen36-decisive-timing.sh \
  accepted-restored-c1-decisive-timing
```

Artifacts:

- Run summary:
  `data/qwen36-accepted-restored-c1-decisive-timing-run-summary-20260615a7.json`
- Timing summary:
  `data/qwen36-accepted-restored-c1-decisive-timing-timing-summary-20260615a7.json`
- Timing decision:
  `data/qwen36-accepted-restored-c1-decisive-timing-timing-decision-20260615a7.md`

Result:

- Timing-on corrected output rate: `92.5220 tok/s`.
- Decode time: `10.8095 ms/token`.
- Client TTFT: `187.55 ms`.
- Leading timing family: `moe`.
- Top visible label: `moe.quant_method_total` at `4.535820 ms`.
- Runner-up: `runtime`, `gpu_model_runner.bookkeeping_sync` at
  `3.923906 ms`.
- Visible collectives are not the c1 wall in this trace; the largest reported
  collective label is tiny compared with MoE and runtime sync.

Decision:

- Do not spend the next iteration on TP rank maps or custom collectives unless
  a later trace contradicts this.
- The next main speed path is a deeper persistent/resident W8A8 MoE layerlet.
- The previous middle-layerlet only fused GEMM1 -> activation/quant -> GEMM2
  behind one native boundary. That is insufficient. The next design needs to
  keep descriptors, expert pointers, route/remap state, scratch, scales, and
  output buffers resident and remove more per-token/per-layer command overhead.
- The runner-up runtime sync is worth tracking, but it should not displace MoE
  unless a candidate can remove it without losing scheduler/canary correctness.

Async-scheduling smoke on the current prefill-safe forced-graph lane:

```bash
PORT=18097 BASE_URL=http://127.0.0.1:18097 STAMP=20260615a8 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=2 JSON_REPEATS=32 COLOR_REPEATS=32 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-async-scheduling-smoke
```

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-async-scheduling-smoke-summary-20260615a8.json`
- Metrics:
  `data/qwen36-ablation-prefill-safe-async-scheduling-smoke-p512o512-20260615a8.json`
- JSON canary:
  `data/qwen36-ablation-prefill-safe-async-scheduling-smoke-json-repeat32-20260615a8.json`
- Color canary:
  `data/qwen36-ablation-prefill-safe-async-scheduling-smoke-color-repeat32-20260615a8.json`

Result:

- Metrics: pass.
- Corrected output rate: `91.0666 tok/s`.
- Decode time: `10.9806 ms/token`.
- Client TTFT: `190.09 ms`.
- JSON canary: pass, `32/32`.
- Color canary: pass, `32/32`.
- Quality suite skipped.

Decision:

- Reject async scheduling as the next speed path for now. It is short-canary
  clean on this lane, but it does not beat the best clean forced-graph control.
- Keep the observation that `_bookkeeping_sync` is expensive. Revisit only if a
  GPU-local token/scheduler path can be proven faster and canary-clean.

Current priority list:

1. Build a MoE replay microbenchmark from the accepted W8A8 path and identify
   which pieces of `moe.quant_method_total` are fixed overhead versus true GEMM
   cost.
2. Prototype the persistent/resident W8A8 MoE layerlet in replay first, with
   exact eager and XPU graph replay parity before any endpoint test.
3. Keep oracle `k=1` speculative parity as the second no-quality-loss route to
   a large single-request speedup, but do not claim speed until token parity
   passes with speculative activity proven active.
4. For any apparent speed win, run adjacent identity-matched control/candidate
   metrics with canaries and then quality. Speed alone is not a promotion gate.

## 2026-06-15 MoE Scratch Recheck On Restored Binary

Fresh route-exact kernel floor on the restored 67 MB `_xpu_C` binary:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-w8a8-kernel-floor.py \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.(9|14|21)\.' \
  --route-stage-regex '^quark_int8_apply$' \
  --route-start-indices 0,12,24,36,48,60,72,84 \
  --route-window-size 1 --max-cases 8 --gemm-stage both \
  --include-compact-grouped --include-quant --warmup 5 --iterations 20 \
  --output-json data/qwen36-w8a8-kernel-floor-restored-binary-20260615a9.json
```

Result:

- Grouped exact GEMM1 mean across cases: `119.207 us`.
- Grouped exact GEMM2 mean across cases: `111.575 us`.
- Quant hidden rows8 mean: `119.860 us`.
- Quant hidden rows24 mean: `116.875 us`.
- SiLU+quant rows8 mean: `85.041 us`.
- SiLU+quant rows24 mean: `85.033 us`.

Fresh fused-prologue route expansion replay:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-moe-prologue.py \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.9\.' \
  --route-stage-regex '^quark_int8_apply$' \
  --route-start-indices 0:64:4 --rows 1 \
  --iterations 30 --warmup 5 \
  --output-json data/qwen36-moe-prologue-restored-binary-20260615a10.json \
  --markdown-out data/qwen36-moe-prologue-restored-binary-20260615a10.md
```

Result:

- Exact route expansion/count parity: pass.
- Current zero+remap mean: `102.640 us`.
- `fused_moe_prologue` mean: `98.990 us`.
- Mean saving: `3.650 us/layer`.
- Decision: exact but too small alone; useful only as part of a deeper
  resident layerlet.

Fresh full route-exact MoE replay:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1 \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.9\.' \
  --route-stage-regex '^quark_int8_apply$' \
  --route-start-indices 0:64:4 \
  --route-min-num-tokens 1 --route-max-num-tokens 1 \
  --iterations 30 --warmup 5 \
  --output-json data/qwen36-int8-moe-kernels-restored-binary-20260615a11.json \
  --markdown-out data/qwen36-int8-moe-kernels-restored-binary-20260615a11.md
```

Result:

- Fused SiLU+quant enabled: `False`.
- `preallocated_staged` is exact against `xpu_fused_moe` in this replay
  (`max_abs_diff=0.0`).
- Best exact non-reference aggregate: `preallocated_staged` at
  `190.786 us`, `1.478x` faster than the replay reference.
- Worst best-exact non-reference row: `221.257 us`.
- The current `160 us/layer` target is not met, so this is not enough by
  itself for a >100 tok/s endpoint.

Endpoint implication:

- Scratch reuse is a real exact-preserving win in replay, but an old endpoint
  test of `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1` was not identity-matched to the
  current prefill-safe forced-graph lane. It used decode GDN fallback and other
  drift, so it was not a valid rejection.

Identity-matched mixed-workspace smoke:

```bash
PORT=18098 BASE_URL=http://127.0.0.1:18098 STAMP=20260615a12 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
METRICS_REPEATS=2 JSON_REPEATS=32 COLOR_REPEATS=32 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-smoke
```

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-smoke-summary-20260615a12.json`
- Metrics:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-smoke-p512o512-20260615a12.json`
- JSON canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-smoke-json-repeat32-20260615a12.json`
- Color canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-smoke-color-repeat32-20260615a12.json`

Result:

- Metrics: pass.
- Corrected output rate: `93.5606 tok/s`.
- Decode time: `10.6891 ms/token`.
- Client TTFT: `187.04 ms`.
- JSON canary: pass, `32/32`.
- Color canary: pass, `32/32`.
- Quality suite skipped.

Decision:

- This is a small identity-matched speed candidate, not the final goal.
- It is higher than the prior clean `93.3137 tok/s` forced-graph reference, but
  the margin is small and it needs adjacent repeat and quality validation
  before accepting.
- Keep pursuing the resident W8A8 MoE layerlet; mixed workspace only stacks a
  little of the available replay-side scratch win into the endpoint.

Identity-matched mixed-workspace plus async smoke:

```bash
PORT=18099 BASE_URL=http://127.0.0.1:18099 STAMP=20260615a13 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=2 JSON_REPEATS=32 COLOR_REPEATS=32 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-async-smoke
```

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-smoke-summary-20260615a13.json`

Result:

- Corrected output rate: `95.0170 tok/s`.
- Decode time: `10.5253 ms/token`.
- Client e2e output rate: `92.0044 tok/s`.
- Client TTFT: `186.97 ms`.
- JSON canary: pass, `32/32`.
- Color canary: pass, `32/32`.
- Quality suite skipped.

Decision:

- Promising short-gated stack candidate, but still below the >100 tok/s target.
- Needs quality and repeat validation before accepting.

Offset-GEMM MoE replay screen:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1 \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.9\.' \
  --route-stage-regex '^quark_int8_apply$' \
  --route-start-indices 0:64:4 \
  --route-min-num-tokens 1 --route-max-num-tokens 1 \
  --iterations 30 --warmup 5 \
  --enable-offset-gemm --enable-active-offset-gemm \
  --output-json data/qwen36-int8-moe-kernels-offset-screen-restored-binary-20260615a14.json \
  --markdown-out data/qwen36-int8-moe-kernels-offset-screen-restored-binary-20260615a14.md
```

Result:

- Offset and active-offset candidates are exact in replay (`max_abs_diff=0.0`).
- They still do not meet the `160 us/layer` replay target.

Decision:

- Do not promote endpoint offset flags yet. The replay result is correct but not
  strong enough, and earlier offset endpoint experiments were instability-prone.

Mixed-workspace plus async quality gate:

```bash
PORT=18100 BASE_URL=http://127.0.0.1:18100 STAMP=20260615a15 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=4 JSON_REPEATS=64 COLOR_REPEATS=64 \
ABLATION_RUN_QUALITY=1 QUALITY_REPEAT_RUNS=8 QUALITY_LONG_CONTEXT_TOKENS=4096 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-async-quality-gate
```

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-quality-gate-summary-20260615a15.json`

Result:

- Corrected output rate mean: `93.2157 tok/s`.
- Corrected output rate median behavior: repeats 2-4 were `94.3273`,
  `94.5414`, and `94.5266 tok/s`; repeat 1 was slow at `89.4673 tok/s`.
- Decode time mean: `10.7339 ms/token`.
- JSON canary: pass, `64/64`.
- Color canary: pass, `64/64`.
- Quality suite: pass; `pass_all=true`, `baseline_match_all=true`,
  long-context pass.

Decision:

- Quality-clean, but not a decisive speed win. Treat as a stackable candidate
  whose steady-state speed is around `94.5 tok/s` after the first measured
  repeat, not as progress toward >100 by itself.
- Next timing should use this exact identity to see whether async and mixed
  workspace shifted remaining c1 wall time from runtime sync into MoE/GDN.

Mixed-workspace plus async MoE boundary timing:

```bash
STAMP=20260615a17 PORT=18102 BASE_URL=http://127.0.0.1:18102 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^(moe\.|xpu_moe\.|gpu_model_runner\.(forward_total|model_forward))' \
bash scripts/run-qwen36-decisive-timing.sh \
  mixed-workspace-async-moe-boundary-timing
```

Result:

- Corrected output rate: `95.3692 tok/s`.
- `moe.quant_method_total`: roughly `0.88-0.99 ms` per MoE call by rank.
- `moe.apply`: roughly `0.34-0.36 ms` per MoE call.
- `xpu_moe.fused_moe_call`: roughly `0.217-0.226 ms` per MoE call.
- `xpu_moe.workspace_scratch_get`: roughly `0.036-0.038 ms` per MoE call.

Decision:

- The routed XPU MoE kernel is not the whole MoE wall. There is about
  `0.5 ms` per MoE call outside `moe.apply`, so the next target is shared
  expert handling.

Shared-expert timing:

```bash
STAMP=20260615a18 PORT=18103 BASE_URL=http://127.0.0.1:18103 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^(moe\.|xpu_moe\.|gpu_model_runner\.(forward_total|model_forward))' \
bash scripts/run-qwen36-decisive-timing.sh \
  mixed-workspace-async-shared-expert-timing
```

Result:

- Corrected output rate: `95.3114 tok/s`.
- `moe.shared_experts.apply_no_overlap`: `0.466-0.473 ms` on ranks 1-3,
  `0.568 ms` on rank 0.
- `moe.apply`: about `0.341-0.345 ms`.
- `xpu_moe.fused_moe_call`: about `0.216-0.219 ms`.

Decision:

- Serial shared experts are the leading newly isolated MoE wall and are larger
  than the routed XPU fused MoE call itself.
- XPU shared-expert overlap looked promising because it should preserve math,
  but the first opt-in graph smoke failed during startup with:
  `wait method cannot be used for an event associated with a command graph`.
- Rejected for the forced PIECEWISE graph lane unless a graph-safe stream
  synchronization strategy is found.

Rejected smoke:

```bash
PORT=18104 BASE_URL=http://127.0.0.1:18104 STAMP=20260615a19 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_XPU_SHARED_EXPERTS_STREAM=1 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=1 JSON_REPEATS=16 COLOR_REPEATS=16 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-async-xpu-shared-stream-smoke
```

Next:

- Keep the `VLLM_XPU_SHARED_EXPERTS_STREAM` patch opt-in only; do not use it
  in accepted graph lanes yet.
- Pursue a graph-safe shared-expert fast path or exact fused shared+routed
  scheduling before returning to routed W8A8 layerlet work.

### 2026-06-15T05:54:52Z - rejected shared-expert fused SiLU+INT8 quant

Hypothesis:

- The shared expert path is now the largest isolated MoE wall.
- `qwen2_moe.shared.silu_and_mul` plus the down-projection input quantization
  looked like a low-risk target because the XPU extension already exposes
  `silu_and_mul_quant_int8_xpu`.
- Added opt-in `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1`, default off, to use:
  `gate_up_proj -> silu_and_mul_quant_int8_xpu -> int8_gemm_w8a8` for the
  shared expert down projection when the shared expert has `reduce_results=False`.

Command:

```bash
STAMP=20260615a21 PORT=18106 BASE_URL=http://127.0.0.1:18106 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=1 JSON_REPEATS=16 COLOR_REPEATS=16 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-async-shared-fused-act-quant-smoke
```

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-fused-act-quant-smoke-summary-20260615a21.json`
- JSON canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-fused-act-quant-smoke-json-repeat16-20260615a21.json`

Result:

- Corrected output rate: `94.5476 tok/s`, slower than the clean mixed-workspace
  async lane.
- JSON canary failed after 3 repeats (`mismatch_count=1`).
- Color canary passed 16/16.

Decision:

- Rejected. Do not enable `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT` in accepted
  lanes.
- This likely differs slightly from the existing two-kernel SiLU+quant path
  despite matching intent; it does not satisfy the no-quality-loss bar.
- Keep the patch only as a documented rejected candidate unless exact token
  parity is repaired.

### 2026-06-15T06:45:49Z - graph replay and sampler follow-ups

Accepted diagnostic patch:

- Added `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_REGEX`,
  `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_INDICES`, and
  `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_MAX_NUMEL` to clone only selected small XPU
  graph inputs into static graph-owned buffers.
- Added `VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_INDICES=all|*` support for
  diagnostics only.
- Fixed `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1` so strong output mode stores the
  real output object instead of still weak-refing it.

Important rejected/neutral graph results:

- `20260615b3` strong output + native GDN + no top-k:
  `98.4654 tok/s`, but JSON failed at repeat 42 and color failed at repeat 6.
  Strong output does not repair the unsafe no-top-k lane.
- `20260615b4` local-argmax direct-reuse crashed during endpoint startup with
  XPU device lost/out-of-resources errors around `_prepare_inputs`.
- `20260615b5` clone-all outputs for `piecewise:0/41` produced immediate JSON
  and color corruption. Whole-output cloning is invalid because graph outputs
  include internal/KV/scratch tensors that must preserve identity.
- `20260615b6` targeted static input copy on safe `piecewise:1/41` args `8,10`
  passed JSON 64/64 and color 96/96 at `93.2155 tok/s`, but was not faster.
- `20260615b7` native GDN + no top-k + the same static input copy still failed
  at the old JSON/color repeat windows. The remaining native/no-top-k
  corruption is not fixed by graph boundary input copying.

New sampler lead:

- The XPU extension already registers `torch.ops._C.top_k_per_row_decode`.
- Direct parity smoke on XPU full-vocab logits matched `torch.topk(k=1)` for
  rows 1, 2, 4, 8, and 16.
- Raw timing on 151,936-vocab rows:
  - `torch.topk(k=1)`: about `392-419 us`
  - `torch.ops._C.top_k_per_row_decode(k=1)`: about `57-58 us`
- Added opt-in sampler fallback:
  `VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk`.
- First endpoint attempt `20260615b8` failed before readiness because the raw
  kernel returned `int32` and the compiled sampler expected `Long`. Fixed by
  returning `indices.view(-1).long()` to match the existing `torch.topk`
  contract.

Current test in flight:

```bash
STAMP=20260615b9 PORT=18108 BASE_URL=http://127.0.0.1:18108 \
CACHE_LABEL=qwen36-ablation-native-gdn-xpu-topk-int8-mixed-workspace-async-b9 \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=0 \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=0 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=0 \
VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=0 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=2 JSON_REPEATS=64 COLOR_REPEATS=96 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  native-gdn-xpu-topk-int8-mixed-workspace-async-smoke
```

Decision gate:

- If b9 passes JSON/color and lands near or above the old no-top-k speed, promote
  immediately to a full quality run.
- If b9 passes but is below 100 tok/s, stack it with the safest next low-risk
  latency lever.
- If b9 fails at the old repeat windows, the no-top-k failure was not only
  sampler argmax; return to graph replay/input state parity.

Result:

- Summary:
  `data/qwen36-ablation-native-gdn-xpu-topk-int8-mixed-workspace-async-smoke-summary-20260615b9.json`
- Corrected output rate: `97.6363 tok/s`.
- JSON canary: 64/64 passed.
- Color canary: failed at repeat 75 with output
  `伪  3  3  3  3  3  3  3`.

Decision:

- Rejected. `xpu_topk` fixes the unsafe sampler argmax concern, but the native
  GDN/prefill-replay lane still has late token corruption.
- Next isolate the sampler win on the known-safe prefill-fallback lane:
  `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`,
  `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`,
  `VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk`.

### 2026-06-15T07:02:00Z - unsafe unsynchronized XPU top-k on safe lane

Command identity:

- Same as accepted safe lane except:
  `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=0`
  and `VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk`.
- `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`
- `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`
- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'`

Result:

- Summary:
  `data/qwen36-ablation-prefill-safe-xpu-topk-int8-mixed-workspace-async-smoke-summary-20260615b10.json`
- Corrected output rate: `98.2378 tok/s`.
- JSON canary: 96/96 passed.
- Color canary: failed at repeat 99 with output
  `blue, green, red, yellow` instead of
  `blue, green, orange, red`.

Decision:

- Rejected despite the speed gain.
- Since this was on the known-safe prefill-fallback lane, the failure points at
  the unsynchronized custom top-k integration or exact top-k semantics rather
  than native GDN state.
- Direct local stress on fixed random full-vocab logits matched `torch.topk`
  for 3 x 2000 repeats, so the next test is endpoint ordering:
  `VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk_sync`.
- Raw microbench:
  `xpu_topk_sync` is about `300 us` per call versus `torch.topk` about
  `392 us`, so it may retain a smaller safe win if the sync resolves color.

Follow-up result:

- `20260615b11`, same safe lane with
  `VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk_sync`.
- Corrected output rate: `95.1228 tok/s`.
- JSON canary: 96/96 passed.
- Color canary: failed at repeat 99.

Decision:

- Rejected. Synchronizing after the raw XPU top-k kernel did not restore
  semantic equivalence.
- The `top_k_per_row_decode` kernel is not a safe drop-in greedy sampler for
  this model/logits path. Keep the sampler patch for diagnostics only; do not
  enable either `xpu_topk` or `xpu_topk_sync` in accepted lanes.
- Next isolation: keep the proven PyTorch `topk` sampler and test native GDN
  with prefill cudagraph replay disabled:
  `VLLM_XPU_GDN_NATIVE_FALLBACK=0`,
  `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`,
  `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`.

Follow-up result:

- `20260615b12`, native GDN with prefill replay disabled and PyTorch top-k.
- Corrected output rate: `94.1672 tok/s`.
- JSON canary: 96/96 passed.
- Color canary: failed at repeat 7 with output `blue, green, orange,`.

Decision:

- Rejected. Native GDN is unsafe on this lane even when prefill cudagraph replay
  is disabled and the sampler is the accepted PyTorch top-k.
- Do not spend more endpoint cycles on `VLLM_XPU_GDN_NATIVE_FALLBACK=0` unless
  we add a focused GDN state/correctness repair.
- Checked prior notes for `torch.max`: already rejected in
  `2026-06-13-qwen36-decode-graph-replay-corruption.md` because it shares the
  bad XPU reduction behavior. Do not rerun it as a candidate.

### 2026-06-15T07:45:00Z - old accepted lane recovery attempt

Goal:

- Reproduce the public/accepted `99.428358 tok/s` p512/o512 text-prompt lane
  before attempting more speculative or MoE changes.
- Treat prompt shape and full run identity as part of the benchmark identity.

Old accepted reference:

- Payload:
  `data/localmaxxing-qwen36-quark-w8a8-int8-tp4-noprefix-p512n512-20260611.payload.json`
- Metric artifact:
  `data/qwen36-quark-int8-tp4-noprefix-accepted-clean-single-r4-20260611.json`
- Corrected output rate: `99.428358 tok/s`.
- Client TTFT: `76.454 ms`.
- vLLM e2e: `5214.734 ms`.
- Prompt: `prompt_kind=text`, `512` prompt tokens, `512` output tokens.
- Command snippet included PIECEWISE graph, forced/noop graph comm capture,
  custom XPU all-reduce flags, `VLLM_XPU_QUARK_W8A8_MOE=1`,
  `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`, and `gpu-memory-utilization=0.95`.

Recovery attempt d1:

- Summary:
  `data/qwen36-ablation-old-accepted-text-async-gmem95-smoke-summary-20260615d1.json`
- Current launcher defaults plus old text prompt, `gmem=0.95`, async enabled,
  and full GDN fallback default `VLLM_XPU_GDN_NATIVE_FALLBACK=decode,prefill`.
- Corrected output rate: `80.3113 tok/s`.
- Decode histogram: `12.4318 ms/token`.
- Client TTFT: `183.140 ms`.
- JSON/color canaries: `64/64` and `64/64` passed.

Decision:

- Safe but much too slow. Full decode+prefill GDN fallback explains a large
  loss versus the old accepted row and is not a candidate for the >100 tok/s
  objective.

Recovery attempt d2:

- Summary:
  `data/qwen36-ablation-old-accepted-text-gdn-prefill-async-gmem95-smoke-summary-20260615d2.json`
- Same old text prompt with `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`,
  `gmem=0.95`, async enabled, and no mixed INT8 MoE workspace.
- Result: rejected before metrics. The first request killed the backend with
  `UR_RESULT_ERROR_DEVICE_LOST` at `block_table.copy_to_gpu`.
- Log:
  `data/qwen36-ablation-old-accepted-text-gdn-prefill-async-gmem95-smoke-20260615d2.log`

Decision:

- Native decode GDN without the later mixed-workspace/stability guard is not
  currently reliable at this identity. Do not treat it as a speed result.

Recovery attempt d3:

- Summary:
  `data/qwen36-ablation-text-prefill-mixedws-async-gmem95-smoke-summary-20260615d3.json`
- Same old text prompt with `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`,
  `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`, `gmem=0.95`, and async enabled.
- Corrected output rate: `92.1688 tok/s`.
- Decode histogram: `10.8372 ms/token`.
- Client TTFT: `178.712 ms`.
- JSON/color canaries: `64/64` and `64/64` passed.

Comparison to old accepted:

- Same prompt/output token counts and same text metric shape.
- Old accepted corrected decode: `99.4284 tok/s`; current mixed safe text:
  `92.1688 tok/s`.
- Old accepted vLLM e2e: `5214.734 ms`; current: `5725.962 ms`.
- Old accepted client TTFT: `76.454 ms`; current: `178.712 ms`.

Current interpretation:

- The current stable lane is safe but has regressed by about `7.26 tok/s`
  against the old accepted text prompt and by about `0.84 ms/token` against the
  old decode budget.
- Mixed workspace is a stability guard for recent native-decode GDN attempts,
  but it was previously rejected as a speed candidate and does not recover the
  old accepted baseline.
- Next rollback candidate: keep the safe native-decode GDN + PyTorch top-k
  sampler lane, but test whether disabling the launcher's default
  `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1` recovers TTFT/decode without
  canary drift. If it fails quality, keep the disable flag and move to timing
  trace / code-drift isolation.

### 2026-06-15T13:20:00Z - old-shape fast lane isolation

Goal:

- Verify whether the old high-90s PIECEWISE forced-comm graph lane is still
  physically reachable, then separate speed plumbing from correctness.

Attempt e1:

- Summary:
  `data/qwen36-ablation-oldshape-nativegdn-piecewise-gmem90-smoke-summary-20260615e1.json`
- Identity: text p512/o512, `GPU_MEMORY_UTILIZATION=0.90`,
  `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'`, graph enabled,
  forced/noop graph comm capture enabled, native GDN enabled
  (`VLLM_XPU_GDN_NATIVE_FALLBACK=0`), prefill replay enabled, zero-fresh/all
  GDN state disabled, PyTorch top-k fallback disabled, async scheduling enabled.
- Corrected output rate: `98.4720 tok/s`.
- JSON canary failed at repeat 42:
  `{"answer": "42", "unit": whiskey whiskey whiskey whiskey2"}`
- Color canary failed at repeat 6:
  `が可能 acquaintanceunyablue, 4green, 5orange, 6red`

Decision:

- Rejected. The machine can still reach the old fast class, but this identity is
  not quality-safe.
- This removes the false conclusion that the hardware or all recent code paths
  are capped at the low-90s. The blocker is correctness in the fast graph/native
  lane.

Attempt e2:

- Summary:
  `data/qwen36-ablation-oldshape-nativegdn-sanitize-piecewise-gmem90-canary-summary-20260615e2.json`
- Same as e1 plus `VLLM_XPU_CUDAGRAPH_SANITIZE_REPLAY_INPUTS=1`, canaries only.
- JSON failed at repeat 51; color failed at repeat 12.

Decision:

- Rejected. The replay input sanitizer moved the failure point but did not fix
  graph/native-lane corruption.
- Runner fix: record `VLLM_XPU_CUDAGRAPH_SANITIZE_REPLAY_INPUTS` in the
  ablation summary JSON because it is now part of benchmark identity.

Attempt e3:

- Summary:
  `data/qwen36-ablation-oldshape-nativegdn-staticall-piecewise-gmem90-canary-summary-20260615e3.json`
- Same as e1 plus broad static input copy:
  `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_REGEX='piecewise:'`,
  `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_INDICES=all`,
  `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_MAX_NUMEL=1048576`.
- First JSON request returned HTTP 500 and the backend died.
- Log:
  `data/qwen36-ablation-oldshape-nativegdn-staticall-piecewise-gmem90-canary-20260615e3.log`
- Root error: Inductor generated-kernel bounds assertion against the static
  input buffer.

Decision:

- Rejected. Broad static input copy reproduces the known `cudagraph_copy_inputs`
  failure class and should not be retried without narrowing the copied input set.

Next ideas:

- Continue with kernel-level safe wins first, especially shared-expert fused
  SiLU+quant exactness. It can be proven with a small parity harness before
  endpoint testing.
- If the fused shared-expert path remains unsafe or too small, trace the first
  corruption point in the old fast graph lane using request-scoped replay traces
  instead of more endpoint-wide guessing.

### 2026-06-15T14:05:00Z - rebuilt fused shared-expert SiLU+quant parity

Problem:

- Earlier endpoint testing rejected `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1`
  because JSON canary failed after only a few repeats.
- The source for `silu_and_mul_quant_int8_xpu` had already been corrected to
  match the accepted two-step BF16 activation/INT8 quantization semantics, but
  the installed `_xpu_C.abi3.so` binary was stale.

Repair:

- Rebuilt the XPU extension with:
  `JOBS=8 GDN_KERNELS=ON scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
- Installed rebuilt runtime binaries:
  - `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so`
    size `55831416`, timestamp `2026-06-15 04:30:22 -0400`.
  - `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so`
    size `2713184`, timestamp `2026-06-15 04:28:38 -0400`.
  - `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/libgrouped_gemm_xe_2.so`
    size `3539968`, timestamp `2026-06-15 04:30:14 -0400`.

Focused parity gate:

- XPU-captured GEMM1 source:
  `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/silu_quant_parity_xpu_20260615e6.json`
- oneDNN-captured GEMM1 source:
  `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/silu_quant_parity_onednn_20260615e6.json`
- Both checked 16 captured windows.
- Both passed:
  - `all_fused_q_exact=true`
  - `all_fused_scales_exact=true`
  - `all_twostep_q_exact=true`
  - `all_twostep_scales_exact=true`
  - `max_fused_q_diff_count=0`
  - `max_fused_scale_abs_diff=0.0`

Decision:

- The fused shared-expert activation+quant kernel is no longer blocked by the
  captured-window exactness gate.
- Next gate is endpoint canary on the safe PIECEWISE forced-comm graph identity
  with `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1`.
- If endpoint canary fails now, the bug is likely outside this local fused
  kernel arithmetic parity and should be traced at endpoint request/state level.

Endpoint canary result:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-fused-act-quant-rebuilt-smoke-summary-20260615e6.json`
- Identity: safe PIECEWISE forced/noop graph collectives, `GDN_NATIVE_FALLBACK=prefill`,
  `DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`, PyTorch top-k fallback,
  mixed INT8 MoE workspace, async scheduling, plus
  `VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT=1`.
- Corrected output rate: `94.1174 tok/s`.
- JSON canary failed at repeat 3:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-fused-act-quant-rebuilt-smoke-json-repeat64-20260615e6.json`
- Color canary passed 64/64:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-fused-act-quant-rebuilt-smoke-color-repeat64-20260615e6.json`

Decision:

- Rejected. The focused fused kernel arithmetic is exact, but the endpoint path
  still corrupts the JSON canary and does not improve speed versus the accepted
  safe baseline.
- Do not spend more endpoint cycles on this candidate unless tracing shows a
  graph/output aliasing bug specific to the shared-expert fused op.
- Move back to the larger blocker: first-divergence tracing in the old fast
  native-GDN/fast-sampler graph lane that reaches `~98.47 tok/s` but fails
  canaries.

### 2026-06-15T14:55:00Z - XPU top-k sampled-token clone rejected

Goal:

- Test whether the near-fast XPU top-k sampler lane fails because async
  scheduling/output bookkeeping aliases the sampled-token tensor.

Candidate:

- Summary:
  `data/qwen36-ablation-prefill-safe-xpu-topk-clonesampled-int8-mixed-workspace-async-smoke-summary-20260615f1.json`
- Identity: safe PIECEWISE forced/noop graph collectives,
  `GDN_NATIVE_FALLBACK=prefill`, `DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`,
  XPU `top_k_per_row_decode` greedy sampler
  (`VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk`), mixed INT8 MoE
  workspace, async scheduling, plus
  `VLLM_XPU_ASYNC_CLONE_SAMPLED_TOKEN_IDS=1`.

Result:

- Corrected output rate: `97.4830 tok/s`.
- JSON canary failed at repeat 3 with
  `{"answer":"12","unit":"widgets"}`.
- Color canary failed at repeat 90 with
  `blue, green, red, yellow`.

Decision:

- Rejected. Cloning the sampled token before async state update does not repair
  the XPU top-k lane and makes quality worse while slightly reducing speed.
- Next diagnostic should record top-logprobs on the original XPU top-k lane:
  if the selected token is not top-1, the bug is in sampler/top-k or transfer;
  if logits already rank the wrong token first, the corruption is upstream.

### 2026-06-15T15:35:00Z - XPU top-k logprob trace

Goal:

- Determine whether the near-fast XPU top-k lane is selecting the wrong token
  from correct logits or whether logits/model state are already corrupted.

Trace:

- Summary:
  `data/qwen36-ablation-prefill-safe-xpu-topk-logprobs-color-trace-summary-20260615f2.json`
- Artifact:
  `data/qwen36-ablation-prefill-safe-xpu-topk-logprobs-color-trace-color-repeat128-20260615f2.json`
- Identity: safe PIECEWISE forced/noop graph collectives,
  `GDN_NATIVE_FALLBACK=prefill`, `DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`,
  direct XPU top-k greedy sampler
  (`VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk`), mixed INT8 MoE
  workspace, async scheduling, with `COLOR_LOGPROBS=5`.

Result:

- Color canary failed at repeat 90 with:
  `blue, green, red, yellow`.
- At the divergence token, the bad token was already top-1 in returned
  logprobs:
  - chosen `" red"`: `-0.34027379751205444`
  - expected `" orange"`: `-1.3402738571166992`

Decision:

- Rejected as a correctness path.
- The failure is not just final sampled-token transfer choosing the wrong token.
  By the time logprobs are returned, the model/logit state has already drifted.
- This makes XPU top-k a possible trigger for upstream corruption, but not a
  simple argmax-selection bug. Do not promote it without a first-divergence
  state trace.

### 2026-06-15T15:55:00Z - XPU top-k no-cache sampler rejected

Goal:

- Test whether cached sampler-side XPU tensors (`indices`, `seq_lens`) were
  corrupting later requests in the direct XPU top-k lane.

Candidate:

- Summary:
  `data/qwen36-ablation-prefill-safe-xpu-topk-nocache-int8-mixed-workspace-async-smoke-summary-20260615f3.json`
- Identity: same safe PIECEWISE forced/noop graph lane as f2, but with
  `VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk_nocache`.

Result:

- Corrected output rate: `98.4856 tok/s`.
- JSON canary failed at repeat 3 with
  `{"answer":"12","unit":"widgets"}`.
- Color canary failed at repeat 90 with
  `blue, green, red, yellow`.

Decision:

- Rejected. Fresh sampler buffers did not repair correctness and produced the
  same color failure point as the original direct XPU top-k lane.
- Cached sampler buffers are not the root cause.
- Keep the diagnostic mode available, but the next high-budget work should move
  back to the timing-directed persistent W8A8/MoE path and/or fast graph-native
  state tracing.

### 2026-06-15T16:45:00Z - Shared-expert and oracle-spec checkpoint

Goal:

- Find a correctness-preserving path above the current safe `~93-95 tok/s`
  decode lane.

Shared-expert experiments:

- `VLLM_XPU_MOE_SHARED_EXPERT_OVERLAP_STREAM=1` failed before readiness with
  `RuntimeError: wait method cannot be used for an event associated with a
  command graph`. Do not retry this form inside graph capture without changing
  the event/stream boundary.
- `VLLM_XPU_MOE_SHARED_ADD_ALLREDUCE_CUSTOM_OP=1` ran cleanly but only reached
  `94.8245 tok/s`, which is not a meaningful win over the accepted safe
  baseline. Keep as a possible cleanup patch, not a promotion candidate.

Oracle k=1 speculative path:

- Fixed `scripts/launch-qwen36-quark-int8-ngram-trace.sh` so
  `COMPILE_CONFIG` no longer appends an extra `}` when supplied by the caller.
  Also added `DISABLE_SPECULATIVE_CONFIG=1` to let the same launcher produce a
  paired no-spec control with identical graph/cache identity.
- `g3` (`qwen36-oracle1-fullbonus-graph-20260615g3`) failed exact parity
  against the older accepted graph baseline, but this was not a valid verdict:
  it used a fresh graph/cache root and hit known sentinel drift positions.
- `g4` (`qwen36-nospec-paired-freshgraph-20260615g4`) is the valid paired
  no-spec control for the fresh graph/cache branch.
- `g5` (`qwen36-oracle1-paired-freshgraph-20260615g5`) is a real paired oracle
  k=1 failure against `g4`:
  - 14 trace rows, 14 drafts, 13 accepted, 1 rejected.
  - `natural_latency_plan` diverged at token index 17:
    no-spec token `321` (` and`), oracle-spec token `4779` (` memory`),
    trace role `replacement_after_reject`.
  - `repetitive_kernel_notes` diverged at token index 10:
    no-spec token `17856` (` timing`), oracle-spec token `22188`
    (` verification`), trace role `verifier_bonus_after_full_accept`.

Current interpretation:

- The paired failure is not just scheduler accounting; replay accounting was
  clean. The verifier forward appears to see a different KV/input-position/slot
  state at the speculative step.
- The next diagnostic is a paired oracle k=1 rerun with COW parent and worker
  traces enabled, focused on token windows, positions, slot mappings, scheduled
  spec tokens, and cached request updates at the first divergence rows.

Next actions:

- Run `g6` using the `g4` completion trace as `ORACLE_TRACE`, same cache base as
  `g4/g5`, plus `COW_WORKER_TRACE_FILE` and `COW_PARENT_TRACE_FILE`.
- If the worker trace shows an off-by-one verifier position or stale
  `token_ids_cpu` window, patch the transaction. If it does not, run the paired
  no-bonus/recompute diagnostic to isolate verifier-bonus emission from
  accepted-draft commit.

### 2026-06-15T11:35:00Z - Oracle k=1 packed verifier diagnosis

Goal:

- Repair oracle k=1 speculative parity so speculative decode can become the
  no-quality-loss path above the safe `~93 tok/s` baseline.

Established control:

- No-spec eager/no-XPU-graph focused control:
  `data/qwen36-nospec-inputtrace-eager-repetitive-20260615g20-completion.json`
  produced:
  `[3817,17856,13,78503,4581,2468,1345,28043,7072,3817,22188,13,15153,1543,6126,16401,85683,15162,5832,4618,3817,17856,13,78503,4581,2468,1345,28043,7072,3817,17856,13]`.
- Normal oracle k=1 eager/no-XPU-graph focused run
  `data/qwen36-oracle1-fatrace-eager-repetitive-20260615g25-completion.json`
  matched until output index 30, then emitted `22188` (`verification`) where
  no-spec emitted `17856` (`timing`).

Trace evidence:

- FlashAttention trace
  `data/qwen36-oracle1-fatrace-eager-repetitive-20260615g25-fa-trace.jsonl`
  showed one prefill row, fifteen packed `q_len=2` verifier rows with
  `seq_lens` 490 through 518, then one final `q_len=1` row.
- The failing packed verifier row feeds `[7072,3817]` at positions `[516,517]`
  and requests logits for both tokens. No-spec feeds the same visible tokens as
  two separate one-token forwards at the same positions.
- Serializing the GDN recurrent update while keeping packed convolution
  (`g23`) did not change the mismatch, so simple GDN recurrent ordering is not
  the root cause.

Full-attention diagnostic matrix:

- Added guarded `VLLM_XPU_FA_SERIAL_SPEC_MODE` in
  `vllm/v1/attention/backends/flash_attn.py`. Modes tested so far are
  diagnostics only and are disabled unless the env var is set.
- `progressive`/legacy serial full attention plus serial GDN (`g24`) fixed the
  final `timing` token but broke the earlier repeated context, causing the
  sequence to shift from output index 10.
- `same` key-length mode plus serial GDN (`g26`) was worse: it introduced an
  early `<think>` divergence at output index 5.
- `progressive_nocausal` plus serial GDN (`g27`) matched the earlier
  `progressive` behavior and still shifted from output index 10.

Decision:

- The simple full-attention replay modes do not restore token-identical oracle
  k=1 bonus parity.
- The verifier bonus token remains unsafe: normal oracle accepts the draft but
  its bonus logits drift on repeated contexts.
- Next best route is no-bonus speculative decode: commit only verified draft
  tokens, repair the worker/scheduler state alignment after bonus suppression,
  then test k>1/k>2 acceptance. This can still give speedup without relying on
  unsafe bonus logits.

### 2026-06-15T12:05:00Z - No-bonus oracle k=1 recompute attempts

Goal:

- Make oracle k=1 no-bonus speculative decode token-identical to no-spec by
  suppressing the verifier bonus and recomputing the next visible token.

Baseline/control:

- Focused no-spec control remains
  `data/qwen36-nospec-inputtrace-eager-repetitive-20260615g20-completion.json`.
- Correct token tail around the repeated branch is
  `..., 7072, 3817, 17856, 13`.

Runs:

- `g28`
  (`qwen36-oracle1-nobonus-allfilters-serialgdn-eager-repetitive-20260615g28`)
  used all current no-bonus filters:
  `DISABLE_FULL_ACCEPT_BONUS=1`,
  `RECOMPUTE_SUPPRESSED_BONUS=1`,
  `FILTER_SUPPRESSED_BONUS_CACHE=1`,
  `VLLM_XPU_SPEC_DECODE_FILTER_SUPPRESSED_BONUS_NEXT_INPUT=1`,
  `VLLM_XPU_GDN_SPEC_ACCEPTED_DRAFT_ONLY=1`, and
  `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`.
  It still mismatched only at output index 30:
  no-spec `17856` (`timing`), oracle no-bonus `22188`
  (`verification`).
- Worker trace showed token tables were correct before the final recompute:
  the packed verifier fed `[7072,3817]` at positions `[516,517]`, suppressed
  bonus `22188`, and the next visible row recomputed position `517` with token
  `3817`. The recompute still produced `22188`.
- `g29`
  (`qwen36-oracle1-nobonus-skipbonus-serialgdn-eager-repetitive-20260615g29`)
  added `VLLM_XPU_GDN_SERIAL_SPEC_SKIP_DRAFT_STATE=1`. It produced the same
  final mismatch at index 30. Skipping only the bonus recurrent state is not
  enough.
- `g31`/`g32`/`g33` tested a temporary
  `VLLM_XPU_GDN_SERIAL_SPEC_NO_STATE_COMMIT=1` patch that snapshot/restored GDN
  conv and recurrent state around serial spec rows. The first version needed an
  int64 index fix; later variants restored after output merge and with
  `torch.xpu.synchronize()`. All variants failed by diverging much earlier at
  output index 12 (`15153` became `271` and then `<think>`). The failed patch
  was removed from the worktree.

Decision:

- No-bonus cache filtering and next-input filtering are correct but incomplete.
  The failing recompute is no longer caused by a visible token table leak.
- Layer-local GDN tensor restore is the wrong abstraction: it changes verifier
  behavior and does not repair parity. A correct repair must coordinate the
  scheduler, KV slots, and hybrid/Mamba state transaction together.
- Do not promote any no-bonus/oracle speed result yet. The only valid safe
  performance baseline remains the accepted no-spec safe lane at about
  `93.2-93.4 tok/s`.

Next:

- Trace and patch the transaction boundary that decides which packed verifier
  states are committed before the recompute row. Candidate targets are
  `mamba_state_idx` bookkeeping in `mamba_utils.preprocess_mamba/postprocess_mamba`
  and attention KV slot overwrite/rollback for accepted draft positions.
- If this remains too invasive, pause speculation and return to timing-directed
  non-spec speed work: MoE persistent layerlet, TP collective replay/topology,
  and graph-safe shared expert overlap.

### 2026-06-15T13:45:00Z - Corrected layer-0 oracle k=1 diagnosis

Goal:

- Localize the oracle k=1 mismatch without relying on invalid graph/no-graph
  speed comparisons or unverified assumptions about GDN state corruption.

Runs/artifacts:

- `g44`
  `qwen36-oracle1-nomambaspec-hiddenrow-eager-repetitive-20260615g44`
  set `NGRAM_NO_MAMBA_SPEC_BLOCKS=1`. It diverged immediately after the first
  few tokens and degenerated into repeated token `15`. Conclusion: Mamba/GDN
  speculative blocks are required; removing them is not a fix.
- `g45`
  `qwen36-nospec-layertrace-eager-repetitive-20260615g45` recorded no-spec
  all-layer row digests for positions `516-517`.
- `g46`
  `qwen36-oracle1-layertrace-eager-repetitive-20260615g46` reproduced the
  single mismatch at output index 30 and showed that token `3817@517` matches
  at embedding but first differs after layer 0 (`linear_attention`).
- `g47`
  `qwen36-oracle1-serialgdn-layertrace-eager-repetitive-20260615g47` enabled
  both `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1` and
  `VLLM_XPU_GDN_SERIAL_SPEC_CONV=1`. It diverged much earlier, so that combined
  serial diagnostic is invalid for promotion.
- `g48`/`g49` added initial GDN row tracing but exposed a diagnostic bug:
  the trace digest treated 3D `[tokens, heads, dim]` tensors with
  `tokens == 1` as if they were `[batch, tokens, ...]`. This made early
  recurrent-output comparisons invalid.
- Fixed the digest rule in `vllm/model_executor/layers/mamba/gdn_linear_attn.py`
  to treat only 4D+ tensors with leading batch dimension as `[1, tokens, ...]`.
- `g56`/`g57` reran short no-spec/oracle traces with the corrected digest.
  First accepted row (`3817@488`) had exact projection and convolution, and
  GDN core matched to tiny floating accumulation scale.
- `g58` compared the oracle draft row (`17856@489`) against a no-spec
  three-token control. Projection and convolution matched exactly; GDN core
  differed only by about `2.5e-4` in aggregate sum and `3.5e-6` in L2.
- `g59`/`g60` reran full 32-token no-spec/oracle post-GDN traces at the known
  target row `3817@517`:
  `data/qwen36-oracle1-gdnposttrace-vs-nospec-pos517-20260615g60.json`.

Corrected evidence at `3817@517`:

- `mixed_qkv`, `b/a`, `z`, and convolution output are exactly identical between
  no-spec sequential decode and oracle packed verifier row.
- GDN core differs only at the tiny numerical level:
  sum delta `3.34e-6`, L2 delta `8.34e-7`.
- Gated norm and output projection amplify this slightly:
  post-norm sum delta `-3.34e-4`;
  output projection head deltas up to `1.22e-4`.
- The layer-level trace still shows real drift after layer 0; the corrected GDN
  traces indicate this is not a gross cache/state transaction bug. It is the
  numerical consequence of evaluating the verifier as packed `M=2` rows instead
  of two sequential `M=1` rows. Later layers amplify that drift enough to flip
  one low-margin token (`17856` vs `22188`) in the repetitive canary.

Decision:

- Do not pursue the earlier "GDN state corruption" hypothesis without new
  evidence. The state selected after prefill matched between no-spec and oracle.
- Do not promote serial GDN conv/recurrent diagnostics; they are not parity
  fixes.
- Token-identical speculative verification likely requires either:
  1. a sequential/bit-compatible verifier lane for low-margin rows; or
  2. a confidence/margin guard that recomputes low-margin verifier tokens on the
     known-good sequential path; or
  3. accepting approximate packed verifier numerics only after a quality suite
     shows no material quality loss, which is not the same as token identity.

Next best work:

- Add a verifier-logit margin trace for the mismatch row and nearby accepted
  rows. If the flipped token is low-margin, prototype a low-margin sequential
  fallback guard.
- If margin guarding is too invasive, pause speculation and return to
  non-spec speed work against the valid `~93 tok/s` forced-comm PIECEWISE
  baseline: graph-safe MoE/GDN timing, output projection/GEMM M=1 fast path,
  and TP collective replay/topology.
- Any speed result must include full run identity per `/home/steve/AGENTS.md`;
  do not compare against graph-none runs.

### 2026-06-15T14:03:00Z - Active-row margin trace and P0a alias tracer

Goal:

- Stop chasing the wrong speculative fix and return to the shortest
  correctness-preserving base-speed path.

Oracle/no-spec rerun:

- `g62`
  `qwen36-oracle1-replaymargin-eager-repetitive-20260615g62` used normal
  oracle k=1, eager/no-XPU-graph, and the corrected replay microscope active
  row trace.
- `g63`
  `qwen36-nospec-replaymargin-eager-repetitive-20260615g63` is discarded. It
  used the accepted launcher identity and diverged from the established `g20`
  no-spec control at output index 10.
- `g64`
  `qwen36-nospec-replaymargin-nglauncher-eager-repetitive-20260615g64` is the
  valid paired no-spec control. It used the same ngram-trace launcher with
  `DISABLE_SPECULATIVE_CONFIG=1` and matched `g20` exactly.

Artifacts:

- `data/qwen36-oracle1-replaymargin-eager-repetitive-20260615g62-completion.json`
- `data/qwen36-nospec-replaymargin-nglauncher-eager-repetitive-20260615g64-completion.json`
- `data/qwen36-oracle1-vs-nospec-replaymargin-20260615g64.json`

Result:

- The only valid mismatch remains output index 30:
  no-spec token `17856`, oracle token `22188`.
- At position 517 the distributions are already confidently separated:
  no-spec top-1 `17856` with top1/top2 margin `3.75`; oracle top-1 `22188`
  with margin `5.625`.

Decision:

- The final flip is not a low-margin sampler decision. A simple margin guard
  would not repair this case.
- Token-identical speculation needs a true sequential/bit-compatible verifier
  transaction, or a more invasive target-verified multi-token path. Do not
  claim speculative speed until exact token parity passes.
- Immediate engineering priority returns to P0a: make the PIECEWISE forced-comm
  fast lane quality-safe before stacking layerlet or speculation.

Implemented:

- Added active-row mapping to
  `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py` replay microscope
  records. The trace now carries input IDs, positions, logits indices, batch
  descriptor, cudagraph mode, and per-active-row top-k logits.
- Added `VLLM_XPU_CUDAGRAPH_ALIAS_TRACE_*` instrumentation in
  `/home/steve/src/vllm/vllm/compilation/cuda_graph.py`.
  - Records tensor byte ranges for args and outputs at direct/capture/replay
    start/finish.
  - Tracks prior output ranges per rank and batch descriptor.
  - Emits explicit alias matches for `inputs_vs_previous_outputs`,
    `outputs_vs_previous_outputs`, and `outputs_vs_inputs`.
  - Records wrapper id, piecewise index, graph pool, weak-ref policy, replay
    count, static-input status, storage pointers, data pointers, storage
    ranges, and data ranges.
- Saved patch:
  `patches/vllm-qwen36-xpu-cudagraph-alias-trace-20260615.patch`.

Validation:

```bash
cd /home/steve/src/vllm
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  vllm/compilation/cuda_graph.py \
  vllm/v1/worker/gpu_model_runner.py \
  vllm/v1/sample/sampler.py \
  vllm/model_executor/layers/mamba/gdn_linear_attn.py \
  vllm/model_executor/models/qwen3_next.py

git diff --check -- \
  vllm/compilation/cuda_graph.py \
  vllm/v1/worker/gpu_model_runner.py \
  vllm/v1/sample/sampler.py \
  vllm/model_executor/layers/mamba/gdn_linear_attn.py \
  vllm/model_executor/models/qwen3_next.py
```

Both passed.

Helper smoke:

```bash
cd /home/steve/src/vllm
/home/steve/.venvs/vllm-xpu/bin/python - <<'PY'
import torch
from vllm.compilation.cuda_graph import CUDAGraphWrapper
w = object.__new__(CUDAGraphWrapper)
base = torch.arange(8, dtype=torch.float32)
prev = w._xpu_cudagraph_tensor_alias_records((base[:4],), max_tensors=8)
cur_same = w._xpu_cudagraph_tensor_alias_records((base[2:6],), max_tensors=8)
cur_new = w._xpu_cudagraph_tensor_alias_records(
    (torch.arange(4, dtype=torch.float32),), max_tensors=8)
assert w._xpu_cudagraph_find_aliases(cur_same, prev, max_aliases=8)
assert not w._xpu_cudagraph_find_aliases(cur_new, prev, max_aliases=8)
print("alias helper smoke: pass")
PY
```

Result: pass.

Important code-state correction:

- Current local `cuda_graph.py` no longer matches the older note that
  `entry.output = weak_ref_tensors(output)` is unconditional. In this tree,
  `entry.output` follows `cudagraph_options.weak_ref_output`, and piecewise
  wrappers pass `weak_ref_output=is_last_graph`. That means intermediate
  piece outputs are already held strongly unless a global override changes the
  policy. P0a still needs an alias trace because the remaining fault can be
  graph-pool/static-input/custom-op scratch aliasing rather than pure weak-ref
  recycling.

Next trace command:

```bash
cd /home/steve/llm-optimizations
LABEL=qwen36-aliastrace-fastlane-smoke-20260615
STAMP=20260615alias1 \
CACHE_LABEL="$LABEL" \
XPU_GRAPH=1 \
VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
GPU_MEMORY_UTILIZATION=0.90 \
VLLM_XPU_CUDAGRAPH_ALIAS_TRACE_FILE="data/${LABEL}-alias-r{rank}.jsonl" \
VLLM_XPU_CUDAGRAPH_ALIAS_TRACE_MAX_LINES=1200 \
VLLM_XPU_CUDAGRAPH_ALIAS_TRACE_RANK=0 \
VLLM_XPU_CUDAGRAPH_ALIAS_TRACE_REGEX='piecewise:(0|1)/' \
VLLM_XPU_CUDAGRAPH_ALIAS_TRACE_INPUT_MAX_TENSORS=96 \
VLLM_XPU_CUDAGRAPH_ALIAS_TRACE_OUTPUT_MAX_TENSORS=32 \
VLLM_XPU_CUDAGRAPH_ALIAS_TRACE_MAX_ALIASES=128 \
METRICS_REPEATS=1 \
METRICS_OUTPUT_TOKENS=64 \
METRICS_WARMUP_OUTPUT_TOKENS=16 \
ABLATION_SKIP_CANARIES=1 \
ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh "$LABEL"
```

Gate after trace:

- If `piecewise:1` inputs alias `piecewise:0` output 5/6 or another graph0
  output after warmup, prototype targeted XPU-safe static input copy for only
  that handoff.
- If aliases are absent at piece boundaries, extend the same tracer to known
  custom-op scratch owners: GDN conv/SSM state, W8A8 MoE scratch/offsets, and
  custom all-reduce clone buffers.

## 2026-06-15 P0a Graph-Lifetime Differential Results

Goal: find a quality-safe fast PIECEWISE forced-comm graph lane before stacking
MoE/shared-expert speed changes.

All runs below used the fast-lane identity unless noted:

- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'`
- `XPU_GRAPH=1`, `VLLM_XPU_ENABLE_XPU_GRAPH=1`
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`
- `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`
- `GPU_MEMORY_UTILIZATION=0.90`
- `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`
- `VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1`
- `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`
- `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`

### `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1`

Medium gate:

- Summary:
  `data/qwen36-ablation-p0a-strong-output-medium-gate-summary-20260615p0strong1.json`
- Corrected output rate: `94.1246 tok/s`.
- JSON canary: pass, `64/64`.
- Color canary: pass, `128/128`.

Deep gate:

- Summary:
  `data/qwen36-ablation-p0a-strong-output-deep-gate-summary-20260615p0strong2.json`
- Corrected output rate: `92.0524 tok/s` over four repeats.
- Quality suite: pass.
- JSON canary: fail at repeat `49/128`, first mismatch index `48`.
- Color canary: fail at repeat `138/256`, first mismatch index `137`.

Conclusion: strong output can pass shallow gates but does not fix the long-run
graph corruption. Do not promote.

### `VLLM_XPU_CUDAGRAPH_PER_WRAPPER_POOL=1`

- Summary:
  `data/qwen36-ablation-p0a-per-wrapper-pool-medium-gate-summary-20260615p0pool1.json`
- First metrics request returned HTTP 500; backend died.
- Server log:
  `data/qwen36-ablation-p0a-per-wrapper-pool-medium-gate-20260615p0pool1.log`
- Root failure:
  `RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)`
  during `block_table.copy_to_gpu`.

Conclusion: per-wrapper graph pools are unstable in this stack. Do not retry
without a lower-level runtime reason or reduced reproducer.

### `VLLM_XPU_CUDAGRAPH_NO_GLOBAL_POOL=1`

Medium gate:

- Summary:
  `data/qwen36-ablation-p0a-no-global-pool-medium-gate-summary-20260615p0noglobal1.json`
- Corrected output rate: `92.3935 tok/s`.
- JSON canary: pass, `64/64`.
- Color canary: pass, `128/128`.

Deep gate:

- Summary:
  `data/qwen36-ablation-p0a-no-global-pool-deep-gate-summary-20260615p0noglobal2.json`
- Corrected output rate: `90.5909 tok/s` over four repeats.
- Quality suite: pass.
- JSON canary: fail at repeat `49/128`, first mismatch index `48`.
- Color canary: fail at repeat `138/256`, first mismatch index `137`.

Conclusion: no-global-pool is stable enough to run and medium-clean, but it
does not move the long-run corruption window. Do not promote.

### Clone all `piecewise:0/41` replay outputs

Environment:

- `VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_REGEX='piecewise:0/41'`
- `VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_INDICES='*'`

Result:

- Summary:
  `data/qwen36-ablation-p0a-clone-piecewise0-all-medium-gate-summary-20260615cloneall1.json`
- Corrected output rate: `92.5674 tok/s`.
- JSON canary: fail immediately at repeat `1/64`, repeated-token corruption.
- Color canary: fail immediately at repeat `1/128`.

Conclusion: broad cloning changes the graph handoff semantics too much and is
not useful. Targeted cloning of output 5/6 had already failed the deep gate, so
the next copy experiment should target the actual `piecewise:1` input args or
a reduced boundary reproducer, not all `piecewise:0` outputs.

### P0a State After These Runs

The corruption window remains remarkably stable across strong-output,
no-global-pool, and targeted output 5/6 clone runs:

- JSON first mismatch: repeat 49, index 48.
- Color first mismatch: repeat 138, index 137.

This points away from simple weak-ref or global-pool lifetime policy and toward
a graph-owned static input/custom-op scratch state that survives many replays.
Next best engineering step:

1. Build a narrow XPU-safe static input copy for selected `piecewise:1` args
   instead of cloning outputs.
2. Use a fresh, non-appended alias trace file to identify the minimal
   `piecewise:1` arg list after a metrics warmup.
3. If static input copy still fails at the same window, write the reduced
   piecewise0/piecewise1 reproducer and trace GDN/MoE/all-reduce scratch
   owners directly.

### Selected `piecewise:1` Static Input Copy: First Deep-Clean Fast Base

Reproduced and deepened the earlier shallow-pass static-input candidate.

Environment additions:

- `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_REGEX='piecewise:1/41'`
- `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_INDICES='8,10'`
- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`
- `VLLM_EXTRA_ARGS='--uvicorn-log-level warning'`

Important identity note: this launch command did not include
`--no-async-scheduling`, so it is distinct from the no-async fast-lane runs.

Deep gate command label:

- `p0a-static-piece1-8-10-deep-gate`

Artifacts:

- Summary:
  `data/qwen36-ablation-p0a-static-piece1-8-10-deep-gate-summary-20260615static810deep1.json`
- Metrics:
  `data/qwen36-ablation-p0a-static-piece1-8-10-deep-gate-p512o512-20260615static810deep1.json`
- JSON canary:
  `data/qwen36-ablation-p0a-static-piece1-8-10-deep-gate-json-repeat128-20260615static810deep1.json`
- Color canary:
  `data/qwen36-ablation-p0a-static-piece1-8-10-deep-gate-color-repeat256-20260615static810deep1.json`
- Quality suite:
  `data/qwen36-ablation-p0a-static-piece1-8-10-deep-gate-quality-suite-20260615static810deep1.json`

Result:

- Corrected output rate: `93.1062 tok/s` over four p512/o512 repeats.
- Decode time: `10.7411 ms/token`.
- JSON canary: pass, `128/128`.
- Color canary: pass, `256/256`.
- Quality suite: pass; baseline-match all: pass; long-context pass.

Conclusion:

- This is the first deep-clean fast base found in this session.
- It is not above 100 tok/s, but it converts the forced-graph lane from
  "unsafe ceiling" to a stackable quality-clean base under the exact identity
  above.
- Next stack candidates must preserve this identity and add one exact change at
  a time: W8A8 layerlet/prefix-offset first, then shared-expert exact
  workspace/reuse, then oracle/verified speculation.

### Static-Input Base + W8A8 Layerlet/Prefix Stack Rejected

Tested the first proposed stack on top of the deep-clean static-input base.

Environment additions versus the static-input base:

- `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`
- `VLLM_XPU_W8A8_USE_OFFSETS=1`
- `VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1`
- `VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1`

Command label:

- `p0a-static810-layerlet-prefix-medium-gate`

Artifacts:

- Summary:
  `data/qwen36-ablation-p0a-static810-layerlet-prefix-medium-gate-summary-20260615stacklayer1.json`
- Metrics:
  `data/qwen36-ablation-p0a-static810-layerlet-prefix-medium-gate-p512o512-20260615stacklayer1.json`
- JSON canary:
  `data/qwen36-ablation-p0a-static810-layerlet-prefix-medium-gate-json-repeat64-20260615stacklayer1.json`
- Color canary:
  `data/qwen36-ablation-p0a-static810-layerlet-prefix-medium-gate-color-repeat128-20260615stacklayer1.json`

Result:

- Corrected output rate: `89.4664 tok/s`.
- Decode time: `11.1786 ms/token`.
- JSON canary: fail at repeat `27/64`.
- Color canary: fail at repeat `91/128`.
- Quality suite: skipped by design because the medium gate already failed.

Conclusion:

- Reject this stack. It is both slower than the static-input base and
  correctness-failing.
- Do not combine the current W8A8 middle layerlet/prefix-offset path with the
  static-input base again until the layerlet has a real-routing oracle test and
  an endpoint canary pass by itself.
- Next exact speed lever should avoid the rejected routed-MoE layerlet path:
  try shared-expert exact activation workspace/reuse, then unsuppressed oracle
  k=1 parity / verified speculation.

### Static-Input Base + Shared-Expert Activation Workspace Rejected

Implemented an opt-in shared-expert activation workspace in
`/home/steve/src/vllm/vllm/model_executor/models/qwen2_moe.py`.

Default behavior is unchanged. The new path is enabled only with:

- `VLLM_XPU_SHARED_EXPERT_ACT_WORKSPACE=1`

The path keeps the exact same activation math and kernel:

- existing math: `torch.ops._C.silu_and_mul(out, gate_up)`
- no fused quantization
- no down-projection math change
- workspace key includes DBO ubatch id, output shape, dtype, and XPU index

Local checks:

- `python -m py_compile vllm/model_executor/models/qwen2_moe.py`: pass.
- XPU kernel parity against native BF16 formula: max diff `0.0`.

Endpoint stack on the static-input base:

- Command label:
  `p0a-static810-sharedact-medium-gate`
- Summary:
  `data/qwen36-ablation-p0a-static810-sharedact-medium-gate-summary-20260615sharedact1.json`
- Metrics:
  `data/qwen36-ablation-p0a-static810-sharedact-medium-gate-p512o512-20260615sharedact1.json`
- JSON canary:
  `data/qwen36-ablation-p0a-static810-sharedact-medium-gate-json-repeat64-20260615sharedact1.json`
- Color canary:
  `data/qwen36-ablation-p0a-static810-sharedact-medium-gate-color-repeat128-20260615sharedact1.json`

Result:

- Corrected output rate: `93.6893 tok/s`.
- Decode time: `10.6762 ms/token`.
- JSON canary: fail at repeat `27/64`.
- Color canary: fail at repeat `91/128`.

Conclusion:

- Reject this stack. The tiny speed gain is not usable because correctness
  fails under the medium canary gate.
- The failure window matches the other graph-owned static-buffer candidates.
  This suggests that reusing a module-owned activation tensor inside the
  PIECEWISE forced-comm graph lane is another stale-state/alias hazard.
- Do not promote `VLLM_XPU_SHARED_EXPERT_ACT_WORKSPACE=1`. Keep it only as a
  diagnostic flag unless a future graph-lifetime fix makes this class safe.
- Next best speed path is unsuppressed oracle k=1 parity / verified
  speculation, because static-buffer micro-stacks are repeatedly failing
  correctness.

### Oracle k=1 Baseline Attempt: Older Trace Launcher Rejected

Attempted to generate a fresh no-spec accepted token trace with the older
`launch-qwen36-quark-int8-ngram-trace.sh` identity:

- port `18139`
- `DISABLE_SPECULATIVE_CONFIG=1`
- `TAG=oracle-k1-nospec-20260615`
- log:
  `data/qwen36-oracle-k1-nospec-20260615.log`

The server loaded and captured graphs successfully, but the first
`qwen36-completion-oracle-trace.py` request crawled at roughly `0.2 tok/s`.
The trace client and server were stopped before completing the 128-token
baseline trace.

Conclusion:

- Reject this diagnostic identity for current oracle work. It is not the
  static-input clean fast lane and is too slow to produce useful iteration.
- Retry oracle parity with the clean fast-lane safety flags:
  `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`,
  `VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1`,
  `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`,
  `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`, and selected static input copy for
  `piecewise:1/41` args `8,10`.

### Oracle k=1 Replay Join Fix And Current Root Cause

Patched the oracle trace tooling so speculative request IDs join reliably:

- `scripts/replay-qwen36-spec-trace.py`
  - `load_token_cases()` now indexes both `request_id` and `response_id`
    aliases instead of choosing only one.
- `scripts/summarize-qwen36-spec-trace.py`
  - quality artifact summaries now include both IDs and count cases with any
    request ID.

Validation:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  scripts/replay-qwen36-spec-trace.py \
  scripts/summarize-qwen36-spec-trace.py
```

Replayed the unsuppressed oracle k=1 trace:

- Trace:
  `data/qwen36-oracle-k1-unsupp-static-20260615-spec.jsonl`
- Quality trace:
  `data/qwen36-oracle-k1-unsupp-static-p256o32-trace-20260615.json`
- Summary:
  `data/qwen36-oracle-k1-unsupp-static-spec-summary-20260615-rerun.json`
- Replay:
  `data/qwen36-oracle-k1-unsupp-static-replay-20260615.json`

Results:

- Request-ID join works: prefix match count `2`.
- Trace acceptance is `100%` across `23` rows and `2` requests.
- Replay accounting mismatch count: `0`.
- The repetitive prompt is token-identical to no-spec.
- The natural prompt has identical prompt token IDs and diverges at output
  index `14`.
- Draft tokens match through the phrase `decode speed,`; the divergence is the
  verifier bonus token after full acceptance:
  - no-spec continues with token IDs `63520, 45543`
  - oracle k=1 continues with token IDs `29541, 33389`

Conclusion:

- The current unsuppressed oracle k=1 failure is not a prompt mismatch and not
  W8A8 math in accepted draft tokens.
- The next bug is in the verifier bonus-token state transaction after accepted
  drafts: KV/position/GDN state, not basic draft acceptance accounting.

### No-Bonus Filtered Oracle k=1 Attempts Rejected

Tried to suppress the verifier bonus and align worker cache/next-input state
before widening speculation. Both lanes are rejected as unstable on the current
XPU/GDN path.

1. `oracle-k1-nobonus-filter-cap128-static-20260615`
   - Added cap-128 graph capture sizes.
   - Enabled:
     `DISABLE_FULL_ACCEPT_BONUS=1`,
     `FILTER_SUPPRESSED_BONUS_CACHE=1`,
     `RECOMPUTE_SUPPRESSED_BONUS=1`,
     `VLLM_XPU_SPEC_DECODE_FILTER_SUPPRESSED_BONUS_NEXT_INPUT=1`.
   - Log:
     `data/qwen36-oracle-k1-nobonus-filter-cap128-static-20260615.log`
   - Result: first request returned HTTP 500 after
     `UR_RESULT_ERROR_DEVICE_LOST`.
   - Failure point:
     `vllm/v1/worker/gpu_model_runner.py` in
     `_update_states_after_model_execute`, copying
     `num_accepted_tokens.gpu` into
     `input_batch.num_accepted_tokens_cpu_tensor`.

2. `oracle-k1-nobonus-filter-norecompute-cap128-static-20260615`
   - Same as above but without `RECOMPUTE_SUPPRESSED_BONUS`.
   - Log:
     `data/qwen36-oracle-k1-nobonus-filter-norecompute-cap128-static-20260615.log`
   - Result: also HTTP 500 / `UR_RESULT_ERROR_DEVICE_LOST` at the same
     accepted-token CPU tensor copy.
   - It reached speculative activity first: mean acceptance length `1.93`,
     accepted `13`, drafted `14`, acceptance `92.9%`.

Conclusion:

- Suppressing the bonus is not a safe workaround right now.
- The crash happens when the request transitions into a non-spec single-token
  step after speculative activity, and the GDN/Mamba accepted-token copy path
  still runs.
- Next candidate before patching is the existing lower-risk toggle:
  `VLLM_XPU_NGRAM_NO_MAMBA_SPEC_BLOCKS=1`.
- If that still device-loses, patch `_update_states_after_model_execute` so
  non-spec rows after a speculative step do not consume stale/invalid accepted
  token counts, then rerun the oracle parity gate.

### No-Mamba-Spec-Blocks Attempt Rejected; Accepted-D2H Patch Added

Tested the lower-risk Mamba/GDN speculative block toggle:

- Label:
  `oracle-k1-nobonus-filter-nomambaspec-cap128-static-20260615`
- Additional env:
  `VLLM_XPU_NGRAM_NO_MAMBA_SPEC_BLOCKS=1`
- Log:
  `data/qwen36-oracle-k1-nobonus-filter-nomambaspec-cap128-static-20260615.log`
- Spec trace:
  `data/qwen36-oracle-k1-nobonus-filter-nomambaspec-cap128-static-20260615-spec.jsonl`

Result:

- Server reached readiness and served the first request.
- It still hit HTTP 500 / `UR_RESULT_ERROR_DEVICE_LOST` at the same line:
  `gpu_model_runner.py` copying `num_accepted_tokens.gpu` into
  `input_batch.num_accepted_tokens_cpu_tensor`.
- The failing scheduler step again had `scheduled_spec_decode_tokens={}`,
  `num_scheduled_tokens=1`, and `num_output_tokens=15`.
- Spec metrics before failure: mean acceptance length `1.93`, accepted `13`,
  drafted `14`, acceptance `92.9%`.

Conclusion:

- Reserving or omitting Mamba speculative blocks is not the trigger.
- The trigger is the transition from speculative rows into a plain one-token
  non-spec row after the no-bonus diagnostic has advanced worker state.

Patch added in `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`:

- New diagnostic flag:
  `VLLM_XPU_SPEC_DECODE_SKIP_ACCEPTED_D2H_NONSPEC=1`
- In `_update_states_after_model_execute`, when there are no scheduled draft
  tokens, set accepted count to `1` on CPU directly and avoid the XPU-to-CPU
  accepted-count copy.
- This is quality-neutral for a one-token non-spec row because exactly one
  sampled token is accepted.
- `python -m py_compile /home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`:
  pass.

Next:

- Rerun the no-bonus filtered lane with this flag.
- If it survives, replay and compare emitted token IDs against the no-spec
  oracle.

### Accepted-D2H Patch Moves Failure; No-Bonus Lane Rejected As Unsafe

Reran the no-bonus filtered lane with the accepted-count D2H shortcut:

- Label:
  `oracle-k1-nobonus-filter-skipd2h-cap128-static-20260615`
- Additional env:
  `VLLM_XPU_SPEC_DECODE_SKIP_ACCEPTED_D2H_NONSPEC=1`
- Log:
  `data/qwen36-oracle-k1-nobonus-filter-skipd2h-cap128-static-20260615.log`
- Spec trace:
  `data/qwen36-oracle-k1-nobonus-filter-skipd2h-cap128-static-20260615-spec.jsonl`

Result:

- Server reached readiness and served the first request.
- Spec metrics before failure were again useful: mean acceptance length `1.93`,
  accepted `13`, drafted `14`, acceptance `92.9%`.
- The original crash at `num_accepted_tokens_cpu_tensor.copy_` did not recur.
- Failure moved later to `_bookkeeping_sync -> _to_list(sampled_token_ids)`,
  where the next XPU-to-CPU sampled-token copy hit
  `UR_RESULT_ERROR_DEVICE_LOST`.

Conclusion:

- The shortcut worked as a diagnostic but did not make the no-bonus filtered
  path stable.
- The no-bonus filtered path corrupts or invalidates XPU state before the next
  host extraction, not only at the accepted-count transfer.
- Stop chasing the no-bonus workaround for now. The safer path is to debug the
  unsuppressed oracle k=1 verifier-bonus divergence, which completes without
  device loss and has an exact first-token mismatch.

### Unsuppressed Oracle k=1 Microscope And Draft-Only Attempt

Captured a narrower unsuppressed oracle k=1 first-divergence microscope on the
static-input fast lane.

Artifacts:

- Rank-0 microscope trace:
  `data/qwen36-oracle-k1-unsupp-microscope2-static-20260615-rank0.jsonl`
- Spec trace:
  `data/qwen36-oracle-k1-unsupp-microscope2-static-20260615-spec.jsonl`

Finding:

- No-spec continuation:
  `Continue with dense numbered engineering notes. Focus on single-request decode speed, reliability gates, and no quality loss.`
- Oracle candidate continuation:
  `Continue with dense numbered engineering notes. Focus on single-request decode speed, low`
- The accepted verifier target row token `11` (comma) is correct.
- The verifier bonus row then runs at position `265` with input token `11` and
  chooses token `3238` (`low`) while the no-spec path expects token `29541`
  (`reliability`). The expected token is present in the bonus-row top-k, but
  not as top-1.

Conclusion:

- Draft acceptance accounting is correct for the target row.
- The remaining oracle k=1 parity bug is the verifier bonus-row recurrent/KV
  state transaction, not prompt identity, target-row acceptance, or a basic
  sampler join issue.

Also tried post-forward "commit only the accepted draft token" as:

- Label: `oracle-k1-gdn-draftonly-static-20260615`
- Log: `data/qwen36-oracle-k1-gdn-draftonly-static-20260615.log`
- Spec trace:
  `data/qwen36-oracle-k1-gdn-draftonly-static-20260615-spec.jsonl`

Result:

- Rejected. It accepted the first three draft rows, then rejected scheduled
  token `24985` and emitted `271`, after which the run stalled.
- This does not repair the unsuppressed bonus state and makes acceptance worse
  earlier in the sequence.

Next:

- Do not continue no-bonus or draft-only workarounds unless a smaller
  standalone recurrent-state reproducer first proves the required state
  transaction.
- For speed, keep separate low-risk base-lane tests possible, but the real
  >100 tok/s no-quality-loss route remains verified speculation after the
  bonus-row parity fix.

### BF16 Greedy Top-K Fast Path Rejected

Implemented a conservative opt-in sampler shortcut in
`/home/steve/src/vllm/vllm/v1/sample/sampler.py`:

- Env: `VLLM_XPU_GREEDY_SAMPLE_BF16_TOPK_FASTPATH=1`
- Only applies to XPU BF16 logits, pure greedy requests, no logprobs, no
  penalties, no masks, no bad words, no active non-argmax processors, no
  thinking budget state, and no spec/bonus row.
- Uses PyTorch `torch.topk` directly on BF16 logits before the normal FP32
  cast. It deliberately avoids the rejected custom XPU top-k kernel family.

Also added the env flag to the ablation runner identity logging:

- `/home/steve/llm-optimizations/scripts/run-qwen36-ablation-candidate.sh`

Checks:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  /home/steve/src/vllm/vllm/v1/sample/sampler.py
bash -n /home/steve/llm-optimizations/scripts/run-qwen36-ablation-candidate.sh
```

Smoke gate on top of the validated static-input fast base:

- Label: `p0a-static810-bf16-greedy-smoke`
- Summary:
  `data/qwen36-ablation-p0a-static810-bf16-greedy-smoke-summary-20260615bf16g1.json`
- Metrics:
  `data/qwen36-ablation-p0a-static810-bf16-greedy-smoke-p512o512-20260615bf16g1.json`
- JSON canary:
  `data/qwen36-ablation-p0a-static810-bf16-greedy-smoke-json-repeat64-20260615bf16g1.json`
- Color canary:
  `data/qwen36-ablation-p0a-static810-bf16-greedy-smoke-color-repeat128-20260615bf16g1.json`

Result:

- Corrected output rate: `92.1217 tok/s`.
- Decode time: `10.8558 ms/token`.
- JSON canary: pass, `64/64`.
- Color canary: fail at repeat `99/128`, first mismatch:
  `blue, green, red, yellow`.

Conclusion:

- Rejected. It is slower than the validated static-input base
  (`93.1062 tok/s`) and fails the color canary.
- Sampling directly on BF16 logits is not bit-equivalent enough for this model
  path. Do not promote or retry this shortcut without a separate tie/order
  proof against the endpoint canaries.

### Prefill-Safe Mixed Workspace Async Deep Gate Promoted

Promoted the fastest short-gate passing base-lane candidate to a deeper gate.
This is the same prefill-safe mixed-workspace async identity as the previous
short smoke, but with four measured repeats, JSON 128, color 256, and the
quality suite enabled.

Command label:

- `prefill-safe-int8-mixed-workspace-async-deep-gate`

Environment:

- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'`
- `XPU_GRAPH=1`
- `VLLM_XPU_ENABLE_XPU_GRAPH=1`
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`
- `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`
- `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`
- `VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1`
- `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`
- `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`
- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`
- `GPU_MEMORY_UTILIZATION=0.90`
- `VLLM_EXTRA_ARGS='--uvicorn-log-level warning'`

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-summary-20260615a13deep2.json`
- Metrics:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-p512o512-20260615a13deep2.json`
- JSON canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-json-repeat128-20260615a13deep2.json`
- Color canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-color-repeat256-20260615a13deep2.json`
- Quality suite:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-quality-suite-20260615a13deep2.json`

Result:

- Corrected output rate: `93.5505 tok/s` over four p512/o512 repeats.
- Decode time: `10.6899 ms/token`.
- JSON canary: pass, `128/128`.
- Color canary: pass, `256/256`.
- Quality suite: pass; baseline-match all: pass; long-context pass.

Identity comparison against the previous validated static-input base:

- Previous base:
  `p0a-static-piece1-8-10-deep-gate`, `93.1062 tok/s`,
  `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_REGEX='piecewise:1/41'`,
  `VLLM_XPU_CUDAGRAPH_STATIC_INPUT_INDICES='8,10'`.
- New base:
  `prefill-safe-int8-mixed-workspace-async-deep-gate`, `93.5505 tok/s`,
  no static-input copy flags.
- The remaining relevant graph/GDN/sampler/mixed-workspace/async identity is
  otherwise the same.

Conclusion:

- Promote this as the current validated research base. It is only a small
  gain, about `+0.444 tok/s` / `+0.48%`, but it is cleaner because the static
  input copy is no longer needed for this identity.
- This does not solve the user's >100 tok/s goal. It provides a slightly better
  no-quality-loss base for the next stackable speed levers.
- Next candidates should be run one at a time on this base: shared add
  all-reduce, dirty block-table/prefill metadata reduction if it can be made
  non-dirty, and real collective/topology work. Speculation remains blocked on
  oracle k=1 bonus-row parity.

### Shared-Add All-Reduce Candidate Rejected As Slower

Promoted the short-gate passing shared-add all-reduce candidate on top of the
current validated base.

Additional env:

- `VLLM_XPU_MOE_SHARED_ADD_ALLREDUCE_CUSTOM_OP=1`

Command label:

- `prefill-safe-int8-mixed-workspace-async-shared-addar-deep-gate`

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-addar-deep-gate-summary-20260615g2deep1.json`
- Metrics:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-addar-deep-gate-p512o512-20260615g2deep1.json`
- JSON canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-addar-deep-gate-json-repeat128-20260615g2deep1.json`
- Color canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-addar-deep-gate-color-repeat256-20260615g2deep1.json`
- Quality suite:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-addar-deep-gate-quality-suite-20260615g2deep1.json`

Result:

- Corrected output rate: `91.9646 tok/s`.
- Decode time: `10.8798 ms/token`.
- JSON canary: pass, `128/128`.
- Color canary: pass, `256/256`.
- Quality suite: pass; baseline-match all: pass; long-context pass.

Conclusion:

- Reject as a performance regression. It is quality-clean, but slower than the
  `93.5505 tok/s` current base by about `1.59 tok/s`.
- Keep this artifact as evidence that this shared-add all-reduce custom-op path
  is not a speed lever in the current base identity.

### Native GDN Top-K Mixed-Workspace Candidate Rejected

Promoted the short-gate passing native-GDN candidate to the deep gate.

Environment differences versus the current base:

- `VLLM_XPU_GDN_NATIVE_FALLBACK=0`
- `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=0`
- `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`
- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`

Command label:

- `native-gdn-topk-int8-mixed-workspace-async-deep-gate`

Artifacts:

- Summary:
  `data/qwen36-ablation-native-gdn-topk-int8-mixed-workspace-async-deep-gate-summary-20260615b2deep1.json`
- Metrics:
  `data/qwen36-ablation-native-gdn-topk-int8-mixed-workspace-async-deep-gate-p512o512-20260615b2deep1.json`
- JSON canary:
  `data/qwen36-ablation-native-gdn-topk-int8-mixed-workspace-async-deep-gate-json-repeat128-20260615b2deep1.json`
- Color canary:
  `data/qwen36-ablation-native-gdn-topk-int8-mixed-workspace-async-deep-gate-color-repeat256-20260615b2deep1.json`
- Quality suite:
  `data/qwen36-ablation-native-gdn-topk-int8-mixed-workspace-async-deep-gate-quality-suite-20260615b2deep1.json`

Result:

- Corrected output rate: `93.8668 tok/s`.
- Decode time: `10.6540 ms/token`.
- JSON canary: fail at repeat `88/128`.
- Color canary: fail at repeat `12/256`.
- Quality suite: fail repeat check.

Conclusion:

- Reject. The speed is only a small metrics improvement over the current base,
  and it is correctness-failing under the deeper gate.
- This reinforces the earlier native-GDN lesson: short canaries are not enough
  for this path; it still has graph/recurrent-state drift under repeated
  requests.

### Current Base Timing: MoE Dominates

Ran decisive timing on the current validated base
`prefill-safe-int8-mixed-workspace-async-deep-gate`.

Artifacts:

- Run summary:
  `data/qwen36-prefill-safe-int8-mixed-workspace-async-current-base-timing-run-summary-20260615basetime1.json`
- Timing summary:
  `data/qwen36-prefill-safe-int8-mixed-workspace-async-current-base-timing-timing-summary-20260615basetime1.json`
- Corrected timing decision:
  `data/qwen36-prefill-safe-int8-mixed-workspace-async-current-base-timing-timing-decision-20260615basetime1-rerun.json`
- Corrected timing decision markdown:
  `data/qwen36-prefill-safe-int8-mixed-workspace-async-current-base-timing-timing-decision-20260615basetime1-rerun.md`

Result:

- Instrumented endpoint speed was `84.65 tok/s`; this is not comparable to
  normal endpoint speed because timing instrumentation adds overhead.
- Corrected family decision: next target is
  `persistent_w8a8_moe_layerlet`.
- Leading label: `moe_forward_shared.custom_op`, max `9.059154 ms`.
- Runner-up: `gdn_attention_core_xpu.native`, max `1.690804 ms`.
- Other hot MoE labels in the raw trace include
  `moe.quant_method_total` at about `8.420 ms`,
  `moe.shared_experts.apply_no_overlap` at about `6.413 ms`, and
  `qwen2_moe.shared.silu_and_mul` at about `3.997 ms`.
- The top visible collective label is about `0.063 ms`, so collectives are not
  the immediate single-request wall in this identity.

Conclusion:

- Stop spending primary cycles on sampler or collective toggles until a new
  trace says otherwise.
- The next serious no-quality-loss path is structural MoE work:
  a prologue-inclusive or persistent W8A8 MoE/shared-expert layerlet with a
  real-route parity harness first. The existing middle-layerlet only covers
  GEMM1 -> activation/quant -> GEMM2 after route/remap/offset setup, which is
  too narrow for the measured bottleneck.

### Prologue-Inclusive W8A8 MoE Replay: Exact Microbench, Endpoint Rejected

Built and tested a decode-route prologue-inclusive replay path for the current
validated base. The isolated route prologue matched route expansion/counts
exactly and was slightly faster than the existing zero/remap setup.

Artifacts:

- Prologue-only replay:
  `data/qwen36-moe-prologue-current-base-20260615.json`
- Full route replay:
  `data/qwen36-int8-moe-full-route-replay-current-base-20260615.json`
- Endpoint failure log:
  `data/qwen36-ablation-prefill-safe-int8-fused-prologue-offset-smoke-20260615prol1.log`

Result:

- Prologue-only replay: current zero/remap average `106.93 us`; fused prologue
  average `103.80 us`; exact route diff `0`.
- Full route replay: `fused_prologue_offset_gemm` was exact
  (`max_abs_diff=0.0`) and about `1.52x` faster than the replay reference, with
  best measured row `184.05 us`.
- Full endpoint promotion failed during PIECEWISE graph capture with
  `UR_RESULT_ERROR_DEVICE_LOST` near the end of capture.

Conclusion:

- Keep the prologue path default-off for diagnostics only.
- Do not enable it in endpoint capture until there is a reduced multi-rank graph
  reproducer and a fix for the device-loss path.
- Even in replay, the best exact path is still above the rough `160 us` layer
  target needed to get comfortably past `100 tok/s` without help from another
  stackable optimization.

### No-Contiguous Activation Cleanup Rejected

Tested removing the explicit `act_output.contiguous()` handoff before GEMM2 in
the W8A8 MoE path after route replay showed a small exact speed improvement.

Command label:

- `prefill-safe-int8-no-act-contiguous-smoke`

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-no-act-contiguous-smoke-summary-20260615nocontig1.json`
- Metrics:
  `data/qwen36-ablation-prefill-safe-int8-no-act-contiguous-smoke-p512o512-20260615nocontig1.json`
- JSON canary:
  `data/qwen36-ablation-prefill-safe-int8-no-act-contiguous-smoke-json-repeat32-20260615nocontig1.json`
- Color canary:
  `data/qwen36-ablation-prefill-safe-int8-no-act-contiguous-smoke-color-repeat32-20260615nocontig1.json`

Result:

- Corrected output rate: `94.1136 tok/s`.
- Decode time: `10.6255 ms/token`.
- JSON canary: failed at repeat `3/32`; output was valid JSON but answered
  `{"answer":"12","unit":"widgets"}` instead of `42`.
- Color canary: pass, `32/32`.

Conclusion:

- Reject and revert the contiguous-removal change. The endpoint graph path needs
  the contiguous GEMM2 handoff even though local route replay looked exact.
- Lesson: local MoE replay parity is required, but it is not sufficient for
  promotion. Endpoint canaries remain mandatory before claiming any speedup.

### Sampler Fast Paths Rejected Under Current Safe Identity

Tested exact greedy sampler substitutions under the current accepted identity
while keeping PIECEWISE forced-comm graph, prefill-only GDN fallback, prefill
graph replay disabled, and INT8 mixed MoE workspace.

Artifacts:

- `max` sampler summary:
  `data/qwen36-ablation-prefill-safe-max-sampler-int8-mixed-workspace-async-smoke-summary-20260615maxsafe1.json`
- FP32 top-k shortcut summary:
  `data/qwen36-ablation-prefill-safe-fp32-topk-fastpath-int8-mixed-workspace-async-smoke-summary-20260615fp32topkfast1.json`

Result:

- `torch.max` path: `98.4505 tok/s` corrected, but rejected. JSON failed at
  repeat `3/64` with `{"answer":"12","unit":"widgets"}`; color failed at
  repeat `56/128`.
- FP32 top-k shortcut: rejected and reverted. It slowed to `88.5245 tok/s`,
  JSON failed at repeat `3/64`, and color failed at repeat `91/128`.
- Earlier `xpu_topk` / `xpu_topk_nocache` / `xpu_topk_sync` variants remain
  rejected because they fail JSON or color canaries even when speed is near
  `98 tok/s`.

Conclusion:

- Keep the accepted `torch.topk` fallback as the sampler correctness anchor.
- The fastest sampler substitutions are not no-quality-loss in the endpoint
  graph path. Do not retry sampler swaps unless a first-divergence trace proves
  the graph/logit state issue is fixed.

### Fused Prologue Capture: Reduced Repros Pass, Endpoint TP4 Fails

Retested the fused prologue offset path after adding a capture guard and
explicit allow-capture flag.

Artifacts:

- Endpoint failure log:
  `data/qwen36-ablation-prefill-safe-int8-fused-prologue-offset-capture-smoke-20260615prolcap2.log`

Reduced repro evidence:

- Prologue-only synthetic graph capture and replay passes.
- Synthetic `xpu_fused_moe` with prologue + INT8 grouped GEMM + gather captures
  and replays.
- Single-rank stress with 15 graph captures, each containing 40 fused-MoE calls,
  also captures and replays.

Endpoint result:

- Endpoint retry with
  `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET=1` and
  `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE=1` still fails during
  PIECEWISE graph capture at `14/15`, on `Worker_TP3`, with
  `UR_RESULT_ERROR_DEVICE_LOST`.
- The failure occurs while preparing the next dummy run after graph capture
  stress, not in the reduced single-rank reproducer.

Conclusion:

- Prologue remains default-off for endpoint use.
- The missing reproducer is now specifically multi-rank/full-model capture, not
  standalone prologue or standalone fused-MoE graph capture.
- Next prologue work should target a reduced TP4/full-capture reproducer or
  rank-scoped capture isolation before another endpoint promotion attempt.

### Real-Row Middle Layerlet Gate Passed; C1 Prologue Capture Still Fails

Extended `scripts/check-qwen36-w8a8-middle-layerlet.py` with a
rows-per-expert grouped-GEMM oracle and a model-shaped TP4 decode case. The
new case uses 256 experts, hidden size 2048, intermediate size 128, and eight
selected experts with all other experts receiving zero rows.

Run:

```bash
STAMP=20260615realparity2 \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/check-qwen36-w8a8-middle-layerlet.py \
  --graph-replay --require-graph \
  --json-out data/qwen36-w8a8-middle-layerlet-realrows-check-20260615realparity2.json \
  --md-out data/qwen36-w8a8-middle-layerlet-realrows-check-20260615realparity2.md
```

Artifacts:

- `data/qwen36-w8a8-middle-layerlet-realrows-check-20260615realparity2.json`
- `data/qwen36-w8a8-middle-layerlet-realrows-check-20260615realparity2.md`

Result:

- Overall: passed.
- All cases, including `qwen36_decode_one_token_tp4_shape`, passed eager and
  XPU graph replay.
- Rows-per-expert reference vs offsets reference: `0` diff.
- Layerlet vs offsets reference: `0` diff.
- Quantized GEMM1 output diff: `0`; quant scales diff: `0`; q output exact.

Interpretation:

- The middle-layerlet math, offset convention, skewed selected-expert routing,
  and zero-row expert handling are not the current blocker.
- Endpoint failures around the prologue path are full-model/multi-rank graph
  integration or lifetime problems, not a standalone INT8 math issue.

Bounded endpoint retry:

```bash
STAMP=20260615prolc1cap1 \
PORT=18126 BASE_URL=http://127.0.0.1:18126 \
CACHE_LABEL=qwen36-ablation-prefill-safe-int8-prologue-c1capture-smoke \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}' \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1 \
VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1 \
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET=1 \
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE=1 \
METRICS_REPEATS=1 JSON_REPEATS=16 COLOR_REPEATS=16 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-prologue-c1capture-smoke
```

Result:

- Rejected before readiness.
- Log:
  `data/qwen36-ablation-prefill-safe-int8-prologue-c1capture-smoke-20260615prolc1cap1.log`
- Failure: `UR_RESULT_ERROR_DEVICE_LOST` on TP1/TP2 during PIECEWISE graph
  capture size `1`, while the worker was preparing the next dummy-run
  `logit_indices_device` tensor.

Decision:

- Reducing the capture sweep from the default 15 sizes to only c1 does not make
  the prologue-capture endpoint path safe.
- Keep the prologue endpoint flags default-off.
- The next MoE engineering step should be a reduced TP4/full-model capture
  reproducer, or a persistent layerlet variant that does not introduce new
  graph-captured prologue state before the prologue lifetime issue is isolated.

### Oracle k=1 Graph-Safe And All-Serial GDN Probes Rejected

Retested unsuppressed oracle k=1 under the current graph-safe identity with
PIECEWISE forced-comm graph, noop comm capture, prefill-safe GDN, prefill graph
replay disabled, top-k sampler fallback, INT8 mixed workspace, and async
scheduling.

Artifacts:

- Candidate trace:
  `data/qwen36-oracle-k1-graph-safe-candidate-20260615graphsafe1.json`
- Spec summary:
  `data/qwen36-oracle-k1-graph-safe-spec-summary-20260615graphsafe1.json`
- Fixture:
  `data/qwen36-oracle-graph-safe-k1-fixture-20260615graphsafe1.md`
- Graph-safe server log:
  `data/qwen36-oracle-k1-graph-safe-20260615a.log`

Result:

- Exact parity gate failed with two mismatches.
- Spec activity was real: `15` accepted tokens, `1` rejected token, `93.75%`
  acceptance across `16` trace rows.
- Mismatch roles were `replacement_after_reject` and
  `verifier_bonus_after_full_accept`.
- First concrete drifts:
  `natural_latency_plan` produced `memory` where the no-spec accepted trace had
  `hardware`; `repetitive_kernel_notes` produced `PU` where the no-spec
  accepted trace had `unique`.

Conclusion:

- Unsuppressed oracle k=1 is not token-identical yet. The remaining bug is not
  "spec did not run"; it is verifier bonus / replacement-row state under the
  hybrid GDN verifier path.

Follow-up all-serial GDN diagnostic:

- Launch label: `qwen36-oracle-k1-graph-gdnserial-20260615a`
- Log:
  `data/qwen36-oracle-k1-graph-gdnserial-20260615a.log`
- Spec trace:
  `data/qwen36-oracle-k1-graph-gdnserial-20260615a-spec.jsonl`
- Oracle draft trace:
  `data/qwen36-oracle-k1-graph-gdnserial-20260615a-oracle-draft.jsonl`

Result:

- Rejected. It emitted only `4` spec trace rows and `20` oracle-draft rows
  before the trace client timed out.
- The engine logged repeated shared-memory broadcast starvation and then died
  with `TimeoutError: RPC call to sample_tokens timed out`.
- Orphaned vLLM workers remained resident on all four XPUs and required manual
  `SIGKILL`; the cards were verified clear afterward with `xpu-smi ps`.

Conclusion:

- Full serial GDN under the graph lane is not a valid fix or a useful speed
  candidate. The next P0b work should be narrower: instrument or patch the
  verifier bonus/replacement row state path directly, or test a reduced eager
  serial probe only as a parity diagnostic, not as an endpoint candidate.

### Oracle k=1 No-Async Isolation

Retested unsuppressed oracle k=1 with the same graph-safe identity but forced
`--no-async-scheduling`.

Artifacts:

- Candidate trace:
  `data/qwen36-oracle-k1-graph-noasync-candidate-20260615noasync1.json`
- Spec summary:
  `data/qwen36-oracle-k1-graph-noasync-spec-summary-20260615noasync1.json`
- Fixture:
  `data/qwen36-oracle-graph-noasync-k1-fixture-20260615noasync1.md`
- Gate summary:
  `data/qwen36-oracle-graph-noasync-k1-gate-summary-20260615noasync1.json`
- Server log:
  `data/qwen36-oracle-k1-graph-noasync-20260615a.log`

Result:

- Exact parity still failed with the same two mismatches as the async
  graph-safe probe.
- Spec activity matched the graph-safe run: `15` accepted tokens, `1`
  rejected token, `93.75%` acceptance.
- First diffs are identical:
  `hardware` -> `memory` after a rejected draft and `unique` -> `PU` on the
  verifier bonus after a fully accepted draft.

Conclusion:

- Async scheduling is not the root cause of P0b drift.
- The shared failing surface is the core speculative verifier path for hybrid
  GDN rows, specifically replacement-row and full-accept bonus-row state/logits.

### Oracle k=1 Eager/No-Graph Isolation

Retested unsuppressed oracle k=1 with `ENABLE_XPU_GRAPH=0`, `--enforce-eager`,
and `--no-async-scheduling`.

Artifacts:

- Candidate trace:
  `data/qwen36-oracle-k1-eager-noasync-candidate-20260615eager1.json`
- Spec summary:
  `data/qwen36-oracle-k1-eager-noasync-spec-summary-20260615eager1.json`
- Fixture:
  `data/qwen36-oracle-eager-noasync-k1-fixture-20260615eager1.md`
- Gate summary:
  `data/qwen36-oracle-eager-noasync-k1-gate-summary-20260615eager1.json`
- Server log:
  `data/qwen36-oracle-k1-eager-noasync-20260615a.log`

Result:

- Exact parity still failed with two mismatches and the same roles:
  `replacement_after_reject` and `verifier_bonus_after_full_accept`.
- The repetitive prompt's verifier bonus drift is identical to graph runs:
  accepted baseline had `unique`, candidate emitted `PU` after accepting draft
  token `1543`.
- The natural prompt still diverges at the rejected-draft replacement row,
  though the eager replacement token was `Arc` instead of the graph run's
  `memory`.

Conclusion:

- P0b is not caused by XPU graph replay or async scheduling.
- The failing surface is now narrowed to the core hybrid speculative verifier
  forward: a packed two-token verifier row is not equivalent to sequential
  one-token target forwards for GDN state/logits.
- Next split: eager/no-graph with `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1` only
  (no serial conv, no packed serial decode) to test whether the recurrent GDN
  packed update is the drift source.

### Oracle k=1 Eager Serial-Recurrent Probe

Retested eager/no-graph/no-async oracle k=1 with only
`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`.

Artifacts:

- Candidate trace:
  `data/qwen36-oracle-k1-eager-serialrecur-candidate-20260615serialrecur1.json`
- Spec summary:
  `data/qwen36-oracle-k1-eager-serialrecur-spec-summary-20260615serialrecur1.json`
- Fixture:
  `data/qwen36-oracle-eager-serialrecur-k1-fixture-20260615serialrecur1.md`
- Gate summary:
  `data/qwen36-oracle-eager-serialrecur-k1-gate-summary-20260615serialrecur1.json`
- Server log:
  `data/qwen36-oracle-k1-eager-serialrecur-20260615a.log`

Result:

- Exact parity still failed with the same two roles:
  `replacement_after_reject` and `verifier_bonus_after_full_accept`.
- The verifier bonus drift remained `unique` -> `PU` after accepting draft
  token `1543`.

Conclusion:

- Recurrent-only serial GDN is not sufficient. The next split is
  eager/no-graph with both `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1` and
  `VLLM_XPU_GDN_SERIAL_SPEC_CONV=1`, while leaving packed serial decode off.

### Oracle k=1 Eager Serial-Conv Probe

Retested eager/no-graph/no-async oracle k=1 with
`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1` and
`VLLM_XPU_GDN_SERIAL_SPEC_CONV=1`, leaving packed serial decode off.

Artifacts:

- Candidate trace:
  `data/qwen36-oracle-k1-eager-serialconv-candidate-20260615serialconv1.json`
- Spec summary:
  `data/qwen36-oracle-k1-eager-serialconv-spec-summary-20260615serialconv1.json`
- Fixture:
  `data/qwen36-oracle-eager-serialconv-k1-fixture-20260615serialconv1.md`
- Gate summary:
  `data/qwen36-oracle-eager-serialconv-k1-gate-summary-20260615serialconv1.json`
- Server log:
  `data/qwen36-oracle-k1-eager-serialconv-20260615a.log`

Result:

- Exact parity still failed.
- Acceptance worsened from `93.75%` to `66.67%` (`4/6` accepted).
- Both mismatches became `replacement_after_reject`; the previous
  full-accept bonus mismatch disappeared only because the draft was no longer
  accepted.

Conclusion:

- The serial conv diagnostic branch is not a candidate fix; it changes verifier
  behavior and lowers acceptance.
- Current P0b evidence says the production packed verifier path and the serial
  recurrent/conv diagnostics are all non-identical to the sequential target.
  The next useful work is first-divergence instrumentation of the verifier
  input/position/logit rows and a CPU-level fixture for spec row construction,
  rather than enabling more serial endpoint fallbacks.

### Current Graph No-Spec Reference Refresh

Regenerated the current graph/no-spec reference under the optimized fast-lane
identity before continuing oracle k=1 work.

Identity:

- Model:
  `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- Quantization: Quark W8A8 INT8.
- TP/PP: `TP=4`, `PP=1`.
- Graph: `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":128}`,
  `XPU_GRAPH=1`, `VLLM_XPU_ENABLE_XPU_GRAPH=1`,
  `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`,
  `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`.
- GDN: `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`,
  `VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1`,
  `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`.
- Sampler/MoE: `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`,
  `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`.
- Runtime: async scheduling enabled, `GPU_MEMORY_UTILIZATION=0.90`,
  `VLLM_EXTRA_ARGS=--uvicorn-log-level warning`.

Artifacts:

- Logprob diagnostic reference:
  `data/qwen36-nospec-graph-current-ref-candidate-20260615graphref1.json`
- Matching no-logprob, 128-token reference:
  `data/qwen36-nospec-graph-current-ref-candidate-20260615graphref2nolog.json`
- Server log:
  `data/qwen36-nospec-graph-current-ref-20260615a.log`

Result:

- The current graph/no-spec fast lane does **not** match the older
  `data/qwen36-quark-int8-tp4-accepted-restored-current-oracle-baseline-20260612i.json`
  token fixture.
- No-logprob rerun still differs:
  - `natural_latency_plan`: first diff output index `17`;
    current token pair `4779,6044` (`memory management`) versus old fixture
    `11436,29796` (`hardware acceleration`).
  - `repetitive_kernel_notes`: first diff output index `14`;
    current token `6126` (`PU`) versus old fixture `4752` (` unique`).

Conclusion:

- The June 12 oracle fixture is stale for the current optimized fast lane and
  must not be used as the quality anchor for current speculative parity work.
- Next oracle k=1 runs should use
  `data/qwen36-nospec-graph-current-ref-candidate-20260615graphref2nolog.json`
  as `ORACLE_TRACE` and as the accepted comparison file.
- This does not weaken the no-quality-loss rule; it corrects the comparison
  identity so speculative candidates are judged against the exact current
  no-spec graph runtime they would replace.

### Oracle k=1 Against Current Graph Reference

Reran graph oracle k=1 against the fresh current no-spec graph reference:

- Oracle/reference:
  `data/qwen36-nospec-graph-current-ref-candidate-20260615graphref2nolog.json`
- Candidate:
  `data/qwen36-oracle-k1-graph-currentref-candidate-20260615currentreforacle1.json`
- Spec summary:
  `data/qwen36-oracle-k1-graph-currentref-spec-summary-20260615currentreforacle1.json`
- Replay:
  `data/qwen36-oracle-graph-currentref-k1-spec-replay-20260615currentreforacle1.json`
- Fixture:
  `data/qwen36-oracle-graph-currentref-k1-fixture-20260615currentreforacle1.md`
- Gate:
  `data/qwen36-oracle-graph-currentref-k1-gate-summary-20260615currentreforacle1.json`

Result:

- Exact parity still failed, but the run now matches past the stale-reference
  divergence points.
- Spec activity is strong: `29/30` draft rows accepted (`96.67%`).
- `natural_latency_plan`: first mismatch at output index `40`.
  No-spec token `29541` (` reliability`) versus spec token `4779`
  (` memory`). Replay role: `verifier_bonus_after_full_accept`.
- `repetitive_kernel_notes`: first mismatch at output index `19`.
  No-spec token `271` (newline) versus spec token `4618` (` graph`).
  Replay role: `replacement_after_reject`.
- Replay accounting found no generated/scheduled/accounting mismatches, so this
  is not a trace join problem.

Conclusion:

- Oracle k=1 remains the highest-upside no-quality-loss path, but it is blocked
  by packed spec verifier state/logit correctness.
- The main bug to inspect is the same-forward verifier bonus after an accepted
  draft. Suppressing the verifier bonus would remove the speed gain, so the fix
  must make the bonus row token-identical to the next normal no-spec decode
  step.
- State-copy-after-forward flags such as
  `VLLM_XPU_GDN_SPEC_ACCEPTED_DRAFT_ONLY` are unlikely to fix the first bonus
  row because that logit is produced inside the same forward pass. They may
  still be useful for the replacement-after-reject tail after the bonus row is
  fixed.

### XPU Shared-Expert Global Aux-Stream Rejection

Retested the opt-in XPU shared-expert overlap path after changing it from a
per-layer stream allocation to a process-global aux stream.

Patch state:

- `vllm/model_executor/layers/fused_moe/runner/shared_experts.py` now keeps a
  process-global XPU aux stream behind `VLLM_XPU_SHARED_EXPERTS_STREAM=1`.
- `vllm/envs.py` registers `VLLM_XPU_SHARED_EXPERTS_STREAM`.
- The path remains default-off.

Run:

```bash
STAMP=20260615xpusharedglobal1 \
PORT=18120 \
CACHE_LABEL=qwen36-ablation-native-decode-safe-prefill-graph \
XPU_GRAPH=1 \
VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_XPU_SHARED_EXPERTS_STREAM=1 \
GPU_MEMORY_UTILIZATION=0.90 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=1 JSON_REPEATS=16 COLOR_REPEATS=16 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-async-xpu-shared-stream-global-smoke
```

Artifact:

- Server log:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-xpu-shared-stream-global-smoke-20260615xpusharedglobal1.log`

Result:

- Server exited before readiness.
- Root error:
  `RuntimeError: wait method cannot be used for an event associated with a command graph.`
- The failure occurred during XPU graph/allocator cleanup after graph-capture
  setup failed; hardware was clear afterward.

Decision:

- XPU shared-expert aux-stream overlap is rejected for the current PIECEWISE
  graph lane. The process-global stream removed one possible allocation cause,
  but did not fix the graph event semantics failure.
- Do not retry this as a speed candidate unless the XPU graph runtime gains a
  safe way to wait on graph-associated events from an aux stream, or a reduced
  repro proves a vLLM-side event ordering fix.

### Dirty Block-Table On Current Fast Identity Rejection

Retested the dirty block-table commit patch on top of the current validated
fast research identity (`prefill-safe-int8-mixed-workspace-async-deep-gate`).
This was a controlled stack attempt, not a new code change to the model path.

Run:

```bash
STAMP=20260615dirtycur1 \
PORT=18121 \
CACHE_LABEL=qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate \
XPU_GRAPH=1 \
VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_XPU_METADATA_COPY_ALLOW=1 \
VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT=1 \
VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY=256 \
GPU_MEMORY_UTILIZATION=0.90 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=2 JSON_REPEATS=128 COLOR_REPEATS=256 \
ABLATION_RUN_QUALITY=1 QUALITY_REPEAT_RUNS=8 QUALITY_LONG_CONTEXT_TOKENS=4096 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-async-dirtyblock-deep-gate
```

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-dirtyblock-deep-gate-summary-20260615dirtycur1.json`
- Server log:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-dirtyblock-deep-gate-20260615dirtycur1.log`

Result:

- Graph capture and readiness completed.
- The first metrics request returned HTTP 500, and the engine exited.
- Root stack:
  `RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)`
  during `block_table.copy_to_gpu(num_reqs)` inside
  `_commit_dirty_block_table` on the first scheduled request.
- No metrics, JSON, color, or quality artifacts were produced.
- Hardware was clear after shutdown.

Decision:

- Dirty block-table commit is rejected for the current PIECEWISE forced-comm
  fast identity. It previously worked as a metadata-copy reliability tool under
  an older accepted launch, but it is not safe to stack onto the current fast
  base.
- Do not count the older ~100 tok/s dirty-block-table A/B as evidence for this
  current identity. The next >100 path remains exact verifier/spec parity or a
  real MoE layerlet capture fix.

### Current-Safe Decisive Timing Recheck

Re-ran the timing trace under the exact current validated research identity
(`prefill-safe-int8-mixed-workspace-async-deep-gate`): PIECEWISE forced/noop
graph, prefill-only GDN native fallback, prefill recurrent fallback, prefill
graph replay disabled, top-k sampler fallback, INT8 mixed MoE workspace, async
enabled, and `GPU_MEMORY_UTILIZATION=0.90`.

Run:

```bash
STAMP=20260615nexttiming1 \
PORT=18123 BASE_URL=http://127.0.0.1:18123 \
CACHE_LABEL=qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
PROMPT_TOKENS=512 OUTPUT_TOKENS=256 METRICS_REPEATS=1 RUN_CANARIES=0 \
bash scripts/run-qwen36-decisive-timing.sh current-safe-decisive-timing-next1
```

Artifacts:

- `data/qwen36-current-safe-decisive-timing-next1-run-summary-20260615nexttiming1.json`
- `data/qwen36-current-safe-decisive-timing-next1-timing-decision-20260615nexttiming1.md`
- `data/qwen36-current-safe-decisive-timing-next1-timing-summary-20260615nexttiming1.json`

Result:

- Metrics-only corrected decode: `95.0788 tok/s` for p512/o256. This is not a
  promoted quality result; use it only as timing evidence.
- Decision JSON picked family `moe`, next target
  `persistent_w8a8_moe_layerlet`.
- Top visible hot labels were `moe_forward_shared.custom_op`,
  `moe.quant_method_total`, and `moe.shared_experts.apply_no_overlap`;
  top collective timing stayed around `0.071 ms`.

Decision:

- The next base-rate attempt should be MoE persistence/layerlet work, not
  collectives, sampler, or GDN-first work.
- Added an opt-in candidate flag,
  `VLLM_XPU_INT8_MOE_PERSISTENT_SCRATCH=1`, to reuse per-layer W8A8 MoE
  scratch tensors for c1 decode without changing kernel math or the scratch
  ABI. This is a small persistence step, not the final layerlet.
- Promotion gate remains unchanged: adjacent accepted-control A/B, canaries,
  and deeper quality before counting any speed improvement.

### XPU INT8 MoE Persistent Scratch Rejection

Implemented a default-off `VLLM_XPU_INT8_MOE_PERSISTENT_SCRATCH=1` candidate
in `vllm/model_executor/layers/fused_moe/experts/xpu_moe.py`. The change keeps
the existing `xpu_fused_moe` kernel ABI and math unchanged, but reuses
per-layer c1 decode scratch tensors instead of taking fresh views from the
global workspace manager on every call. It is registered in `vllm/envs.py`.

Run:

```bash
STAMP=20260615persist1 \
PORT=18124 BASE_URL=http://127.0.0.1:18124 \
CACHE_LABEL=qwen36-ablation-prefill-safe-int8-persistent-scratch-async-smoke \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_XPU_INT8_MOE_PERSISTENT_SCRATCH=1 \
GPU_MEMORY_UTILIZATION=0.90 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=2 JSON_REPEATS=32 COLOR_REPEATS=32 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-persistent-scratch-async-smoke
```

Artifacts:

- `data/qwen36-ablation-prefill-safe-int8-persistent-scratch-async-smoke-summary-20260615persist1.json`
- `data/qwen36-ablation-prefill-safe-int8-persistent-scratch-async-smoke-p512o512-20260615persist1.json`
- `data/qwen36-ablation-prefill-safe-int8-persistent-scratch-async-smoke-json-repeat32-20260615persist1.json`
- `data/qwen36-ablation-prefill-safe-int8-persistent-scratch-async-smoke-color-repeat32-20260615persist1.json`

Result:

- Corrected decode: `92.9897 tok/s`, slower than the current validated base
  (`93.5505 tok/s`).
- JSON canary: `32/32`.
- Color canary: `32/32`.
- Quality suite: skipped because the speed gate failed.

Decision:

- Reject persistent scratch as a standalone base-rate improvement. It is
  quality-clean in a shallow smoke gate, but slower.
- Keep the flag default-off as a diagnostic building block only.
- Next MoE work needs to be true prologue-inclusive/persistent layerlet or
  endpoint-safe offset/layerlet graph integration, not Python scratch-view
  reuse.

### GDN Spec Store-All Guard Rejection

Added an env-gated diagnostic around the FLA/GDN speculative final-state store
path in:

- `/home/steve/src/vllm/vllm/model_executor/layers/fla/ops/fused_recurrent.py`
- `/home/steve/src/vllm/vllm/model_executor/layers/fla/ops/fused_sigmoid_gating.py`

The safe default remains accepted-only state stores:

```bash
VLLM_XPU_GDN_SPEC_STORE_ACCEPTED_ONLY=1
```

Diagnostic attempt:

- Label: `qwen36-oracle-k1-storeall-20260615`
- Mode: oracle/prompt-lookup k=1 with
  `VLLM_XPU_GDN_SPEC_STORE_ACCEPTED_ONLY=0`
- Identity: Quark W8A8 INT8, TP4, 32K, PIECEWISE forced-comm/noop graph,
  prefill-safe GDN, prefill graph replay disabled, top-k fallback.

Result:

- Endpoint reached readiness.
- The first deterministic trace request failed with HTTP 500.
- Worker log root error:
  `UR_RESULT_ERROR_DEVICE_LOST` during `block_table.copy_to_gpu()`.

Decision:

- Reject store-all GDN spec state as a parity fix. It is not endpoint-safe.
- Keep the accepted-only default and only use store-all as an opt-in diagnostic
  if a smaller recurrent-state reproducer needs it.
- This reinforces the latest row-trace finding: the oracle k=1 mismatch is not
  a simple missing GDN final-state write.

### TP2 Current-Safe Topology Smoke Rejection

Parameterized the accepted launcher with `TP_SIZE` while keeping the default
at `4`, so topology checks can reuse the same ablation harness without changing
existing TP4 behavior.

Run:

```bash
STAMP=20260615tp2safe1 \
PORT=18125 BASE_URL=http://127.0.0.1:18125 \
CACHE_LABEL=qwen36-ablation-prefill-safe-int8-mixed-workspace-async-tp2-smoke \
TP_SIZE=2 ONEAPI_DEVICE_SELECTOR=level_zero:0,1 ZE_AFFINITY_MASK=0,1 \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
GPU_MEMORY_UTILIZATION=0.90 MAX_NUM_SEQS=24 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=1 JSON_REPEATS=16 COLOR_REPEATS=16 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-async-tp2-smoke
```

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-tp2-smoke-summary-20260615tp2safe1.json`
- Metrics:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-tp2-smoke-p512o512-20260615tp2safe1.json`
- JSON canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-tp2-smoke-json-repeat16-20260615tp2safe1.json`
- Color canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-tp2-smoke-color-repeat16-20260615tp2safe1.json`

Result:

- Corrected decode: `85.8691 tok/s`.
- Decode time: `11.6458 ms/token`.
- JSON canary: `16/16`.
- Color canary: `16/16`.
- TP2 memory load: about `16.88 GiB` per rank.

Decision:

- Reject TP2 for the current single-request target. It is clean in a shallow
  gate but materially slower than the TP4 validated base (`93.5505 tok/s`).
- Do not spend a deep quality run on TP2 unless a new engine/kernel path changes
  the balance. The next high-value work remains MoE structural work and exact
  verified-spec parity, not topology.

### TP4 Prologue Capture Reproducer Passed; Full Endpoint Still Fails

Built a reduced TP4 reproducer for the prologue-inclusive W8A8 MoE decode stack:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/repro-qwen36-prologue-tp4-capture.py \
  --captures 15 --layers-per-capture 40 --distinct-layers --replays 1 \
  --json-out data/qwen36-prologue-tp4-capture-repro-20260615tp4proldistinct15.json \
  --md-out data/qwen36-prologue-tp4-capture-repro-20260615tp4proldistinct15.md
```

Artifacts:

- `data/qwen36-prologue-tp4-capture-repro-20260615tp4prolrepro1.json`
- `data/qwen36-prologue-tp4-capture-repro-20260615tp4prolrepro15.json`
- `data/qwen36-prologue-tp4-capture-repro-20260615tp4proldistinct1.json`
- `data/qwen36-prologue-tp4-capture-repro-20260615tp4proldistinct15.json`

Result:

- Repeated-layer and distinct-layer TP4 graph capture both passed.
- The reproducer covers `fused_moe_prologue`,
  `per_token_quant_int8_xpu_out`, `qwen36_moe_w8a8_middle_layerlet`, and a
  post-capture CPU-to-XPU dummy tensor copy.
- This did not reproduce the endpoint `UR_RESULT_ERROR_DEVICE_LOST`.

Endpoint follow-up:

```bash
STAMP=20260615pprolc1 \
PORT=18126 BASE_URL=http://127.0.0.1:18126 \
CACHE_LABEL=qwen36-ablation-prefill-safe-int8-persistent-prologue-c1capture-smoke \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
VLLM_XPU_INT8_MOE_PERSISTENT_SCRATCH=1 \
VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1 \
VLLM_XPU_W8A8_USE_OFFSETS=1 \
VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1 \
VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1 \
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET=1 \
VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE=1 \
GPU_MEMORY_UTILIZATION=0.90 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=1 JSON_REPEATS=16 COLOR_REPEATS=16 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-persistent-prologue-c1capture-smoke
```

Result:

- Endpoint failed before readiness with
  `UR_RESULT_ERROR_DEVICE_LOST` during PIECEWISE graph capture size `1`, at the
  `logit_indices_device = torch.from_numpy(logit_indices).to(...)` copy.
- Persistent prologue scratch did not repair the full endpoint failure.

Decision:

- The prologue math/kernel stack is not the immediate blocker by itself.
- The remaining failure is full-vLLM graph/memory-manager/adjacent-graph state
  around capture, not standalone TP4 prologue + layerlet capture.
- Keep prologue/persistent scratch flags default-off. Do not promote them.
- The next base-rate path should either isolate the full-model capture
  interaction further or shift to exact verified-spec parity; sampler swaps
  remain rejected unless token-handoff tracing proves a narrow repair.

### XPU Top-K TP Sampled-Token Sync Rejection

Added two default-off diagnostics:

- `xpu_topk_sync` now synchronizes after the int32-to-int64 sampled-token
  conversion, so the returned `LongTensor` is covered by the sync.
- `VLLM_XPU_SYNC_SAMPLER_TOKENS=1` broadcasts normal sampler outputs from TP
  first rank before next-input state, reusing the local-argmax sync helper.

Tested them together under the current safe identity:

```bash
STAMP=20260615samptpsync1 \
PORT=18127 BASE_URL=http://127.0.0.1:18127 \
CACHE_LABEL=qwen36-ablation-prefill-safe-xpu-topk-sync-tpsampled-int8-mixed-workspace-async-smoke \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk_sync \
VLLM_XPU_SYNC_SAMPLER_TOKENS=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
GPU_MEMORY_UTILIZATION=0.90 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=1 JSON_REPEATS=32 COLOR_REPEATS=128 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-xpu-topk-sync-tpsampled-int8-mixed-workspace-async-smoke
```

Artifact:

- `data/qwen36-ablation-prefill-safe-xpu-topk-sync-tpsampled-int8-mixed-workspace-async-smoke-20260615samptpsync1.log`

Result:

- Graph capture completed and the server reached readiness.
- The first metrics request failed before metrics were written.
- Root error: `UR_RESULT_ERROR_DEVICE_LOST` during
  `block_table.copy_to_gpu()` in the next `_prepare_inputs` call, with the
  async output copy thread also failing while synchronizing the copy-ready
  event.

Decision:

- Reject TP sampler-token broadcast for this graph lane.
- Do not use `VLLM_XPU_SYNC_SAMPLER_TOKENS=1` in accepted or promotion runs.
- The remaining sampler-only probe is `xpu_topk_sync` with the post-conversion
  sync but without TP broadcast; if that still fails the previous canary window,
  stop sampler swaps and return to MoE structural or oracle-parity work.

### XPU Top-K Post-Long Sync Rejection

Tested the remaining sampler-only probe: `xpu_topk_sync` with synchronization
after the returned `LongTensor` conversion, but without TP sampled-token
broadcast.

Run:

```bash
STAMP=20260615samppostlong1 \
PORT=18128 BASE_URL=http://127.0.0.1:18128 \
CACHE_LABEL=qwen36-ablation-prefill-safe-xpu-topk-sync-postlong-int8-mixed-workspace-async-smoke \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK=xpu_topk_sync \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
GPU_MEMORY_UTILIZATION=0.90 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=1 JSON_REPEATS=32 COLOR_REPEATS=128 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-xpu-topk-sync-postlong-int8-mixed-workspace-async-smoke
```

Artifacts:

- `data/qwen36-ablation-prefill-safe-xpu-topk-sync-postlong-int8-mixed-workspace-async-smoke-summary-20260615samppostlong1.json`
- `data/qwen36-ablation-prefill-safe-xpu-topk-sync-postlong-int8-mixed-workspace-async-smoke-p512o512-20260615samppostlong1.json`
- `data/qwen36-ablation-prefill-safe-xpu-topk-sync-postlong-int8-mixed-workspace-async-smoke-json-repeat32-20260615samppostlong1.json`
- `data/qwen36-ablation-prefill-safe-xpu-topk-sync-postlong-int8-mixed-workspace-async-smoke-color-repeat128-20260615samppostlong1.json`

Result:

- Corrected decode: `94.8247 tok/s`.
- JSON canary: failed at repeat `3/32`.
- Color canary: failed at repeat `91/128`.

Decision:

- Reject XPU top-k sampler substitution under the current safe identity.
- Post-conversion synchronization does not repair correctness.
- Keep the accepted PyTorch `topk` fallback as the only validated greedy
  sampler path.
- Stop sampler swaps and return to MoE structural work or exact verified-spec
  parity for the next no-quality-loss speed path.

### Fused Prologue C1 Endpoint Isolation

Date: 2026-06-15

Purpose:

- Determine whether the fused W8A8 MoE prologue path can be used to recover
  the fixed per-token MoE overhead without reducing quality.
- Avoid repeating the benchmark-identity mistake: every comparison here used
  the current PIECEWISE forced-comm graph lane unless explicitly noted.

Accepted safe reference:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-summary-20260615a13deep2.json`
- Corrected output rate: `93.5505 tok/s`.
- Decode: `10.6899 ms/token`.
- Quality: JSON 128, color 256, and quality suite passed.

Isolation results:

- `prefill-safe-int8-layerlet-noprolog-directsync`
  - Summary:
    `data/qwen36-ablation-prefill-safe-int8-layerlet-noprolog-directsync-summary-20260615layerletnoprologsync1.json`
  - Result: reached readiness with direct sync and no fused prologue.
  - Interpretation: the no-prologue layerlet path is graph-stable enough to
    capture.
- `prefill-safe-int8-layerlet-noprolog-smoke`
  - Summary:
    `data/qwen36-ablation-prefill-safe-int8-layerlet-noprolog-smoke-summary-20260615layerletnoprologsmoke1.json`
  - Corrected output rate: `86.8206 tok/s`.
  - Decode: `11.5236 ms/token`.
  - JSON/color smoke passed, but the quality suite failed
    `exact.arithmetic`.
  - Decision: reject. Stable is not enough; it is slower and not quality clean.
- `prefill-safe-int8-prologue-nopersist-directsync`
  - Log:
    `data/qwen36-ablation-prefill-safe-int8-prologue-nopersist-directsync-20260615prologenopersistds1.log`
  - Trace:
    `data/qwen36-prologue-nopersist-directsync-trace-r*-20260615prologenopersistds1.jsonl`
  - Result: device loss during c1 capture. All ranks finished the 8192 warmup
    and c1 piece 0; c1 piece 1 (`submod_2`) started and failed at direct sync.
- `prefill-safe-int8-prologue-nolayerlet-directsync`
  - Log:
    `data/qwen36-ablation-prefill-safe-int8-prologue-nolayerlet-directsync-20260615prologenolayerletds1.log`
  - Trace:
    `data/qwen36-prologue-nolayerlet-directsync-trace-r*-20260615prologenolayerletds1.jsonl`
  - Result: same c1 `submod_2` device loss without the middle layerlet.
  - Interpretation: the endpoint blocker is the fused prologue offset path
    itself, not persistent scratch and not the middle layerlet.
- Patched standalone prologue replay:
  - Script: `scripts/repro-qwen36-prologue-tp4-capture.py`
  - New controls: `--topk-dtype`, `--prewarm-rows`, `--prewarm-repeats`.
  - Artifact:
    `data/qwen36-prologue-tp4-capture-repro-int64-prewarm8192-20260615a.json`
  - Result: TP4 standalone capture/replay passed even with int64 top-k ids and
    8192-row prewarm.
  - Interpretation: the failure needs more full-vLLM context: compiled segment
    adjacency, shared-output/add/allreduce, workspace manager, stream ordering,
    or an adjacent op inside the same PIECEWISE submodule.

Compiled segment mapping:

- Cache inspected:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-ablation-prefill-safe-int8-prologue-nopersist-directsync/vllm/torch_compile_cache/890f183398/rank_0_0/backbone/computation_graph.py`
- `submod_2` contains layer 0 GDN output projection/allreduce,
  post-attention RMSNorm, `torch.ops.vllm.moe_forward_shared(...)`, MoE output
  combine, allreduce, and the beginning of layer 1 GDN input projection.
- Since no-prologue capture reaches readiness through this boundary, the fused
  prologue path poisons the stream inside the layer 0 MoE portion of the
  compiled segment.

Decision:

- Keep `VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET=1` rejected/default-off for
  endpoint work.
- Do not use fused prologue results for speed claims until a reduced repro
  includes enough endpoint context to reproduce and fix the c1 `submod_2`
  device-loss failure.
- The next high-upside no-quality-loss route is exact verified speculation
  parity. A secondary low-risk route is scheduler/shape tuning after confirming
  clean XPU memory.

Machine cleanup:

- Two orphaned `VLLM::Worker_TP` processes from the failed device-loss run were
  killed.
- `xpu-smi ps` then showed no live vLLM process.
- `xpu-smi dump` reported about `26-44 MiB` used per card and no throttling.

Rejected/invalid result:

- `prefill-safe-int8-mixed-workspace-maxseq1-smoke` failed before readiness
  because stale failed-run state left cards with too little free memory.
  This is not a valid `MAX_NUM_SEQS=1` performance result and must not be
  compared.

### Fresh Oracle k=1 Speculation Gate Attempt

Date: 2026-06-15

Purpose:

- Re-run the oracle/speculation correctness path under the current safe
  PIECEWISE forced-comm identity instead of relying on older June 11 traces.

Accepted no-spec trace:

- Artifact:
  `data/qwen36-oracle-accepted-current-20260615oraclefresh1.json`
- Log:
  `data/qwen36-oracle-accepted-current-20260615oraclefresh1.log`
- Result: pass. Both `natural_latency_plan` and `repetitive_kernel_notes`
  produced 128 output tokens.

N-gram k=1 candidate:

- Log:
  `data/qwen36-oracle-ngram1-current-20260615oraclefresh1.log`
- Intended spec trace:
  `data/qwen36-oracle-ngram1-current-20260615oraclefresh1.jsonl`
- Result: rejected before parity. The server never reached readiness and no
  candidate token trace was produced.
- Failure: `UR_RESULT_ERROR_DEVICE_LOST` during PIECEWISE graph capture.
- Observed capture progress: `21/27` graph capture sizes completed or in
  progress before the failure.
- Identity difference: vLLM disables async scheduling for n-gram speculative
  decoding, so any later speed result from this path must be labeled as a
  separate spec identity.

Decision:

- This is a graph-stability failure, not a token-parity failure.
- Next speculation step is to constrain graph capture to the c1-relevant small
  sizes, then run the same accepted-vs-candidate parity gate. If small capture
  reaches readiness and parity fails, repair token/KV/spec accounting. If small
  capture also fails, debug spec graph capture before spending more time on
  spec correctness.

### Fresh Oracle k=1 C1-Capture Parity Result

Date: 2026-06-15

Purpose:

- Continue oracle k=1 from the fresh current accepted trace, but avoid the
  full capture-size device loss by constraining speculative graph capture to
  the c1-relevant sizes.

Baseline:

- Accepted no-spec trace:
  `data/qwen36-oracle-accepted-current-20260615oraclefresh1.json`
- Current safe no-spec speed/quality baseline remains:
  `prefill-safe-int8-mixed-workspace-async-deep-gate`,
  `93.5505 tok/s`, full deep quality gate passed.

Candidate:

- N-gram k=1, small capture config:
  `{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1,2,4],"max_cudagraph_capture_size":4}`
- Artifact:
  `data/qwen36-oracle-ngram1-c1capture-20260615oraclec1cap2.json`
- Spec trace:
  `data/qwen36-oracle-ngram1-c1capture-20260615oraclec1cap2.jsonl`
- Gate:
  `data/qwen36-oracle-current-ngram1-c1capture-gate-summary-20260615oraclec1cap2.json`

Result:

- The server reached readiness. Small capture fixes the graph-capture
  stability failure seen by the full n-gram graph-size run.
- Exact parity failed for both oracle cases.
- Spec activity was real: `34` draft tokens, `31` accepted, `3` rejected,
  `91.18%` acceptance.
- `natural_latency_plan` first diverged at the verifier bonus after a
  full-accept row: accepted token `11436` (` hardware`) versus candidate token
  `321` (` and`) after `reliability gates,`.
- `repetitive_kernel_notes` stopped after only three tokens and emitted a
  ChatML/special-token-looking sequence. This is also rejected and should not
  be used for speed claims.

Conclusion:

- Oracle k=1 is still the highest-upside exact-output path to clear
  `100 tok/s`, but the current implementation is not parity safe.
- The first natural mismatch is not caused by the draft token itself: the draft
  comma was accepted correctly. The bad token is the target-owned verifier
  bonus, so the next fix must make the packed verifier bonus row use the same
  context, positions, KV, and GDN/Mamba state as the following normal no-spec
  decode row.
- Do not claim or benchmark speed for this path until exact parity passes.

### Accepted-Draft-Only State Diagnostic Rejection

Date: 2026-06-15

Purpose:

- Test whether excluding the verifier bonus from the hybrid/GDN accepted-token
  state copy repairs the fresh c1-capture oracle parity failure.

Candidate:

- Same n-gram k=1 small-capture identity as above, plus:
  `VLLM_XPU_GDN_SPEC_ACCEPTED_DRAFT_ONLY=1`
- Artifact:
  `data/qwen36-oracle-ngram1-c1capture-adraftonly-20260615adraft1.json`
- Spec trace:
  `data/qwen36-oracle-ngram1-c1capture-adraftonly-20260615adraft1.jsonl`
- Spec summary:
  `data/qwen36-oracle-ngram1-c1capture-adraftonly-spec-summary-20260615adraft1.json`
- Gate:
  `data/qwen36-oracle-current-ngram1-c1capture-adraftonly-gate-summary-20260615adraft1.json`

Result:

- Exact parity failed for both cases.
- Acceptance collapsed to `43/112` draft tokens, `38.39%`.
- `natural_latency_plan` diverged at output index `7`, where the accepted
  output continued `Focus ...` but the candidate entered a `<think>` section.
- `repetitive_kernel_notes` diverged at output index `3`, also entering a
  `<think>` section.
- Replay accounting had no mismatch, but request-id join was not useful for
  these artifacts. The result is still rejected because the candidate trace
  itself does not match the accepted outputs and acceptance is too low for a
  speed path.

Decision:

- Reject `VLLM_XPU_GDN_SPEC_ACCEPTED_DRAFT_ONLY=1` as a route to the current
  oracle k=1 parity fix. It is at best a later state-copy diagnostic, not the
  verifier-bonus repair.
- Next work item: add precise verifier-row tracing/join metadata and patch the
  packed verifier bonus transaction itself. Required traces are token IDs,
  positions, slot IDs, `num_computed_tokens`, `num_accepted_tokens`, logits
  indices/roles, and GDN state indices for each target/draft/bonus row.

### GMEM95 Promotion Gate Rejection

Date: 2026-06-15

Purpose:

- Test whether raising `GPU_MEMORY_UTILIZATION` from `0.90` to `0.95` improves
  the accepted safe baseline without changing model quality.

Baseline:

- Accepted control:
  `prefill-safe-int8-mixed-workspace-async-deep-gate`
- Speed: `93.5505 tok/s` corrected output mean.
- Full deep gate passed: metrics, JSON repeat 128, color repeat 256, and
  quality suite.

Candidate:

- Label:
  `prefill-safe-int8-mixed-workspace-async-gmem95-deep-gate`
- Same accepted identity except:
  `GPU_MEMORY_UTILIZATION=0.95`
- Artifacts:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-gmem95-deep-gate-p512o512-20260615gmem95deep1.json`
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-gmem95-deep-gate-json-repeat128-20260615gmem95deep1.json`
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-gmem95-deep-gate-20260615gmem95deep1.log`

Result:

- Corrected output mean: `93.1948 tok/s`.
- Decode mean: `10.7307 ms/token`.
- TTFT mean: `189.3772 ms`.
- JSON repeat 128 passed.
- Color and quality suite were intentionally not run because the candidate
  missed the speed gate versus the accepted baseline.

Decision:

- Reject `GPU_MEMORY_UTILIZATION=0.95` for the current safe lane. It is slower
  than the accepted `0.90` baseline and has no reason to spend deeper quality
  time.

### Oracle k=1 Current Small-Capture Identity Correction

Date: 2026-06-15

Purpose:

- Continue the no-quality-loss speculative path without repeating the earlier
  benchmark-identity mistake.

Correct comparison identity:

- The exact no-spec control for current small-capture oracle work is:
  `COMPILE_CONFIG={"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1,2,4],"max_cudagraph_capture_size":4}`
  with `VLLM_EXTRA_ARGS=--no-async-scheduling` and no speculative config.
- Artifact:
  `data/qwen36-nospec-smallcap-current-candidate-20260615nospecsmall1.json`
- This control is not comparable to the older `graphref2` trace because
  `graphref2` used a different capture identity. Do not use `graphref2` as the
  oracle for current small-capture spec rows.

Current oracle k=1 small-capture result:

- Candidate:
  `data/qwen36-oracle-k1-current-candidate-20260615speccurrent4b.json`
- Spec trace:
  `data/qwen36-oracle-k1-current-20260615speccurrent4b-spec.jsonl`
- Spec summary:
  `data/qwen36-oracle-k1-current-speccurrent4b-spec-summary-20260615.json`
- Result: rejected for exact parity.
- Natural prompt first divergence is output index `17`: no-spec emits
  `11436` (` hardware`) after `reliability gates,`, while oracle k=1 emits
  `321` (` and`).
- Spec trace confirms the draft comma was accepted correctly; the bad token is
  the target-owned verifier bonus row emitted in the same forward. This remains
  the active no-quality-loss speculative blocker.

Decision:

- Do not claim speed for oracle k=1 until the packed verifier bonus row is
  token-identical to the next ordinary no-spec decode row under the exact same
  small-capture/no-async identity.
- The next diagnostic needs focused no-spec and spec microscope rows around
  output index `17`, including token IDs, positions, slot IDs,
  `num_tokens_no_spec`, `num_computed_tokens`, logits top-k, and GDN state
  indices.

### Oracle k=1 Serial-Recurrent Current Probe Rejection

Date: 2026-06-15

Purpose:

- Test whether `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1` fixes the current
  small-capture oracle k=1 verifier bonus mismatch.

Candidate:

- Same small-capture oracle k=1 identity as above, plus:
  `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`
- Candidate:
  `data/qwen36-oracle-k1-current-candidate-20260615serialcurrent1.json`
- Spec trace:
  `data/qwen36-oracle-k1-current-20260615serialcurrent1-spec.jsonl`
- Spec summary:
  `data/qwen36-oracle-k1-current-serialcurrent1-spec-summary-20260615.json`

Result:

- Exact parity still failed.
- Natural prompt first divergence remains output index `17`: candidate emits
  `321` (` and`) where no-spec emits `11436` (` hardware`).
- Repetitive prompt also diverged at output index `10`.
- Runtime was visibly much slower, around only a few generation tok/s while the
  endpoint was running.
- Acceptance was high (`98/105`, `93.33%`), but high acceptance is useless
  until token parity passes.

Decision:

- Reject serial-recurrent GDN as both a parity fix and a performance candidate.
- Keep serial modes only as local diagnostics if they reveal state accounting;
  do not spend endpoint speed-gate time on them.

### Oracle k=1 Small-Capture Microscope and GDN Row Trace

Date: 2026-06-16

Purpose:

- Pin the current oracle k=1 parity failure to exact verifier rows before
  attempting another speed claim.

Clean no-spec microscope:

- Candidate:
  `data/qwen36-nospec-smallcap-micro-candidate-20260616micro1.json`
- Replay trace:
  `data/qwen36-nospec-smallcap-micro-20260616micro1-replay-r0.jsonl`
- Identity:
  `COMPILE_CONFIG={"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1,2,4],"max_cudagraph_capture_size":4}`,
  no speculative config, `VLLM_EXTRA_ARGS=--no-async-scheduling`.

Clean oracle k=1 microscope:

- Candidate:
  `data/qwen36-oracle-k1-smallcap-micro-candidate-20260616micro1.json`
- Replay trace:
  `data/qwen36-oracle-k1-smallcap-micro-20260616micro1-replay-r0.jsonl`
- Spec trace:
  `data/qwen36-oracle-k1-smallcap-micro-20260616micro1-spec.jsonl`
- Spec summary:
  `data/qwen36-oracle-k1-smallcap-micro-spec-summary-20260616micro1.json`

Finding:

- Exact parity still fails.
- Natural first divergence is output index `17`: no-spec emits `11436`
  (` hardware`), oracle k=1 emits `321` (` and`).
- At the failing natural row, oracle target row has `input_id=33389`,
  `position=517`, `draft_token_id=11`, and correctly accepts token `11`.
- The immediately packed oracle bonus row has `input_id=11`, `position=518`,
  `num_tokens_no_spec_cpu=518`, `num_computed_tokens_cpu=517`,
  `num_accepted_tokens_cpu=2`, and top-1 `321`.
- The matching no-spec row has `input_id=11`, `position=518`,
  `num_computed_tokens_cpu=518`, and top-1 `11436`.
- This is not sampler randomness. The target row is correct; the packed bonus
  row is using a different effective recurrent/context state than the next
  ordinary decode row.

GDN row trace:

- Candidate:
  `data/qwen36-oracle-k1-smallcap-gdntrace-candidate-20260616gdn1.json`
- GDN row trace:
  `data/qwen36-oracle-k1-smallcap-gdntrace-20260616gdn1-gdn-r0.jsonl`
- Replay trace:
  `data/qwen36-oracle-k1-smallcap-gdntrace-20260616gdn1-replay-r0.jsonl`
- Result reproduced the same natural first divergence at output index `17`.
- Layer-0 GDN trace confirms the spec path is consistently running two-token
  target+bonus rows with `num_accepted_tokens=[2]`, `stateidx=[1,2]`, and
  `qsl=[0,2]` around the failing window. More precise no-spec-vs-spec
  per-layer alignment is still needed before a kernel-level fix.

Decision:

- Continue treating oracle k=1 as the highest-upside no-quality-loss path, but
  do not benchmark it for speed until token parity passes.
- The next verifier repair should compare no-spec and spec GDN rows for the
  same layer and request window, then patch the packed target+bonus state
  transaction. Reducing the previous accepted count is already rejected and
  does not address the current-row bonus.

### Corrected Serial Conv/Recurrent Probe Rejection

Date: 2026-06-16

Purpose:

- Repair and test the existing serial GDN diagnostic path. The old serial path
  started `spec_pos==0` from `spec_state_indices[:,0]`; for a continuing
  request the real running state is `spec_state_indices[:,num_accepted-1]`.

Patch:

- `vllm/model_executor/layers/mamba/gdn_linear_attn.py`
- Under `VLLM_XPU_GDN_SERIAL_SPEC_CONV=1`, copy the previously accepted
  convolution state slot into the first target slot before serial target/bonus
  conv updates.
- Under `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`, copy the previously accepted
  recurrent state slot into the first target slot before serial target/bonus
  recurrent updates.
- `py_compile` passed.

Candidate:

- Same small-capture oracle k=1 identity plus
  `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`,
  `VLLM_XPU_GDN_SERIAL_SPEC_CONV=1`, and
  `VLLM_XPU_GDN_SERIAL_SPEC_PACKED_DECODE=1`.
- Candidate:
  `data/qwen36-oracle-k1-serialfixed-smallcap-candidate-20260616fix1.json`
- Replay trace:
  `data/qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-replay-r0.jsonl`
- Spec trace:
  `data/qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-spec.jsonl`
- Spec summary:
  `data/qwen36-oracle-k1-serialfixed-smallcap-spec-summary-20260616fix1.json`

Result:

- Exact parity still failed.
- Natural first divergence remains output index `17`: no-spec emits `11436`,
  candidate emits `321`.
- Repetitive first divergence moved later, from output index `12` in the
  unpatched small-capture oracle to output index `19`; this proves the patched
  serial state-start matters, but it is not sufficient.
- Acceptance was `93.75%`, but runtime was extremely slow (`~2` generation
  tok/s in server logs), so this is not a performance candidate.

Decision:

- Keep the serial-start-state patch only as diagnostic code behind serial env
  flags. Do not promote it and do not use it for throughput claims.
- Next speculation repair should not be another broad serial flag trial. It
  needs a row-aligned no-spec/spec trace at the first divergent layer or a
  purpose-built verifier-bucket path that recomputes the bonus row with the
  exact no-spec transaction.

### Oracle k2 Replacement Suppression Rejection

Date: 2026-06-16

Purpose:

- Test whether exact oracle k1 draft-only parity can be extended to k2 by
  suppressing target-owned verifier replacement tokens after a reject.

Artifacts:

- k2 no-skip candidate:
  `data/qwen36-oracle-k2-draftsonly-noskip-candidate-20260616m4.json`
- k2 no-skip spec trace:
  `data/qwen36-oracle-k2-draftsonly-noskip-20260616m4-spec.jsonl`
- k2 replacement-suppression candidate:
  `data/qwen36-oracle-k2-draftsonly-suppressrepl-candidate-20260616m7.json`
- k2 replacement-suppression trace:
  `data/qwen36-oracle-k2-draftsonly-suppressrepl-20260616m7-spec.jsonl`
- k2 rollback-adjust trace:
  `data/qwen36-oracle-k2-draftsonly-suppressrepl2-20260616m8-spec.jsonl`

Result:

- k2 without replacement suppression is not token-identical. The natural probe
  first diverged when the spec path emitted token `321` where the no-spec
  baseline emitted `11436`.
- Suppressing the replacement token prevented the immediate bad emission, but
  the request later stalled after a rejected row because the scheduler had
  `num_tokens == num_computed_tokens` and no visible output placeholder to
  force the next one-token recovery step.
- Rollback adjustment avoided moving the committed-token cursor one token too
  far backward, but did not create a complete recovery transaction.

Decision:

- k2/k4 speculation remains blocked. Do not benchmark speculative speed until
  the verifier replacement/bonus transaction is token-identical against the
  current no-spec baseline.
- The next speculative repair should be a proper recovery placeholder or
  verifier-bucket path, not another throughput run.

### Dirty Block-Table Range-Copy Smoke Rejection

Date: 2026-06-16

Purpose:

- Repair the opt-in dirty block-table metadata-copy experiment after the
  previous current-fast-identity run device-lost in
  `block_table.copy_to_gpu(num_reqs)`.
- The new diagnostic path removes the full-copy fallback when all active rows
  are dirty; it always copies contiguous dirty row ranges and skips unchanged
  decode steps.

Patch:

- `vllm/v1/worker/block_table.py`
- `scripts/check-qwen36-block-table-dirty-commit.py`

Local validation:

- `py_compile` passed for both files.
- Simulation artifact:
  `data/qwen36-block-table-dirty-rangecopy-check-20260616a.json`

Endpoint smoke identity:

- Current fast base: PIECEWISE forced/noop graph, prefill-only GDN native
  fallback, prefill recurrent fallback, prefill graph replay disabled, top-k
  sampler fallback, INT8 mixed MoE workspace, async scheduling, and
  `GPU_MEMORY_UTILIZATION=0.90`.
- Added:
  `VLLM_XPU_METADATA_COPY_ALLOW=1`,
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT=1`,
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY=128`.

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-dirtyrange-smoke-summary-20260616dirtyrange1.json`
- Metrics:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-dirtyrange-smoke-p512o512-20260616dirtyrange1.json`
- JSON canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-dirtyrange-smoke-json-repeat16-20260616dirtyrange1.json`
- Color canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-dirtyrange-smoke-color-repeat16-20260616dirtyrange1.json`

Result:

- The repaired path no longer device-lost on the first metrics request.
- One-repeat corrected decode rate: `94.6513 tok/s`
  (`10.5647 ms/token`).
- Color canary passed `16/16`.
- JSON canary failed at repeat `3/16`: emitted
  `{"answer":"12","unit":"widgets"}` instead of the expected answer.

Decision:

- Rejected as a no-quality-loss speed candidate.
- Keep the range-copy change default-off as diagnostic infrastructure only.
  It fixed the prior crash mode but did not pass even the short correctness
  smoke, so it must not be counted toward the >100 tok/s goal.

### Oracle Speculative Repair Follow-Up Rejections

Date: 2026-06-16

Purpose:

- Record the later oracle k1/k2 repair attempts after the small-capture
  microscope proved packed target+bonus rows do not share the same effective
  recurrent/GDN state as ordinary no-spec decode rows.
- Prevent future speed comparisons from treating speculative acceptance as a
  quality-cleared result.

Artifacts:

- m18 k2 recompute-row/full-bonus preempt:
  `data/qwen36-oracle-k2-recompute-row-preempt-candidate-20260616m18.json`
  and `/tmp/qwen36-oracle-k2-recompute-row-preempt-20260616m18-debug-spec.jsonl`
- m19 k2 bonus-logit trace:
  `data/qwen36-oracle-k2-bonuslog-candidate-20260616m19.json`,
  `data/qwen36-oracle-k2-bonuslog-20260616m19-bonus-logits.jsonl`, and
  `data/qwen36-oracle-k2-bonuslog-20260616m19-spec.jsonl`
- m20 k2 margin-bonus with old cache filtering:
  `data/qwen36-oracle-k2-marginbonus-20260616m20-server.log`
- m21 k2 margin-bonus after cache-filter repair:
  `data/qwen36-oracle-k2-marginbonus-candidate-20260616m21.json` and
  `data/qwen36-oracle-k2-marginbonus-20260616m21-spec.jsonl`
- m23 k2 margin-bonus plus suppressed-bonus preempt:
  `data/qwen36-oracle-k2-marginbonus-preempt-candidate-20260616m23.json`
  and `data/qwen36-oracle-k2-marginbonus-preempt-20260616m23-spec.jsonl`
- m24 k2 margin-bonus plus low-margin verifier-row recompute:
  `data/qwen36-oracle-k2-marginbonus-recompute-row-candidate-20260616m24.json`
  and `data/qwen36-oracle-k2-marginbonus-recompute-row-20260616m24-spec.jsonl`
- m25 k2 GDN accepted-draft-only with mask-aware accounting:
  `data/qwen36-oracle-k2-gdnaccepted-marginbonus-preempt-candidate-20260616m25.json`
  and
  `data/qwen36-oracle-k2-gdnaccepted-marginbonus-preempt-20260616m25-spec.jsonl`
- m26 clean oracle k1:
  `data/qwen36-oracle-k1-clean-candidate-20260616m26.json` and
  `data/qwen36-oracle-k1-clean-20260616m26-spec.jsonl`

Findings:

- m19 found a real bad k2 verifier bonus row:
  scheduled `[22188, 13]`, bonus token `271`, top candidates
  `[271, 15153, 198, 78503, 248044]`, and top-1/top-2 margin about `1.25`.
  Correct full-accept bonus rows in the same trace had much larger margins.
- m20 exposed a bug in the cache-filter experiment: the worker-side full-bonus
  cache filter was global whenever
  `VLLM_XPU_SPEC_DECODE_FILTER_SUPPRESSED_BONUS_CACHE=1`, so it stripped even
  correct high-margin bonuses. The filter now only applies to actual suppressed
  bonus rows unless the explicit full-bonus disable flag is set.
- m21 suppressed the immediate low-margin bad bonus and kept the natural prompt
  exact, but the repetitive prompt still diverged at output index `12` because
  there was no recovery/preempt transaction.
- m23 added preempt after a suppressed low-margin bonus. It fixed the immediate
  bad emission and recovered the next visible token, but the repetitive prompt
  still drifted later at output index `19`.
- m24 recomputed the low-margin verifier row and still drifted later at output
  index `19`; this makes the replay/preempt transaction itself suspect.
- m25's `VLLM_XPU_GDN_SPEC_ACCEPTED_DRAFT_ONLY=1` path remains rejected even
  after mask-aware accounting. It changes otherwise high-confidence rows and
  fails earlier than the base speculative path.
- m26 clean oracle k1 fails in the current identity. Natural drift starts at
  output index `17`; the oracle row that should verify draft token `11436`
  instead verifies/generates token `321`. Repetitive drift starts at output
  index `12`.

Decision:

- Do not run or report speculative throughput as a candidate speed win until a
  k1 oracle path is token-identical against the current no-spec baseline.
- The speculative branch remains useful only for diagnostics. The next repair,
  if resumed, must trace no-spec and spec hidden/GDN state at the first
  divergent verifier row before sampler output, not add more preempt or margin
  heuristics.
- For the near-term >100 tok/s no-quality-loss goal, pivot back to exact
  non-spec MoE work. Current decisive timing still puts MoE at roughly
  `9 ms` of the `10.7 ms/token` base, while collectives are small; an exact
  persistent/resident W8A8 MoE layerlet is the best remaining path to stack a
  real decode-rate improvement.

### Disabled Timing Context Fast-Path Rejection

Date: 2026-06-16

Purpose:

- Test whether the dense disabled `timed_region(...)` / `allreduce_label(...)`
  wrappers in the Qwen decode hot path were adding measurable Python overhead.
- This was an exact non-math candidate: it does not alter weights, kernels,
  graph flags, sampling, or model tensors.

Patch:

- `vllm/utils/xpu_decode_timing.py`
- Initial attempt returned a singleton `_NoopContext` whenever timing was
  disabled. That failed before readiness because Torch Dynamo does not support
  entering a user-defined context manager in compiled model code.
- Final patch keeps the original generator-style disabled context by default
  and exposes the singleton path only behind
  `VLLM_XPU_FAST_DISABLED_TIMING_CONTEXT=1`.

Validation:

- `py_compile` passed.
- A tiny `torch.compile(..., backend="eager")` check with `timed_region(...)`
  passed after restoring generator behavior for compiled regions.

Artifacts:

- First failed startup:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-noop-timing-smoke-20260616tnoop1.log`
- Second endpoint smoke:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-noop-timing-smoke2-summary-20260616tnoop2.json`
  and associated metrics/JSON/color artifacts.

Result:

- Startup-safe opt-in smoke reached `94.1988 tok/s` corrected on one
  p512/o512 repeat (`10.6158 ms/token`).
- JSON canary failed at repeat `3/32`.
- Color canary passed `32/32`.

Decision:

- Rejected as a no-quality-loss optimization.
- Keep the singleton no-op context default-off only as a diagnostic switch.
- Do not include it in future accepted baseline comparisons unless the flag is
  explicitly listed in the run identity and canaries pass.

### Shared + Routed In-Place Add Rejection

Date: 2026-06-16

Purpose:

- Test a narrower alternative to the rejected
  `VLLM_XPU_MOE_SHARED_ADD_ALLREDUCE_CUSTOM_OP=1` path.
- Instead of replacing add+all-reduce with a custom op, this only mutates the
  routed MoE output with `fused_output.add_(shared_output)` and leaves the
  existing all-reduce path unchanged.

Patch:

- `vllm/model_executor/layers/fused_moe/runner/moe_runner.py`
- New opt-in flag: `VLLM_XPU_MOE_SHARED_ADD_INPLACE=1`
- Default remains off.

Validation:

- `py_compile` passed.

Artifacts:

- Summary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-add-inplace-smoke-summary-20260616addinplace1.json`
- Metrics:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-add-inplace-smoke-p512o512-20260616addinplace1.json`
- JSON canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-add-inplace-smoke-json-repeat32-20260616addinplace1.json`
- Color canary:
  `data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-shared-add-inplace-smoke-color-repeat32-20260616addinplace1.json`

Result:

- Corrected one-repeat decode rate: `93.2107 tok/s`
  (`10.7292 ms/token`), slower than the accepted `93.5505 tok/s` deep-gate
  base.
- JSON canary failed at repeat `3/32`.
- Color canary passed `32/32`.

Decision:

- Rejected as both slower and not quality-clean.
- Keep default off only as a diagnostic. Do not stack it into future
  candidates.
