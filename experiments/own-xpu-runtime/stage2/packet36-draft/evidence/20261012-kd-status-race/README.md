# KD stopped by a race in the wrapper's memory watch (2026-10-12 05:18–05:19 UTC)

K0, K1a, K1b (`r36b`), K2 and W0p (`r36c`) had passed. KD's first owner ran the draft
head on the second card over the 150 captured positions: native receipt `passed: true`,
clean teardown, clean kernel log ([receipt](owner0-receipt.json),
[rows](owner0-draft-rows.jsonl)). The wrapper then failed with an empty error message:
its loop read `/proc/<pid>/status` of the child in the instant after it exited and
before it was reaped; such a process has no `RssAnon` line, `next()` raised
`StopIteration`, and the failure path wrote the boot latch (`FAULT-retired.json`).
The second owner never started and the byte comparison with the host fixtures did not
run, so this window proves nothing about host/device draft parity either way.

What the completed owner does show (diagnostic, not a gate): the draft layer takes
1.8 ms per position on the card without the output head and 4.1 ms with it (wall time
in a standalone owner), and its first guess after the prompt is the token the target
emits there.

Coordinator fix: a default value in that one expression (`draft_window.py`), source
seal amended in `build-receipt.json`. Latch retired (not a device fault). Because K0
binds the receipt hash, every window is rerun under the suffix `r36e`.
