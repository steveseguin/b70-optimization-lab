# K2 ended with an empty receipt: the root filesystem was full (2026-10-12 04:56–04:59 UTC)

K0, K1a and K1b (suffix `r36b`) had passed. K2 started at 04:56:01 on card 0 and the
wrapper stopped at 04:59:44 with `JSONDecodeError: Expecting value` while reading a
receipt: the root filesystem had reached 100% (see
[the incident record](../../../DISK-CLEANUP-20261012.md)), so the native program's
receipt was written empty. No GPU fault line; no retained process. The wrapper's failure
path wrote the boot latch, kept here as `FAULT-retired.json`.

Coordinator decision, 2026-10-12 05:03 UTC: latch retired (storage failure, not a
device fault). K2 and the windows after it are rerun under the suffix `r36c`; K0, K1a
and K1b keep their `r36b` receipts.
