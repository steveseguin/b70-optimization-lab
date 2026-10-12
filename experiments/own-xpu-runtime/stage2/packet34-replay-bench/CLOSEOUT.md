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
images. The lifetime model passes 304 checks; the window passes 29 tests.
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

## October 12 preflight repair

The coordinator's card-3 K0 attempt at 02:23:55 UTC refused old reviewed boot
faults before starting a process. Its latch and complete refusal evidence are
[archived byte-for-byte](evidence/20261012-k0-refused-old-boot-fault-lines/README.md);
no active latch remains from that refusal. The original build receipt is retained
there so the old K0 identity remains reviewable.

`window.py` now accepts an explicit UTC review instant, records the reviewed
entry/fault counts, and binds the same instant across K0 and R1. Journal reads
use epoch time rather than ambiguous local time. Old unreviewed faults still
refuse; they do not create a latch if older than one hour and no packet 34 native
launch was attempted on this boot. New faults retain the existing latch path.

All 29 window tests passed, including old faults with/without review, a fault one
microsecond after review, timezone independence in three zones, retained cursor
for an empty interval, the one-hour boundary, prior-launch history, and changed
K0/R1 review rejection. Journal/loader/child calls in those tests are mocked.
A separate read-only journal check parsed 2,417 entries, including 18 matching
old fault entries; none followed `2026-10-12T02:20:00Z`. It did not launch a native child.
The source/gate seal was refreshed and independently checked. Other gates bind
unchanged C++ sources and binaries; they do not include `window.py` and were not
rerun. Binary hashes are unchanged. No compilation, device execution or device
discovery occurred during this repair; inherited affinity, nice 19 and idle I/O
priority were preserved. The next coordinator windows are `k0-r34b` and `r1-r34b`
on card 3 under [WINDOW.md](WINDOW.md). Native correctness and speed remain open.
