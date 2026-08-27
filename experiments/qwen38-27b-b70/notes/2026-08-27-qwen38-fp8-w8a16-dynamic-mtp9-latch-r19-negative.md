# Qwen3.8 FP8 dynamic MTP9 busy-period latch R19 negative

The first busy-period latch implementation failed its preregistered
single-user gate because its idle reset was placed at the wrong scheduler
lifecycle point. It is closed negative and remains immutable evidence.

| Shape | promoted MTP8 median | latch R19 | change |
| --- | ---: | ---: | ---: |
| one user, fresh after-TTFT decode | **146.814418** | 61.620428 | **-58.03%** |
| c64 aggregate decode | **1,094.314767** | not run | — |

The excluded c2 canary latched batch size 2. `_free_request()` then tested
`get_num_unfinished_requests()` before the caller removed the completed
requests from its queues, so the reset condition was false. The later genuine
singleton therefore stayed on MTP1 rather than MTP9; its rate independently
matches that diagnosis. The ordered protocol stopped before c64 and the
512-request canary.

The c2 canary returned 2/2 complete token-ID streams, cache zero, and no
cross-base collision, but only 1/2 matched its sequential oracle. The separate
quality suite passed 7/7 exact cases, 8/8 repeat stability, and the frozen
baseline. The endpoint remained healthy and stopped with exit 0 and no OOM.

The corrected default-off patch resets only after `_free_blocks()` removes the
last request from the authoritative request map. Its isolated lifecycle test
kept the latch with one request outstanding and reset it after the final free.
That correction is a distinct R20 treatment, not a reinterpretation of R19.

Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp9-latch-dynamic-mtp1-20260827-r19/`](../data/qwen38-fp8-w8a16-mtp9-latch-dynamic-mtp1-20260827-r19/).
No missing shape is inferred, interpolated, or extrapolated.
