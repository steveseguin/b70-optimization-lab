# Integrating packet 28 after G2

No runtime file was changed here. These steps are for the subsequent integration packet.

1. Run K0 and G2 from WINDOW.md on one admitted card. G2 owns two fresh processes.
   Preserve both owners, exactness rows, all event timestamps, failures, native and
   window receipts. A baseline outside15% of its in-model event sum is unrepresentative:
   inspect model shape, actual R5 entry, compiler/overlay, memory layout and event grouping
   before interpreting candidate gains. Do not relax the threshold to admit a result.
2. Inspect `dispatch-gemv-measured.json` and `timing-table.md`. It has packet26's exact
   top-level vocabulary: `schema: packet26.dispatch.v1`, `classes`, `gemv`, `fusions`.
   GEMV keys are actual class labels (`hc.a.low`, not a made-up `hc.low`). `r5` means keep
   current. Candidate values are `p28.dense.{rows4,wg32}`, `p28.private.{rows4,wg32}`,
   `p28.shared.{rows4,wg32}`, and `p28.paired.{rows4,wg32}`. A class can switch only if
   all of its type/shape fixtures pass the same candidate in both owners and every
   candidate median is below0.9× that owner's R5 median. Mixed-NaN byte failures exclude it.
3. Link `submit.cpp`, `dense.hpp`, `expert.hpp`, `registry.hpp`, and `submit.hpp` into a
   new packet26/27-style runtime. Keep packet26's `integrated::arithmetic::r5_variant`
   and its exact expanded weight bytes. Add a host branch after `dispatch.gemv_for(label)`:
   names starting `p28.` call `p28::submit(device, matrices, name, shared, variant)`;
   `r5`/empty keeps the existing entry. Keep p25 handling unchanged for existing selections.
   Compile all baseline translation units using packet26's recorded overlay. New class
   choice is host-side; no string/descriptor interpretation belongs in device kernels.
4. Allocate candidate scratch in the runtime plan before any measured step:32 bytes per
   output row/route slot (two projections × four FP32 partials). Even rows4 currently
   validates this extent. Add it to resident/scratch accounting and owner lifetime rules.
   Keep matrices' BF16 activation/output types, count10 routed contract, span, output/status
   separation and alias checks. Inactive/invalid routes must preserve NaN output/status.
   No weights, activation or status copies belong inside repeated GEMV submission.
5. Merge **only** the measured `gemv` section into the integration packet's table. Keep
   independently admitted non-GEMV `classes` and `fusions`. The packet26 parser accepts
   string GEMV values but its old bridge cannot execute p28 names until step3 is linked.
6. K1: run all classes against actual R5 and the v2 CPU oracle, both compilers' host
   argument tests, odd rows, aligned/un-aligned boundary tests, Q8 upgrade, IQ4 K640,
   signed zero, denormal and exceptional fixtures. Require new/current same-card bytes,
   deterministic fresh-process repeats, unchanged BF16 rounding and split trees.
7. K2: repeat per-class performance against the linked integration runtime's R5 branch,
   two fresh owners and unchanged settings; retain all event sums and class weights.
   Then run full 64-token model/oracle layer captures and two-card fresh-owner repeats.
   Only measured wall ms/token on that model establishes progress toward35ms/token.

Single-SG split4 is two events; both must be charged. Four-row split4 is one WG512
submission. Neither changes the sum tree. Do not transplant a candidate timing from
one format, class, split or card count to another. No packet28 candidate is admitted yet.
