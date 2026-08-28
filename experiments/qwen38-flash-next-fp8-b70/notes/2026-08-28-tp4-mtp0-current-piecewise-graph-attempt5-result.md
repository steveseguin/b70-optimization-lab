# Qwen3.8 Flash-Next TP4 graph attempt 5 result

Date: 2026-08-28

Attempt 5 passed the ext4 staging and event-bound journal policy, loaded all
131 checkpoint shards on all four ranks, and entered post-load PIECEWISE graph
compilation. Every worker reported 31.27 GiB of model-loading memory and about
86.9-87.0 seconds. Rank 0 completed its 8.20-second Dynamo transform and logged
the `(1, 64)` compile-range cache event at 11:43:16. The API never became
healthy, so the client, quality suite, 96+96 replay gate, and speed rows never
ran.

This boot exhausted global host memory despite the 64-GiB temporary swap
treatment. The watchdog sampled 240 times over 256 seconds. `MemAvailable`
fell from 115,055,792 KiB to 9,070,068 KiB; temporary-swap use peaked at
6,400,744 KiB and the final sample showed 6,392,412 KiB temporary / 13,435,652
KiB total swap used with memory PSI `some/full avg10` at `7.33/7.14`. The
12-GiB floor latched at 11:44:20, one second before the first global OOM wave.

The timing matters. The first OOM wave at 11:44:21 killed three desktop-audio
services, not a model worker. The owned TERM path did not yield a timely
descendant exit under the severe pressure. A second OOM wave at 12:56:35
eventually killed TP2 and TP3, after which the engine exited. The final journal
contains nine OOM invocations and nine killed-process records. It also contains
42 corrected APEI source records and 43 RxErr lines, primarily for root NVMe
`0000:01:00.0` plus two corrected root-port sections at `0000:00:03.1`; no
B70 address, fatal/uncorrected PCIe severity, NVMe timeout/reset, or I/O error
appears.

Cleanup ultimately passed exactly: inner rc `130`, outer rc `70`, port 19679
and all model workers absent, compile/RPC paths absent, temporary swap disabled
and removed, original swap layout restored, and the four cards at
`42.890625 / 42.87890625 / 42.87890625 / 42.87109375 MiB`.

The unchanged 39-file ext4 evidence set remains at
`/var/tmp/q38-piecewise-graph-a5-resource` and was byte-verified against the
declared USB archive
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt5-resource-archive`.
Its 39-entry `raw-manifest.sha256` has SHA-256
`a06e8546638bf540d05dd3f99190cd496e35e7f635ab142554f599f51d0484f4`.
The combined archive/run/supervisor manifest has 79 entries, verifies from the
raw family root, and has SHA-256
`b2ddc4323c2b76da507736495fa81f2968bce29b5ba75bf7b5ce66d23622de4f`.
Its tracked copy is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt5-primary-evidence.sha256`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt5-primary-evidence.sha256),
and the structured receipt is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt5-result.json`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt5-result.json).

This is Grade-D failed-incomplete host-resource evidence. It provides no graph
correctness, quality, deployment, matrix, website, or speed credit. The live
contract remains 25/270 classified and every captured speed is unchanged. A
further swap-only retry is not justified: any successor needs a material way
to reduce compilation host-memory pressure and a monotonic wall-clock shutdown
deadline with owned-descendant escalation that remains bounded under swap
thrash.
