# Arithmetic v3 design sketch — conditional, no oracle job

2026-10-17. Packet52 is a speed-ceiling probe. No winner is selected, no new
full-model oracle is generated, and packet49c retains
`iq3-p49-split32-v1`. The candidate combined identity is provisionally
`iq3-arithmetic-v3-p53-v1`; its final identifier and source hashes must be
frozen only after coordinator E/T receipts select its exact class/order map.
Old packet17/47/49 identities, receipts and output records remain immutable.

## Decision before the oracle expense

Proceed only when one fixed set of deterministic per-class candidates saves
**at least 120 us per ordinary M1 layer in both independent timing owners**
against the contemporaneous current controls. The same winner/order per
class must account for both owners; do not pick a different best arm for each
owner and sum incompatible configurations. Keep unchanged classes at zero
saving and count each subtotal once (particularly both HC sides and the
four-member small FFN tuple). Count every split/reduction/epilogue event.
M2, numeric distance and estimated bandwidth are information, not substitutes
for the M1 rule. The probe's selected sum is a component estimate, not an
end-to-end model-speed result.

Pending receipts mean **undecided**, not a negative result. If complete admitted
receipts miss the bar, record every per-class ceiling and a negative closeout;
do not spend the five-hour oracle cost on this identity. If they pass, freeze a
selection artifact with class, shape/format, exact order ID, epilogue contract,
both owner timings, E byte-equality receipts and source/binary hashes before
starting packet53. No tolerance or closeness to the old order qualifies an arm.

## Exact proposed orders and scalar mirror

The source authority for these probe orders is [freeorder.hpp](freeorder.hpp).
Each uses BF16 input values widened exactly, FP32 weight decoding, separate
FP32 product then add, and one BF16 projection boundary. Compiler contraction
and reassociation remain disabled. Workgroup scheduling and table placement
are not floating-point ordering authorities.

For K columns, let `tiles=K/8`. With `S` parts, part `p` owns eight-value tiles
`floor(tiles*p/S)` through `floor(tiles*(p+1)/S)-1`. With `L` lanes per row,
lane `l` starts at `begin+8*l` and advances by `8*L`. Within a tile, evaluate
columns in ascending `j=0..7`. For `A` accumulators, all eight products of tile
iteration `t` add to accumulator `t mod A`; initialize each accumulator to
positive zero. For A2, form `sum0+sum1` after all tiles; for A4, form
`(sum0+sum1)+(sum2+sum3)`. Reduce the L lane
values with the explicit adjacent binary tree (widths 1,2,4,…); never use an
implementation-defined reduction. With four parts, write four FP32 partials
and use exactly `(p0+p1)+(p2+p3)` in the second stage. No BF16 cast occurs
between parts. The CPU mirror can execute every scalar operation in that
order regardless of GPU scheduling.

| Probe order | L / A / S | Device rows per SG32 | CPU arithmetic change | Question |
| --- | --- | ---: | --- | --- |
| `row16-v8` | 16 / 1 / 1 | 2 | 16 strided tile chains and adjacent16 tree | Can fewer lanes per row and more independent rows improve work supply despite longer chains? |
| `row8-dual-v8` | 8 / 2 / 1 | 4 | Eight tile chains, alternate tiles between two accumulators, add them, adjacent8 tree | Can four rows/subgroup and two independent accumulators compensate for longer lane work? |
| `split4-row16-v8` | 16 / 1 / 4 | 2 row-parts | Four contiguous tile partitions, adjacent16 trees and exact final four-part tree | Does shorter serial work repay partial writes and a second launch? |
| `row16-dual-local` | 16 / 2 / 1 | 2 | Two alternating accumulators per lane, adjacent16 tree; same decoded weights | Does extra arithmetic independence plus locally staged IQ2 codebook help? |
| `row32-quad-v8` | 32 / 4 / 1 | 1 | Four rotating tile accumulators per lane, `(a0+a1)+(a2+a3)`, adjacent32 tree | Does a shorter dependency chain help without a split buffer or second launch? |

