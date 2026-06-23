# Qwen3.6 35B Quark INT8 on B70

This folder is the durable result packet for the Qwen3.6 35B A3B Quark W8A8
INT8 lane on Intel Arc Pro B70. It exists to make the final state easy to
reference before moving effort to another model.

## Bottom Line

The Qwen3.6 35B 4x B70 lane is exhausted for now. The best strict-valid TP4
result is `93.55 tok/s` corrected output on the PIECEWISE forced-comm graph
baseline. A legacy LocalMaxxing-approved run reached `99.43 tok/s`, but newer
deep gates are stricter and should be used for current claims.

No attempted speculative decode path produced a valid `>150 tok/s` result for
this model. The fastest numbers above the baseline were invalid, synthetic, or
crashed before validity gates.

## Start Here

- [4x B70 results](4x-b70-results.md): valid, legacy, smoke, invalid, and
  ceiling results for TP4.
- [2x B70 reference](2x-b70-reference.md): TP2 numbers and caveats.
- [Validity gates](validity-gates.md): what counts as a real result.
- [Reproduce](reproduce.md): commands for the best valid 4x and 2x references.
- [Bugs and failed paths](bugs-failed-paths.md): MTP, ReplaySSM, DFlash, graph,
  and metadata shortcuts.
- [Intel/vLLM suggestions](intel-vllm-suggestions.md): actionable upstream and
  platform feedback.
- [Next model carryover](next-model-carryover.md): what to reuse when switching
  away from this model.

## Best Results Summary

| Scope | Result | Validity | Primary artifact |
| --- | ---: | --- | --- |
| 4x strict-valid current base | `93.55 tok/s` | JSON `128/128`, color `256/256`, quality pass | [`deep-gate-summary`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-summary-20260615a13deep2.json) |
| 4x legacy public approved | `99.43 tok/s` | LocalMaxxing approved, older gates | [`localmaxxing snapshot`](../../data/localmaxxing-qwen36-35b-quark-int8-exacthf-20260612ak.json) |
| 2x reference smoke | `85.87 tok/s` | JSON `16/16`, color `16/16`, quality skipped | [`tp2-smoke-summary`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-tp2-smoke-summary-20260615tp2safe1.json) |
| 2x older raw reference | `91.59 tok/s` | smoke/reference only, not promoted | [`tp2-latency-truth`](../../data/qwen36-quark-int8-tp2-latency-truth-p512o256-metrics-20260612bx.json) |
| Fastest raw artifact | `198.95 tok/s` | invalid/reference only | [`ngram5 raw`](../../data/qwen36-ngram5-current-storeguard-random-p512o512-r4-20260615.json) |
| Fastest synthetic ceiling | `181.91 tok/s` | canaries skipped, synthetic accept | [`eagle2 ceiling summary`](../../data/qwen36-ablation-eagle2-tokenheavy-synthaccept6-piecewise-tp2-k5-ceiling-20260618h-summary-20260618h02.json) |
| Fastest MTP-ish invalid | `107.77 tok/s` | JSON and color failed immediately | [`mtp parity fix v2`](../../data/qwen36-ablation-tp4-mtp-k1-parity-fix-v2-summary-20260620061440.json) |

## Status Recommendation

Stop spending ad hoc benchmark time on Qwen3.6 35B Quark INT8 unless the task is
one of these controlled follow-ups:

- upstream XPU kernel/runtime bakeoff against the strict `93.55 tok/s` identity;
- deep graph-compatible speculative-state engineering, with full endpoint gates;
- extracting reusable DFlash/ReplaySSM lessons for a different model.

For new optimization work, switch to another model. Prior successful lanes
include Qwen 27B and MiniMax M2.7; Gemma 4 12B also has strong TP4 production
material. See [next model carryover](next-model-carryover.md).
