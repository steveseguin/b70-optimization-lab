# Packet 28: specialised GEMV candidates, CPU preparation only

No device program ran during preparation. No candidate has a measured speed or is
admitted to the runtime. Arithmetic identity remains `iq3-p17-detmath-v2`.
The prepared G2 compares the actual packet26 R5 entry before each candidate;
`summary.py` refuses a class whose baseline differs by more than 15% from the
in-model GPU event sum. Packet25's slower substitute baseline is not reused.

## Source and arithmetic

Current dense: [packet10 expanded value/lane](../packet10-kopt5/expanded.hpp)
and [gemv](../packet10-kopt5/kernels.cpp). Current experts:
[packet8 decode8/dot](../packet8-kopt3/decode.hpp) and
[packet9 Projection](../packet9-kopt4/kernels.cpp). G2 calls
[packet26 performance.cpp](../packet26-specialised/performance.cpp) directly,
with its [R5 selector](../packet26-specialised/arithmetic.hpp) and its exact
[packet6/7/8 compile overlay](../packet26-specialised/kernel_overlay.py).
That overlay is applied only in our ignored build mirror. Source packets stay read-only.
The [tensor manifest](model-tensors.tsv) records the plan read for type/shape coverage.

Every weight value retains its original rounding before multiplying x; additions
stay in each lane's eight-consecutive-elements then 256-column tile order. The
32-lane adjacent-pair tree and `(p0+p1)+(p2+p3)` split tree remain unchanged.
Each gate/up output is rounded separately to BF16. No reassociation, FMA, fast math,
compressed cache, or changed model bytes are introduced.

Expanded Q6 has one FP32 scale per 16 signed-byte codes; expanded Q8 has one per 32.
Tile starts are `begin + 256*t + 8*lane`; production split bounds are multiples
of 256. Eight divides 16 and 32, proving each active tile stays in one scale group.
The dense implementation also splits arbitrary unaligned tiles at each group boundary;
CPU fixtures exercise this additional case. IQ4_NL K640 ends with 16 active complete
lane tiles. Inactive lanes participate in shared-scale operations using a safe block
but read no activation and accumulate no product.

IQ2/IQ3 grids are converted to byte arrays at compile time from the existing credited
format data. Weight loops load bytes rather than uint64 grid words. Wide integer
operations used to construct constexpr format data are never device weight-loop work.
Exceptional IQ scales retain magnitude-then-sign multiplication. Expanded exceptional
scales use the old per-weight `value()` expression. Paired expert candidates reuse each
converted x for two independent accumulators. Private and shared metadata candidates
are measured separately. New captures are by value, statically bounded at 1024 bytes;
there is no device descriptor table. Native pointer address formation remains native width.

## Per-weight source operation counts

Counts below describe explicit source work in a full eight-weight lane tile, divided
by 8, before compiler common-subexpression elimination. They are not assembly counts.
All paths keep one input product and one ordered add per weight, plus the same tree.
Scale multiplication and code/input conversion count 1 each in every quantised path.

| Family | Current → candidate work per weight beyond product/add |
|---|---|
| Expanded Q6/Q8 (D) | scale address1→1/8; scale byte loads4→1/2; FP32 assembly3 shifts+3 ORs→3/8 each; code byte1→1; code conversion1→1; input conversion1→1; format branch specialised away; exceptional test **0→1/8** |
| IQ4_NL (N) | half conversion1/32 shared→1/8 private (or1/32 shared); half byte loads2/32→2/8 private (or2/32 shared); scale broadcast1/8→0 private (or1/8 shared); code byte1→1; nibble shift1→1; level lookup1→1 signed byte; exceptional test1/8→0 because old fallback has the same value equation |
| IQ2_S (I2) | uint64 grid load1/8→0; uint64 shift1→0; byte magnitude lookup0→1; index/sign fetched1/8→1/8; scaled-NaN test1→1/8; half exception test1/8→1/8; metadata broadcasts2/8→0 private (or2/8 shared); paired input conversion1→1/2 across gate+up weights |
| IQ3_S (I3) | grid loads2/8 promoted into uint64→0; uint64 magnitude shift1→0; byte magnitude lookup0→1; two indices and sign per tile unchanged; exceptional tests/broadcasts/input conversion as I2 |
| Raw F32/BF16 (R) | no quant scale, quant code, grid lookup, or exceptional-scale work before or after; raw decode and input conversion1→1; BF16 weight NaN quieting unchanged |

