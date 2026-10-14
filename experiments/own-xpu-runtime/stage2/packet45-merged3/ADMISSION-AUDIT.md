# Packet45 complete admission-path audit, October 14

Scope: the merged coordinator, every `admit_output` call, its nested KD and
suite producers, host/device allocation checks, retention, timeout and fixture
identity gates. This audit is CPU-only. No device binary was executed, no
`/dev/dri` descriptor opened, no discovery or sudo used. Existing incident and
device window directories are read-only inputs.

The checked-in source assigns **1.1 GB to K1a/K1b and 2.5 GB to K2**. The
owner's reported `reserve write=2500000000` is exactly reproduced by the old
cap arithmetic, but the supplied label K1b differs from that source mapping.
No receipt is relabeled to resolve this discrepancy. The fix covers both
windows and all subsequent windows.

## Every admission constant and consumer checked

| Consumer / constant | Verdict and evidence |
|---|---|
| `storage.admit`: 8,000,000,000 free-byte floor | Preserved. The full next write and another full chain must fit above it. Boundary/negative-input tests refuse exhausted space. |
| Old aggregate 3,000,000,000 build cap | Stale. Now the base allowance in a finite structural ceiling; actual cap is also bounded by current `df` headroom. Exact arithmetic in [CAPACITY](CAPACITY.md). |
| Structural chain: 9 windows, capacity 32768, 13 requests, 16 retained steps | Checked against coordinator order and immutable default suite of 12 prompts plus warm-up. Reserve 11,486,186,752 bytes; structural cap 14,486,186,752. Repeats do not increase this ceiling. |
| `window.main` 64,000,000 CPU substitution | Removed. Rehearsal uses actual capacity, request count, retained-step count, live aggregate build size, cap and filesystem reserve. All are retained per window and recomputed by the seal. |
| `run_fixtures` whole-window admission | Same real K0/K1/K2 projection in CPU and device paths. Both former CPU substitutions removed. |
| Per fixture child: 16,000,000 K0, 550,000,000 K1, 2,500,000,000 K2 | Retained. Whole-window check is 32 MB / 1.1 GB / 2.5 GB; per-child check accounts for existing earlier child output. No artifact deletion assumed. |
| K0/W0p 32,000,000 | Retained. Packet44 trees below 46 KB; W0p also rechecks this reserve before its 1,000 handovers. |
| K1a/K1b 1,100,000,000 | Retained. Packet44 raw-output/log reconstruction below 25 MB; merged CPU full fixture matrix tests the extra p39 owner. Fresh maximum-capacity merged output is 23,397,496 bytes plus 3,024 linked bytes, also below the reserve. Both children remain sequential. |
| K2 2,500,000,000 | Retained. Full66-grid bound is 2,159,371,200 output bytes plus logs/metadata, not packet44's smaller grid. The original rejection is reproduced under a patched 3 GB cap without allocating gigabytes. |
| W2/WS/WSs/WS128x old 550 MB + 16 MB/request | Incomplete at larger capacity. Now full state reserve is `550000000 + 13*2368*(C-256)`, plus 32 MB per request and additional retained-step copies. |
| 13 BF16 caches, 2368 bytes/position/cache | Checked against memory plan: twelve target caches and one draft. No KV precision change. Draft-rank placement changes ownership, not the sum. |
| Retained layer: 48 layers × 20,480 bytes, two copies | Checked against `collect_fixtures` and checker shape `[1,4,2560]` BF16. Rank files and checker hardlinks coexist; build_size counts both paths, so budgeting both logical extents conservatively over-reserves physical disk. Additional steps reserve `2*48*20480` each per request. This covers WS128x's 16 steps and custom larger retention. |
| KD old 566,000,000 projection | Now `550000000 + 3*2368*(C-256)`; host capture and two fresh owner captures coexist until comparison. At 32768 this reserves 780,965,248; packet44 retained two-owner tree is 168,958,989 bytes. |
| KD nested reference bytes +32 MiB / +16 MiB | Data-derived, retained. Count actual authenticated capture members before host launch and each device launch; full-window reserve additionally covers three copies. Rehearsal uses miniature capture sizes internally but the outer full-scale reserve remains mandatory. |
| KD log compression: raw size +2,000,000 | Retained. Verified lossless compression before unlink; failure preserves raw bytes. Generic archive admission also bounds base64/gzip coexistence. |
| Suite RESET old miniature 8,000,000 bypass | Removed. Every RESET reserves the same context-dependent full state dump, including CPU rehearsal. Raw states are hash-bound and removed before the next request; no two raw request snapshots accumulate. |
| Suite `run_request` 8 MB mini / 32 MB real | Uses the same real 32 MB plus extra-retention formula in both paths. No miniature storage exemption remains in a coordinator request. |
| State-retention archive: compressed bytes +1 MB | Data-derived, retained. Exact packed size known before write; temporary file round-trip and hashes checked before deleting state. |
| Window compression: size + size/1000 +2 MB | Retained, covers gzip coexistence. Oversized `output.bin` threshold 20 MB stays hash-only after authenticated native/launcher provenance, never a second gzip copy. |
| General archive: retained size ×4/3 +4096/member +1024/member +1 MB | Retained, explicit base64/JSON/gzip worst case. Uses zero build growth only when destination is outside build; filesystem reserve always charged. |
| `admit_output` output inside/outside build | All five consumers checked: pre-window, fixture stage, fixture child, canary, compression. Build growth charged only inside build; full filesystem growth charged everywhere. Nested suite/KD generic `admit` is conservatively charged to build even for external output. |
| KD `MemAvailable` 16 GiB; isolated-owner anonymous guard 8 GiB | Retained. Host reference exits before either device owner; owner captures are sequential. Full draft weights/cache plan remains below 3.5 GB per owner. No new target-rank co-residency in KD. |
| W2 and suites `MemAvailable` 97 GiB | Retained. All six capacity/placement plans plus 29,321,610,240 host-table bytes and pinned/IPC allowances fit. Minimum margin 13,774,577,010 bytes. Exact rows in audit JSON. |
| Legacy `memory_admission`: sum owned +29,321,610,240, reserve 0 | Only legacy `fixture_support.execute`, not `window.main`; current merged path uses 97 GiB plus capacity/placement-specific live census. The table allowance is explicitly included in the six-plan comparison; old census never substitutes for merged census. |
| Device allocation capacity 34,242,297,856; free margin 1,500,000,000 | Preserved. Six plan rows and live allocation sum checks; worst planned free margin is 2,498,639,158. Driver residency remains a device observation, not claimed by this audit. |
| Memory-plan base weights/reserves, 22/26 vs 24/24, 839,321,600 duplicated head, strict images | All retained and covered by the 65 memory-plan tests. Rank0 image 701,213,368/781,005,336 at maximum capacity is hashed in place in request inventory, not duplicated in disk dumps. Full constant/source inventory is in audit JSON. |
| CPU qualification: 8/9 GB aggregate anonymous, transport 8 GiB, per-process 8 GB AS | Preserved. Mini/real campaign watches plus inherited stricter transport limit. Full six-case real gate rerun records actual peak. Never run alongside heavy compilation. |
| CPU gate writes: 100/150/250 MB setup/mini, 1.3 GB real | Active merged harness, retained. Full max-capacity state output stays below real reserve; evidence is archived and verified before scratch removal. Largest packet44 raw state is 1,111,809,016 bytes. |
| Active CPU-only `capacity_fixture_gate` secondary 3 GB cap, 100 MB arm / output-size+1 MB compression | Retained private qualification limit; passes at the current 1.55 GB build. It is never called by coordinator windows. After accumulating device chains it can intentionally refuse a future CPU fixture campaign; no cleanup authority is implied. |
| Legacy `capacity_cpu_gate` 4 GB secondary cap, 20 MB mini or 550 MB +26 caches | Historical runner only, absent from packet45's seal/campaign; could refuse a manual legacy invocation with retained chains. Not a device admission path or an alternative merged qualification. Its two-copy reserve and stricter private cap are intentionally not silently relaxed. |
| CPU draft capture private 3 GB build cap / 8 GB free floor / 8 GB anonymous; 150 MB arm, actual-size+1 MB archive, 300 MB retained-reference maximum | Retained. CPU-only six-arm generator, not coordinator KD. Maximum-capacity capture is under 85 MB per arm; all six retained captures together fit 300 MB. Fresh campaign reruns all six and their archive receipts. |
| CPU selection compile: 8 GB free floor; HC helper 20 MB before each compile | Retained. Sequential bounded CPU compiles; helper binaries tiny and final retained build identity rechecked. These do not launch device windows or select their budgets. |
| Build preparation 100 MB; configure 350 MB; fixture/capture-specific CPU reserves | Retained as CPU producer reservations, not coordinator storage plans. No full runtime rebuild in this repair. Current retained build fits these gates; fresh CPU fixture, compiler and capture stages rerun them. |
| Context choices 256/4096/32768; suite caps 32/64/128; prompt+output ≤context; repeat ≥1 | Retained and exercised by 78 mocked combinations and final no-launch admission. Manifest determines cap; long32 at context256 refuses. Repeat request count enters storage projection. |
| K2 time estimates 485/555/2867 +17 seconds; watchdog 14400 | Retained. Worst required minimum is 11536 seconds, below 14400. K2 capacity grids and 65 timing classes remain required on device. CPU zero timing must fail the separate speed gate. |
| K0/W0p 30/600; K1 120/10800; KD 1800/10800; W2m 2100/10800; WS 7200/30000; WS128x 14400/60000 | Expected/watchdog seconds retained. Repeat scales expected and watchdog; ≥4×(expected+17), ≥300 and ≤172800 checked before launch. All 63 window/context combinations checked by audit. |
| Child wait 600s; cooperative drain 65s; postflight 5s; kernel poll 0.1s | Retained, bounded lifecycle checks, no retries or device restart. No timeout is relabeled as a storage failure. |
| Owner count and fixture coverage | Previous named five-owner repair retained. Full fixture matrix, p33 216 checks/36 splits, current p39/length-grid formulas and freshness checks rerun. No stale four-owner or fixed pre-merge fixture-count gate introduced. |
| Identity: boot/cards/context/draft/seal/artifacts/env/input/dispatch | Preserved. Changing host source/seal invalidates partial chains. Device artifact values themselves need not change for a host-only repair. |

