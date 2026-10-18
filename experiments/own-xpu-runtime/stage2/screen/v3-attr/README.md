# Lane-B packet64 attribution screen

This is a separate copy of `v3-packet64-lanes`, with attribution-selection
admission and a paired control/observation request schedule. It keeps all lane,
card-mask, fault, memory, graceful drain and whole-host speed-window interlocks.
The frozen wrappers are unchanged.

Use the [packet's commands](../../packet64-attribution/WINDOW.md). One loaded
pair checks incident64, then twelve 128-token control requests and twelve
instrumented requests. All are checked against packet49. The full target and
draft request state resets between requests. No prompt/KV/response reuse.
The repeated control/observation suite is diagnostic and cannot be submitted.

Only `--plan` and `cpu_seal.py` were run here. The coordinator owns every device
window. The copied wrapper's ordinary request path still has its original CPU
byte fixture; new tests cover the paired schedule, reset flags, plan, and tamper
refusal. Device overlap and timings remain unmeasured.
