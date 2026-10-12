# Packet 42: launch floor and code generation, round 2

Prepared on 2026-10-12 for one coordinator-controlled B70. **No device binary,
device discovery or GPU kernel ran. No speed is claimed.** The local binaries
are ready for K0 compile smoke, T1 launch-floor measurement, then K2 candidate
screening. Exact commands are in [WINDOW.md](WINDOW.md); hashes and input seals
are in [build-receipt.json](build-receipt.json).

The measured packet29 class ledger attributes roughly 8 ms/token to about
1,400 small launches. Packet37 selected about 4.3 ms/token expert down and
4.0 ms/token expert gate/up. Those are historical measurements, not packet42
results. Sources: [class ledger](../packet29-merged/receipts-cards01-20261012-chain/w2c-r29/class-times.json),
[packet37 selection](../packet37-merged2/receipts-cards23-20261012-chain/README.md).
T1 asks which launch form is cheapest; K2 checks whether exact reshaping and
specific generated-code changes help the actual classes.

## T1: the missing launch-floor measurement

The operation is an exact element-wise BF16 input → FP32 add 1 → BF16 output.
N is 1, 32, 640, 2560, 6400, 10240 or 25600. The matrix covers plain range,
WG32 lane-0 work, WG32 all-lane work and WG256 all-lane work; required SG32
on/off, unused local accessor on/off, barrier on/off for nd_range, arguments
by value or a pointer block, and one/two/four launches. Range barriers are
invalid and excluded explicitly. This makes 1,176 matrix rows. Four additional
rows submit 1,000 identical tiny kernels in a row, with 200 repetitions each.
The runtime Device submission path and profiling events are used throughout.

Each row retains 200 GPU-event sums and 200 host submission-through-completion
wall times, medians and p90, with exact output checks. The burst reports both
whole-burst and per-launch times and a ratio against its matched single launch.
The generated table includes failed rows. Its one-paragraph rule names the
cheapest passing form at each N after measurement; there is no invented winner
in this CPU preparation. [Design](launch-design.md), [native source](launch_floor.cpp),
[summary](launch_summary.py). Offline floor assembly contains 65 images: the
unused local accessor is optimized away, and explicit nd_range barriers add
three messages. Both subgroup-attribute choices emit SIMD32 here. These are
compiler findings, not measured launch costs.

The [tiny inventory](tiny-inventory.md) maps runtime sources to their current
geometry. Direct activations, HC mix, MoE and convolution retain each arithmetic
leaf while changing element ownership to range/WG32/WG256. Cooperative gated
norm, QSA prepare/pool/select and norm preserve their original reduction nodes,
odd-tail zeros, barriers and local storage. Complementary entries cover status
checks, streams, commits, HC combine and norm stages. No new local memory or
barrier is introduced into an incumbent that does not need it. Which current
shape costs more is deliberately pending T1 and the class-specific K2 rows;
assembly alone cannot answer that question.

## K2: candidates and assembly evidence

Instruction figures below are **conditional GEN path counts**, not cycles.
Expert figures are issued SIMD instructions/messages for weights processed by
one active lane; they are not scalar counts across all 32 lanes. Counts use the
finite full-interior path. Whole-function counts are labeled separately.

