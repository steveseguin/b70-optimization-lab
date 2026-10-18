# Packet90: exact expert and HC decode caches

CPU-only follow-ups to the packet86 limiter study. The
[preregistration](PREREGISTRATION.md) maps every diagnostic outcome to the next
exact candidate and labels all expected savings as unmeasured hypotheses.

Three selectable views share one binary built from copied packet84 sources:

| View | Change | Extra weight bytes, rank 0 / rank 1 |
| --- | --- | ---: |
| production | hc-wide, wide64, ordered, rec-parallel; other record settings unchanged | 0 |
| exp-halfcache | Decode IQ2 gate/up half scales once at load into exact FP32 values | 301,465,600 / 314,572,800 |
| hc-weightcache | Store the exact FP32 decoded target HC gate coefficients | 442,368,000 |

Neither cache stores prompts, KV, activations or responses. Model bytes,
quantization identity, verifier and full BF16 KV remain unchanged. The 32
logical chains, their ordered FP32 products/additions, adjacent reduction tree,
BF16 boundaries and route/error outputs remain unchanged. Expert down, draft
and final HC are untouched. Cached views explicitly reject unsupported native
modes and their unqualified combination. Nonfinite weight scales refuse rather
than silently taking a different NaN path.

[GNU/Intel byte proof](evidence/cpu-byte-identity.json),
[full-size startup proof](evidence/full-shape.json),
[memory admission](evidence/full-shape-admission.json),
[Python gates](evidence/python-tests.json), and
[build identity](build-device-receipt.json) are separate gates. Generated CPU
startup code retains real allocation, dispatch, extent/alignment, prepared
capture, snapshot and draft construction. Only the backend and payload reads
are mocked. No real model payload or device is needed for preparation.

The shared pinned v4 wrapper owns all future device admission, supervision,
first-request oracle checking, timing, drain and release. Its built-in single
64-token incident gate precedes the twelve timed requests for each view. The
lane-A bracket is production / expert / HC / production. Lane B runs only the
exact lane-A winner, bracketed by controls. Every prompt's acceptance counts
must stay equal. Proposed queues are never live queues.

These are screen candidates. Existing K2 and submission consumers reject the
new choices; a future bundle must integrate and qualify them explicitly. No
speed claim, model-output qualification or submission follows from CPU gates.

[Coordinator handoff](WINDOW.md) · [retention and rebuild](ARTIFACT-RETENTION.md) · [CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
