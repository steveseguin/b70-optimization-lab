# MiniMax M2.7 Post-89 tok/s Plan

Date: 2026-05-19

## Current Promoted Baseline

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70, TP4, vLLM/XPU
- Current promoted result: `89.314195` output tok/s and `119.085594` total tok/s at p512/n1536, ctx2048, batch 1.
- Quality baseline: exact raw145 n64/n256 token hashes, semantic suite, 16-repeat arithmetic, and extended sixpack all match promoted references.
- LocalMaxxing result: `cmpct6t4m007fnw01yjdtlcs4`

## Promotion Policy

Only promote or submit a new result when all of these are true:

- Exact-token and semantic quality gates pass.
- The run is repeatable across at least four benchmark repeats.
- The mean output tok/s is above `89.314195` by more than normal run noise.
- No sampling, routing, quantization, or precision shortcut changes quality semantics.

Negative, quality-failed, or merely noisy results stay local/GitHub-only.

## Immediate Candidates

1. Current-high stack plus `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`.
   - Rationale: communication-only knob, no model math change.
   - Risk: previous CCL topology override screens were negative on older stacks.
   - Status: rejected. Strict quality passed, but mean output fell to `89.037858` tok/s and oneCCL/PMI teardown noise appeared. Keep this env unset.

2. Current-high stack plus `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1`.
   - Rationale: avoid redundant Python/framework tensor copies when the MoE input and router logits are already contiguous.
   - Risk: an older related screen was slightly negative, but it was not the exact current full-forward stack.
   - Status: rejected. Strict quality passed, but mean output was `89.141961` tok/s and shutdown logs showed intermittent `Bad address` noise.

3. Attention `o_proj` custom-op boundary.
   - Rationale: rank-0 sync timing showed FP16 hidden-state allreduce/projection boundaries as the visible synchronized cost.
   - Status: rejected. Strict quality passed, but mean output was `89.100464` tok/s, `0.24%` below the promoted mean. Broad Python custom-op wrapping alone is not enough.

4. Site-labeled allreduce timing.
   - Rationale: the previous timing run grouped collectives only by shape and dtype. The next run should label Q/K variance, attention `o_proj`, MoE output, and any delayed/final hidden-state allreduces so the next fusion target is selected by evidence.
   - Status: completed. MoE output labels were captured, while attention/RowParallel labels did not survive the compiled graph path. The remaining unlabeled FP16 hidden-state shapes/counts match the attention `o_proj` collective family. The largest visible buckets were Q/K variance FP32 `(1, 2)`, attention-shaped FP16 hidden `(1, 3072)`/`(2, 3072)`, and MoE-output FP16 hidden `(1, 3072)`/`(2, 3072)`.

5. MoE output direct-allreduce inside the custom-op boundary.
   - Rationale: MoE-output FP16 hidden-state allreduce remained visible in the site-labeled timing run.
   - Status: rejected. Exact raw145 and semantic quality passed, arithmetic n64/r8 passed, and extended sixpack passed, but four p512/n1536 repeats averaged `88.843823` output tok/s / `118.458431` total tok/s. This is `0.470372` output tok/s below the current promoted mean. The active runtime hook was reverted and the result was not submitted to LocalMaxxing.

6. Q/K RMS variance allreduce+scale custom op.
   - Rationale: the site-labeled timing run showed the FP32 `(1, 2)` Q/K variance collective as the largest visible synchronized bucket. This candidate preserved the exact promoted ordering by performing allreduce first and then multiplying by `1 / tp_world` inside a single custom-op boundary.
   - Status: rejected. Exact raw145 n64/n256, semantic suite, 16-repeat arithmetic, and extended sixpack all passed, but four p512/n1536 repeats averaged `88.558751` output tok/s / `118.078334` total tok/s. This is `0.755445` output tok/s below the current promoted mean. It also produced intermittent `Bad address (src/pipe.cpp:367)` shutdown noise. The active runtime hook was reverted and the result was not submitted to LocalMaxxing.

7. Targeted RowParallel attention `o_proj` in-place allreduce.
   - Rationale: the remaining visible FP16 hidden-state allreduce family matches attention `o_proj`, and the previous broad attention custom-op wrapper was quality-safe but slower. This tried a narrower math-preserving in-place path only for `*.o_proj` RowParallelLinear outputs on XPU FP16/BF16 tensors up to 6144 elements.
   - Status: rejected. Exact raw145 n64/n256, semantic suite, 16-repeat arithmetic, and extended sixpack all passed, but four p512/n1536 repeats averaged `88.852415` output tok/s / `118.469886` total tok/s. This is `0.461781` output tok/s below the current promoted mean. It also produced intermittent `Bad address (src/pipe.cpp:367)` shutdown noise during quality teardown. The active runtime hook was reverted and the result was not submitted to LocalMaxxing.

