# Packet 27: second kernel round over packet 26

This packet is CPU-prepared research code. **No device ran during preparation;
no packet 27 speed is claimed.** Arithmetic identity remains
`iq3-p17-detmath-v2`: same weight products, lane assignments, reduction trees,
rounding points and full-precision state/cache storage. The default dispatch is
packet 26's measured selection; candidates become defaults only through exact,
same-run K2 comparisons below 0.9 times that incumbent.

Packet 26's measured two-card result is 17.85 tok/s, about 55.4 ms per token:
11.3 ms issuing work on the host and 43.8 ms waiting on the cards. Its profiled
kernels sum to 53.5 ms over 2,426 launches. These overlapping timing definitions
are not added together. The reference target is 28.49 tok/s (about 35 ms/token).
The copied source identities are recorded in `source-proof.json`; complete build,
compiler, CPU-gate and binary identities belong to `build-receipt.json` after
successful sealing. Prior packets and their evidence remain read-only.

## Changes and measured questions

The pool timing fixture now seeds only previously completed pooled blocks after
its position changes. The newly completed block is still produced and checked.
The previous mismatch affected both implementations and was a harness defect.
K2 still records failed candidates and continues with remaining candidates.

Every viable packet 25 GEMV alternative is now an actual bridge kernel compared
with the runtime's own R5 kernel at the same decode shape and format, rather than
two columns pointing to R5. Output-byte equality, implementation identity,
median/p90 microseconds and comparison-candidate identity are explicit. The
historical staged weight-decoding arm is excluded as requested; the unused
half-table source remains evidence, not an unimplemented runtime dispatch entry.

The native priority guard accepts exactly the priority requested by its wrapper
and records it. W2/W2m/W2c run at nice 0 from a nice-0 coordinator; CPU preparation
and helper work stay at nice 19. No priority escalation is attempted.

| Class | Packet 26 time, microseconds | New mechanism | Hypothesis, microseconds |
| --- | ---: | --- | ---: |
| HC low + inject, each attention/FFN pair | 37–39 | compile-time two-member tuple, common ready normalized input | 22–27 |
| GDN a + b | about 19 | two concrete F32 members, one launch | 8–12 |
| router + shared expert gate/up + shared scalar gate | about 61 | four-member tuple, ready FFN normalized input | 34–42 |
| HC gate | 29.5 | original single GEMV; depends on low/activation | unchanged |
| shared expert down | about 16 | original single GEMV; depends on shared activation | unchanged |
| route / folded route+gather | about 68 | cooperative softmax, distributed early-out rank, selected normalization | 20–25 |
| QSA attention | about 264 | subgroup-sized score/value groups, one head maximum | 100–120 |
| GDN recurrence | about 53 | original state-row ownership with register values and identical shuffle tree | 30–35 |
| QSA select | about 68 | parallel block scores, stable ranks, disjoint suffix writers | 25–30 |
| argmax | about 297 in full decode | parallel chunk winners, exact tie order | 40–60 |
| expert gate/up | about 178 | packet25 wg32; reusable exact FP32 input | 140–175 |
| expert down | about 130 | private decoder; two short rows/subgroup; shared packed64 words | 90–125 |
| GDN qkv | about 101 | packet25 rows4; FP32 input or packed64 | 75–95 |
| GDN z | about 62 | packet25 wide8; FP32 input or packed64 | 45–58 |
| QSA qgate | about 118 | packet25 rows4; FP32 input or packed64 | 95–110 |
| attention output | about 67 | FP32 input or packed64 | 55–65 |
| logits | about 2,140 | every dense bridge alternative competes with actual R5 | 1,900–2,300 |

These ranges are design hypotheses, not measured improvements or projected totals.
The small tuples alone plausibly remove about 2–3 ms/token, so they do not claim
the requested 11-to-5-ms goal. Some small GEMVs remain separated by real data
dependencies. The card measurements must determine the next useful changes.

The minimum measured launch cost is 3.4–5 microseconds; 15–30-microsecond small
GEMVs also spend time on short row counts, idle subgroups and split finalization.
Their tuple bodies have format/rows/columns/variant fixed at compile time, typed
by-value pointer captures and no descriptor interpreter inside a row loop.
The schedule checks that all member inputs exist before fusion and remain
unchanged until their original sites. It rejects intervening writers, premature
consumers and card-boundary crossings.

The large-GEMV FP32 preparation shifts BF16 bits once and reuses that exact vector
across siblings until a writer changes the source. Packed64 loads change integer
access only. The two-row short-dot candidate keeps 32 virtual lanes per row,
the original product order and the original width-1-through-16 reduction tree.
No staged weight decode, R6 decoder, compressed KV or reassociated arithmetic
was introduced.

Read [small GEMV analysis](small-gemv.md), [large GEMV analysis](large-gemv.md),
and [non-GEMV analysis](round2-nongemv.md) for concrete shapes, dependency order,
source-level failure analysis and exactness arguments. Independent source reviews
record bit identity, write ownership and interpreter exclusion; their hashes and
resolved findings are retained with this packet.

## Gates and handoff

CPU gates cover unit tests, both mini card counts, default/all-new integration,
both host compilers with fresh-process fixture repeats, host execution of device
argument guards for every K1/K2 entry, sanitizers with randomized mini order,
entry exit codes, copy budgets, precision flags at compile and link, math grep,
and one-card layer-streaming real-model comparison for eight generated tokens
and 384 layer fixtures against the v2 oracle. Actual counts and pass/fail status
come from the sealed gate JSON; no unrun count or binary hash is asserted here.
The all-new real-model map exercises FP32 input reuse, packed64 and short-row
kernels. Mini large GEMVs explicitly retain their registered packed arithmetic;
new miniature tuple and non-GEMV kernels are still exercised.

K1a/K1b are fresh fixture processes, each with four sequential owners. K2 uses
packet 26's measured selection as its incumbent, tests every registered candidate
and production format, and writes a hash-bound measured table. A losing or failed
candidate never lowers that incumbent. W2 is the unchanged selection control;
W2m uses only K2's selected table; W2c profiles that same table. The latter two
require matching K0/K1a/K1b/K2/W0 identities and safe teardown.

Exact commands are in [WINDOW.md](WINDOW.md); timing estimates and independent
safety limits are in [DEADLINES.md](DEADLINES.md). The coordinator supplies shared
library paths and owns all device execution. Every launch is explicit; no server,
retry loop, driver discovery from CPU preparation, or host-setting change is
part of this packet.
