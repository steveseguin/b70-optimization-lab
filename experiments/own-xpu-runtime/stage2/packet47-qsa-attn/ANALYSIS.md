# Packet 47: where QSA decode time goes

This analysis reads packet45 and packet46 without changing either. All figures
after a proposed change are **conditional estimates, not measurements**. The
new kernel still needs the coordinator's device windows. No external runtime
code was copied or ported.

## Measured decomposition and source identity

Packet46's [baseline dispatch](../packet46-specialized/dispatch-baseline.json)
selects `p30.attention.score_softmax`, `round2` selection and
`p33.dense.segment` qgate. These names matter: the generic three-stage attention
and p30's alternative `sg32` path have different decomposition. The estimate
script hashes and re-reads both retained timing JSONLs, excludes warmups, and
uses all 200 current-arm pairs from each fresh timing owner.

| Operation, GPU event duration | T1 median µs | T2 median µs |
|---|---:|---:|
| Whole attention | 2370.312 | 2370.104 |
| Fused scores and softmax | 1512.9165 | 1513.125 |
| Value reduction and gate | 856.875 | 857.083 |
| Whole selection | 180.207 | 180.209 |
| Selection block scores | 8.646 | 8.750 |
| Selection rank and IDs | 171.562 | 171.562 |
| Query and gate projection | 113.333 | 113.333 |

Medians of subevents need not sum to the median total. These are event endpoint
durations, not host submission time. Sources are
[`p30_attention.cpp`](../packet45-merged3/p30_attention.cpp),
[`p30_attention.hpp`](../packet45-merged3/p30_attention.hpp),
[`round2.hpp`](../packet45-merged3/round2.hpp) and
[`p33_candidates.hpp`](../packet45-merged3/p33_candidates.hpp).

The fused attention stage launches **24 work-groups, one 32-lane subgroup per
query head**. Each lane owns selected-token indices `lane+32*c`. It computes
each 256-dimensional score with a private `float p[256]` adjacent reduction,
not a subgroup dot. The lane can hold up to 65 scores in `owned[65]`. Only
24 subgroups cover the entire GPU, while each lane executes up to 65 complete
dot products. Across lanes at a given scalar dimension, K addresses are
separated by entire token rows; they are not contiguous vector loads.

Every subgroup then walks **all selected scores sequentially**, using one
shuffle per score for the ordered maximum. It computes deterministic exp,
reduces the denominator by fixed 32-leaf subtrees and an upper tree, and
writes FP32 scores and probabilities. The private arrays are a serious
register-pressure/spill risk; actual spills require compiler/profiler evidence
and are not claimed as measured here. Dynamic indexing alone is visible in
source. The score loop's low occupancy and sequential maximum are established
without assuming spills.

The value stage launches **6144 work-groups**: one subgroup for each head and
output dimension. Each subgroup walks up to 65 chunks of selected tokens,
performs five shuffles per full chunk, stores chunk sums in `partial[65]`,
and finally has lane zero reduce those sums. V loads at adjacent subgroup
lanes differ by selected token, hence at least a 1024-byte token stride for
adjacent IDs, while only one 2-byte component is used. The layout cannot
coalesce contiguous dimensions within this subgroup. Probability and selected
ID loads are repeated for all 256 dimensions. Admission independently scans
the whole selected-ID list in lane zero in **each of the 6168 groups** before
use. At 2048 selected tokens that alone spells 12,632,064 ID visits. Reuse in
caches may reduce physical DRAM traffic; source-level loads are not a DRAM
measurement. There are **no floating-point accumulation atomics**: relaxed
integer atomics load/store the shared error flag. No floating race is needed
to explain this slowness.

The old CPU oracle preserves the 256-leaf score tree, sequential selected-order
maximum, deterministic exp, adjacent-tree denominator, per-token division,
adjacent-tree weighted values, BF16 rounding **before** the sigmoid multiply,
then the BF16 output store. Its blocked tree deliberately preserves odd-tail
`+0` nodes, including signed-zero consequences. Parallel ownership can preserve
these nodes; ordinary online softmax cannot preserve its arithmetic identity.

## K2 and selection structure

There are **two KV heads**, each shared by 12 of the 24 query heads; every head
has dimension 256. The KV address is `(selected_id*2 + query_head/12)*256+k`.
Both K and V stay full BF16. Separately, the indexer has four 128-dimensional
query heads and one 128-dimensional pooled key per four-token block. Selection
is shared by all 24 query heads in a row. It sums the four nonnegative block
dot scores in their fixed head order, divides by sqrt(128), and takes at most
512 blocks, expanding each selected block to its four original tokens.
Blocks are ranked by decreasing score, ties by ascending block index. The
unfinished last block contributes its 0–3 tokens unconditionally, appended
after the ranked blocks. Thus, for **populated** context C,
`N(C)=4*min(floor(C/4),512)+(C mod 4)`, maximum 2051. At all requested
power-of-two contexts above 1K the count is **2048, not 2051**. The latter
appears at residues three, so exactness also needs these boundary cases.
Selected order generally differs from chronological order.