| Class | Candidate and intended change | Incumbent → candidate assembly |
|---|---|---|
| Paired IQ2_S gate/up | `p42.gate.packed`: packed table/input loads, shared addressing, validated 32-bit offsets | Per 16 weights: 392 instructions/22 messages → 429.5/16; candidate unrolls two tiles, 859/32 per 32 weights |
| Paired IQ3_S gate/up | Same candidate, own weight bytes preserved | Per 16 weights: 418/22 → 459/18 |
| Expert down | `p42.down.select_vector`: select lookup plus packed input/code loads | Per 8 weights: homogeneous select path 290–306/17 → 249–265/7; mixed-arm union 482 → 441 instructions |
| Expert down diagnostic | `p42.down.bank_scalar`: isolate scalar loads with bank lookup | Per 8 weights: bank 188/7 → 288/11 |
| Attention projection, Q6_K K6144 Split4 | `p42.dense.fourparts`: four exact lane accumulators/trees, final `((p0+p1)+(p2+p3))`, one launch | Per 8 weights: 209/17 → 201–203/17; removes finish launch |
| Production route | `p42.route.production_rank32`: combine normalization/rank, distribute 512 comparisons over SG32 | Five launches → four; rank performs 16 comparisons per lane; static stage totals below |
| GDN recurrence | `p42.gdn.token1`: specialize token count and flags | Whole-function 2825 instructions/24 messages → 2374/21 (flags2), 2373/21 (flags10) |
| Tiny classes | `p42.tiny.*`, `p42.extras.*`: preserve arithmetic; replace launch/mapping | Direct leaves remove unused scratch/guard barriers; per-kernel counts in tiny/extras evidence |
| QSA select | `p42.extras.select.wg256` | Stage0 static 1519/271 → 1155/223; stage1 379/25; original barriers retained |
| Streams / combine / PLE | `p42.extras.*.range` | Static 453/32 → 279/14; 930/44 → 744/24; 466/43 → 279/24 |
| Checks / commit / begin | `p42.extras.*` | Static 234/13, 40/6, 39/5 respectively, zero local memory/barriers versus generic 32 KiB scratch |

Expert down's faster historical select kernel has **more** instructions and
messages than bank. Thus neither count establishes its bottleneck. Dependent
variable lookup versus independent predicate alternatives is a latency or
occupancy hypothesis; select-vector and bank-scalar test the cross-combinations.
The split4 dense path already has little instruction-count headroom; its segment
form leaves reduction/finish costs. Four independent subgroups cannot combine
without synchronization. This packet instead keeps four exact parts in one
subgroup per row, reducing parallelism while eliminating finish traffic. That
trade needs card timing. No claim is made that one subgroup per part survives.

Production route historical stage medians are 3.333, 20.312, 2.604, 37.500 and
3.021 us. Actual production adapter static instruction/message counts are
298/26, 873/32, 270/25, 1779/132, 1529/169; candidate stages are 133/11,
705/16, 926/55, 1363/154. The rank comparison loop is parallel, not a new
serial 512-element loop. The FP32 normalization divisions, tie rules, top-10
odd-tail tree and descriptors stay exact. The separately implemented
`p42.route.rank32` on a route_gather fixture remains diagnostic and cannot
populate production route dispatch.

Detailed reasoning, final GEN block selections, source/SPIR-V hashes and
compressed assembly: [experts](expert-report.md), [independent blind expert
assembly reading](launch-expert-blind-review.md), [dense/GDN/diagnostic route](parallel-notes.md),
[actual production route](route42-notes.md), [tiny inventory](tiny-inventory.md),
[complementary tiny classes](extras-notes.md). Offline analysis selects final
GEN whose bytes match the compiled ELF text, not an earlier compiler dump.

## Gates and limits

Both host compilers run in two fresh processes, using existing fixtures plus
odd lengths, ties, invalid routes and control/error cases. CPU tests compare
the reference core and the incumbent, including intermediate reductions where
applicable. These are CPU identity gates; the coordinator must still pass exact
on-card output/status equality before any timing row can enter dispatch.

| Family | Recorded CPU checks |
|---|---:|
| Experts | 335,620 qualified checks × 4 processes = 1,342,480 |
| Expert nonfinite diagnostics | 533,028 × 4; candidate/incumbent bytes agree; frozen-reference exceptions remain visible |
| Dense, GDN and diagnostic route | 20,108,976 byte comparisons × 4 = 80,435,904 |
| Actual production route | 120 cases × 4 = 480; 134,400 byte checks |
| Main tiny families | 240 fixtures × 4 = 960 Core checks; 720 geometries × 4 = 2,880 |

