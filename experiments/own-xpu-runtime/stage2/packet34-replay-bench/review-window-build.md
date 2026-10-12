# Independent window and build review

This review read source and generated host build commands only. It did not
compile, execute a device binary, discover devices or access a driver. The
reviewer ran the serial mocked Python window tests, which launch no children.

## Findings and corrections

1. **Fixed:** the original caller environment gate accepted `PATH` and
   `OMP_NUM_THREADS`, contrary to “only LD_LIBRARY_PATH supplied”. The gate now
   accepts only `LD_LIBRARY_PATH`, plus Python's exact `LC_CTYPE=C.UTF-8` locale
   coercion, which it discards. Other locale values, caller PATH/OMP and all
   other variables fail. The child receives canonical internal OMP=2 and
   PATH=/usr/bin:/bin. Updated tests cover these inputs; all 13 window tests
   passed after the edit.
2. **Source fix reviewed:** original K0 linked runtime objects but not the
   bench translation unit, so it could not compile the new boundary kernel or
   backend marker present only in R1. CMake now compiles `bench_entry` once with
   its host entry renamed, and links that exact object plus runtime objects
   into both K0 and R1. The missing-source problem is closed. Final executable
   closure remains gated by the matching embedded device-image comparison.

## Window observations

The wrapper requires explicit coordinator authorization, a nonnegative card,
a fresh output directory inside packet34, binary hashes matching the build
receipt, and successful `ldd` before launch. R1 also requires a passed K0 receipt
bound to the same boot, card, environment, binary hashes and build receipt.
There is no device discovery in Python. The native owner selects the card.

The unchanged packet29 K0 program constructs a context and builds linked input
kernel bundles; it creates no queue, allocates no explicit device buffers, and
submits no kernel. This is device JIT compilation reserved for the coordinator,
not a CPU-only preparation command. It has no cooperative signal handler; the
wrapper correctly retains a stopped/timed-out K0 child without sending SIGTERM.

The watchdog enforces max(300 s, 4 * the reported expectation); the final
source reports a 300 s expectation. Expected duration is metadata, not a
premature timeout. Exact current command budgets are in WINDOW.md/DEADLINES.md.
R1 receives at most one cooperative SIGTERM after the durable fault/failure
record, then a bounded drain interval. A busy child is retained with its PID.
There is no hard kill, reset, retry loop, taskset call, priority elevation or
host setting change. Native child affinity/priority is inherited, allowing an
authorized nice-0 taskset parent. Read-only ldd/journal helpers run nice19/idle.
Helper timeout termination affects only CPU utilities, not the native child.

The kernel log watcher uses specific fault signatures and treats inaccessible
journal data as failure. Preflight faults latch before launch; subsequent faults
latch and stop. Mock tests cover watchdog, fault, journal loss, interruption,
cooperative exit, busy-child retention, K0 no-signal retention, bounds and receipt
rejection. Final wrapper success requires normal child exit, a passing native
receipt, and safe teardown for R1.

## Build and argument guards

CMake applies no-fast-math and no contraction on compile and link for every
configuration. Device compilation/link additionally require IEEE denormals,
precise FP32 divide/sqrt and fsycl. `build.py` reads actual compile_commands.json
and every link.txt and asserts exact flag tokens, rather than trusting CMake
intent. At the review snapshot, the host build had 13 compile entries and one
link command; independent read-only checking found the required flags on all.
Other configurations were not yet generated, so this review does not claim
their final flags or binary hashes.

`mirror.py` reads existing sources, applies packet29's existing compile overlay,
and writes local build copies only. Its added `checked` guards require by-value
lambda capture <=1024 bytes; reference default capture fails mirror generation.
It asserts every detected parallel_for/single_task site received a guard and
records input hashes. Bench Boundary and backend marker also use `checked`.
Generated source inspection alone does not establish final ABI sizes: final
compiler capture-size symbols and all linked device entries need the parent's
compile-only gate. Dead-argument-preservation is not required for graph replay;
raw remains unavailable and separately fail-closed.

Native `--mode raw` currently fails as an unsupported argument while parsing,
before any Native owner construction. No native device binary should be run to
test that fact during CPU preparation; the host build can test identical parser
behavior. Its final rebuilt hash must bind the result.

## Final source follow-up

The shared `bench_entry` object is now present in both executable link inputs.
`capture_gate.py` reads each final ELF as bytes, resolves its embedded
`.sycl_offloading.*.data` symbols to section data, requires SPIR-V magic, and
compares the **multiset of SHA-256 hashes of the actual image bytes** between
K0 and R1. It does not merely compare kernel or symbol names. The receipt binds
both executable hashes. The gate also checks every emitted capture-size symbol
is <=1024 bytes and compile-tests that a 1025-byte value is rejected, removing
its temporary source afterwards. It neither loads nor runs a device executable.
At this review, final builds were still running; gate execution and final hashes
remain the parent's responsibility. No final ELF pass is asserted here.

`summarize.py` requires complete 210-iteration sequences for all three modes,
10 warmups and 200 measured rows, 420 corresponding state hashes matching direct,
the final state hash, and changed routes/parities/attention counts. Native mode
checks the direct per-kernel event counts and GPU-duration sum and the exact
1/24 graph submission counts. It reports wall/thread-CPU summaries separately.
It requires all six recording receipts and bounds both allocation accounting
and observed driver memory growth before declaring `replay_pays`; unavailable
driver counters leave the bounded-memory verdict unproven. Thus an accounting
fallback cannot silently produce a positive replay-pay verdict. No observed
speed has been supplied or inferred by this review.

The window now samples summed `RssAnon` for the native process and descendants,
including children of every thread, with PID deduplication. Loss of the live
root or inaccessible memory evidence stops admission/progress. At 7.5 GiB it
uses the same durable cooperative-stop/retain path, leaving 512 MiB before the
8 GiB requested ceiling. K0 is retained without a signal. This is sampled
protection, not an absolute address-space/cgroup ceiling: rapid allocation
between samples can exceed a threshold before observation. No memory, swap,
page-cache or host power settings are changed. A retained child remains the
coordinator's responsibility; the wrapper does not kill it to enforce a cap.

## Final admission closure

A final review found that matching binary hashes alone could admit a partially
built package before its CPU or capture gates finished. This is fixed in
`sealed_build_gate`, called before ldd, journal reads or native launch. Admission
now requires `build-receipt.json` to be explicitly sealed with `passed=true` and
CPU-only preparation, and exactly the five named gate receipts: CPU, capture,
lifetime, window and raw-capability. Every receipt must match its sealed SHA-256,
pass, and state that no device ran. Unknown/missing receipt names fail.

The capture receipt must bind the actual K0/R1 binary hashes and affirm identical
device images, the negative oversized-capture test, and a maximum capture size
between one and 1024 bytes. Raw remains explicitly unavailable and unqualified.
All three host configurations must have exactly two fresh passing, safely exited
CPU rows; each row hash must match both the sealed binary identity and the
current host binary on disk. Stale ASan rows cannot qualify a rebuilt ASan file.

Sealed packet34 source hashes, the source-proof receipt hash and every upstream
source hash are rechecked. Absolute or repository-escaping source paths fail.
Changes after sealing therefore invalidate admission. Five new test methods
exercise complete admission, missing/unsealed evidence, unknown receipt paths,
changed receipt bytes, failed or mismatched gate identities, incomplete repeats,
changed host binaries and changed current/upstream sources. The complete serial
mock suite passed 23/23 tests; it launched no child or device. Parent must rerun
`seal.py` after these source/test changes and completion of final CPU gates.
