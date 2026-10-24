# Class diagnostic — October 24, 2026

The unchanged native binary with class timing passes exact equality with baseline prompt00: all128 output tokens and complete target-state maps. Both owners exit cleanly; the retained inventory/fault baseline is unchanged. The [independent audit](evidence/independent-a/review.json) rehashes6,472 files/714,333,833 bytes, verifies214 consumed positions and both RESETs, and binds all six retained target state manifests. Raw evidence stays at `/mnt/usb-models/own-xpu-runtime-results/gsq-profile-a`.

These are summed GPU event execution durations over the entire measured request, including prefill, across both ranks. They are not end-to-end wall time, decode-only costs, or a speed comparison. The two excluded small warmup/blank snapshots do not contribute to these measured request class counters. Class labels group multiple layers and sometimes multiple formats. Event total is15,511.303219ms.

| Class | GPU event milliseconds | Share | Launches |
| --- | ---: | ---: | ---: |
| gdn.qkv | 1811.757 | 11.68% | 7,704 |
| attention | 1709.685 | 11.02% | 10,272 |
| expsgate | 1341.549 | 8.65% | 10,272 |
| expsup | 1334.396 | 8.60% | 10,272 |
| gdn.z | 1210.228 | 7.80% | 7,704 |
| expsdown | 1092.508 | 7.04% | 10,272 |
| qsa.qgate | 767.758 | 4.95% | 2,568 |
| route | 700.991 | 4.52% | 51,360 |
| gdn.recurrence | 377.881 | 2.44% | 7,704 |
| hc.f.low | 367.763 | 2.37% | 10,272 |
| hc.a.low | 364.205 | 2.35% | 10,272 |
| hc.f.inject | 357.092 | 2.30% | 10,272 |

The largest individual classes are GDN QKV, attention projections, and expert gate/up. The attention projection class uses Q8_0 weights at all48 sites (N2560×K6144); its BF16 input/output does not make the weights BF16. GDN QKV and Z include mixed Q6_K, Q5_K, Q4_K and IQ4_XS weights, so their aggregate cannot be assigned to one kernel format. The target output head is a smaller share of this diagnostic. Select one focused lossless candidate from these measurements; do not interpret inherited enqueue-family names or the generic GEMV/non-GEMV aggregate as reliable format attribution.

The private adapter command function changes only the timing value relative to the original command function for the same plan. Relative to the separate baseline launch, the actual argv also changes per-run shared/output paths and watchdog seconds7200→3600; private cache paths likewise differ. Class timing enables event queries and rank1's profiling queue property. All these differences are diagnostic identity, and no measured speed benefit is claimed from this run. Target tensors, quantization, accumulation path, context4096, full BF16 KV, full-vocabulary draft allocation and native binary remain the same.

[Plan and terminal receipts](evidence/run-a/terminal.json) bind the operational identity. Owners3586476/3586484 exit0 with no live allocations, in-flight work or signals; orchestration took108.274seconds. The compressed index contains metadata and hashes, not tensor payloads; retain it with the raw evidence and use `audit.py` to reconstruct the enumeration against unchanged roots. Both original applications remain stopped from their earlier single graceful stops; vision remains unchanged. No service action, retry, reset or setting change occurred in this diagnostic.
