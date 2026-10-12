# Packet 35 host preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet 29's repeated host issue work be prepared once without changing its
device kernels or arithmetic? This packet is a CPU-only implementation and
verification step in the IQ3 runtime lane, using the packet 29 source snapshot
and `iq3-p17-detmath-v2` authority. No accelerator was opened or run. The intended
device topology remains two resident B70 cards; one-card production staging keeps
the legacy issue path. Work is confined to packet35-hostpath.

## Outcome

The host-path implementation is prepared. Its actual-family CPU mock records
zero allocation calls over 294,912 prepared launches across 14 families; the
per-family before/after measurements are in [README.md](README.md) and
[prepared-host-benchmark.json](prepared-host-benchmark.json). These are CPU issue
costs, not model speed. Fresh CPU suites pass 234 integration cases, 32 sanitizer
runs, fixtures and
argument validation. The fresh real-eight run passes 8/8 tokens, 384/384 layers
and 192,114 full argument comparisons; the two-card mini gate passes 6/6 cases
and 1,887 argument blocks. All required CPU gates pass and bind the final build.
Inherited evidence retains its original identity.

No device window ran and no device result is accepted. The next stage is the
coordinator's existing real-plan windows after every final admission gate passes.

## What worked

Preparation removes candidate searches, validation, arena lookups, allocation
binding, range construction and device-capability queries from repeated issue.
Immutable plan/options, a dispatch snapshot and process-unique owner generations
prevent stale reuse. The independent invalidation tests pass 13/13 with ASAN,
UBSAN and leak detection; window protocol tests pass 102/102.

K2 now compares measured fusion cost with selected member sums. Reaggregation of
packet 29's historical measurements keeps all three small fusions; the costs and
source hash are preserved in [k2-selection-regression.json](k2-selection-regression.json).
The preparation pass reads lookup pages after device uploads and receipts flag
subsequent major faults instead of silently treating paging noise as clean speed.

## What failed or remains uncertain

The first copied command-group design retained an extra virtual dispatch; a
preparation-time callback factory removes it. Native compilation found an
inherited Stream handler implicitly borrowing `this` through its `copy` field;
explicit value capture corrected the lifetime problem without changing the
kernel body. Owner-address reuse and erased-operation capture also required
fail-closed guards, now exercised by independent tests.

Eventless execution is not adopted: the existing event/retirement protocol needs
real completion events to protect allocations and retain bounded failure checks.
Local accessors remain unchanged. Moving an inner kernel to a new lexical site is
not accepted as a host-only change. After preserving original `#line` locations, the final executable identity
comparison passes all 24 SPIR-V modules and all 369 kernel names. The proof
binds the final binaries in `kernel-identity.json`.

The CPU mock excludes the SYCL runtime and driver, Engine dispatch strings/maps
and native-only split launches. Native argument binding, errors and timing still
require hardware. MADV_WILLNEED plus reads cannot prevent later page eviction;
warm/cold residency estimates are not measurements. A major-fault decode must
remain labelled contaminated. The fresh real-eight host run completes in
1,750.06 seconds at 1,238,068 KiB
peak RSS. Its one-card immediate-preparation audit exercises actual callbacks
after staging; native two-card execution still needs the documented windows.

## Evidence and patches

The complete implementation and host overlay are in this directory. Evidence:
[build-receipt.json](build-receipt.json), [cpu-tests.json](cpu-tests.json),
[prepared-equivalence.json](prepared-equivalence.json),
[prepared-invalidation.json](prepared-invalidation.json),
[kernel-identity.json](kernel-identity.json), [LIFETIME.md](LIFETIME.md),
[REVIEW-INVALIDATION.md](REVIEW-INVALIDATION.md) and
[REVIEW-PREPARED-EVENTS.md](REVIEW-PREPARED-EVENTS.md). A `passed` field is current only
when its source and binary hashes match the final build.

Parent evidence remains under its original identities and is described in
`inherited-files.json` and `inherited/`. The new gate-log archive is
`evidence/preparation-logs-p35.json.gz`; retain it even above 1 MiB because its
commands and case outputs permit independent review. Every member is byte-verified
before disposable scratch is removed, then the final receipt is sealed. Read the
archive with gzip plus JSON; regeneration requires rerunning the same CPU gates.
Historical evidence is preserved.

## When to revisit

With the final CPU gates and binary-bound admission receipts passed, the
coordinator runs [WINDOW.md](WINDOW.md) one window at a time with the documented
card, environment, ldd, watchdog and graceful-stop rules. Measure real-plan host
enqueue time and W2c's family split; do not substitute no-op kernels. New native
receipts decide whether this implementation improves the actual model. Faults
need saved evidence and the existing coordinator recovery process; no retry,
hard kill, reset or unsolicited GPU launch is permitted. This packet closes CPU
preparation, not the optimization lane.
