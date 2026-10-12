# Packet 34 CPU preparation closeout

Question: does recording the current resident half-token kernel sequence remove
host launch gaps on a B70 without changing bytes or growing memory unboundedly?
This packet prepares that one-card measurement. It does not answer it yet.
No device ran; no speed is claimed.

Identity: packet29's measured dispatch snapshot, unchanged submission sources
and qualified compile overlay, layers 24–47, 18 GDN/6 QSA layers, synthetic
finite weights at actual shapes/formats, four rotated weight sets, BF16 state/KV.
The [source census](census.json) has 1,142 native submissions and
4,766,268,444 application device bytes. The head and cross-rank transport are
excluded; the last fused normalization remains included.

Built paths are direct immediate submission, one whole-half SYCL graph and
24 per-layer graphs. Raw replay is blocked by missing current-kernel typed
entry/ABI manifests; [independent review](review-raw-abi.md) specifies the work
needed. Packet22's unrelated receipts are rejected by four CPU capability tests.

CPU evidence: [CPU gates](cpu-tests.json), [capture gates](capture-gates.json),
[lifetime tests](lifetime-tests.json), [window tests](window-tests.json),
[build receipt](build-receipt.json), [binary hashes](BINARY-HASHES.md).
The final host oracle has six fresh processes (GNU, Intel and GNU ASan/UBSan,
two each), 210 iterations per process, and 2,545,200 exact buffer comparisons.
Each process covers both parities, 210 different routed expert sets and 11
attention slot counts. The common final state SHA-256 is
`f6637089dffda256515bc051a21b3729ae3ecb2370c8049d5f8a2e17b697ebba`.
There are 309 compiler-inspected captures, maximum 744 bytes; an oversized 1025
byte capture fails compilation. K0/R1 contain the same 24 embedded SPIR-V
images. The lifetime model passes 304 checks; the window passes 23 tests.
These are CPU results, including reduced-geometry arithmetic. They cannot
qualify full-size native arithmetic or a SYCL graph implementation.

Independent reviews fixed expanded-storage allocation, K0 image coverage,
missing dynamic-state checks, and failure-path ownership/teardown defects.
A stale sanitizer object compiled while source changed was discarded; the
final object was rebuilt and its two fresh gates rerun. Earlier CPU receipts
remain labeled preparation evidence, not the final gate. No prior packet or
shared state file was changed.

The coordinator must still run [K0/R1](WINDOW.md). Open questions are native
compile/JIT support, local-memory/subgroup graph support, byte equality,
individual direct event profiling, recording cost and memory growth,
cooperative fault retention/teardown, and actual wall/CPU/GPU durations.
The memory query uses only the owner's device when its optional counter is
available. Without that counter the bounded-memory verdict remains pending.
The harness records synthetic-data boundary costs outside the timed half;
its parity test does not claim dynamic pointer selection inside old kernels.

Useful mechanism retained: stable resident bindings let the same unchanged
submission path be recorded with in-order dependencies. Per-token position,
routes and attention lengths remain device data. [INTEGRATE.md](INTEGRATE.md)
describes qualification per rank and parity; no packet32 code is imported.
Revisit raw only with an independently qualified current ABI bridge. Proceed
to runtime integration only after the coordinator measures exact bytes,
bounded memory and replay wall at or below direct summed GPU time.

[DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) retains closed preparation mistakes.
[Scratch cleanup](scratch-cleanup.json) hashes the retained CPU evidence and
records scratch removal. Ignored K0/R1 binaries remain available.
