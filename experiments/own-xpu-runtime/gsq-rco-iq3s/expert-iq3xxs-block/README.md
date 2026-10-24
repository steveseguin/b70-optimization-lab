# IQ3_XXS packed block-field candidate — source checkpoint

No build, weight/fixture payload read or device operation has occurred. Root
must authorize these stages separately after archival. Frozen generic control
and every previous source remain unchanged.

## Why this candidate

The independently audited current attribution (`469fe156…`) assigns gate
27.620520ms and up27.502191ms to IQ3_XXS:55.122711ms of192.148198ms sampled routed
events. This is the fixed early-generated positions94–101 sample, not a full
request/decode speed attribution. Selection metadata records the actual17layers,
34gate/up sites, N640/K2560/top10/512experts, raw980-byte rows.

The initial request's “shared input” wording was corrected against the actual
Engine: these unfused routed sites use gathered **per-slot** BF16 input. Original
expert_gather and10slot strides remain. No shared-input conversion, fusion,
expanded storage, indirect cache or additional resident weight allocation.

## Exact change

`block.hpp` includes the frozen packed control. Its new `BlockKernel` keeps
that operation's route validity, zero-count/tail NaNs, status, SG32 tree,
BF16 rounding, by-value command capture and five tracked live allocations.
Actual frozen main.cpp matrix() sets m.rows=l.shape[1] and m.span=m.rows,
so selected graph[10,640,2560] gives span640. Selection metadata lists only
the two consumed Matrix inputs; graph active/error dependencies are retained,
but the original packed operator does not bind or mutate them.
The strict facade admits only selected matching label/weight, type18,
N640/K2560/count10/experts512/span640 and per-slot BF16 input/output.

Only the lane loop changes from k=lane;k+=32 into10blocks ×8groups. Each lane
still sees precisely the same k sequence and sum=sum+product order. The block
half is converted once per lane per256-element block instead of eight calls.
The actual frozen decoder expression remains
`(((d*(0.5f+float(word>>28)))*0.5f)*float(magnitude))*float(sign)`, followed by
multiplication with BF16 input. No factoring across products/sums, FMA, signed
code conversion, NaN canonicalization, tolerance or exception waiver.
`expanded::lane` is deliberately not used: its lane-eight order differs.
Compiler CSE may already remove part of the repeated work; source call count is
not a machine-code or speed claim.

## CPU and native proof plan

`proof.cpp` is an unbuilt CPU-only delta fixture: frozen lane_sum<18>/decoder
versus new loop, focused signed/exceptional half, all scale/sign-code fields and
varied grid bytes, exact lane and BF16/status outputs. Full640rows/top10 with
distinct per-slot inputs covers valid, duplicate, zero-count, invalid and tail
routes plus live input/weight mutation. Its internal Host operation uses four
populated synthetic experts; it does not claim complete512bank public facade or
Device lifetime qualification. Existing frozen type18 ABI proof remains the
control authority; future native micro qualifies the new kernel.

`micro-plan.json` fixes layers0gate/22up/46gate (first selected layer, last selected rank0 layer, last selected rank1 layer;
not timing selection). Unique graph writer identities for input/routes/output/
status are recorded. No fixture was extracted. Once authorized, stream only
these named ranges from audited closed attribution bundles, matching original
baseline logical hashes. Authenticate loader/header identities and only the
at-most10 referenced expert slices percase (18,816,000 packed bytes upper bound
across3cases), preserving per-slice hashes. Populate three321,126,400-byte packed
512banks with unreferenced entries zeroed; every actually consumed expert slice
must be present. Control/candidate share each bank; no writes during timing.

Proposed device arrays963,610,200B, plus actual runtime bookkeeping under a
reviewed1GiBcap. This bound still needs concrete runner admission/accounting.
Three cases ×(4excluded warmup+24measured cycles)=84pairs/168kernels, balanced
case rotation andAB/BA order, all raw event latencies retained, timing queried
before retirement. Every full output/status must match both original kernel
and saved oracle each pair. No cache flush/settings changes, no fullEngine
integration or speed claim from CPU/source evidence. The runner/build recipe
are intentionally not implemented or invoked at this source checkpoint.
