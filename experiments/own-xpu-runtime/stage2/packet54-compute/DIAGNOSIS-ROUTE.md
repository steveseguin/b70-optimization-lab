# Packet54 routing diagnosis

This is a source diagnosis and preregistered hypothesis, not a device result.
The matched control is packet49c's selected packet51 route, not packet42's
superseded per-lane denominator implementation. The standalone fixture uses
the namespace-equivalent packet51 body on its existing packet45 type tree;
the packet build must check that selected source against packet49c.

Production references:

- `packet49c-round2/main.cpp:1218`, `Engine::execute_site`, calls
  `p49c::route` for resident route sites, including prepared capture.
- `packet49c-round2/p49c_submit.cpp:35` forwards to `route_submit`.
- `packet49c-round2/p49c_kernel.hpp:25–85` contains the four-pass selected
  route and its binding checks; `route42.hpp` supplies the exact arithmetic
  helpers and output descriptors. The common shape is 512 experts, top ten.
- `packet17-detmath/detmath.hpp:55` is the deterministic exponential. Its
  normal finite path has range reduction and twelve dependent paired-float
  Horner steps, including explicit FMAs. No native/fast exponential is used.

## Where the time can go

| Stage | Production geometry | Serial work, synchronization and traffic |
| --- | --- | --- |
| 0, block maxima | 32 range work items; compiler chooses physical groups | Each item scans 16 BF16 inputs in index order, validates finiteness, and writes one FP32 maximum. There is almost no parallel work. Sticky failures and partially written scratch are observable. |
| 1, exp and block sums | Two 256-item workgroups, SG32; 16 subgroups total | One work item per group performs the ordered 32-maximum scan. All items wait at a local-memory barrier, then each evaluates one deterministic exp. Four subgroup shuffle/add stages preserve each original adjacent 16-value subtree. There are 512 exponentials and 32 × 15 = 480 sum additions. Only two groups can distribute this expensive work across the device. |
| 2, normalized ranks | 64 × 256-item groups, eight SG32 outputs per group | Each group serially computes the same 31-add denominator tree, waits, computes 512 rounded probability divisions, then waits again. It keeps 513 FP32 values (2052 bytes) in local memory. Each lane walks 16 competitors; each SG32 reduces the 32 integer counts in the original five-stage adjacent tree. The ten selected output writers recompute the exact denominator and probability before writing descriptors. |
| 4, normalize selected weights | One range work item | The original top-ten padded sum tree and ten ordered output divisions are serial. Its additions of zero at incomplete subtree edges are retained. |

Stage 2 performs 262,144 normalized comparisons and lower-index tie tests.
The production cached probabilities cost 64 × 512 = 32,768 divisions;
the 64 denominator trees cost 1984 additions. These are source counts before
compiler common-subexpression elimination. There are also ten output
denominator trees and divisions, which this packet leaves in place.
The source competitor loads are 262,144 FP32 local reads, but subgroup
broadcast/cache behavior means this is not a measured SLM transaction count.
Register allocation and achieved occupancy have not been measured.

The unique BF16 input is only 1024 bytes. The visible scratch writes cover
32 maxima, 32 block sums and 512 exponentials, or 2304 bytes; four output
arrays total 320 bytes. The distinct-byte accounting is 3648 bytes, under
0.007 microseconds at the lab's 550 GB/s planning ceiling. This deliberately
optimistic lower bound ignores repeated accesses, cache lines and compute;
it explains why a DRAM bandwidth argument cannot price this kernel. The
control additionally reads its 512-exponential array in each of 64 groups
(131,072 source bytes) and pays local-memory traffic and barriers.

The current full-route measurement is about 24.6 microseconds, from
[packet51's device result](../../../../notes/2026-10-17-own-runtime-packet51-device-result.md).
The inherited stage 0/stage 4 timings are about 3.6/3.1 microseconds. Keeping
those stages leaves an optimistic changed-stage budget below roughly
17.9 microseconds; a real saving must be smaller because all 512 exponentials,
262,144 comparisons, output arithmetic and positive execution cost remain.
The component timings and whole-route result came from different retained
measurements, so 17.9 is a planning bound, not a freshly measured subtotal.
No sustained deterministic-exp, precise-division or comparison issue rate is
available. A numerical compute floor from nominal peak FLOPs would be false
precision. The rank-only candidate is further bounded by stage 2 alone;
its current separate device timing is not asserted here.

## Two registered candidates

`route-rank4`: keep stages 0/1/4, then assign four independent output ranks
to each subgroup in stage 2. There are 16 groups of 256 items instead of 64.
Each group still allocates 2052 bytes and has the same two local barriers.
The denominator and normalized cache are reused by 32 outputs instead of 8:
the source count falls to 16 denominator trees (496 adds) and 8192 probability
divisions. Each competitor load feeds four independent comparisons, reducing
source competitor reads fourfold. All 262,144 comparisons and 512 integer SG32
trees remain. Per-lane live rank/value arrays grow from one to four; reduced
group count and extra register pressure can lose more than the saved work.
The device result decides that tradeoff.

`route-exp32-rank4`: use the same rank candidate, and give stage 1 sixteen
32-item groups instead of two 256-item groups. The sixteen subgroups and 512
deterministic exponentials remain. This makes expensive exp work available
to more schedulable groups; it does not reduce exp instructions. The ordered
maximum scan is repeated 16 rather than 2 times (512 versus64 source maximum
operations), and each group retains the local barrier. It might gain from
distribution or lose from repeated scans/scheduling. It preserves every
16-value floating-point reduction tree.

A single-workgroup fused route is not registered. It would confine all 512
rank outputs and 262,144 comparisons to one group, worsening the principal
occupancy concern, and would require extra care to preserve stage 0's partial
scratch/error behavior. Four existing kernel events remain: this round is
not a launch-gap experiment. Packet 34 already bounded the launch gaps.

## Exactness contract and tests

Each candidate keeps the BF16 input conversion, every deterministic exp,
FP32 subtraction and division, all floating reduction trees, integer rank
walks and SG32 integer reductions, lower-index ties, top-ten selected-weight
normalization and output descriptor shape. Ranking raw exponentials would
be wrong: distinct positive values can become equal after the normalized
division. The direct rank adversary in `route_test.hpp` tests that case.
Repeated deterministic expressions may be shared across independent output
ranks; no operation is reassociated within an output's dependency chain.

Stages 0 and 4 use the actual production operation types. Inputs, all 1088
allocated scratch floats (including untouched tail bytes), all four output
arrays, active and sticky error controls are compared. Tests include ties,
signed zero, extreme finite logits, NaN and both infinities, inactive calls,
sticky errors and two serial rows. M2 means two actual sequential calls;
there is no joint-token batch or cross-row cached probability. Inputs change
for the ordinary random second row. CPU host mirrors preserve the device
candidate's per-output lane walks and integer trees, rather than merely
calling the reference rank implementation.

The host proof is a prerequisite only. Both coordinator E windows must match
the production bytes and full mutable state before timing. This standalone
packet adds no new model oracle, no runtime adoption and no measured saving.

## Integration handoff

For a selected route candidate, packet49d should replace the forwarding body
at `p49c_submit.cpp:35` with the admitted
`p54route::submit<4,256>` or `p54route::submit<4,32>`, using the packet49d local
production type tree. The `main.cpp:1218` dispatch and `finish(...,false)`
remain. Bindings and four-stage event dependencies are unchanged; preserve
the existing active/error duplicate-input allowance, extent/alignment checks
and scratch/output alias refusal. No tensor layout, state capacity, table,
model identity, BF16 cast boundary or caller-side scheduling changes.
