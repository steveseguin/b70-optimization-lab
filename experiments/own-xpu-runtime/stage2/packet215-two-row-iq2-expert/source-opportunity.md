# Two-row expert work: source opportunity

The next bounded step is a two-row **IQ2_S gate/up arithmetic proof**, using
synthetic production-layout weights and the selected operator as its independent
control. It should establish whether sharing weight decoding preserves every
output bit before any full Engine integration. The input pins and calculations
are in [source-inputs.json](source-inputs.json). No new execution or measurement
supports this design note.

## Why this work

The closed P201 fresh 370-token request spent 10.790 seconds of 15.404 seconds
in native prefill; its 369 ordinary prompt positions each issued 1,110 kernels
and six waits. This recurring work is a stronger target than a small decode
change. Existing traces contain no expert route IDs or device family timings:
**adjacent-token expert overlap and expert time share are unmeasured**.

The first request is a separate question. Its first position spent 23.511 seconds
inside enqueue and scheduled zero cache-fill bytes. Paging, lazy runtime work
and host expert access remain hypotheses. Do not label that stall cache copying
or count it as a predicted benefit of paired experts. A later first-use phase
trace can attribute it without becoming a prerequisite for this CPU proof.

## Exact selected opportunity

The selected production override is `wide64+halfcache`: 47 layers use the
`p58ag_exp` IQ2_S gate/up kernel, K=2560, 640 output rows, ten routed experts and
512 experts per bank. Layer2's gate/up banks use IQ3 and retain their original
fallback. Down projection remains the selected IQ4 path, including its original
tile16 choice. This first proof changes neither fallback nor down projection.

Each ordinary IQ2 gate or up expert slice is 524,800 stored bytes; together they
are 1,049,600 bytes. Two full ten-expert rows therefore name 20,992,000 gate/up
weight bytes per IQ2 layer before any hardware caching or repeated loads.
If the two rows share `c` distinct full-slice experts, a single traversal per
shared slice could remove `c × 1,049,600` nominal bytes, or `c/20` of that
two-row gate/up traversal (0–50%). This is a structural bound, **not measured
traffic, whole-layer saving or speed**. Weight cache reuse, decoder cost,
register pressure and unmatched routing may erase the benefit. Stored-bank
sizes and cumulative cache-fill counters cannot establish actual overlap.
The `c/20` bound assumes ten distinct full-slice routes per row. The fixture's
greedy `raw_id_overlap`, `tuple_overlap` and compatible-pair counters instead
count matched slot multiplicity; duplicate-slot tests must not be reported as
distinct-expert observations.

## Small proof and later integration boundary

Use the exact selected half lookup, IQ2 decoding, eight independent accumulation
chains, local tree and four-physical-lane adjacent reduction. Decode each shared
weight value once but update two separate accumulator sets in the original
multiply/add order, with the original final BF16 conversion. Do not combine
the two sums, reassociate arithmetic, or replace the serial control with the new
pair helper. Keep exceptional half/scale behavior and status/error semantics.

Required cases are disjoint routes, all shared, partial sharing at different
slot indices, reordered slots, equal and unequal row inputs, nonzero signs and
scales, rounding-sensitive values, and exceptional half values. Check gate and
up output bytes separately, exact status bytes, original-slot placement, and
input/weight mutation sensitivity. Refuse unsupported IQ3/type/layout/extents;
do not silently apply IQ2 arithmetic to layer2. Route matching must include
expert ID and compatible row slice, and preserve original slot order. A pure
overlap counter should report common/unique experts and compatible slice bytes,
with zero/full/partial/reordered cases; it observes no real routing by itself.
The arithmetic helper's raw-pointer bind interface is internal to this CPU
fixture. Count/null/geometry checks do not establish allocation extents, alias
safety or live production ownership; the fixture must supply complete, disjoint
active buffers. No production binding-validation claim follows from this proof.

Current paired Engine traversal completes row0's entire FFN before row1's
suffix, so both route sets are not yet live together. Future integration would
run the two attention/recurrent updates causally, then retain both FFN HC
mix/injection, routes/probabilities and gate/up/activation/status buffers before
grouping expert work. Outputs return to the original route slots; mixture
summation order, cache recency replay and frozen table lifetime stay unchanged.
This liveness/schedule change is outside the first arithmetic proof.

Only add overlap observations to a separately admitted, already-needed native
qualification. Decide whether to integrate and measure the paired kernel from
those observations and exact arithmetic results. No native build, GPU access,
model execution, service change or performance claim is authorized by this note.
