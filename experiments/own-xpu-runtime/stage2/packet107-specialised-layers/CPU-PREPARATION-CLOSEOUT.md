# Packet107 CPU preparation closeout

Question: do two structural per-layer implementations preserve the record
arithmetic well enough for a single-card microbenchmark?

Complete synthetic GDN layer 4 and QSA layer 3 pass four fresh finite-layer
runs (GNU twice, Intel twice), 1,216 byte comparisons each. Stronger leaf checks
close GDN for Intel NaN-payload drift; see `gdn-closeout.md`. QSA passes 58 cases
per compiler/process, including raw pre-BF16 FP32 and exceptional outputs.

One QSA candidate remains: compile-time head routing and grouped local K/V
reuse, with unchanged split32 arithmetic. Its two proposed lane-B jobs pass
CPU queue planning. No GPU, service or live queue ran. QSA device equality,
speed and full-model integration remain pending; CPU exactness is not a device
quality claim. The build is below 200 MB and the observed CPU peak below 8 GiB.

The code-derived bandwidth quotient at short context is only 4.29 µs, so the
80 µs integration threshold is deliberately demanding. Measure both fresh
processes; close promptly if either short-context result misses it. A
long-context gain cannot silently satisfy the short-context gate. Retained
source, parent-object identities, failed GDN source and byte evidence, CPU
receipts, cost accounting and queue plans are linked from README/work note.
