# Functional budget-15 DDTree: exact-stack century lane rejected

Date: 2026-08-13

## Result

The first integrated budget-15 DDTree implementation did not reach the honest
four-GPU target. The canonical 256-token suite measured:

| class | tok/s | accepted | drafted | hash |
|---|---:|---:|---:|---|
| prose | 65.349 | 188 | 958 | `914f754747d0edaa` |
| code | 93.612 | 207 | 676 | `b4a2bda611510441` |
| JSON | 106.993 | 213 | 594 | `4f813a9706abc163` |

Arithmetic mean: **88.651 tok/s**.

The tree executed (first-hit log: `verified=16 committed=16`) and preserved
the prose/JSON identities. Code changed from the retained speculative identity
`cf2b2c4fd9e36fe5` to the target no-spec identity `b4a2bda611510441`, so it also
fails the campaign's canonical three-class identity gate.

The realized target-round counts were approximately `256-accepted` =
68/49/43, close to the offline 66/48/42 coverage prediction. The miss was
primarily cost, not coverage: request-derived round times were roughly
57.62/55.82/55.63 ms, several milliseconds above the approximately 51--52 ms
pre-integration model. The synchronized feature profile also rose to
`enc=3.95 ms/round` by 128 calls. The functional transaction's sequence
fork/promotion, sampler, indexed feature processing, and multi-sequence graph
cost were materially underpriced by the shadow/offline model.

The 64-token smoke had passed all three canonical smoke hashes and measured
70.861/122.767/183.032 tok/s (125.553 mean), demonstrating why a full 256-token
gate is mandatory.

## Source and evidence

- functional source: `948cf7860`;
- canonical-admission fix: `c0579c7d6`;
- reverts: `99484946a`, `350beb175`;
- full config: `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-ddtree-functional-full256.json`;
- smoke config: `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-ddtree-functional-smoke64.json`;
- full JSONL: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-ddtree-functional-full256-20260813.jsonl`, SHA-256 `c7fb9af140797384c74350c16233808114a42fa879101a28e266aff5b4201a67`;
- full log: `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-dflash-ddtree-functional-full256-20260813-ddtree-budget15.log`, SHA-256 `c8c3d4ab632e4ee3ada8b010a4af5cc40cc6e4353e8074ba2676ada014e7f879`.

Known pre-promotion limitations also remain: history-dependent sampler
penalties were not supported, and EOG/stop-string mid-tree needed explicit
transaction truncation.

## Decision

Preserve and revert. Budget-15 DDTree is not the >100 route on this exact stack
without a new multi-millisecond verifier/runtime saving, and its current code
identity is not acceptable.

