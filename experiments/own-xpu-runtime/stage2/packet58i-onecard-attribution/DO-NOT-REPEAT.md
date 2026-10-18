# Packet58i decisions

| Arm / interpretation | Outcome | Revisit condition |
| --- | --- | --- |
| Treat 58g zero device fields as zero compute | Invalid: profiling disabled | Actual bounded class/event timing |
| Call all 7.835 ms cache wall hideable DMA | Invalid: CPU planning, submissions and publication included | Separate spans on a common clock |
| Infer individual ordinary-layer hit rates from fill totals | Unidentifiable; only layer 2 and ordinary-layer pooled rate recover | Retained route IDs or per-layer counters |
| Spend 5.89 GB physical VRAM headroom | Not admitted under unchanged host bound | Exact freed-byte and peak-lifetime proof |
| Seal post-router BCS speed from perfect overlap | Missing router wait, split dispatch, sparse-miss and overlap costs | Matched one-card stage trace and unchanged output gates |
| Tested LFU / one frequency prefetch per layer visit | Proxy traffic regression | A distinct causal policy with lower total transfer cost |
| Reuse packet55 replay as native one-card hits | Invalid topology/scheduling transfer | Actual 58g-style route trace |

See [closeout](CLOSEOUT.md). Frozen 58b–58h and packet81 decisions are retained
in the input snapshots. Static host expert identity tuning, MTP and load-count
geometry are not reopened.
