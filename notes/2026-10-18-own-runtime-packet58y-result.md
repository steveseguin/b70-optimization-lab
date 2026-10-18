# Packet58y result: one-card attribution on the overlap engine. Diagnostic only; no lever selected

Lane A, card 0, inside the packet58x whole-host hold, 20:28–20:36 UTC October 18 (fault count 2). Analysis: `stage2/packet58y-onecard-attribution/analysis/report.md` / `report.json` (`analyze.py`, status complete_diagnostic).

| Bucket (instrumented run) | ms/token | Perfect-removal bound | Analyzer decision |
| --- | ---: | ---: | --- |
| Compute-tail wait incl. zero-copy miss kernels | 20.77 | 93.6% | needs causal test |
| Token lookup/preparation (host-exclusive 8.04) + input-upload waits (2.24) | 10.28 | 31.7% | needs causal test |
| Host command submission | 8.09 | 23.0% | needs causal test |
| Cache publication + fill submission at the safe boundary | 1.58 | 3.8% | needs causal test |
| Overlapped CPU cache planning | 1.15 | 2.9% | killed (< 3%) |
| Token/route readbacks + cache bookkeeping | 0.89 | 2.0% | killed (< 3%) |

The instrumented class-balanced rate is **22.86 tok/s** (43.7 ms/token), against the uninstrumented line's 28.04 (35.7 ms/token). The tracing itself adds about 8 ms/token, about the size of the "prepare" bucket. Packet58i's uninstrumented `prepare_ms` was 0.56 ms/token. The host buckets are therefore not trustworthy as projections, and the analyzer itself grants none: upper bounds overlap device work and are not additive.

Coordinator decision: no one-card lever is briefed from this diagnostic. Capacity is done (packet58x, +4.1%, record chain packet58z in preparation). The dominant real cost is the compute tail (device kernels plus zero-copy misses). Any exact 2-card target-body win from packet142's class-layout screens is ported to the one-card line next. A future one-card host-side lever needs a causal test (for example injected-delay sensitivity in one load) before any brief.
