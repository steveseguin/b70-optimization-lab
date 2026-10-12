# Packet 35: prepare the host issue path once

This packet copies packet 29's runtime and moves repeated host work out of the
two-card token loop. No device program ran during preparation. The measurements
below are CPU mock issue costs; they are not model throughput or GPU speed.

Each resident plan site is prepared after dispatch selection and buffer uploads.
Preparation resolves candidate names, geometry, device capabilities, validation,
allocation addresses, aliases and operation arguments once. The token loop checks
admission, drains both queues at card switches, then invokes the bound submission
callback. Normal token mode has no per-launch strings, map lookups, allocations,
device-info queries or clock reads in the application issue path. Checked and
class-timing modes retain their extra diagnostics. Content changes in the bound
token, cache and control buffers remain visible to the kernels.

The Engine owns an immutable plan and options. A token-boundary dispatch check
rejects a changed selection. Process-unique owner generations reject commands
after buffer release, explicit invalidation, shutdown or reuse of an owner's
address. A new configuration needs a new Engine and fresh preparation. One-card
layer streaming keeps the legacy path. Its CPU `--audit-prepare-each` mode prepares
and calls the actual host callback after staging each operation, so the real-eight
check can exercise capture without keeping a full second model in host memory.

## Measured CPU issue cost

The benchmark links the actual kernel-family host front ends and common owner
capture/issue code to a mock backend. It uses two warmups and nine measured
iterations of 2,048 sites per family. Values are median nanoseconds per launch;
the two-launch specialised and round2 sites are divided by their launch count.

| Family | Legacy ns/launch | Prepared ns/launch |
| --- | ---: | ---: |
| dense_r5 | 99.67 | 20.69 |
| experts_r5 | 98.31 | 10.06 |
| p25_gemv | 171.30 | 12.33 |
| p27_gemv | 172.01 | 12.29 |
| p28_gemv | 160.07 | 11.59 |
| p29_gemv | 209.32 | 8.06 |
| p27_input_prepare | 40.84 | 7.39 |
| small_gemv_fusion | 129.08 | 8.79 |
| specialised | 57.89 | 22.20 |
| round2 | 170.03 | 27.79 |
| packet18_parallel | 155.54 | 21.37 |
| combine | 26.58 | 7.60 |
| check | 52.08 | 9.83 |
| commit | 51.92 | 8.83 |

The prepared path made **zero hooked allocation calls across 294,912 measured
launches** in all 14 families. Pointer, operation-type and submission-order
comparisons passed. Scalar/array/aligned `new` and linked `malloc`, `calloc` and
`realloc` are counted. These hooks do not inspect allocation inside dynamically
linked SYCL or driver code. The benchmark excludes Engine string/map dispatch,
device arithmetic, native-only split launches and the SYCL runtime itself. It
therefore cannot predict how much of packet 29's measured host delay disappears.
Its pointer/type comparison is separate from the full argument serialization gate.

The measurement ran with inherited CPU affinity, nice 19, idle I/O priority and
`OMP_NUM_THREADS=2`; the receipt records its affinity, load and linked object
hashes. See [prepared-host-benchmark.json](prepared-host-benchmark.json) and
[prepared_issue_benchmark.cpp](prepared_issue_benchmark.cpp).

## Device code and submission forms

The kernel bodies, arithmetic, reduction order, local accessors, target weights
and full-precision KV representation are unchanged. The host overlay copies the
original command group by value and prebinds ranges. The compute callback makes
one application indirect call and then calls eventful `queue::submit`; prepared
copies use the `queue::memcpy` shortcut. Redundant dependencies on the preceding
command of the same in-order queue are removed. Both queues still drain on every
card switch.

Eventless submission is not used. The installed compiler offers it, but this
owner's bounded completion checks, failure handling and allocation lifetime rely
on real recorded events. A default event cannot stand in for unfinished work.
Moving the kernel functor to a new lexical site for a queue shortcut would also
risk changing device identity. Local accessors are left intact. See
[LIFETIME.md](LIFETIME.md) for exactly which event, profiling, submission-budget
and checked-layer guarantees remain.

The independent identity gate checks the unchanged closed kernel registry,
inner-kernel source hashes and SPIR-V kernel names plus executable instruction
hashes. It compares 24 embedded module slots, including the packet 29 expert-down
kernels; source names alone are insufficient. The refreshed build preserves original `#line` locations and passes the final
comparison: **24/24 SPIR-V modules and all 369 kernel names match exactly**.
[kernel-identity.json](kernel-identity.json) binds the final binaries;
[review-kernel-identity.md](review-kernel-identity.md) explains the independent proof.

## Selection and token preparation