The original `expanded::value` has an IQ-only NaN test. Q6/Q8 compile it out.
It would be incorrect to claim eight exceptional tests were removed from these dense
kernels. Their new once-per-tile check exists to choose the requested fallback.
Route validity is currently checked once per lane/row, not once per weight; the new
bridge retains that check. Dense candidate shape/format selection is on the host;
T, K, split count, output pairing and geometry/metadata policies are template constants. Loop bounds use32-bit integers. IQ4's actual
packet9 baseline uses ConstantTables, so it does **not** broadcast its16-level table
per weight; only half scales are shared. No fictitious table-broadcast saving is claimed.

## Class coverage and planning numbers

The current group time is the measured sum of all baseline GPU events in a logical
class call, from [class-times.json](../packet26-specialised/receipts-cards01-20261011-native-w2m/class-timing-run-b/class-times.json).
Launches/token comes from its `launches / tokens`; groups/token is also shown because
raw split4 GEMVs use two events. G2 sums all candidate events before comparison.
Type/shape variants sharing one dispatch class must all pass and beat0.9× baseline
in both owners before that class changes. A conservative minimum saving across
variants is used for the sorted table, avoiding invented format-frequency weights.

| Class / fixture | Shape per projection | Current R5 path | Operations | Current us/group | Launches; groups/token | Hypothesis or admission target us |
|---|---|---|---|---:|---:|---|
| expsgate.iq2 | 640×2560, count 10 | packet9 packed SG32 | I2 | 177.92 | 48; 48 | admit <160.13 |
| expsgate.iq3 | 640×2560, count 10 | packet9 packed SG32 | I3 | 177.92 | 48; 48 | admit <160.13 |
| expsdown | 2560×640, count 10 | packet9 packed SG32 | N | 130.13 | 48; 48 | ≈71 (hypothesis); admit <117.12 |
| gdn.qkv.q6 | 10240×2560, count 1 | packet10 expanded Q6 | D | 100.65 | 36; 36 | ≈48 (Q6 hypothesis); admit <90.59 |
| gdn.qkv.q8 | 10240×2560, count 1 | packet10 expanded Q8 | D | 100.65 | 36; 36 | ≈48 (Q6 hypothesis); admit <90.59 |
| gdn.z.q6 | 6144×2560, count 1 | packet10 expanded Q6 | D | 62.03 | 36; 36 | ≈22 (Q6 hypothesis); admit <55.82 |
| gdn.z.q8 | 6144×2560, count 1 | packet10 expanded Q8 | D | 62.03 | 36; 36 | ≈22 (Q6 hypothesis); admit <55.82 |
| qsa.qgate | 12288×2560, count 1 | packet10 expanded Q6 | D | 118.00 | 12; 12 | admit <106.20 |
| qsa.k | 512×2560, count 1 | packet10 expanded Q6 | D | 10.81 | 12; 12 | admit <9.73 |
| qsa.v | 512×2560, count 1 | packet10 expanded Q6 | D | 10.54 | 12; 12 | admit <9.49 |
| attention.gdn | 2560×6144, count 1 | packet10 expanded Q6 | D | 66.74 | 48; 48 | admit <60.07 |
| attention.qsa | 2560×6144, count 1 | packet10 expanded Q6 | D | 66.74 | 48; 48 | admit <60.07 |
| ple.key | 10240×2560, count 1 | packet10 expanded Q8 | D | 102.62 | 1; 1 | admit <92.35 |
| ple.value | 2560×2560, count 1 | packet10 expanded Q8 | D | 38.52 | 1; 1 | admit <34.67 |
| hc.a.gate | 10240×320, count 1 | packet10 expanded Q8 | D | 29.34 | 48; 48 | admit <26.41 |
| hc.a.low | 320×10240, count 1 | packet10 expanded Q8 | D | 18.38 | 48; 48 | admit <16.54 |
| hc.a.inject | 4×10240, count 1 | packet8 raw split4 | R | 18.76 | 96; 48 | admit <16.89 |
| hc.f.gate | 10240×320, count 1 | packet10 expanded Q8 | D | 29.50 | 48; 48 | admit <26.55 |
| hc.f.low | 320×10240, count 1 | packet10 expanded Q8 | D | 19.76 | 48; 48 | admit <17.79 |
| hc.f.inject | 4×10240, count 1 | packet8 raw split4 | R | 19.37 | 96; 48 | admit <17.43 |
| final.gate | 10240×320, count 1 | packet10 expanded Q8 | D | 29.82 | 1; 1 | admit <26.84 |
| final.low | 320×10240, count 1 | packet10 expanded Q8 | D | 18.06 | 1; 1 | admit <16.25 |
| qsa.iq | 512×2560, count 1 | packet8 raw split4 | R | 16.07 | 24; 12 | admit <14.46 |
| qsa.ik | 128×2560, count 1 | packet8 raw split4 | R | 10.39 | 24; 12 | admit <9.35 |
| router | 512×2560, count 1 | packet8 raw split4 | R | 20.17 | 96; 48 | admit <18.15 |
| gdn.a | 48×2560, count 1 | packet8 raw split4 | R | 10.00 | 72; 36 | admit <9.00 |
| gdn.b | 48×2560, count 1 | packet8 raw split4 | R | 9.12 | 72; 36 | admit <8.21 |
| shexpgate.q6 | 640×2560, count 1 | packet10 expanded Q6 | D | 16.40 | 48; 48 | admit <14.76 |
| shexpgate.q8 | 640×2560, count 1 | packet10 expanded Q8 | D | 16.40 | 48; 48 | admit <14.76 |
| shexpup.q6 | 640×2560, count 1 | packet10 expanded Q6 | D | 15.22 | 48; 48 | admit <13.70 |
| shexpup.q8 | 640×2560, count 1 | packet10 expanded Q8 | D | 15.22 | 48; 48 | admit <13.70 |
| shexpdown | 2560×640, count 1 | packet10 expanded Q8 | D | 15.75 | 48; 48 | admit <14.18 |
| shared_gate | 1×2560, count 1 | packet8 raw split4 | R | 8.91 | 96; 48 | admit <8.02 |
| logits | 248320×2560, count 1 | packet10 expanded Q6 | D | 2136.48 | 1; 1 | admit <1922.83 |

