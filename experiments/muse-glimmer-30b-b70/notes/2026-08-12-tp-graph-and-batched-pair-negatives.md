# TP graph capture and batched-pair negatives

Date: 2026-08-12

## Decision

Reject cached whole-subgraph and island SYCL graphs for the current exact
oneDNN path. Reject the proposed one-call gate/up batch at the current backend
layer because the relevant projections do not coexist in one TP4 simple-backend
subgraph. Preserve both source prototypes and correct the earlier claim that
shared BF16 activation conversion contributed a measured win.

No drafter training or weight changes occurred.

## Cached command graph results

Source commit `fb10f473b` re-applied the default-off persistent TP graph cache.
With oneDNN flash attention disabled, whole-subgraph recording still failed on
the first `MUL_MAT`: oneDNN returns an event created outside the recording
graph. This proves the incompatibility is the oneDNN projection path, not only
oneDNN SDPA.

A graph-island prototype recorded custom-kernel stretches and left oneDNN
matmuls eager. It is preserved as source commit `40979b59c` and immediately
reverted by `a5e66f0b3`. After a cache-key collision fix it ran end to end, but
measured only 10.578 / 44.731 / 70.259 t/s. Prose and code hashes changed to
`a71ceb1ecf6a3e43` and `b4a2bda611510441`; only JSON retained
`4f813a9706abc163`. Cached replay is therefore both slower and unsafe for the
changing argument state in these graph objects.

Evidence:

- config: `sweeps/20260812-native-fa-graph-smoke.json`;
- result: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/native-fa-graph-smoke-20260812.jsonl`;
- result SHA-256: `5946738bf7cb73e96b8b7f6a367eff248d3e60f3b7c568f17a56fa49d6b0442f`.

## Gate/up batch feasibility correction

The oneDNN audit proposed a zero-copy 3D batch=2 GEMM for gate and up. A guarded
prototype was built and an adjacent suite initially appeared neutral:

| Arm | Prose | Code | JSON | Mean |
| --- | ---: | ---: | ---: | ---: |
| exact-stack control | 40.269 | 62.509 | 69.658 | 57.479 |
| guarded batch flag | 40.357 | 62.419 | 69.691 | 57.489 |

Hashes and accepted counts matched, but the required execution marker was
absent. The guarded path had correctly fallen back, so this table is not a
batch-kernel performance result.

A subsequent runtime dump exposed the structural cause. The TP meta backend
builds per-device subgraphs around tensor-parallel reduction boundaries. The
attention graph already shows each projection separated by intervening ops;
the FFN gate and up projections are separate meta subgraphs. The existing
`GGML_SYCL_BF16_PAIR` recognizer only examines `cgraph->nodes[i + 1]`, so it has
zero TP4 hits. This also invalidates the earlier +2.10% attribution to shared
activation conversion; that delta was run noise.

Evidence:

- guarded config: `sweeps/20260812-bf16-pair-batch-ab.json`;
- result: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/bf16-pair-batch-ab-20260812.jsonl`;
- result SHA-256: `978b0369a00082e1eb92d8634413ad0429b5c7c262fe1497f01f927ab30e9da9`.

## Implication

Cross-projection batching or shared conversion must be implemented above the
simple SYCL subgraph boundary (in the TP meta scheduler/graph construction),
where both independent projections and their reductions are visible. A local
SYCL adjacent-node fusion cannot reach them. Even a successful gate/up batch
would remove only 52 of 716 batch-16 target GEMMs per pass, so it is supporting
work rather than a standalone route to 100 t/s.
