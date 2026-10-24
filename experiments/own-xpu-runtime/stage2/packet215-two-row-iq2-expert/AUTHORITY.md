# P215 arithmetic authority

This is a standalone synthetic HOST_ONLY gate/up proof for the selected IQ2_S,
K2560, N640, top10, wide64 and halfcache shape. It is not an Engine integration,
native kernel qualification, model result or speed measurement. The actual
selected frozen `p58ag::expert` GNU Host operator supplies the M1 control;
`p49dvirtual::host_row<IQ2_S,2560,8>` supplies the separate scalar oracle.
The selected source is byte preserved except for one pinned include relocation.

The fixture compares all 51,200 output bytes and 168 status/error bytes per case,
including invalid routes, unwritten tails, zero-count valid routes, active flags
and sticky errors. Both gate and up retain original route-slot order. Four cases
use all 640 output rows; shorter cases exercise duplicates, different slices,
backing addresses, generations and half-table storage, plus cancellation,
signed zero, subnormal, infinity and NaN scales. Exceptional classes occupy
separate output rows, with independent decoded-tile bit comparisons.

Matching is a stable one-to-one slot-multiset match, not set intersection.
Both backing pointers/generations and half-table storage must agree before
sharing. The full 512-entry tables point into 21 compact synthetic banks;
unused entries deliberately alias. This internal raw-pointer fixture provides
complete disjoint buffers but does not prove production extent, lifetime or
alias admission. Host CPU arithmetic is real; event and queue ownership use
the inherited simulated backend.

## Retained failures

The first attempt compiled but refused exact equality in the exceptional-scale
case. Its exact source, logs and receipt remain in
[evidence/cpu-1792805663473210614/receipt.json](evidence/cpu-1792805663473210614/receipt.json).
The original binary and dependency file remain locally under ignored
`build/first-arithmetic-failure`; their recovery pins are in
[first-failure-retention.json](evidence/first-failure-retention.json).
That attempt did not emit prior-case output summaries or a positive shutdown
receipt; process exit and source cleanup intent are narrower evidence.

A separately reviewed diagnostic-only attempt left candidate arithmetic and
exact comparison unchanged. Its
[diagnostic failure record](evidence/diagnostic-failure.json) binds the raw logs,
13 preceding passing case summaries and explicit safe Host teardown. The first
actual differing output was second input row, gate projection, slot 0, output
row 6, with all ten half scales `0x7e11`: candidate BF16 `0x7fc0`, selected and
scalar BF16 `0xffc0`. Status/error bytes matched. Recomputed diagnostic FP32
results were `0xffc00000` for selected/scalar/candidate-single and `0x7fc00000`
for candidate-paired row 1. These recomputations localize the discrepancy;
they do not replace the captured-output equality gate. The diagnostic binary
and dependency file remain locally under `build/diagnostic-arithmetic-failure`.
No equality tolerance, NaN normalization or arithmetic-control edit is allowed
by this proof. The reviewed targeted correction preserves the accumulator sign and payload
when both addends are quiet NaNs, matching the selected GNU Host control.
It leaves ordinary addition, multiplication, reduction trees, decode visits and
all independent equality gates unchanged. This is a CPU control-specific
behavior binding, not a claim about native NaN propagation.

## Counter limits

The fixture counts actual candidate decode visits and compares against its
unshared instrumentation. One shared visit feeds two independent accumulators.
The independent controls do not call the candidate arithmetic. Savings count
slot multiplicity and valid row slices; they are not hardware traffic, elapsed
speed, or observed production route overlap. Actual P201 route overlap remains
unmeasured. No serving recipe or publication may infer a speed gain from these
synthetic counters.

## Final result

The separately reviewed corrected candidate passed all **100 checks across 17
cases** in [the full retained proof](evidence/arithmetic-proof.json). The
[build receipt](evidence/cpu-build.json) binds 53 compiler dependencies, 23 reused
GNU Host objects, 124 parent pins and the exact resulting binary. The final
attempt is [cpu-1792806179719719049](evidence/cpu-1792806179719719049/receipt.json).
All 51,200 BF16-output bytes and 168 status/error bytes match both controls in
every case. Four focused opposite-sign/payload quiet-NaN checks and six ordinary
addition checks supplement the unchanged operator comparisons. The Host owner
closed with zero in-flight work and zero live allocation bytes.

The four full-row cases recorded 8,192,000 unshared decode visits. Candidate
visits were 8,192,000 for no overlap, 6,144,000 for half overlap, and 4,096,000
for full overlap in permuted and equal-input cases. These are directly
instrumented synthetic work counts, not measured speed or production overlap.

The [read-only authority suite](tests/test_authority.py) passed nine tests,
rehashing source/object/compiler/relocated-header closure, raw outputs,
status/error rules, route slot-multiset matches, decode counters, mutation
controls, safe teardown and both failed-attempt lineages. Its
[receipt](evidence/authority-tests.json) records that verification without
replaying a fixture. The complete raw output is deliberately retained as
research evidence: future readers can rehash every BF16 byte and recompute
route/status/counter expectations without starting a runtime.