All arms use contiguous eight-activation vector loads and the admitted
production byte layouts. The local-table arm stages the compact 1024-entry
16-bit IQ2 magnitude representation in workgroup-local memory. Scalar CPU
arithmetic must decode the same signs, half scales and nibble-scale sequence.
Table residency has no CPU numerical counterpart: its reference uses the same
logical table values. For Q6/Q8/F32/IQ4, that table has no role in decoding;
the dual-accumulator mapping still distinguishes the arm. Do not ascribe any
speed gain to local tables on formats that do not use them.

For the unsplit K2560 controls, each SG32 lane previously executed ten tiles
and 80 dependent additions. `row32-quad-v8` distributes those ten tiles as
3/3/2/2 across its four accumulators: **24/24/16/16 additions**, averaging20,
followed by the explicit accumulator tree. Its longest chain is24 additions,
not20. In contrast, `row16-dual-local` has20 tiles/lane and ten tiles per
accumulator, so each chain still has80 additions. The quad arm directly tests
shortening that dependency without a second kernel or split scratch; its
extra live accumulators and merge operations can still offset the benefit.

The five variants change several mechanisms together; their purpose is a small
ceiling screen, not a factorial attribution study. Exact differences from the
current order must be retained as information (FP32 distance where captured,
BF16 changed outputs, maximum absolute/relative difference and hashes with
finite/nonfinite accounting). Byte equality is demanded against the candidate's
own mirror and across fresh processes, not against the old arithmetic.

## Class selection and boundaries

No row in this table is selected yet. The final selection artifact fills an
order ID or `unchanged` for each class. These are future integration contracts;
packet52's finite, valid-active probe does not itself qualify invalid routes,
sticky errors, inactive calls or the full exceptional-input policy. Those
remain mandatory packet53 gates before model use.

| Candidate class | New scalar dot path if selected | Preserved boundary / exclusions |
| --- | --- | --- |
| IQ2_S expsgate pair | Both gate and up use selected lane/part sequence over K2560 independently | Ten routed experts; per-projection BF16 before existing activation; layer2 IQ3_S remains old order |
| GDN QKV Q6 | Selected K2560 row, 10240 outputs | BF16 QKV before convolution; layer2 Q8 QKV remains old order |
| IQ4_NL expsdown | Selected K640 row for each expert's activation | Ten expert outputs and BF16 boundary before old mixture order |
| Attention output/combine Q6 | Selected K6144 row, 2560 outputs | BF16 projection, then same exact four-stream injection/combine; QSA split32 itself remains unchanged |
| HC low+gate on both sides | Selected Q8 K10240 low and K320 gate orders | Low BF16 then exact activation then gate; preserve HC exceptional-value handling and both sides; final HC is excluded unless separately qualified |
| Small FFN tuple | Selected order for router F32, both shared Q6 projections, scalar F32 gate | Four separate matrices and all BF16 outputs; do not silently change a same-shaped nonmember |
| GDN Z Q6 | Selected K2560 row, 6144 outputs | BF16 projection before gating; layer2 Q8 Z remains old order |

The ordinary layer has all seven classes; matching layer counts differ across
the model. The IQ2 and ordinary small-FFN cases occur in 47 layers, Q6 GDN
QKV/Z in 35, attention output in 48. Do not multiply the ordinary-layer sum by
48 and present it as total model savings. Layer2 and QSA require their own
engine fixtures even when their excluded GEMVs stay on the old order.

## Actual CPU oracle paths that would change

The current oracle generator is
[packet49 oracle/build.py](../packet49-integrate/oracle/build.py). It verifies
frozen source identities and generates a private source tree from packet17's
`runtime_main.cpp`, `performance.cpp`, `performance.hpp`, `runtime_kernels.*`,
`arithmetic.hpp`, `core_v2.hpp`, `detmath.hpp` and `rope.hpp`, plus the registered
suite driver. It currently changes the arithmetic ID and replaces QSA's scalar
attention body with the independent packet49 split32 reference. Packet53 must
make a new generator/output directory; it must not edit that running oracle's
source, build, completion manifest or service.

The real GEMV call chain is:

1. [packet17 `Engine::linear`](../packet17-detmath/runtime_main.cpp) has the
   launch label and makes dense or routed matrix descriptors.
2. [packet17 `performance.cpp`](../packet17-detmath/performance.cpp)
   `dense` / `experts` call the host `Multiply::run` operation. It selects
   the expert and row, checks route validity, calls the scalar row reference,
   and writes BF16. Gate/up currently pass arithmetic variant2 to both
   matrices; dense calls carry the shape-selected arithmetic variant.