8. Size-ranged oneCCL `CCL_ALLREDUCE` algorithm selection.
   - Rationale: Intel oneCCL supports size-ranged algorithm selection, so this screened whether tiny TP collectives could benefit from `recursive_doubling` without changing model math.
   - Candidate: `CCL_ALLREDUCE='recursive_doubling:0-8192;ring:8193-max'` on top of the current promoted graph-enabled stack.
   - Status: rejected before quality. oneCCL accepted the env var, but XPU graph capture failed with `sched algorithms do not support sycl_graph recording, please use sycl_algorithms`. The strict runner reported `quality_failed_raw145_n64`, but no tokens were generated; classify this as runtime/graph incompatibility, not a quality regression. Keep `CCL_ALLREDUCE` unset for promoted graph-enabled runs unless a future oneCCL/XPU stack provides a graph-compatible SYCL algorithm path.

9. oneCCL topo copy-engine pipeline toggles.
   - Rationale: keep the default graph-compatible `topo` allreduce path, but test whether disabling reduce-scatter/allgatherv monolithic pipeline kernels changes copy-engine overlap or slow-tail behavior without changing model math.
   - Candidate: unset `CCL_ALLREDUCE`, set `CCL_REDUCE_SCATTER_MONOLITHIC_PIPELINE_KERNEL=0`, and set `CCL_ALLGATHERV_MONOLITHIC_PIPELINE_KERNEL=0`.
   - Status: rejected. Exact raw145 n64/n256, semantic suite, 16-repeat arithmetic, and extended sixpack all passed, but four p512/n1536 repeats averaged `88.749571` output tok/s / `118.332762` total tok/s versus the promoted `89.314195` / `119.085594`. One repeat fell to `87.099748` output tok/s, so this was both slower and noisier. Keep these oneCCL topo pipeline envs unset for promoted graph-enabled runs.

## Source-Level Work Queue

- Audit remaining decode-time CPU/framework boundaries in `minimax_m2.py`, `moe_wna16.py`, and `xpu_communicator.py`.
- Prioritize a lower-level fusion or scheduling candidate around one of the three proven collective families: Q/K variance FP32, attention `o_proj` FP16 hidden-state allreduce, or MoE-output FP16 hidden-state allreduce.
- Do not spend more time on broad Python custom-op wrappers unless the wrapper changes a lower-level compiled/collective boundary.
- Do not force non-`topo` `CCL_ALLREDUCE` in graph-enabled runs; the scheduled algorithm path is not compatible with current `sycl_graph` capture.
- Prefer math-preserving changes that remove import/call/copy overhead or custom-op graph breaks.
- Preserve exact operation ordering around residual add, RMSNorm, router logits, expert selection, and final allreduce unless a canary explicitly proves equivalence.
- For any new patch, save a patch note and strict run summary before considering LocalMaxxing.

## Current Next Step

Implement the next math-preserving candidate against a real collective boundary. Preferred order:

1. A narrow Q/K variance collective path that reduces the `(1, 2)` FP32 dependency without changing the exact Q/K RMSNorm formula.
2. A lower-level attention `o_proj` scheduling/fusion candidate, since Python custom-op wrapping was quality-safe but slower.
3. A true MoE-output epilogue/allreduce fusion candidate, since direct Python-level allreduce replacement was quality-safe but slower.

The simple Q/K custom-op boundary and the targeted RowParallel `o_proj` in-place hook did not help, so future work needs to be lower-level than Python conditional/custom-op wrapping. The next useful candidates should either fuse a proven collective with its adjacent kernel at the backend level, or reduce CPU/framework scheduling boundaries without adding Python branches to the hot path.

The size-ranged `CCL_ALLREDUCE` screen also failed before quality under graph capture. That removes high-level oneCCL algorithm selection from the current near-term path; the remaining credible route to another large gain is lower-level XPU/SYCL fusion or graph scheduling around the known collective families while preserving the default graph-compatible communication backend.

The oneCCL topo copy-engine toggles were quality-clean but slower. High-level communication environment changes have now produced regressions or graph incompatibilities; the next pass should move back into source-level scheduling/fusion where the candidate can remove a real hot-path boundary instead of changing oneCCL's global heuristics.
