# Qwen3.8 FP8 TP2 c64 conditioning R28

Date: 2026-08-26. Status: **complete; transient effect rejected**.

The corrected within-server factorial reproduced both sides of the earlier
discrepancy. A direct c64 batch measured `726.621852 tok/s`. After the exact
c1→2→4→8→16→32 ladder, the ladder-terminal c64 measured `773.548460`
(`+6.458%`), matching R10's approximately 774 tok/s. But the immediately next
c64 batch fell to `722.346645` (`-0.588%` versus the initial c64).

The two post-ladder results have a `6.846%` relative range, failing the frozen
`<=2%` persistence gate. Their median is `747.947553` (`+2.935%`), but that
median is not an operating point and must not be published.

## What changed was TTFT, not steady decode

Median c64 TTFT moved from 1431.94 ms to 765.14 ms at the ladder-terminal
point, then returned to 1511.78 ms. Median per-request post-TTFT decode stayed
flat at 13.366, 13.324, and 13.363 tok/s. The high c64 wall-rate endpoint is
therefore a transient measurement-order/TTFT state, not a sustained decode
optimization.

This preserves R10 as a truthful measured ladder endpoint, but it must not be
presented as repeated-batch capacity. The sustained short-output HTTP c64
operating range on this server was approximately 722–727 tok/s. Future work
should measure and optimize post-TTFT decode directly, while retaining the HTTP
wall metric as a separate user-facing measurement.

## Evidence

- [Structured result](../data/2026-08-26-qwen38-fp8-tp2-http-p64-conditioning-r28-result.json)
- [Preregistration](../data/2026-08-26-qwen38-fp8-tp2-http-p64-conditioning-r28-prereg.json)
- [Raw qualified factorial](../data/qwen38-fp8-tp2-http-p64-conditioning-20260826-r28-attempt1/)
- [Corrected harness](../scripts/qwen38-concurrency-conditioning-factorial-r28.py)
- [Failed-closed R27](../data/2026-08-26-qwen38-fp8-tp2-http-p64-conditioning-r27-result.json)