The repository also calls its kernel-choice qualification window **K2**;
that is distinct from the two KV heads and the speculative k=2 probe.
[`KERNELS.md`](../packet45-merged3/KERNELS.md) requires exact outputs and
complete event sequences before adopting a selected kernel. Packet47's M=2
must retain two independently addressed rows, with causal limits differing
by one. The p30 entry point admits only M=1; a faithful old M=2 control is two
row-sliced invocations in sequence. There is no implicit generic M=2 fallback.

Selection's first stage has one work-group per completed four-token block,
four tree128 dots and barriers. Its second stage launches one work-group per
block again. Each scans all block scores for finiteness, and lane zero scans
all scores again to rank its own block. Ranking therefore has B² comparisons,
where B=floor(C/4): 1,048,576 at 4K and 67,108,864 at 32K. The 2051-token cap
does **not** cap this selection cost. The recorded 171.562 µs rank stage,
versus only 8.6–8.8 µs dot stage, confirms where to focus. An exact cheap
candidate may parallelize the integer rank sum and share the finite check,
keeping tie order and all selected IDs; a new floating score tree would be
an unnecessary oracle change. Early rank cutoff after 512 can save rejected
blocks, but a finite check must still cover all scores before output.

Qgate is a **12288 by 2560 Q6_K matrix-vector projection**, producing 6144
query values and 6144 gates, not a softmax/gating scalar operation. Its
resident expanded layout reads 2560 signed codes and 640 scale bytes per row
(39,321,600 useful matrix bytes), while retaining source metadata in the row
stride. The matrix allocation is larger; metadata is not all used by this
kernel. It performs about 62.9 million conventional multiply/add FLOPs, plus
scale multiplication/conversion. One 32-lane subgroup owns each output row;
each lane accumulates 80 contiguous-within-tile terms across ten 256-wide
tiles, then reduces a fixed tree32. At 113.333 µs useful matrix throughput
is approximately **347 GB/s**. At the assumed 550 GB/s ceiling its useful
matrix bytes alone take 71.5 µs. This is a much smaller opportunity than
attention; do not rebase its arithmetic or launch an extensive tuning campaign
to chase a few microseconds. Exact wider loads are reasonable only if cheap.

## Bytes, FLOPs and lower bounds

These are analytical bounds, **not measured context-performance points**.
The 550 GB/s bandwidth is the approximate available-bandwidth assumption in
the packet46 result note, not a new hardware measurement. The 20 TFLOP/s
column is an explicitly illustrative scalar compute ceiling, not a B70
specification or achieved rate. Recompute it for another ceiling using the
recorded FLOP count. Exponentials, divisions, integer address arithmetic,
launches and synchronization are additional costs.

Unique selected KV is `N*2KVheads*256*2bytes*2(K,V)=2048N` bytes. The table
adds Q, gate, output and one ID load. It assumes perfect reuse across query
heads. A second bound charges each of the 24 heads its own K and V, adding
`24576N` rather than `2048N`; neither includes the old code's redundant
ID/probability traffic. Dot products need `24*N*511 + 6144*(2N-1)` FLOPs
when a multiply and add each count as one. Tree padding may add extra zeros.

| C | N | Unique bytes MB | Head-reloaded bytes MB | Dot MFLOPs | Unique floor µs, 550 GB/s | Head-reloaded floor µs | Dot floor µs, 20 TF/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
|1024|1024|2.138|25.207|25.135|3.887|45.831|1.257|
|2048|2048|4.239|50.377|50.276|7.708|91.594|2.514|
|4096|2048|4.239|50.377|50.276|7.708|91.594|2.514|
|8192|2048|4.239|50.377|50.276|7.708|91.594|2.514|
|32768|2048|4.239|50.377|50.276|7.708|91.594|2.514|

At the 2051 cap, KV alone is 4,200,448 bytes. M=2 roughly doubles FLOPs and
head traffic; perfect overlapping selected-KV reuse may avoid doubling unique
DRAM bytes, but selections may differ so that reuse is not assumed. The 4K
2370 µs observation is 307 times the optimistic unique-byte floor and 26
times even the head-reloaded byte floor. Saying only “100x memory floor”
conceals this range and the importance of reuse. Neither bound is a promised
kernel time.

## Preserve order before changing the oracle

