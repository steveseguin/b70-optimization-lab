# Packet 46: specialized layers and one-card CPU prerequisites

Work started at 02:01 UTC on October 17, 2026 on `steve-b70s`, from `main`
after `git pull --rebase` reported up to date. The owner's brief prohibits
builds and sustained CPU work until **02:55 UTC** while the four-card FP8
comparison runs. Preparation uses nice 19, cores 4–15 and 20–31, and Python
without bytecode writes. No device use, model payload reads beyond existing
fixtures, service actions or host-setting changes are authorized here.

Source design: [roadmap](2026-10-17-own-runtime-iq3-speed-roadmap.md),
[one-card plan](../experiments/own-xpu-runtime/ONE-CARD-DESIGN.md).
Packet45 and the protected A367/driver sources remain untouched.
All new code lives in
[`packet46-specialized`](../experiments/own-xpu-runtime/stage2/packet46-specialized/).

## Preregistered work

One ordinary GDN layer and one QSA layer, M=1 decode with 4K occupied context,
compare the current packet45 kernels to compile-time-specialized compositions.
Require every retained intermediate and state byte to agree on changing inputs
and fresh processes. Preserve FP32 rounding, reduction trees, BF16 stores and
state update order. Descriptor-interpreting fused kernels remain closed.
The integration bar is **at least 80 microseconds saved per layer**, measured
with GPU event durations by class. A lower launch count or faster host wall
time alone cannot pass. The coordinator alone runs the card-0 windows.

The CPU expert implementation must match the selected P39/P28 arithmetic using
only existing fixture generation. This Threadripper PRO exposes AVX2 and no
AVX-512 flags. Compilation started after the time boundary; sustained CPU throughput and
fresh-process CPU exactness are recorded below. Route-ID and phase diagnostics are
default-off and excluded from speed claims.

## Cache refinement

The metadata-only [budget](../experiments/own-xpu-runtime/stage2/packet46-specialized/CACHE-BUDGET.md)
corrects PLE history to the census's 184,320 bytes and accounts for aligned
slots and metadata. The 18 GB cache holds 9,082 experts; the total design leaves
681 MB beyond the unchanged physical reserve. This is not a device admission.
The hypothetical uniform route scenario requires 35.9268 GB/s and 18,157
expert evaluations/s at 60 target positions/s. Its hit rate is unmeasured.
Three metadata unit tests passed in 0.011 seconds before the build boundary;
no compiler, device binary or sustained test ran.

## Results and handoff

The default-off route/phase adapter and its strict JSONL validator are written
in `packet46-specialized/diagnostics/`. An offline cache report separates
accepted-token popularity from all executed work, including rejected work,
and labels partial layer coverage. Five Python schema/report test groups pass
in 0.002 seconds. After the boundary, the C++ mock compiled and two fresh processes produced
identical nine-record traces; both strict validations passed. This adapter is not installed in packet45.

The independently authored AVX2 CPU expert, exact arithmetic specification,
existing-fixture oracle comparisons and sustained benchmark are written in
`packet46-specialized/cpu-expert/`. The runner checks every worker's affinity,
FP environment and source/binary identity. Its 284,928,000-byte synthetic
packed bank preserves the 47:1 ordinary/exceptional layer mix. Both fresh compiled CPU tests passed 27,587 checks each, including 18 complete
expert comparisons and 30 finite down-row edge cases. Their raw-output digest
is identical. The [test receipt](../experiments/own-xpu-runtime/stage2/packet46-specialized/cpu-expert/evidence/test/receipt.json)
binds the arithmetic sources and binary.
Nonfinite device-oracle parity is explicitly unqualified.

The specialized layer source and coordinator windows are now written. The
static launch plan is GDN **35 → 28** and QSA **41 → 30**; these are expected
counts to assert on device, not measured speedups. The six exact cases include
changing positions/inputs and inactive, sticky-error and out-of-range controls.
Full mutable snapshots include scratch and padding without masks. Every timed
input pair also checks complete state and a clean error flag outside timing.
The final short Python gates pass all 17 tests (three budget, nine window and
five diagnostic groups). Both host and native builds pass. Each reused parent
object set reproduced its pinned packet45 binary byte-for-byte before reuse.
The CPU leaf gate passes 3,079 raw checks. Two fresh complete-layer processes
each pass 1,866 intermediate, logical-state and full-allocation comparisons;
each layer selects three distinct route sets. Both processes have identical
SHA256 `ee48f54c99d01d793e8a1de73169681dc40955a03c59d36540c005924dbb1785`
and retire safely. [Layer gate and retained files](../experiments/own-xpu-runtime/stage2/packet46-specialized/cpu-layer-gates.json).
The native program was compiled only and never executed.

The CPU expert benchmark ran at 02:55:39–02:56:00 UTC on the requested 24
logical CPUs, nice 19, with five samples of at least two seconds per fresh
process. The [full receipt](../experiments/own-xpu-runtime/stage2/packet46-specialized/cpu-expert/evidence/bench/receipt.json)
retains every sample and worker affinity. Results:

| Fresh process | Median packed GB/s | p10 packed GB/s | Median experts/s | p10 experts/s |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3.873152 | 3.260361 | 1,957.456 | 1,647.757 |
| 2 | 5.325281 | 4.742674 | 2,691.348 | 2,396.904 |

These are processed packed bytes, not measured DRAM bandwidth or engine speed.
The visible drift is retained; neither run is selected as a headline. Both
fall far below the hypothetical uniform-miss requirement of 35.9268 GB/s
and 18,157 experts/s. This CPU implementation cannot sustain that scenario.
Actual route locality, dependent ten-slot layer tails and CPU/GPU overlap are
still unknown. The next prerequisite is the opt-in IQ3 route census, followed
by a faster exact CPU path if observed misses still demand it.

The [CPU preparation seal](../experiments/own-xpu-runtime/stage2/packet46-specialized/seal.json)
passes with 317 source pins, five compiled artifacts and seven gate receipts.
Seal SHA256:
`ab9760f3f787dbb5bb35c01be97967b17f28654c6e5fa90635ca010cca479104`.
Native binary SHA256:
`613062382676d0df036deafdf08fdd99a903308aa1949ab8ee0f72444c8d1b41`.
All layer build/proof/mirror output totals about 53 MB; retained CPU layer
evidence is about 1.5 MB, with no individual new evidence file over 1 MiB.
The root disk still has about 23.7 GB free. No protected source was edited.

The coordinator can use the exact script-file commands in
[WINDOW.md](../experiments/own-xpu-runtime/stage2/packet46-specialized/WINDOW.md):
E1 and E2 on card 0, then T1 and T2 only after both exactness receipts pass.
The diagnostic adapter is ready for attachment to a future unsealed two-card
owner; it is not installed in packet45 or enabled in these timing windows.

Open risks: device intermediate/state agreement, actual native launch counts,
GPU timing and the 80-microsecond bar; the QSA tuple's serial split work may
cost performance. CPU nonfinite parity, actual cache hit rates, dependent
miss tails, live one-card memory peaks and engine integration are unqualified.
No model speed or one-card fit is claimed. The device coordinator retains
ownership. The [CPU expert closeout](../experiments/own-xpu-runtime/stage2/packet46-specialized/CPU-EXPERT-CLOSEOUT.md)
records the measured shortfall and the next conditions for revisiting it.
