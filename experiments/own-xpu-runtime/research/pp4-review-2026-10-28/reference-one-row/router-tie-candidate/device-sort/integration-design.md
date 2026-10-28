# Proposed RouteFast2 integration — source plan only

Do not edit the canonical runtime until the coordinator releases its pinned
seven-case historical regression. This proposal is not an implemented patch.
The CPU and card27 probe establish compatibility of the bounded sorting helper
on tested inputs; they do not measure integration cost or prove model quality.

## Preserve the native arithmetic and ordinary selection

Keep `RouteFast2<512,10,MERGE>`'s maximum, deterministic exp, denominator tree,
division, subgroup candidate construction, top-ten selection, and weight
normalization exactly as written. Store its ten selected IDs in 40 bytes of
local memory while the existing `put` writes the ordinary outputs. Do not run a
new softmax or reconstruct probabilities on the host.

After a work-group barrier, detect whether any selected rank has an equivalent
probability. Comparing every expert with every selected rank is unnecessary:

1. Lane zero compares the nine adjacent selected probability pairs. This detects
   every tie entirely inside the selected top ten, since scores are sorted.
2. Every lane compares its one native probability with rank nine's probability,
   excluding rank nine's own expert ID. A work-group `any_of_group` detects a tie
   crossing the selected/unselected boundary, and also selected boundary ties.
3. Combine these flags uniformly. If neither is true, skip the sorter; preserve
   every original ID, route, and weight. The new barrier and detection reduction
   still have a cost, which must be measured on no-tie inputs.

This detector is complete: an unselected expert can tie a selected score above
the cutoff only when that same score occupies the cutoff too. Use floating `==`,
matching equivalence under finite-score `>`; do not substitute bit equality for
probability equivalence (signed zero is a useful adversarial test).

## Rare selected-tie path

For a tied row, lane zero initializes and sorts all 512 expert IDs using the
already-computed, unchanged local `prob` array. Sorting only the tied IDs or the
160 subgroup candidates is insufficient: the registered introsort's permutation
depends on partitions and other equal-score groups throughout the full array.

Use a bounded local index array (2048 bytes) and a new explicit caller-provided
18-frame workspace (216 bytes). The current helper's stack is private; exposing
the frame buffer requires its own small host/device compatibility gate. Other
work items wait at uniform barriers. Do not allocate a private 512-index array
per work item in the production route, and do not add any host readback or
device-to-host decision. A serial lane sorting local memory is only a candidate;
it may be expensive on frequent ties, and must be timed.

Before any replacement is published, validate all ten proposed IDs: bounds,
uniqueness, and exact score equality to each original selected slot. Retain the
diagnostic's stricter changed-ID guard as well: raw native router float words
must be identical for each old/new replacement. Distinct raw words that happen
to round to the same probability remain an unresolved policy case and must
refuse through the existing sticky error path, not silently change behavior.

After complete validation, replace only IDs and corresponding first components
of `routes`/`routes.down`. Preserve every existing weight byte and all other
route fields; the same probability occurs in each replaced slot, so the native
normalization tree receives unchanged rank values. Keep the original normalization
instructions/order. For the initial experiment, use an explicit default-off build
or configuration choice so an unselected lane has the original kernel unchanged.

Current merged RouteFast2 explicit local storage is 5512 bytes (two 512-float
arrays, 32 float sums, 322 uint32 flags). A simple implementation adds 2048 index
bytes, 216 frame bytes, 40 selected-ID bytes and about eight control bytes:
roughly 7824 bytes before compiler padding. Do not alias the exp float buffer as
an int workspace merely to save memory; make ownership and types explicit.

## Meaningful next gate and timing

Use the actual route kernel and native input rows, comparing the original and
candidate against a host reference sort of the **same captured native device
probabilities**, rather than independently recomputed softmax values. Verify all
512 probabilities, top-ten weight bytes, all route fields, status words, active
mask behavior, and the exact selected IDs. Include no tie, internal selected tie,
cutoff-crossing tie hidden by subgroup truncation, unselected-only ties, all equal,
same-probability/different-raw-word refusal, and multiple rows. Cover both MERGE
settings only if both will be supported; otherwise refuse unsupported settings.

Time the same route-kernel workload and same build identity after one meaningful
correctness gate, with representative no-tie and rare-tie rates. Include long
prefill rows because extra local memory can affect occupancy even when sorting
is skipped. Then run the existing matched model correctness and fair timing
harness. No speed claim follows from the current independent sorting probe.