Bound hypotheses refer to [clean bounding code and card0 receipt](../bounds-20261011-gemv/README.md):
48.1us gdn.qkv,21.9us gdn.z,71.2us expert-down. Those simplified encodings omit real
fallback/route overhead and cannot establish a packet28 speed. Other rows only state
the admission threshold; no unsupported timing prediction is substituted for a measurement.
Four rows/work-group and one subgroup/work-group are each present. Split4 with four
rows uses 16 subgroups and local partials; single-subgroup split4 uses a second final
reduction event, included in its measured sum. This preserves the original arithmetic.

`hc.*.inject`, router, gdn.a/b, and shared_gate are raw F32 today. qsa.iq/ik are raw
BF16. hc low/gate, shared-expert projections, and ple.key/value are quantised expanded
paths. Other ple.* operations are norms, lookup, gating, convolution, and addition,
not GEMVs. They are outside this GEMV dispatch and must not be relabelled expanded.

## Gates and limits

[Dense CPU receipt](dense-cpu-receipt.json), [expert CPU receipt](expert-build-receipt.json),
[CPU aggregate](cpu-tests.json), and [build receipt](build-receipt.json) bind source,
compiler flags, binary hashes, repeated outputs, argument checks and protocol tests.
Independent reviews: [dense](review-dense.md), [experts](review-experts.md),
[bridge](review-bridge.md), [admission](review-admission.md).

CPU mixed-NaN fixtures expose compiler-dependent NaN payload/sign choices. All
non-NaN bits must agree; CPU receipts separately count both-NaN encoding differences.
This is **not full exceptional-output bit certification**. Native G2 requires exact
new/current bytes, including NaNs, and allows only host/card NaN encoding differences
when both are NaN. A candidate that fails is recorded and excluded while other
candidates continue. There is no canonicalisation of kernel outputs. Runtime K1/K2
and the v2 oracle remain mandatory after integration.

See [WINDOW.md](WINDOW.md) for coordinator commands, [DEADLINES.md](DEADLINES.md)
for budgets, and [INTEGRATE.md](INTEGRATE.md) for the subsequent runtime gates.

CPU preparation receipt:34 G2 workloads across28 dispatch classes and78 new entries;
112 positive device-argument entries (34 original +78 new),546 malformed entry checks,
579 bridge fixtures per compiler/process. Per-family suites add7,890,288 arithmetic
comparisons and1,451,529 range/validation checks per process. GCC and icpx each ran
in two fresh processes.15 protocol regressions passed. All non-NaN outputs agree;
exceptional NaN encodings remain explicitly unqualified pending native bytes.
Final capture size/count and binary SHA256 are authoritative in build-receipt.json
and kernel-sizes.json. Sealed native executable: `build/device/g2` (ignored).

A coordinator addendum landed on main while this packet was being prepared:
[grid-format bound](../bounds-20261011-gemv/bound-grid.cpp) and
[receipt](../bounds-20261011-gemv/run-grid-card0.txt) measure byte-grid stand-ins
at128.0us (one row/work-group) and130.7us (four rows), against178us in-model.
This gives gate/up a128–131us planning anchor. It is not real GGUF layout or a
packet28 measurement. The uint64 stand-in is126.2–126.7us in that separate study,
so bytes alone are not proven faster there; the proposed saving requires the whole
metadata/branch/broadcast change and still needs G2. No protected file was modified here.
