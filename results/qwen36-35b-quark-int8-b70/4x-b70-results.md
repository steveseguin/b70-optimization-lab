# 4x B70 Results

Model identity for all results in this file unless stated otherwise:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`;
- revision: `cced56592e8c8935f8220836b4baa04dfd389118`;
- hardware: 4x Intel Arc Pro B70 32GB;
- engine family: vLLM/XPU, Quark W8A8 INT8, TP4/PP1, 32K context.

## Best Strict-Valid Current Result

`prefill-safe-int8-mixed-workspace-async-deep-gate`, `20260615a13deep2`.

| Metric | Value |
| --- | ---: |
| Corrected output throughput | `93.55054235558917 tok/s` |
| E2E output throughput | `90.62548580766561 tok/s` |
| Total client token rate | `178.77293098777787 tok/s` |
| Decode latency | `10.68988536269444 ms/token` |
| TTFT client mean | `187.33663426246494 ms` |
| JSON canary | `128/128`, pass |
| Color canary | `256/256`, pass |
| Quality suite | pass |
| Decision | accepted by requested gates |
| LocalMaxxing ID | `cmqq4mw4c00yfqo01gb2ucgxj`, `APPROVED` |

Primary artifacts:

- [`deep-gate-summary`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-summary-20260615a13deep2.json)
- [`deep-gate-metrics`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-p512o512-20260615a13deep2.json)
- [`deep-gate-json`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-json-repeat128-20260615a13deep2.json)
- [`deep-gate-color`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-color-repeat256-20260615a13deep2.json)
- [`deep-gate-quality`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-quality-suite-20260615a13deep2.json)
- [`LocalMaxxing submission log`](../../data/localmaxxing-responses/qwen36-35b-quark-int8-b70-valid-2x4x-20260623.submit.log)
- narrative note: [`2026-06-14-qwen36-recovery-implementation.md`](../../notes/2026-06-14-qwen36-recovery-implementation.md)

Key identity fields:

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

This is the current safe baseline for future 4x comparisons.

## Legacy/Public Approved Result

LocalMaxxing approved record:
[`localmaxxing-qwen36-35b-quark-int8-exacthf-20260612ak.json`](../../data/localmaxxing-qwen36-35b-quark-int8-exacthf-20260612ak.json).

| Metric | Value |
| --- | ---: |
| LocalMaxxing ID | `cmq8yhxvo001ipb0149aoa79o` |
| Status | `APPROVED` |
| Corrected output throughput | `99.42835812273452 tok/s` |
| Total throughput | `196.3252731420561 tok/s` |
| TTFT | `76.45406149094924 ms` |
| Shape | p512/o512, streaming completions, temperature `0`, 4 repeats after warmup |

Supporting artifacts:

- [`accepted-clean-metrics`](../../data/qwen36-quark-int8-tp4-noprefix-accepted-clean-single-r4-20260611.json)
- [`frontdoor-quality-rerun8`](../../data/qwen36-quark-int8-tp4-noprefix-accepted-clean-frontdoor-quality-rerun8-20260611.json)
- [`submission-payload`](../../data/localmaxxing-qwen36-quark-w8a8-int8-tp4-noprefix-p512n512-20260611.payload.json)
- [`submission-response`](../../data/localmaxxing-qwen36-quark-w8a8-int8-tp4-noprefix-p512n512-20260611.response.json)

Caveat: this was approved and should remain in the record ledger, but later work
added stricter repeat/canary discipline. Use the `93.55 tok/s` deep gate as the
current strict-valid comparison point unless this older run is revalidated under
the newer gates.

## Best Clean Smoke

`prefill-safe-int8-mixed-workspace-async-smoke`, `20260615a13`.

| Metric | Value |
| --- | ---: |
| Corrected output throughput | `95.01697182719025 tok/s` |
| E2E output throughput | `92.004380418574 tok/s` |
| Decode latency | `10.525270629841543 ms/token` |
| JSON canary | `32/32`, pass |
| Color canary | `32/32`, pass |
| Quality suite | skipped |

Artifacts:

- [`smoke-summary`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-smoke-summary-20260615a13.json)
- [`smoke-metrics`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-smoke-p512o512-20260615a13.json)

Use this only as a smoke reference, not a record claim.

## Invalid, Synthetic, And Ceiling Results

These are valuable for direction-setting but are not valid records.

| Lane | Throughput | Status | Why not valid |
| --- | ---: | --- | --- |
| ngram5 current-storeguard raw | `198.9479016380729 tok/s` corrected | raw artifact | ngram/spec artifact, not clean endpoint correctness |
| EAGLE2 tokenheavy synthetic accept | `181.9100662518911 tok/s` corrected | synthetic ceiling | canaries skipped; synthetic accept, not valid serving output |
| MTP k1 parity-fix-v2 | `107.76565033909118 tok/s` corrected | invalid | JSON and color failed on first repeat |
| MTP k1 ReplaySSM graph cap-nonuniform | `75.69792475939613 tok/s` corrected | invalid | JSON `96/96`, color failed with first-decode garbage |
| MTP k1 ReplaySSM graph cap-small full | `76.244550687551 tok/s` corrected | invalid | JSON failed at 83, color failed at 23; full-accept double-processing signature |
| MTP k1 restore-sync | `73.45316484087655 tok/s` corrected | invalid | restore sync did not fix JSON/color; below the target direction |
| MTP k3 graph throughput probe | no throughput result | crash | engine-core cancellation after scheduling 4 tokens with 3 spec tokens |

Artifacts:

- [`ngram5 raw`](../../data/qwen36-ngram5-current-storeguard-random-p512o512-r4-20260615.json)
- [`eagle2 synthetic ceiling`](../../data/qwen36-ablation-eagle2-tokenheavy-synthaccept6-piecewise-tp2-k5-ceiling-20260618h-summary-20260618h02.json)
- [`mtp parity-fix-v2`](../../data/qwen36-ablation-tp4-mtp-k1-parity-fix-v2-summary-20260620061440.json)
- [`replayssm iter14 graph full`](../../data/qwen36-ablation-tp4-mtp-k1-replayssm-iter14-graph-capnonuni-full-summary-20260622193709.json)
- [`replayssm iter19 graph cap-small full`](../../data/qwen36-ablation-tp4-mtp-k1-replayssm-iter19-graph-capsmall-full-summary-20260622222755.json)
- [`replayssm iter20 restore-sync`](../../data/qwen36-ablation-tp4-mtp-k1-replayssm-iter20-graph-restoresync-summary-20260623023236.json)
- [`mtp k3 crash log`](../../data/qwen36-ablation-tp4-mtp-k3-graph-throughput-probe-20260623024028.log)

## Interpretation

The strict-valid non-spec graph baseline is near `93.55 tok/s`. The `>150 tok/s`
target requires more accepted tokens per step or a fundamentally cheaper
proposer/verifier path. K1 MTP never got there: even when fast enough to appear
promising, it failed canaries, and the correct ReplaySSM path was either slow or
graph-racy.

The best use of this lane now is as a reference set for upstream/runtime
bakeoffs and as a cautionary record for speculative decode state handling.