3. [packet17 `arithmetic.hpp`](../packet17-detmath/arithmetic.hpp) maps
   type/rows/K/experts to a variant and delegates to the old SG32/split4 row
   references. `arithmetic::row` has no semantic class argument today.

A blanket replacement of Q6 decoding or of `arithmetic::row(type,K,variant)`
is therefore wrong: several classes share K2560 and may select different
orders, while exceptions and draft/final paths must retain their identities.
Add an explicit immutable class/order selector at `Engine::linear`, where the
launch label is available, and carry the selected order through `dense` /
`experts` into `Multiply`. The scalar-order implementation belongs in a new
oracle-owned header. Key the selection by semantic class plus checked format,
rows, K, expert count and target/draft role. Fail closed on a selected class
whose geometry differs. Unselected calls delegate to the original reference.
Record the complete selector in the arithmetic identity.

The full CPU oracle continues to decode **original packed GGUF bytes**, not
GPU-repacked rows. Its scalar decoder must independently establish equal
weight values against the probe's admitted p48/expanded layouts. The new
header should implement the above ordering in ordinary scalar loops and
explicit partial arrays, rather than invoke the GPU `lane()` helper. Compare
it bit for bit to the packet52 mirror on every selected shape, tails, routed
slot and admitted exceptional input before the expensive full model run.
Include cross-compiler, cancellation-heavy and BF16-boundary fixtures.

`core_v2.hpp` retains packet49 split32 QSA, deterministic nonlinear functions,
BF16 state/KV and existing gate/combine boundaries. A GEMV order change does
not authorize changing exp, sigmoid, state precision or recurrence. The full
model's CPU oracle can differ in token sequence from the old one; retain the
old-versus-new report for review without using it as a tolerance gate.

## Oracle cost and one combined identity

Budget **about five hours with two CPU workers**, as supplied by the current
brief's observed campaign progress. This is a planning estimate, not a newly
measured packet52 runtime. The older packet49 README's prior estimate was
6–12 hours; preserve that historical estimate rather than rewriting it.
New scalar orders may change the CPU cost. Measure a bounded scalar fixture
first and report any revised estimate before launching the future oracle.

Batch every selected class into one source-bound identity and one complete
oracle campaign. Use the same registered twelve prompts, capacity4096,
128-token model suite, captured layer steps, repeat coverage and KD stream
capture contract as packet49 unless a separately registered extension is
required. Retain completion, per-prompt hashes, full fixture identities and
fresh-process repeat. Two workers and nice19/cores4–15,20–31 remain upper
limits, not authorization to interfere with the protected packet49c window.
Packet52 starts **no oracle job**.

## Packet53 follows packet49c's integration shape

Start a new packet from the source-bound packet49c closure after its final
qualification status is known; preserve sealed packets. Integrate only the
frozen selected orders into the corresponding engine dispatch sites. Keep
packet49c's route/HC/attention scheduling improvements wherever the selection
does not supersede their arithmetic. Retain independent old-order controls
and every negative result. Audit ordinary submission and prepared-command
capture/replay together: both must reach the same selected dot implementation.
Update allocation/partial scratch accounting and retained-output admissions
before compiling. No extra cache, changed weight source or compressed KV is
part of v3.

Use packet49c's early **K0 → K1a → K1b → K2 → W0p** structure, with the new
order fixtures and complete producer/state coverage, then wait for the new
hash-bound oracle before **KD → W2m → WS → WSs → WS128x → WS128**. Include
ordinary GDN, layer2 exception, QSA, target/draft, M1 and both serial M2 rows,
active/inactive/error paths, invalid routes/positions, every mutable output,
and deterministic fresh owners. Same-device old/new equality is no longer
the pass criterion for changed arithmetic; new CPU/new GPU equality is.
Untouched operators and behavior still require their original exact gates.

The twelve-prompt 128-token WS128 record remains an internal model gate and
does not satisfy the separate fixed 512-token publication gate. Keep timing,
quality and promotion decisions separate. GPU ownership, admission, cooldown,
fault handling and script-file windows remain the coordinator's responsibility;
no packet52 step touches the oracle or packet49c units.
