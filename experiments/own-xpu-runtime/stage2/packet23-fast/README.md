# Packet 23: fused exact decode with cheap timing

CPU preparation only. No device binary, Level Zero discovery or /dev/dri access
ran in this task. K1/W0/W2/W3 remain coordinator gates; no new GPU speed is claimed.
All work is confined to this packet, with two compile jobs and two numeric threads.

This combines packet21's qualified fused schedule (876 compute launches per
generated token) with packet18's later canary borrower lifetime repair, closed
environment policy and separated deadlines. V2 arithmetic, target weights,
launch order, 16-bit state and exact oracle remain unchanged. Frozen and R5
are separate dispatch choices for the quantized compressed model.

`--timing token` is the default: unprofiled queues, no per-launch timing queries,
no pending timing-event list, one whole-token steady-clock span and counters.
`--timing drain` adds a wall span around each completed drain including retirement.
`--timing launch` preserves profiling for diagnosis; its receipts are explicitly
marked distorted and the window wrapper suppresses the throughput claim.
W0 always profiles its small canary so its safety budget remains enforced.

Packet18 measured 406.8 ms/token (2.46 tok/s), including approximately 92 ms GEMV
and 47 ms non-GEMV device spans on the unfused schedule. Those 139 ms are prior
unfused measurements, not a prediction for packet23. Fused kernels can change
occupancy, serialization and duplicated transforms. Packet20 measured roughly
3.4–5 microseconds per SYCL submission; packet18's thousands of profiling queries
are a distinct overhead. Only the new device windows can establish the speed.

Host changes grow the event ledger geometrically before submission, use stack
storage for ordinary compute dependencies and pointers, find arena handles by
binary search, and use ordered pointer-range lookup in the native backend.
Non-GEMV resident bindings are cached after first resolution. The chained tail's
successful wait proves preceding events complete, removing redundant status
queries at retirement while preserving native synchronize, fault handling,
allocation checks and queue fences. Native dependency vectors reuse capacity and
release every retained event before context release. Timing files flush every
16 positions and at close; upload/progress safety records remain available.

The [submission benchmark](submission-benchmark.json) measures the actual owner
compute path with null operations, 19 bindings, 2048 live allocations, 876
submissions per segment, one discarded warmup and ten measured repeats. Its
before/after median is **18.0743 → 0.288997 microseconds per submission**
(about 62.5× lower). This is host cost, not a model speed or SYCL measurement.

Fresh gates include both mini-model card counts; 13 integration cases across
three timing modes and both non-GEMV paths; GNU/Intel fixture repeats; four-seed
mini/integration dependency checks; ASan/UBSan bounds checks; owner/lifetime
controls; window tests; precision flags on device compile and link; and recursive
platform-math checks. [CPU receipts](cpu-tests.json) bind the final host binary.
The [three-position streaming check](streaming-real.json) verifies 3/3 tokens
and 144/144 layer hashes against packet21 with less than 0.8 GiB peak RSS.

[Carryover proof](carryover-proof.json) hashes identical numerical source files
and exact unchanged schedule/arithmetic regions in main.cpp. Whole main.cpp is
not identical: the [reviewable delta](host-plumbing.patch) changes host plumbing.
Carried evidence is precisely packet21's frozen 64-token/384-layer oracle gate,
R5 8-token/384-layer gate, four-seed short real-model dependency sanitizer, and
87-position full-prompt sanitizer. Their original binary hashes are retained;
no resident real-model or full-prompt sanitizer ran here.

[WINDOW.md](WINDOW.md) has exact K1/W0/W2/W3/W2d/W3d commands and optional W1.
[DEADLINES.md](DEADLINES.md) separates expectations, submission budgets and
watchdogs. The packet refuses its own same-boot fault latch; boot-level recovery
belongs to the coordinator. W0 and K1 are mandatory; W1 is recommended, optional.
[Closeout](CLOSEOUT.md) and [negative arms](DO-NOT-REPEAT.md) retain the limits.

Rebuild with `nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B
experiments/own-xpu-runtime/stage2/packet23-fast/build.py` after restoring the
small ignored input and fusion-fixture directories from packet21 or running
prepare.py/prototype/fixtures.py. The build never invokes native executables.
Build outputs and sealed fixture inputs remain ignored; test scratch is removed
once compact receipts and hashes are saved. build-receipt.json binds binaries,
inputs, compiler flags and the source closure.

## Sealed native binaries

| Binary | SHA256 |
| --- | --- |
| `device/own-rt-iq3` | `02ef63a2ce5035f82dd75d4287e4af7cc9e1b9326408b4dfa8bd566409deb1d5` |
| `device/fused-fixtures` | `4c100c94c6a5acd8ca464055792b7dd53f3ec780ce7e8719a90e3e5c904eb6ee` |
| `device/nongemv-fixtures` | `c1fb601b155253a0a4211b27bc93297545668ca71f277ae88462255ff3ad9062` |

Final checks: 78/78 integration cases; 16/16 randomized mini runs; 104/104
randomized integration cases; 8/8 fresh GNU/Intel fixture processes; 79/79
guard checks; 7/7 lifetime controls; 54/54 window tests; 2/2 deliberate layer
mismatches rejected. Streaming: 3/3 tokens and 144/144 layer hashes exact.