There is no numerical necessity to change the old tree. Scores can be spread
over (head, selected-index) subgroups with contiguous dimension loads.
Probability normalization can retain the sequential maximum and exact tree;
value loads can be tiled over adjacent dimensions, with fixed 32-token
subtrees reduced in the same selected-index order and identical tail nodes.
This removes the 24-subgroup bottleneck and the transposed value gather while
preserving the old outputs. Merely replacing the score stage cannot reach
5x: the measured 857 µs value stage alone exceeds the 474 µs total target.
Both stages need work. The 92 µs head-reloaded byte bound leaves room for
5x, but CPU analysis cannot establish that speed. **Preregister and time the
order-preserving candidate first, and prefer it if both fresh owners show
at least 5x with all byte gates passing.**

The alternative fixed-split design assigns a compile-time number of selected
indices to each split, regardless of device occupancy or work-group count.
Subgroups load contiguous BF16 dimensions, preserve fixed score nodes and
produce each split's maximum, exponential sum and weighted-value vector.
A separate combine stage computes the fixed tree over split maxima, rescales
each sum and vector by `exp(local_max-global_max)`, then reduces and divides.
This changes exp/normalization/weighted-value rounding. Its independent CPU
reference needs a new identity, explicit empty-split/tail behavior and fixed
nonfinite policy. Keep the record oracle unchanged. New-vs-old ULP/absolute
attention differences are informational; **full-model logits are unavailable
without a separate authorized model fixture/run**. Matching this operator's
new CPU tree is necessary but does not certify the complete IQ3 engine or
the realistic suite. Those need later integration, fresh-process repeats and
full-model qualification under the new identity.

## Conditional effect on the actual 128-token suite

Capacity 4096 is allocation capacity, **not populated context**. The actual
12 hashed input JSONs have 60–90 prompt tokens, mean 71.8333. Counts are:
incident-retrospective 87; code-review 90; customer-email 77; sql-debugging 83;
release-plan 68; benchmark-analysis 65; architecture-tradeoff 67;
bug-report-synthesis 71; technical-guide 69; risk-register 61;
performance-hypotheses 64; decision-memo 60. The cap128 manifest confirms
the same input lengths and 128 generated tokens. Their last output sees
187–217 occupied tokens. None reaches the selection cap.

[`analysis/estimate.py`](analysis/estimate.py) reads the actual inputs and
both timing files and verifies input hashes against their manifest. It writes
all **12 × 128 positions × 6 scenarios** to
[`per-position-estimate.csv`](analysis/per-position-estimate.csv), with
per-layer before/after attention time, 12-layer totals and separate five/seven
layer rank savings. Position g=1 is the scalar equivalent of final prefill;
it is **not a TTFT estimate**. Actual decode intervals start at g=2. The
source pins, prompt distribution and summary are in
[`estimate.json`](analysis/estimate.json).

The explicit sensitivity model is
`old_us(C)=L+(2370.208-L)*N(C)/2048` and
`new_us(C)=L+(old_us(C)-L)/s`, for assumed fixed cost L=0,50,100 µs and
variable-work speedup s=3 or 5. This extrapolation is requested estimation,
not a measured or publishable curve. It does **not** assert that a 3x result
at 4K transfers to short prompts; an extra split/combine launch can even
regress them. It assumes no new fixed cost and hence is optimistic about it.
Every extra 10 µs per layer reduces a serial 12-layer saving by 0.12 ms.

The conventional 99 inter-token intervals use outputs 2–100, with mean
occupied length 121.8333. In the L=50 µs illustration, per-layer attention
averages **188.027 µs before, 96.009 µs after at 3x variable work, or
77.605 µs at 5x**. Serial savings over all 12 layers would average 1.104 or
1.325 ms/token. Rank1's seven layers alone save 0.644 or 0.773 ms; rank0's
five alone save 0.460 or 0.552 ms. Across L=0–100 the serial savings span
1.080–1.128 ms at 3x and 1.297–1.354 ms at 5x.

Subtracting these illustrative savings from `1000/39.42=25.368` ms/token
would suggest roughly **40.4–41.6 tok/s**, depending on whether only the
seven-layer bottleneck or all twelve serial savings reach the critical path.
This is arithmetic sensitivity around the user-supplied record, not a
forecast, matched benchmark or recomputed suite statistic. The record uses
class medians; averaging layer savings does not reproduce that statistic.
MTP misses, two-row verification, wasted speculation, overlap, changed
acceptance after an oracle rebase and one-card CPU-expert stalls are unknown.
No one-card throughput baseline is assumed. The 4K populated context lever
can still be large for genuinely long inputs, but the short registered suite
cannot inherit 12 times the 4K saving. Measure short-context end-to-end
behavior separately before integration or any speed claim.