Complementary tiny gates pass 19 fixture Core, 76 fixture geometry, 675 flat
geometry, 610 compact/scheduled incumbent/Core, and 240 in-place geometry
checks per process. Across four processes those are 76, 304, 2,700, 2,440 and
960 checks respectively.
See [extras-cpu-gates.json](extras-cpu-gates.json).
The 15 [CPU window tests](protocol-tests.json) exercise all three windows through a mock
native program and the real summary, including missing libraries, failed cases,
new versus historical faults, missing /proc fields, and ENOSPC during writes.
Mocks are test data, never device measurements.

Packet29 excludes nonfinite GEMV from production qualification. GNU retains
256 frozen-reference nonfinite lane differences per process; candidate versus
incumbent matches raw bytes. Intel's ordinary host optimization also exposed a
qNaN payload difference in a tiny activation; strict host floating-point mode
restores exact Core agreement. The diagnostic is retained, device flags are
unchanged, and native tiny gates check nonfinite/control scenarios explicitly.
Neither issue is hidden by NaN-category or tolerance comparisons.

Independent reviews: [identity](identity-review.md), [parallel families](expert-review-parallel.md),
[actual route](extras-review-route42.md), [complementary tiny](expert-review-extras.md),
[wrapper](expert-review-wrapper.md). Review findings were fixed before sealing.

## Coordinator outputs and reproducibility

K2 compares each candidate with its incumbent through the runtime submission
path, takes 200 repetitions and rotates eight full payload banks for GEMVs
above 8 MB. It retains GPU events and host wall times, continues ordinary failed
cases, and sorts `table.md` by measured ms/token saved using ledger frequencies
(47 IQ2 + 1 IQ3 gate groups). Missing or failed cases cannot enter
`dispatch-measured.json`; the schema is `packet26.dispatch.v1`. A 10% screening
threshold keeps ties and smaller changes on the incumbent. These are class
screening results, not an end-to-end model claim. See [INTEGRATE.md](INTEGRATE.md).

The wrapper forwards LD_LIBRARY_PATH verbatim, checks libraries before device
contact, uses its own journal cursor, and latches only new GPU faults. Receipt,
format, refusal and storage errors are failed windows, not GPU faults. Failures
are written before graceful teardown. No retry, hard kill, or automatic reset.
Estimated durations and watchdog rules are in [DEADLINES.md](DEADLINES.md).

This packet uses local, hash-recorded packet29/33 objects and existing fixtures;
it is a coordinator preparation on this checkout, not a standalone published
runtime recipe. Build scripts retain exact compile/link commands. `seal.py`
records local source, read-only dependency, gate and native binary hashes and
checks disk budgets. Ignored `build/` retains executable/object/SPIR-V inputs
for the window; compiler dump scratch is removed after compressed evidence is
verified. Source and compressed evidence remain here for review/rebuild.

[Closeout](CLOSEOUT.md) records the CPU preparation boundary.
[Do not repeat](DO-NOT-REPEAT.md) records methods and failures to preserve.

[Retention record](RETENTION.md) explains the large route CFG artifact and
restoration of compressed evidence.

## Sealed coordinator binaries

| Local binary | SHA-256 |
|---|---|
| `build/launch/p42-launch-floor` | `a06df687f86fba805ffbecb0584d372982705055b5278640d748199debc35364` |
| `build/gemv/p42-gemv` | `c728efbb256487c3e72dc9a46cc215523fe433935e858a9e84564fec7cdf2e54` |
| `build/parallel/parallel-native` | `89a91eb8e12229c72e231a0bda1da129313be337e37d01ca53bd67855609ba93` |
| `build/route42/p42-route` | `62ebd4c8b76b3dfd02e968d2e0cb5724931e707f50352c309ca23b85ad24571e` |
| `build/tiny/p42-tiny` | `acd86240a7755a4bd8791948a059863ae6f56b8b52003e2aa752a21b4e603c66` |
| `build/extras/p42-extras` | `bd2331a4567030b8101ea58d46b7a0ddbc4ebb3e0084398968d893f03e99a00c` |