The machine-readable [audit](evidence/storage-admission-fix/admission-audit.json)
contains 63 window/context projections, all six memory rows, every predecessor
receipt hash, authenticated state-retention receipt sizes, and a source/line
inventory of numeric literals in seventeen admission-related modules. Numeric
shape, token and formatting constants in that inventory are not storage caps;
their existing arithmetic/fixture gates remain unchanged. The wrapper receipt
binds the audit hash, and the seal rechecks its source closure.

## Packet44 measurement interpretation

`window.json.storage_admission.admitted_write_bytes` is a **reservation**, not
measured writes. `build_bytes` measures the whole build tree at admission;
differences can include other windows and coordinator cleanup. The audit does
not relabel either as isolated per-window disk I/O. All twenty local window
receipts match their checked-in sealed copies. Current tree sizes and raw
sizes from authenticated retention receipts provide the comparison below.

For suites the conservative peak estimate is current retained tree + original
log/fixture bytes + largest serial state dump. Cumulative state-write totals
are recorded separately: repeated RESET writes can total many GB while only
one raw state survives. At 32768 packet44's coordinator deleted W2m state
bytes; that row cannot establish its original full peak. The recorded build
growth from W2m to WS128 was 1,125,115,454 bytes, consistent with the retained
suite state sizes, but it is not claimed as isolated W2m I/O.

