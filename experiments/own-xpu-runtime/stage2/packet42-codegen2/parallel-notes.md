# Parallel classes: prepared, no device run

The candidate native binary is `build/parallel/parallel-native`. K0 uses
`--compile-smoke`; K2 omits it. Both require `--card N --output DIR
--repetitions 200 --authorized-device-window`. The root window wrapper owns
admission, new-fault watching, receipts, and summaries. The dense entry links
into the root GEMV program. CPU-only rebuilds are `python -B parallel_build.py`
and `python -B parallel_gates.py`, under the owner’s nice/ionice environment.

## Attention projection

`p42.dense.fourparts` keeps four independent FP32 lane accumulators and four
unchanged adjacent subgroup trees. Lane 0 finishes `((p0+p1)+(p2+p3))` and rounds
once to BF16. It uses one subgroup per **row**, replacing four subgroups per row
and the finish kernel. It does not claim to retain one subgroup per row part:
separate subgroups cannot share four partials without a memory synchronization
mechanism. Adding local memory/barriers to the chosen `p28.dense.wg32` incumbent
was forbidden. The alternative trades parallelism for one fewer launch and no
partial-buffer traffic; timing must decide. It supports only Q6_K/Q8_0, K6144,
Split4, one nonrouted matrix.

The original finite-scale path is already better than a lexical loop count
suggests. `parallel-dense-path.json` selects B016–B022 and B026/B028/B030,
excluding exceptional-scale B023–B025. Each full eight-weight tile has 209
SIMD instruction issues and 17 memory messages (scale once plus eight weight
and eight input loads); inner B021 executes eight times. The new unrolled body
has 201 issues in its first part and 203 in the remaining parts, also 17
messages. These are 26.125 versus 25.125–25.375 instruction issues per weight
**per logical lane path**, not a scalar instruction count across the whole
subgroup. Each part has six tiles. The small decrease is consistent with a
modest segment improvement; it cannot establish the cause of the measured
6% versus 17–25% differences across other shapes. Split4 also retains reduction
and finish costs in the segment-only case. The new no-finish alternative tests
that overhead directly. Whole-function counts are 351 instructions/12 static
messages for one incumbent part versus 1074/71 for the four-part candidate;
those totals have different work and are not speed predictors.

## Route

The measured five-stage route history is extracted, with source SHA256, in
`parallel-route-events.json`. The production adapter’s specialised stages have
200-sample medians 3.333, 20.312, 2.604, 37.500, and 3.021 microseconds.
They are maxima, exp/subtrees, normalization, stable rank, and selected
normalization/descriptor completion. The standalone route_gather fixture has
its own separately labeled rows and must not be substituted for the adapter.

The ng-only diagnostic `p42.route.rank32` keeps stages 0, 1 and 4
byte-for-byte arithmetic and merges
stages 2/3. There is one subgroup per element; each lane compares 16 elements
and the integer adjacent tree combines ranks. Every comparison uses the same
FP32 division as before, preserving probability-rounding ties and lower-ID tie
priority. It performs more divisions and many more subgroups, a deliberate
trade to remove the serial 512-comparison lane and one launch. No local memory
or barrier is added. The retained stages have the same generated counts:
590/39, 13520/75, and 268/16 instructions/static messages. The merged stage is
453/22, replacing 156/12 plus 1216/79. Counts include conditional divide paths;
whole-function totals are static, not dynamic performance estimates. There
remain 512 comparisons per element, 262144 per route, distributed over lanes.
The ng upper 16-subtree FP32 tree is unchanged; no floating sum is reordered.
These counts apply to the route_gather diagnostic, not the timed production
route class. The production adapter port is separately implemented and gated
in `route42*`, with its actual five-stage submission path, 16-element partial
trees and folded U32 descriptor ABI; see `route42-notes.md`. Only that
production entry can use the route class-times group count for dispatch.

## GDN recurrence

`p42.gdn.token1` specializes the incumbent subgroup program to one token and
compile-time flags. Four products per lane retain left-to-right addition from
+0; all four 32-lane reductions retain their original adjacent trees. State
rounding and store order stay unchanged. The terminal subgroup barrier has no
subsequent token read to protect in this one-token candidate. The general
multi-token implementation remains the incumbent. The source-level terminal
barrier was already absent from the selected incumbent GEN count, so removing
it is not claimed as a generated-code speedup. Compile-time flags remove
arithmetic branches: flags2 has 2374 instructions/21 static memory messages,
compared with 2825/24 for generic recurrence. Flags10 gives 2373/21. No new
local memory or barrier appears. CPU tests cover plain, packed and F32-runtime
weights, inactive control, sticky error, and invalid position.

## Gates and evidence

`parallel-gates.json` records GCC and Intel clang, two fresh processes each,
20,108,976 byte comparisons per process, zero failures. Tests compare the
reference core, the incumbent, and candidate host arithmetic. Direct rank
helper gates include varied positive denominators, ties, signed zeros and
nonfinite predicate diagnostics; nonfinite routes themselves follow the
reference rejection path. Odd-length rank partitions cover 1,3,17,255,512.
The dense output and every intermediate lane sum use exact byte equality.

`parallel-codegen.json` selects final GEN only where the `.dat` bytes match the
ELF text section, with zero padding allowed. `parallel-evidence/` retains
compressed assembly; incumbent evidence is copied from packet33 with its
original identity. `parallel-current-binary-proof.json` confirms the examined
SPIR-V bytes still occur in the final rebuilt binary. `parallel-build.json`
records the final binary hash and commands. The native event ABI uses the
packet26 class/candidate/variant/repetition/stage_count/event/start_ns/end_ns
vocabulary, with host wall durations in `walls.jsonl`. Device byte checks run
against the frozen reference; candidate failures are recorded before teardown.
Storage, driver, timeout and submission infrastructure errors fail the window.
Output bytes feed SHA256 incrementally, avoiding a large raw output file.

No speed estimate is a measurement. There was no device discovery or execution
in this preparation session. Device exactness and timing remain pending.
