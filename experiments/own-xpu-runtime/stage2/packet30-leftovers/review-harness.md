# Independent G3/build review

Reviewed by the attention-family agent directly from `g3.cpp`, `build.py`,
`window.py`, `window_safety.py`, the runtime's `owner.cpp` and the candidate
interfaces. This review used CPU source inspection; no native binary,
device discovery, Level Zero discovery or device file was executed/opened.

## Timing and baseline path

The baseline invokes packet27's actual runtime adapter
`packet18::submit_parallel`, the packet27 small GEMV path, or the packet28
incumbent wrapper; it does not time a CPU mirror or a rewritten baseline.
The adapter sequences its phases, and `Device::compute` automatically includes
the previous owned event as a dependency. Combining two runtime sites therefore
retains the order even without an explicit cross-site dependency argument.

Candidate submit functions return their real SYCL event vector. G3 profiles
all returned events rather than just the enclosing owner's last event.
Incumbents enumerate owned events from first to last. The raw JSONL retains
start/end for each event and launch-group index. No CPU wall duration is used
as kernel time. There are exactly 200 repetitions per admitted variant.

For payloads exceeding8 MiB, each `BoundNg`/`BoundSmall` ring member uploads
its own full-size input/weight/output buffers before timing. Eight members
are selected by repetition modulo8. Timing loops only submit/wait/profile;
there is no copy, upload, output readback or input reset per measured launch.
All semantic byte comparisons happen before this timed phase. Input buffers
are immutable and outputs are overwritten rather than reused as inputs.

## Correctness, admission and failures

The reference path evaluates the actual arithmetic-v2 Core for non-GEMV
fixtures. The small GEMV host oracle uses the registered arithmetic row.
Candidates compare complete semantic output bytes with the incumbent;
incumbents compare host finite elements exactly (NaN payload equivalence is
explicit). Attention scratch suffixes are not semantic outputs and are not
included in the output list. Attention's standalone CPU gate additionally
compares every admitted score/probability cell.

Every candidate entry calls its host binding guard before native submission.
The validation mode invokes the same guards with real allocations and rejects
truncated outputs, aliased outputs, and (for small GEMVs) short weights.
Family CPU gates add shape/null/alignment/range-overflow checks. The CPU
backend allocates ordinary host memory and never loads accelerator libraries.
The native executable rejects CPU-only mode flags before device creation.

Output mismatches are emitted to flushed exactness JSONL, exclude only the
failing candidate and continue the remaining candidate/class checks. A bad
baseline makes candidate evidence ineligible for timing. Reported failures
are persisted before owner shutdown. Runtime/device faults leave the ordinary
failure/teardown path, rather than being treated as an invitation to retry.

## Build and prepared window

Compilation is CPU-only, sequential inside each build process, bounded to8 GiB
address space, with nice19/OMP2 admission. Both compile and link commands
include no-fast-math and contraction-off; native commands additionally require
IEEE denormals and precise offload division/sqrt. The seal rechecks every
command, hashes the full local/external include closure and binaries, and
rejects native transcendental bypasses through its math grep.

Native compilation applies the guarded mirror under ignored build storage;
external packet sources remain read-only. Device kernel lambdas must capture
by value. The checked wrapper asserts the actual closure size<=1,024 bytes.
The build script never runs native g3. Host modes run in two fresh processes.

The device window runs ldd before latch inspection/creation, binds a completed
same-card/same-binary/same-boot K0, rejects unlisted environment keys and device
masks, and passes only the recorded native allowlist. K0 compiles kernels
without executing them. G3 uses two fresh owners, each in a separate user
unit without restart. Its watchdog is at least300s and at least4x the declared
expected work/JIT total. Each native submission wait is300s. Fault/watchdog
failures are saved before SIGTERM; no hard-kill fallback is hidden in the
wrapper. Expected duration is metadata, not an enforced short timeout.

## Findings fixed during this review

1. `route_cpu.cpp` was missing from the common compilation sources although
   the host harness calls its out-of-line function. It is now included.
2. Submission-budget metadata still said0.010s although the actual wait was
   300s. It now reports300s, retaining0.010s only as an expected event duration.
3. An incumbent `invalid_argument` could leave the incumbent-output vector
   empty, then a following candidate indexed it out of bounds. Both family
   loops now bound-check the vector index and set `base_ok=false` on an
   incumbent exception. This cannot accidentally admit a timing result.

The actual qsa_select tie gate is present in `attention_cpu.cpp`: unchanged
ng selection and Core both produce ascending tied block IDs and then the
unpooled tail. Empty attention's incumbent/Core disagreement remains explicit
and is not called a triple-equality pass.

No remaining source-level blocker was found in the reviewed timing/admission
paths after those changes. Compilation and CPU receipts provide execution
checks; GPU equality, baseline representativeness and performance are still
pending. This review does not certify unexecuted native behavior.