Fresh device behavior, allocator residency, and filesystem changes by other
processes remain outside CPU proof. Admission is a real refusal gate, not a
promise that any number of future chains can run without a new capacity check.


## Predecessor measured sizes versus new projections

All byte values are exact logical file sizes. The conservative peak column
is the reconstruction described above, not a physical I/O counter.

| Context | Packet44 window | Retained tree bytes | Largest recorded state dump | Reconstructed peak | Packet45 projection |
|---:|---|---:|---:|---:|---:|
| 4,096 | K0 | 41,963 | 0 | 41,963 | 32,000,000 |
| 4,096 | K1a | 1,072,299 | 0 | 24,434,606 | 1,100,000,000 |
| 4,096 | K1b | 1,072,309 | 0 | 24,434,616 | 1,100,000,000 |
| 4,096 | K2 | 13,453,885 | 0 | 136,403,535 | 2,500,000,000 |
| 4,096 | KD | 33,168,510 | 0 | 33,168,510 | 577,279,360 |
| 4,096 | W0p | 45,945 | 0 | 45,945 | 32,000,000 |
| 4,096 | W2m | 242,479,026 | 0 | 242,479,152 | 700,210,560 |
| 4,096 | WL | 66,879,595 | 229,170,166 | 296,049,887 | 764,210,560 |
| 4,096 | WS128 | 253,316,242 | 229,170,168 | 482,486,536 | 1,084,210,560 |
| 4,096 | WS64 | 447,391,273 | 229,170,166 | 676,561,565 | 1,468,210,560 |
| 4,096 | WSs128 | 240,330,385 | 219,464,058 | 459,794,569 | 1,084,210,560 |
| 32,768 | K0 | 42,034 | 0 | 42,034 | 32,000,000 |
| 32,768 | K1a | 1,090,378 | 0 | 24,456,045 | 1,100,000,000 |
| 32,768 | K1b | 1,090,388 | 0 | 24,456,055 | 1,100,000,000 |
| 32,768 | K2 | 14,047,231 | 0 | 139,415,828 | 2,500,000,000 |
| 32,768 | KD | 168,958,989 | 0 | 168,958,989 | 780,965,248 |
| 32,768 | W0p | 45,954 | 0 | 45,954 | 32,000,000 |
| 32,768 | W2m* | 90,910,913 | 0 | 90,911,039 | 1,582,849,408 |
| 32,768 | WS128 | 321,212,404 | 1,111,809,016 | 1,433,021,546 | 1,966,849,408 |
| 32,768 | WS64 | 515,288,636 | 1,111,809,014 | 1,627,097,776 | 2,350,849,408 |