K2 now compares a qualifying fusion's measured cost with the sum of its selected
member costs. It records both numbers, compares each FFN format separately, keeps
the fusion only when cheaper in every workload, and selects members on a tie.
Missing measurements fail admission. The HC aliases count as one low plus one
inject operation. Replaying packet 29's historical measurements on CPU restores
all three small fusions:

| Fusion | Fusion time | Selected members' sum |
| --- | ---: | ---: |
| HC | 15.625 us | 20.104 us |
| GDN A/B | 4.583 us | 7.292 us |
| FFN Q6 | 20.521 us | 32.5515 us |
| FFN Q8 | 14.687 us | 31.978 us |

These are historical packet 29 device measurements, not packet 35 results.
[k2-selection-regression.json](k2-selection-regression.json) binds their source.
W2x also accepts an explicit coordinator `--dispatch-override` file. Its kernels
must be covered by both K1 runs; an override is not labelled a K2 winner.

After device uploads finish, startup requests the embedding and PLE pages with
`MADV_WILLNEED` and reads every page, retaining the mappings. The lookup tables
total **29,321,610,240 bytes**. There is no mlock, cache drop or system setting
change. A warm pass is estimated at roughly **2–10 seconds** at 3–15 GB/s plus
page-fault overhead; a cold pass roughly **15–75 seconds** at 0.4–2 GB/s. These
are planning estimates, not measured warm/cold results. They can grow under
contention. Read-ahead is best effort: it does not pin pages or guarantee future
residency.

Every token records prepare time, total host enqueue time, process major/minor
faults and issuing-thread voluntary/involuntary context switches. The receipt
records CPU affinity and the one-minute load average at start. A decode window
with any major faults explicitly says `PAGE-FAULT CONTAMINATED`. Such a window
cannot establish clean host/kernel timing just because its tokens matched.
Per-family issue times are measured only in class mode; token mode writes null
family times to avoid adding per-launch clock reads.

## Verification and coordinator handoff

The independent window protocol tests pass 102/102. The prepared owner/copy
invalidation tests pass 13/13 under ASAN/UBSAN with leak detection. The current
argument-state census covers 14 operation definitions and 17 state members.
These are CPU checks, not permission to infer native token equivalence.

Fresh CPU suites now pass: **234 integration cases**, **32 sanitizer runs**,
fixtures and argument validation, alongside the packet's precision and lifetime
checks. The fresh real-eight host run passes **8/8 tokens and 384/384 layers**,
with **192,114 full argument comparisons** through immediate preparation after
one-card staging. It took 1,750.06 seconds and peaked at 1,238,068 KiB RSS. The
two-card mini equivalence gate passes **6/6 cases and 1,887 argument blocks**.
All required CPU gates pass. Copied parent `passed` fields remain historical
evidence; admission uses the final packet 35 source/binary-bound receipts. Use
[build-receipt.json](build-receipt.json),
[cpu-tests.json](cpu-tests.json), [prepared-equivalence.json](prepared-equivalence.json)
and [prepared-invalidation.json](prepared-invalidation.json), not this prose, as
admission evidence. [REVIEW-INVALIDATION.md](REVIEW-INVALIDATION.md) records the
independent
stale-binding review and fixes. [REVIEW-PREPARED-EVENTS.md](REVIEW-PREPARED-EVENTS.md)
independently reviews the final submission/event ownership and fault protocol.

[WINDOW.md](WINDOW.md) provides exact K0, K1a, K1b, K2, W0, W2, W2m, W2c and W2x
commands with explicit card selection. [DEADLINES.md](DEADLINES.md) keeps separate
watchdog, submission and graceful-drain bounds. A nice-0 coordinator may use
`taskset`; wrapper and child inherit its affinity. This CPU preparation agent
has not run any of those commands.

The device issue benchmark must time the real plan in its normal W2 window using
`enqueue_loop_ms`; W2c supplies the diagnostic family split. No real plan with
no-op replacement kernels is admitted as a device issue benchmark. Native
prepared arguments, asynchronous failures, checked-layer localization, individual
submission budgets and throughput still need the coordinator's device windows.
No device speed is claimed here.

## Evidence retention

The inherited packet 29 files are the parent runtime and its history, not fresh
packet 35 passes. `inherited-files.json`, `source-packet29.json` and `inherited/`
preserve that distinction. Historical fixture, failed-candidate and kernel notes
remain useful evidence; their old performance/qualification statements do not
admit this new binary.

New CPU preparation logs are retained in
`evidence/preparation-logs-p35.json.gz`, with every member byte-verified before
disposable scratch removal. Even above 1 MiB, it is retained because the per-case
commands and gate outputs are required to audit this packet; unpack its JSON with
Python gzip/json readers. It can be regenerated only by rerunning the recorded CPU gates against the same
source/model/toolchain identities. Do not replace it with a summary or delete
older evidence because it overlaps. Build trees and disposable scratch stay
ignored; the sealed build receipt records binary hashes and rebuild inputs.
