# Accepted mechanism inventory against packet58aj

October 19, 2026. Selection authority is the saved final bundle, not every
candidate mentioned in its preparation README. The compared selections are
[packet97](../packet97-record-bundle/bundle-selection.json),
[packet103](../packet103-record-bundle/bundle-selection.json),
[packet124c](../packet124c-record-bundle/bundle-selection.json),
[packet136](../packet136-record-bundle/bundle-selection.json), and
[packet58aj](../packet58aj-onecard-resident/runtime-selection.json).
Their exact observed bytes are hashed in [analysis.json](analysis.json).
Bundle numbering in old READMEs differs; the explicit selection is authoritative.

## Two-card accepted mechanisms

| Requested packet / mechanism | On packet58aj? | Actual target-only disposition |
| --- | --- | --- |
| 97 inherited p60 three-stage HC fusion | Yes, 58ab → 58ad → 58ah → 58aj | Two HC sides each use norm, low/activation/inject, gate/mix; original BF16 intermediates and reduction trees. |
| 97 inherited p65 expert wide64 | Yes, 58ag → 58ah → 58aj | Smaller workgroups/wide code reads retain the logical SG32 accumulation. |
| 97 inherited p73 HC-wide | Yes, 58ag → 58ah → 58aj | Adjacent gate rows share inputs, with independent ordered trees. |
| 97 inherited p76 ordered host retirement | Yes, adapted in 58ag | Two foreground queue terminals; maintenance remains separately owned. Not the rank1-only original ownership rule. |
| 97 p90 E1 half-scale cache | Yes, adapted in 58ag | Exhaustive 65,536-entry exact FP32 half decoder (262,144 device bytes), rather than 820→840-byte IQ2 rows. The literal expanded-row implementation is absent; the accepted decoding mechanism is present. |
| 97 p78/91 route-fast | Yes, inside p109 fusion in 58ag | The older selection still says route-exp32-rank4, but native dispatch calls p109's exact fast route. Do not infer absence from that string. |
| 97 p82/82b/91 rec-both-plus | **No, not enabled on the accepted line** | 58j compiled it; 58r tested route+recurrence, then closed inconclusive. 58aj still selects rows4-shared. This is the sole applicable accepted target compute delta left unselected. |
| 100 down-tile16 | Yes, 58j → 58n/58p | Same packed bytes transposed in 16-row tiles in pinned banks before fills; hits and zero-copy misses both use the layout. Down-interleave is not the accepted selection. |
| 101 split32 draft attention | Excluded | Draft-only; no draft exists on this line. Its draft-HC aliases introduce no distinct target change. |
| 103 composition of 97 + 100 + 101 | Target mechanisms above are present except recurrence | Composition is not an additional kernel mechanism. Production dense/head/norm choices are not missing optimizations. |
| 105b target-head split and active-state reset repair | Excluded by topology | Requires a second rank, hidden transfer and exact winner merge. The reset repair is for that suffix path. One-card target-only decode cannot use the split. |
| 109 route/shared activation + shared-down/mixture/blend fusion | Yes, 58ag | Preserves each BF16 boundary, ten ordered expert additions, multiply-by-one, sigmoid/SiLU and original reduction. |
| 124c bundle7 fixed 80,128-row draft prefix | Excluded | Draft-only. Its target additions are p109 and p105b, accounted above. Cooldown clamp is a harness repair, already inherited by the one-card chain, not a compute lever. |
| 131b snapshot banks and banked rollback | Excluded | Speculative-state capture/rollback; absent in target-only decode. Batched restore is not one-card expert cache filling. |
| 136 bundle8, banks-batch | Excluded delta | Composition of bundle7 and 131b; no additional target kernel port. |
| Accepted placement=1, rank1 draft, 24/24 split | Excluded by topology/draft | All 48 target layers remain on the one card. |

Packet97's selected head is **production**, not p93 head-transpose; host is
**ordered**, not reply-first; HC norm is **production**, not normfuse; experts
do not select grid-prefetch. Their presence in the source or an earlier
source-screen win does not make them accepted missing ports. No MTP, draft,
snapshot, changed precision or changed oracle is included in the candidate set.

## One-card acceptance history

| Requested port | What survived onto 58aj | Evidence / qualification boundary |
| --- | --- | --- |
| 58j | Pointer-table-compatible down-tile16 | The three-way down/route/recurrence bundle was not wholly accepted. [README](../packet58j-onecard-port/README.md), [58n exclusions](../packet58n-onecard-loo/DO-NOT-REPEAT.md). |
| 58p | Tile16-only record chain | Route-exp32-rank4 and rows4-shared retained. [README](../packet58p-onecard-record/README.md). |
| 58v/w | Asynchronous maintenance and one table upload at a safe boundary | Later publication, separately owned fill work, unchanged reader lifetime; no current-miss speed credit inferred. [58v](../packet58v-async-cache/README.md), [58w](../packet58w-onecard-record/README.md). |
| 58x/z | 21,552,729,600-byte cache with max allocation and usage | Retains original workspace/reserves and overlap. [58x](../packet58x-cache-capacity/README.md), [58z](../packet58z-onecard-record/README.md). |
| 58ab / 58ad | p60 HC fusion | Already spent; packet147's leading missing port is obsolete. [58ab](../packet58ab-onecard-hcfusion/README.md). |
| 58ag / 58ah | HC-wide, wide64, exact half-decode cache, p109 fusion, ordered foreground retirement | Combined +3.38% bracket; not separate measured gains for each component. [58ag](../packet58ag-onecard-ports/README.md), [58ah result](../../../../notes/2026-10-19-own-runtime-packet58ah-chain-a-result.md). |
| 58aj | Complete resident lookup copies at load | Every row, unchanged bytes; current record 31.9668197878 tok/s, +1.27% minimum bracket gain. [Result](../../../../notes/2026-10-19-own-runtime-packet58aj-result.md). |

## Source cross-checks

The retained native sources independently confirm the runtime selections:

- [engine_bracket.hpp](../packet58aj-onecard-resident/native/engine_bracket.hpp):
  `bracket_domain` requires down-tile16 and rows4-shared; the port dimensions
  are applied separately from this inherited selection.
- [main.cpp](../packet58aj-onecard-resident/native/generated/main.cpp):
  `p60::submit` receives HC-wide; `p58ag::expert` receives wide64/halfcache;
  `p109::route_activation` and `p109::shared_down` implement fused sites.
- [runtime selection](../packet58aj-onecard-resident/runtime-selection.json):
  overlap, max cache, zero-copy, full BF16, context4096, resident lookups.

The old [58ag audit](../packet58ag-onecard-ports/AUDIT.md) is an input about
what was missing **before** 58ag, not evidence those mechanisms remain missing.
Likewise 58j's original 616 MB E1 objection was resolved by the different
lookup-table adaptation; importing expanded rows now is not a new E1 port.