*W2m at 32768 is incomplete because its raw states were deleted in packet44;
its listed size is not an upper bound on the original peak. WS64 has two
repeats (25 requests including warm-up); other suites have 13, long WL has 3.

## Host memory against merged plans

| Context | Draft rank | Device + host table + pinned/IPC bound | Required MemAvailable | Margin |
|---:|---:|---:|---:|---:|
| 256 | 0 | 88,992,588,430 | 104,152,956,928 | 15,160,368,498 |
| 4,096 | 0 | 89,156,264,590 | 104,152,956,928 | 14,996,692,338 |
| 32,768 | 0 | 90,378,379,918 | 104,152,956,928 | 13,774,577,010 |
| 256 | 1 | 88,157,704,686 | 104,152,956,928 | 15,995,252,242 |
| 4,096 | 1 | 88,330,473,966 | 104,152,956,928 | 15,822,482,962 |
| 32,768 | 1 | 89,620,484,590 | 104,152,956,928 | 14,532,472,338 |


## Complete coordinator CPU rehearsal: exact admission receipts

All 27 windows passed. `used + projection < effective cap` was checked with
real aggregate build usage and `df` free space. No 64 MB substitute was used.
The suites contain twelve miniature prompts; each reserves thirteen requests
including warm-up. These receipts qualify host orchestration, not device speed.

| Context | Draft rank | Window | Projected bytes | Build used bytes | Effective build cap | Result |
|---:|---:|---|---:|---:|---:|---|
| 4,096 | 0 | K0 | 32,000,000 | 1,554,684,874 | 13,588,328,138 | PASS |
| 4,096 | 0 | K1a | 1,100,000,000 | 1,554,688,502 | 13,588,298,998 | PASS |
| 4,096 | 0 | K1b | 1,100,000,000 | 1,579,092,328 | 13,588,221,032 | PASS |
| 4,096 | 0 | K2 | 2,500,000,000 | 1,603,496,153 | 13,588,175,833 | PASS |
| 4,096 | 0 | W0p | 32,000,000 | 1,605,573,437 | 13,588,123,197 | PASS |
| 4,096 | 0 | KD | 577,279,360 | 1,605,584,988 | 13,588,065,116 | PASS |
| 4,096 | 0 | W2m | 700,210,560 | 1,605,846,080 | 13,587,769,152 | PASS |
| 4,096 | 0 | WS | 1,084,210,560 | 1,609,718,107 | 13,586,627,675 | PASS |
| 4,096 | 0 | WSs | 1,084,210,560 | 1,686,800,992 | 13,582,437,728 | PASS |
| 4,096 | 1 | K0 | 32,000,000 | 1,761,467,030 | 13,578,055,062 | PASS |
| 4,096 | 1 | K1a | 1,100,000,000 | 1,761,470,662 | 13,578,025,926 | PASS |
| 4,096 | 1 | K1b | 1,100,000,000 | 1,785,874,492 | 13,577,980,732 | PASS |
| 4,096 | 1 | K2 | 2,500,000,000 | 1,810,278,322 | 13,577,935,538 | PASS |
| 4,096 | 1 | W0p | 32,000,000 | 1,812,355,610 | 13,577,891,098 | PASS |
| 4,096 | 1 | KD | 577,279,360 | 1,812,367,165 | 13,577,833,021 | PASS |
| 4,096 | 1 | W2m | 700,210,560 | 1,812,628,301 | 13,577,537,101 | PASS |
| 4,096 | 1 | WS | 1,084,210,560 | 1,816,500,270 | 13,576,395,566 | PASS |
| 4,096 | 1 | WSs | 1,084,210,560 | 1,893,864,866 | 13,572,225,186 | PASS |
| 32,768 | 0 | K0 | 32,000,000 | 1,969,276,993 | 13,567,826,753 | PASS |
| 32,768 | 0 | K1a | 1,100,000,000 | 1,969,280,626 | 13,567,797,618 | PASS |
| 32,768 | 0 | K1b | 1,100,000,000 | 1,993,705,757 | 13,567,740,957 | PASS |
| 32,768 | 0 | K2 | 2,500,000,000 | 2,018,130,886 | 13,567,651,526 | PASS |
| 32,768 | 0 | W0p | 32,000,000 | 2,020,249,986 | 13,567,607,938 | PASS |
| 32,768 | 0 | KD | 780,965,248 | 2,020,261,552 | 13,567,549,872 | PASS |
| 32,768 | 0 | W2m | 1,582,849,408 | 2,022,013,631 | 13,567,241,663 | PASS |
| 32,768 | 0 | WS | 1,966,849,408 | 2,028,122,435 | 13,566,096,451 | PASS |
| 32,768 | 0 | WSs | 1,966,849,408 | 2,106,014,447 | 13,561,929,199 | PASS |
