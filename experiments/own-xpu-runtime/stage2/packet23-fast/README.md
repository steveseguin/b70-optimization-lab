# Packet 23: fused exact decode with cheap timing

CPU preparation only. No device binary, Level Zero discovery or /dev/dri access
ran in this task. K0/K1/W0/W2/W3 remain coordinator gates; no new GPU speed is claimed.
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
before/after median is **17.8275 → 0.289168 microseconds per submission**
(about 61.7× lower). This is host cost, not a model speed or SYCL measurement.

Fresh gates include both mini-model card counts; 13 integration cases across
three timing modes and both non-GEMV paths; GNU/Intel fixture repeats; four-seed
mini/integration dependency checks; ASan/UBSan bounds checks; owner/lifetime
controls; window tests; precision flags on device compile and link; and recursive
platform-math checks. [CPU receipts](cpu-tests.json) bind the final host binary.
The [three-position streaming check](streaming-real.json) verifies 3/3 tokens
and 144/144 layer hashes against packet21 with less than 0.8 GiB peak RSS.

[Carryover proof](carryover-proof.json) hashes the unchanged numerical files and the exact arithmetic bodies in the changed adapter/GEMV sources
and exact unchanged schedule/arithmetic regions in main.cpp. Whole main.cpp is
not identical: the [reviewable delta](host-plumbing.patch) changes host plumbing.
Carried evidence is precisely packet21's frozen 64-token/384-layer oracle gate,
R5 8-token/384-layer gate, four-seed short real-model dependency sanitizer, and
87-position full-prompt sanitizer. Their original binary hashes are retained;
no resident real-model or full-prompt sanitizer ran here.

[WINDOW.md](WINDOW.md) has exact K0/K1a/K1b/W0/W2/W3/W2d commands.
[DEADLINES.md](DEADLINES.md) separates expectations, submission budgets and
watchdogs. The packet refuses its own same-boot fault latch; boot-level recovery
belongs to the coordinator. K0, W0 and both fresh K1 attempts are mandatory.
[Closeout](CLOSEOUT.md) and [negative arms](DO-NOT-REPEAT.md) retain the limits.

Rebuild with `nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B
experiments/own-xpu-runtime/stage2/packet23-fast/build.py` after restoring the
small ignored input and fusion-fixture directories from packet21 or running
prepare.py/prototype/fixtures.py. The build never invokes native executables. `real_eight_gate.py` reproduces the additional one-card, full-prompt eight-token CPU check against v2 with layer-streaming and an 8 GiB address-space cap.
Build outputs and sealed fixture inputs remain ignored; test scratch is removed
once compact receipts and hashes are saved. build-receipt.json binds binaries,
inputs, compiler flags and the source closure.

## Sealed native binaries

| Binary | SHA256 |
| --- | --- |
| `device/jit-smoke` | `9d33a36559d60e74d52608b4f4af9819edb09ee219f209fdab385953ac1381c6` |
| `device/own-rt-iq3` | `007dea183b9d0eb804497c1be2f8a04bda50806fce5f15156be16b58c968995d` |
| `device/fused-fixtures` | `1c21c64788113616fef3a7b8b01abb4890f835eb89ceb7572aae7080781f5dda` |
| `device/nongemv-fixtures` | `d33708cfca6ee9fba80c5a3f261584bc7c06500bef3ac5f3b8b5fac0ed15c249` |

Final checks: 78/78 integration cases; 16/16 randomized mini runs; 104/104
randomized integration cases; 8/8 fresh GNU/Intel fixture processes; 79/79
guard checks; 7/7 lifetime controls; 2/2 injected failure exits plus 1/1 metadata upload/cache-order control; 56/56 window tests; 2/2 deliberate layer
mismatches rejected. Streaming: 3/3 tokens and 144/144 layer hashes exact.

## October 11 kernel-capture and failure-exit repair

W0's device compiler rejected 6,036 bytes of kernel arguments against a 2,048-byte
limit. The C++ Chain closure measured 6,056 bytes; it is now 56 bytes. All **41**
instantiated kernel classes fit within **224 bytes**. The complete before/after
list is in [KERNEL-ARGUMENTS.md](KERNEL-ARGUMENTS.md). Per-binding descriptor and
pointer tables now live in owner-tracked device USM, initialized once on first
planning/use and reused while the bindings match. Arithmetic, phase order,
barriers and BF16 rounding stores are unchanged. Read-only imported kernels
receive explicit storage-only substitutions in kernel_overlay.py.

Every submitted kernel functor passes `static_assert(sizeof(F) <= 1024)`.
The source mirror rejects unknown/unwrapped submission syntax. Both build.py
and the CMake kernel target run the gate; a 1,025-byte negative control must fail.
K0 links the very same kernel objects as all three native programs and asks the
device compiler to build every kernel for each admitted card, with no queue,
execution or explicit USM allocation. Its same-boot, same-binary receipt is
required before K1, W0 and every model window. Device qualification is pending.

K1 attempt a's hiding mechanism is proven in code: the old owner refused cleanup
once compute stored an exception, then parked in destruction before the outer
catch could print it. The actual triggering exception remains **unproven**;
the W0 Chain JIT error is the leading hypothesis. No external retained SYCL
borrower was found in that fixture. Both original coordinator evidence folders
are retained unchanged, with a new explanatory README for K1.

Failure handlers now report the error and owner state to stderr and failure.json
before a bounded shutdown attempt. They include pending event IDs, live bytes
and registered borrowers. Fixture hashes/rows and token rows are saved before
shutdown. Zero-work failures exit normally with code 1, including first-build
exceptions and retained-borrower controls. Repeated reporting of an already
drained failure reuses its receipt. Only unresolved work can retain the owner.
A backend retained after a zero-work cleanup failure is released by process exit;
that path is explicitly a failure, not clean teardown.

The additional [eight-token streaming check](real-eight.json) matched **8/8 tokens
and 384/384 layers** against v2 after the full registered prompt, below 1 GiB peak
RAM. Its exact tested binary hash is retained: it ran while final failure-path
reporting was completed. [The reuse proof](real-eight-reuse.json) and the complete
main.cpp diagnostic delta bind that evidence without relabeling it as the final
binary. The final binary independently passes the fresh three-position streaming
check (3/3 tokens, 144/144 layers) and all cheap gates. This task ran no device code.

Parameter-upload ordering is also checked: native backends assign compute event
IDs after the submission has finished preparing its tables. This keeps the
owner's event ledger sorted when preparation adds tracked copy events. One CPU
control checks metadata upload/cache reuse and the resulting event handle; the
queue source gate binds the check to both native backends. Earlier packets are
unchanged; the one-card backend change lives in the asserted local overlay.
