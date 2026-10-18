# Packet109 launch and dependency census

Source: copied packet103 bundle, with route-fast, rec-both-plus, expert half-cache, down-tile16, wide HC and split32 draft attention. Every row below comes from actual allocation/capture startup on CPU; only model payload and backend are mocked. The raw bindings, logical inputs/outputs, and every source-expanded command are in [census.json.gz](evidence/census.json.gz).

All commands on a rank use its in-order queue. Thus each row depends on the preceding row as well as its listed logical inputs. Rank0 speculation and rank1 target run separate halves; no compute/compute overlap is assumed on one B70. A cancelled speculation can stop at any command boundary; this table is the completed half.

**Bytes:** `bound` is the exact sum of distinct allocation extents bound to that command, including shared scratch and unused ABI placeholders. `working` excludes the shared scratch/rope/control arenas and scales routed banks to ten experts; it remains a binding-footprint upper bound, not DRAM bytes. `useful` is supplied only for the small fusion sites whose byte accesses were derived directly. Repeated loads and cache transactions are not inferred. `LOW` means at most 64 KiB by the useful count when known, otherwise the working footprint.

The CPU backend folds attention GEMV and its finish into one operation, and folds p28 Split4/RPG1 finishes too. The device sources add those launches, listed explicitly here. The resulting **636/628** rank0/rank1 counts exactly reconcile Packet108’s running baseline. The **matched change** in these captures is 72 launches on each rank.

| Rank | CPU captures | Device-source production | Device-source fused | Removed |
| --- | ---: | ---: | ---: | ---: |
| 0 | 605 | 636 | 564 | 72 |
| 1 | 598 | 628 | 556 | 72 |

## Fusion decisions

- Route top-k and normalized mixture weights already run inside packet78’s one-workgroup route. Fusing router GEMV into it would cross workgroups or serialize the dense projection. Do not reopen that form.
- The small.ffn tuple writes router, shared gate/up and shared gate scalar before route. Shared SiLU/product needs only the gate/up rows, so it can run after route’s final barrier in the same workgroup. The unchanged route guarantees valid expert IDs for the later expert status checks. Both original activation inputs and the rounded activation output remain present.
- Shared down is after expert down. The shared gate scalar is already written by small.ffn; its later plan site is empty. A row subgroup can therefore finish the same K640 Q8 dot, write BF16 down, compute slots0..9 in order, write BF16 mixture, and execute the original rounded shared blend. The subsequent HC combine stays separate. No phase reads another workgroup’s newly produced result.
- No expert gate/up activation fusion: packet39 found predicate/register pressure in that loop. No descriptor interpreter, new reduction tree, NaN canonicalization, changed verifier, or cross-workgroup barrier is introduced.

## Previous attempts checked

Every repository `DO-NOT-REPEAT.md` was searched; retained matches: [fusion-history.txt](evidence/fusion-history.txt).

| Packet | Prior boundary | Why this proposal differs |
| --- | --- | --- |
| 21 | Generic fusion; unsafe cross-workgroup producer/consumer; repeated CPU HC prologue | Two fixed shapes; routing stays one WG; downstream row-local inputs already exist |
| 39 | Expert activation spills; down/mixture and HC norms require multiple rows; shared-up absorption disables small.ffn | Keep small.ffn; fuse already-complete ten-expert row inputs into shared-down, leaving HC norm alone |
| 59 | Empty capture Sites must remain; draft arithmetic is distinct | Preserve empty original Sites and all draft choices; target-only fusion |
| 69 | Fused argmax too small; expanded row stride includes metadata | No argmax campaign; shared-down stride checked against expanded::row_bytes =760 |
| 77 | Historical timings cannot stand in for a current matched identity | Historical budget motivates work only; five-view in-engine bracket decides benefit |
| 78 | Probability ties and reduction trees must be exact | Copy the selected route body unchanged; append activation after final phase |

At 3.4–5 microseconds per launch, 72 removals suggest 0.245–0.360 ms per half before added fusion work, overlap and engine transfer. This is an issue-cost hypothesis only. No gain, record or device quality is claimed.

## Complete per-layer kernel inventory

Labels are full plan labels. The immediately preceding ordinal in the same rank is the queue dependency; `inputs` in the raw JSON gives the data dependency. Host-only operation names identify the corresponding native ng/Glue kernel family. All unselected plan sites have zero launches; they are retained for recapture.

### Rank 0: speculative layers0–23

| # | Layer/site | Kernel | Bound bytes | Working bytes | Useful bytes | Small |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 0 | begin.0 | `p18::Glue` | 272629784 | 12 | — | LOW |
| 1 | streams | `p18::SimpleNew<(integrated::Op)3, 0, 0, 0>` | 272655372 | 25612 | — | LOW |
| 2 | blk.0.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 3 | blk.0.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 4 | blk.0.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 5 | blk.0.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 6 | blk.0.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 7 | blk.0.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 8 | blk.0.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 9 | blk.0.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 10 | blk.0.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 11 | blk.0.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 12 | blk.0.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 13 | blk.0.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 14 | blk.0.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 15 | blk.0.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 16 | blk.0.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 17 | blk.0.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 18 | blk.0.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 19 | blk.0.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 20 | blk.0.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 21 | blk.0.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 22 | blk.0.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 23 | blk.0.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 24 | blk.0.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 25 | blk.0.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 26 | blk.1.ple.hash | `p18::Glue` | 272630212 | 440 | — | LOW |
| 27 | blk.1.ple.key | `p33::Kernel<0u, (iq3::Type)8, 2560u, 1u>` | 39543808 | 31155200 | — |  |
| 28 | blk.1.ple.value | `p28::Kernel<(iq3::Type)8, 2560u, 4u, 1u, false, false>` | 16181248 | 7792640 | — |  |
| 29 | blk.1.ple.value | `p28::split4 finish (device-only)` | 16181248 | 7792640 | 46080 | LOW |
| 30 | blk.1.ple.kn | `specialised::Kernel<(ng::Op)2, 0, 2560, 4>` | 272711704 | 81932 | — |  |
| 31 | blk.1.ple.kn | `specialised::Kernel<(ng::Op)2, 1, 2560, 4>` | 272711704 | 81932 | — |  |
| 32 | blk.1.ple.qn | `specialised::Kernel<(ng::Op)2, 0, 2560, 4>` | 272711704 | 81932 | — |  |
| 33 | blk.1.ple.qn | `specialised::Kernel<(ng::Op)2, 1, 2560, 4>` | 272711704 | 81932 | — |  |
| 34 | blk.1.ple.gated | `p18::Glue` | 272696344 | 66572 | — |  |
| 35 | blk.1.ple.cn | `specialised::Kernel<(ng::Op)2, 0, 2560, 4>` | 272711704 | 81932 | — |  |
| 36 | blk.1.ple.cn | `specialised::Kernel<(ng::Op)2, 1, 2560, 4>` | 272711704 | 81932 | — |  |
| 37 | blk.1.ple.conv | `p18::NgHost` | 4767768 | 573452 | — |  |
| 38 | blk.1.ple.add | `p18::SimpleNew<(integrated::Op)16, 0, 0, 0>` | 272691212 | 61452 | — | LOW |
| 39 | blk.1.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 40 | blk.1.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 41 | blk.1.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 42 | blk.1.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 43 | blk.1.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 44 | blk.1.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 45 | blk.1.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 46 | blk.1.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 47 | blk.1.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 48 | blk.1.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 49 | blk.1.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 50 | blk.1.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 51 | blk.1.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 52 | blk.1.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 53 | blk.1.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 54 | blk.1.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 55 | blk.1.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 56 | blk.1.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 57 | blk.1.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 58 | blk.1.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 59 | blk.1.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 60 | blk.1.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 61 | blk.1.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 62 | blk.1.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 63 | blk.2.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 64 | blk.2.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 65 | blk.2.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 66 | blk.2.gdn.qkv | `p33::Kernel<0u, (iq3::Type)8, 2560u, 1u>` | 39543808 | 31155200 | — |  |
| 67 | blk.2.gdn.z | `p33::Kernel<0u, (iq3::Type)8, 2560u, 1u>` | 27083776 | 18695168 | — |  |
| 68 | blk.2.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 69 | blk.2.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 70 | blk.2.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 71 | blk.2.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 72 | blk.2.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 73 | blk.2.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 74 | blk.2.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 75 | blk.2.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 76 | blk.2.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 77 | blk.2.router | `p30integrated::Small` | 9153026 | 9153026 | — |  |
| 78 | blk.2.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 79 | blk.2.expsgate | `p28::Kernel<(iq3::Type)21, 2560u, 1u, 1u, false, true>` | 729315528 | 14110920 | — |  |
| 80 | blk.2.expsgate.check | `p18::Glue` | 272629824 | 52 | — | LOW |
| 81 | blk.2.expsup.check | `p18::Glue` | 272629824 | 52 | — | LOW |
| 82 | blk.2.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 83 | blk.2.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 84 | blk.2.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 85 | blk.2.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 86 | blk.2.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 87 | blk.2.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 88 | blk.2.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 89 | blk.3.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 90 | blk.3.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 91 | blk.3.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 92 | blk.3.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 93 | blk.3.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 94 | blk.3.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 95 | blk.3.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 96 | blk.3.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 97 | blk.3.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 98 | blk.3.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 99 | blk.3.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 100 | blk.3.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 101 | blk.3.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 102 | blk.3.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 103 | blk.3.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 104 | blk.3.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 105 | blk.3.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 106 | blk.3.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 107 | blk.3.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 108 | blk.3.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 109 | blk.3.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 110 | blk.3.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 111 | blk.3.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 112 | blk.3.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 113 | blk.3.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 114 | blk.3.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 115 | blk.3.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 116 | blk.3.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 117 | blk.3.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 118 | blk.3.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 119 | blk.3.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 120 | blk.4.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 121 | blk.4.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 122 | blk.4.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 123 | blk.4.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 124 | blk.4.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 125 | blk.4.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 126 | blk.4.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 127 | blk.4.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 128 | blk.4.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 129 | blk.4.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 130 | blk.4.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 131 | blk.4.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 132 | blk.4.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 133 | blk.4.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 134 | blk.4.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 135 | blk.4.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 136 | blk.4.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 137 | blk.4.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 138 | blk.4.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 139 | blk.4.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 140 | blk.4.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 141 | blk.4.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 142 | blk.4.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 143 | blk.4.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 144 | blk.5.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 145 | blk.5.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 146 | blk.5.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 147 | blk.5.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 148 | blk.5.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 149 | blk.5.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 150 | blk.5.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 151 | blk.5.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 152 | blk.5.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 153 | blk.5.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 154 | blk.5.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 155 | blk.5.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 156 | blk.5.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 157 | blk.5.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 158 | blk.5.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 159 | blk.5.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 160 | blk.5.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 161 | blk.5.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 162 | blk.5.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 163 | blk.5.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 164 | blk.5.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 165 | blk.5.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 166 | blk.5.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 167 | blk.5.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 168 | blk.6.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 169 | blk.6.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 170 | blk.6.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 171 | blk.6.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 172 | blk.6.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 173 | blk.6.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 174 | blk.6.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 175 | blk.6.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 176 | blk.6.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 177 | blk.6.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 178 | blk.6.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 179 | blk.6.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 180 | blk.6.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 181 | blk.6.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 182 | blk.6.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 183 | blk.6.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 184 | blk.6.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 185 | blk.6.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 186 | blk.6.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 187 | blk.6.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 188 | blk.6.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 189 | blk.6.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 190 | blk.6.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 191 | blk.6.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 192 | blk.7.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 193 | blk.7.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 194 | blk.7.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 195 | blk.7.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 196 | blk.7.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 197 | blk.7.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 198 | blk.7.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 199 | blk.7.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 200 | blk.7.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 201 | blk.7.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 202 | blk.7.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 203 | blk.7.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 204 | blk.7.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 205 | blk.7.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 206 | blk.7.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 207 | blk.7.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 208 | blk.7.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 209 | blk.7.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 210 | blk.7.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 211 | blk.7.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 212 | blk.7.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 213 | blk.7.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 214 | blk.7.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 215 | blk.7.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 216 | blk.7.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 217 | blk.7.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 218 | blk.7.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 219 | blk.7.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 220 | blk.7.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 221 | blk.7.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 222 | blk.7.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 223 | blk.8.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 224 | blk.8.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 225 | blk.8.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 226 | blk.8.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 227 | blk.8.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 228 | blk.8.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 229 | blk.8.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 230 | blk.8.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 231 | blk.8.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 232 | blk.8.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 233 | blk.8.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 234 | blk.8.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 235 | blk.8.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 236 | blk.8.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 237 | blk.8.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 238 | blk.8.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 239 | blk.8.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 240 | blk.8.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 241 | blk.8.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 242 | blk.8.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 243 | blk.8.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 244 | blk.8.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 245 | blk.8.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 246 | blk.8.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 247 | blk.9.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 248 | blk.9.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 249 | blk.9.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 250 | blk.9.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 251 | blk.9.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 252 | blk.9.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 253 | blk.9.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 254 | blk.9.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 255 | blk.9.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 256 | blk.9.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 257 | blk.9.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 258 | blk.9.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 259 | blk.9.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 260 | blk.9.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 261 | blk.9.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 262 | blk.9.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 263 | blk.9.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 264 | blk.9.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 265 | blk.9.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 266 | blk.9.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 267 | blk.9.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 268 | blk.9.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 269 | blk.9.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 270 | blk.9.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 271 | blk.10.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 272 | blk.10.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 273 | blk.10.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 274 | blk.10.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 275 | blk.10.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 276 | blk.10.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 277 | blk.10.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 278 | blk.10.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 279 | blk.10.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 280 | blk.10.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 281 | blk.10.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 282 | blk.10.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 283 | blk.10.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 284 | blk.10.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 285 | blk.10.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 286 | blk.10.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 287 | blk.10.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 288 | blk.10.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 289 | blk.10.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 290 | blk.10.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 291 | blk.10.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 292 | blk.10.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 293 | blk.10.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 294 | blk.10.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 295 | blk.11.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 296 | blk.11.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 297 | blk.11.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 298 | blk.11.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 299 | blk.11.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 300 | blk.11.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 301 | blk.11.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 302 | blk.11.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 303 | blk.11.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 304 | blk.11.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 305 | blk.11.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 306 | blk.11.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 307 | blk.11.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 308 | blk.11.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 309 | blk.11.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 310 | blk.11.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 311 | blk.11.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 312 | blk.11.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 313 | blk.11.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 314 | blk.11.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 315 | blk.11.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 316 | blk.11.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 317 | blk.11.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 318 | blk.11.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 319 | blk.11.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 320 | blk.11.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 321 | blk.11.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 322 | blk.11.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 323 | blk.11.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 324 | blk.11.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 325 | blk.11.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 326 | blk.12.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 327 | blk.12.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 328 | blk.12.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 329 | blk.12.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 330 | blk.12.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 331 | blk.12.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 332 | blk.12.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 333 | blk.12.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 334 | blk.12.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 335 | blk.12.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 336 | blk.12.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 337 | blk.12.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 338 | blk.12.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 339 | blk.12.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 340 | blk.12.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 341 | blk.12.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 342 | blk.12.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 343 | blk.12.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 344 | blk.12.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 345 | blk.12.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 346 | blk.12.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 347 | blk.12.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 348 | blk.12.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 349 | blk.12.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 350 | blk.13.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 351 | blk.13.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 352 | blk.13.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 353 | blk.13.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 354 | blk.13.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 355 | blk.13.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 356 | blk.13.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 357 | blk.13.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 358 | blk.13.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 359 | blk.13.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 360 | blk.13.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 361 | blk.13.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 362 | blk.13.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 363 | blk.13.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 364 | blk.13.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 365 | blk.13.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 366 | blk.13.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 367 | blk.13.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 368 | blk.13.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 369 | blk.13.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 370 | blk.13.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 371 | blk.13.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 372 | blk.13.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 373 | blk.13.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 374 | blk.14.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 375 | blk.14.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 376 | blk.14.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 377 | blk.14.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 378 | blk.14.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 379 | blk.14.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 380 | blk.14.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 381 | blk.14.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 382 | blk.14.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 383 | blk.14.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 384 | blk.14.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 385 | blk.14.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 386 | blk.14.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 387 | blk.14.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 388 | blk.14.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 389 | blk.14.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 390 | blk.14.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 391 | blk.14.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 392 | blk.14.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 393 | blk.14.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 394 | blk.14.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 395 | blk.14.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 396 | blk.14.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 397 | blk.14.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 398 | blk.15.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 399 | blk.15.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 400 | blk.15.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 401 | blk.15.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 402 | blk.15.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 403 | blk.15.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 404 | blk.15.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 405 | blk.15.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 406 | blk.15.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 407 | blk.15.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 408 | blk.15.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 409 | blk.15.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 410 | blk.15.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 411 | blk.15.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 412 | blk.15.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 413 | blk.15.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 414 | blk.15.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 415 | blk.15.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 416 | blk.15.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 417 | blk.15.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 418 | blk.15.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 419 | blk.15.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 420 | blk.15.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 421 | blk.15.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 422 | blk.15.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 423 | blk.15.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 424 | blk.15.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 425 | blk.15.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 426 | blk.15.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 427 | blk.15.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 428 | blk.15.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 429 | blk.16.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 430 | blk.16.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 431 | blk.16.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 432 | blk.16.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 433 | blk.16.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 434 | blk.16.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 435 | blk.16.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 436 | blk.16.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 437 | blk.16.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 438 | blk.16.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 439 | blk.16.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 440 | blk.16.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 441 | blk.16.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 442 | blk.16.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 443 | blk.16.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 444 | blk.16.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 445 | blk.16.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 446 | blk.16.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 447 | blk.16.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 448 | blk.16.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 449 | blk.16.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 450 | blk.16.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 451 | blk.16.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 452 | blk.16.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 453 | blk.17.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 454 | blk.17.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 455 | blk.17.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 456 | blk.17.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 457 | blk.17.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 458 | blk.17.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 459 | blk.17.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 460 | blk.17.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 461 | blk.17.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 462 | blk.17.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 463 | blk.17.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 464 | blk.17.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 465 | blk.17.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 466 | blk.17.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 467 | blk.17.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 468 | blk.17.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 469 | blk.17.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 470 | blk.17.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 471 | blk.17.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 472 | blk.17.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 473 | blk.17.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 474 | blk.17.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 475 | blk.17.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 476 | blk.17.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 477 | blk.18.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 478 | blk.18.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 479 | blk.18.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 480 | blk.18.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 481 | blk.18.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 482 | blk.18.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 483 | blk.18.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 484 | blk.18.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 485 | blk.18.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 486 | blk.18.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 487 | blk.18.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 488 | blk.18.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 489 | blk.18.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 490 | blk.18.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 491 | blk.18.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 492 | blk.18.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 493 | blk.18.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 494 | blk.18.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 495 | blk.18.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 496 | blk.18.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 497 | blk.18.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 498 | blk.18.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 499 | blk.18.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 500 | blk.18.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 501 | blk.19.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 502 | blk.19.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 503 | blk.19.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 504 | blk.19.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 505 | blk.19.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 506 | blk.19.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 507 | blk.19.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 508 | blk.19.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 509 | blk.19.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 510 | blk.19.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 511 | blk.19.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 512 | blk.19.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 513 | blk.19.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 514 | blk.19.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 515 | blk.19.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 516 | blk.19.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 517 | blk.19.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 518 | blk.19.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 519 | blk.19.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 520 | blk.19.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 521 | blk.19.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 522 | blk.19.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 523 | blk.19.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 524 | blk.19.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 525 | blk.19.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 526 | blk.19.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 527 | blk.19.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 528 | blk.19.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 529 | blk.19.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 530 | blk.19.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 531 | blk.19.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 532 | blk.20.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 533 | blk.20.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 534 | blk.20.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 535 | blk.20.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 536 | blk.20.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 537 | blk.20.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 538 | blk.20.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 539 | blk.20.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 540 | blk.20.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 541 | blk.20.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 542 | blk.20.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 543 | blk.20.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 544 | blk.20.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 545 | blk.20.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 546 | blk.20.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 547 | blk.20.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 548 | blk.20.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 549 | blk.20.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 550 | blk.20.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 551 | blk.20.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 552 | blk.20.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 553 | blk.20.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 554 | blk.20.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 555 | blk.20.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 556 | blk.21.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 557 | blk.21.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 558 | blk.21.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 559 | blk.21.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 560 | blk.21.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 561 | blk.21.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 562 | blk.21.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 563 | blk.21.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 564 | blk.21.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 565 | blk.21.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 566 | blk.21.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 567 | blk.21.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 568 | blk.21.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 569 | blk.21.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 570 | blk.21.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 571 | blk.21.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 572 | blk.21.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 573 | blk.21.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 574 | blk.21.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 575 | blk.21.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 576 | blk.21.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 577 | blk.21.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 578 | blk.21.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 579 | blk.21.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 580 | blk.22.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 581 | blk.22.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 582 | blk.22.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 583 | blk.22.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 584 | blk.22.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 585 | blk.22.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 586 | blk.22.gdn.conv | `p18::NgHost` | 4522008 | 327692 | — |  |
| 587 | blk.22.gdn.recurrence | `p82brec::Kernel<true>` | 7373388 | 3179084 | — |  |
| 588 | blk.22.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 589 | blk.22.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 590 | blk.22.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 591 | blk.22.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 592 | blk.22.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 593 | blk.22.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 594 | blk.22.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 595 | blk.22.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 596 | blk.22.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 597 | blk.22.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 598 | blk.22.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 599 | blk.22.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 600 | blk.22.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 601 | blk.22.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 602 | blk.22.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 603 | blk.22.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 604 | blk.23.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 605 | blk.23.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 606 | blk.23.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 607 | blk.23.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 608 | blk.23.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 609 | blk.23.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 610 | blk.23.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 611 | blk.23.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 612 | blk.23.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 613 | blk.23.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 614 | blk.23.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 615 | blk.23.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 616 | blk.23.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 617 | blk.23.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 618 | blk.23.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 619 | blk.23.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 620 | blk.23.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 621 | blk.23.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 622 | blk.23.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 623 | blk.23.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 624 | blk.23.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 625 | blk.23.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 626 | blk.23.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 627 | blk.23.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 628 | blk.23.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 629 | blk.23.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 630 | blk.23.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 631 | blk.23.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 632 | blk.23.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 633 | blk.23.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 634 | blk.23.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 635 | commit.final | `p18::Glue` | 272629784 | 12 | — | LOW |

### Rank 1: target layers24–47 and head

| # | Layer/site | Kernel | Bound bytes | Working bytes | Useful bytes | Small |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 0 | begin.0 | `p18::Glue` | 272629784 | 12 | — | LOW |
| 1 | blk.24.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 2 | blk.24.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 3 | blk.24.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 4 | blk.24.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 5 | blk.24.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 6 | blk.24.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 7 | blk.24.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 8 | blk.24.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 9 | blk.24.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 10 | blk.24.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 11 | blk.24.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 12 | blk.24.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 13 | blk.24.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 14 | blk.24.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 15 | blk.24.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 16 | blk.24.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 17 | blk.24.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 18 | blk.24.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 19 | blk.24.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 20 | blk.24.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 21 | blk.24.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 22 | blk.24.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 23 | blk.24.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 24 | blk.24.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 25 | blk.25.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 26 | blk.25.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 27 | blk.25.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 28 | blk.25.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 29 | blk.25.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 30 | blk.25.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 31 | blk.25.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 32 | blk.25.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 33 | blk.25.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 34 | blk.25.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 35 | blk.25.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 36 | blk.25.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 37 | blk.25.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 38 | blk.25.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 39 | blk.25.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 40 | blk.25.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 41 | blk.25.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 42 | blk.25.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 43 | blk.25.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 44 | blk.25.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 45 | blk.25.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 46 | blk.25.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 47 | blk.25.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 48 | blk.25.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 49 | blk.26.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 50 | blk.26.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 51 | blk.26.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 52 | blk.26.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 53 | blk.26.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 54 | blk.26.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 55 | blk.26.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 56 | blk.26.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 57 | blk.26.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 58 | blk.26.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 59 | blk.26.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 60 | blk.26.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 61 | blk.26.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 62 | blk.26.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 63 | blk.26.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 64 | blk.26.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 65 | blk.26.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 66 | blk.26.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 67 | blk.26.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 68 | blk.26.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 69 | blk.26.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 70 | blk.26.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 71 | blk.26.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 72 | blk.26.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 73 | blk.27.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 74 | blk.27.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 75 | blk.27.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 76 | blk.27.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 77 | blk.27.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 78 | blk.27.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 79 | blk.27.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 80 | blk.27.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 81 | blk.27.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 82 | blk.27.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 83 | blk.27.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 84 | blk.27.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 85 | blk.27.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 86 | blk.27.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 87 | blk.27.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 88 | blk.27.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 89 | blk.27.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 90 | blk.27.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 91 | blk.27.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 92 | blk.27.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 93 | blk.27.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 94 | blk.27.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 95 | blk.27.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 96 | blk.27.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 97 | blk.27.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 98 | blk.27.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 99 | blk.27.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 100 | blk.27.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 101 | blk.27.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 102 | blk.27.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 103 | blk.27.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 104 | blk.28.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 105 | blk.28.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 106 | blk.28.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 107 | blk.28.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 108 | blk.28.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 109 | blk.28.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 110 | blk.28.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 111 | blk.28.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 112 | blk.28.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 113 | blk.28.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 114 | blk.28.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 115 | blk.28.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 116 | blk.28.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 117 | blk.28.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 118 | blk.28.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 119 | blk.28.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 120 | blk.28.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 121 | blk.28.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 122 | blk.28.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 123 | blk.28.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 124 | blk.28.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 125 | blk.28.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 126 | blk.28.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 127 | blk.28.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 128 | blk.29.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 129 | blk.29.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 130 | blk.29.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 131 | blk.29.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 132 | blk.29.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 133 | blk.29.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 134 | blk.29.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 135 | blk.29.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 136 | blk.29.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 137 | blk.29.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 138 | blk.29.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 139 | blk.29.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 140 | blk.29.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 141 | blk.29.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 142 | blk.29.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 143 | blk.29.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 144 | blk.29.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 145 | blk.29.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 146 | blk.29.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 147 | blk.29.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 148 | blk.29.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 149 | blk.29.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 150 | blk.29.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 151 | blk.29.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 152 | blk.30.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 153 | blk.30.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 154 | blk.30.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 155 | blk.30.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 156 | blk.30.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 157 | blk.30.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 158 | blk.30.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 159 | blk.30.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 160 | blk.30.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 161 | blk.30.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 162 | blk.30.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 163 | blk.30.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 164 | blk.30.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 165 | blk.30.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 166 | blk.30.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 167 | blk.30.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 168 | blk.30.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 169 | blk.30.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 170 | blk.30.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 171 | blk.30.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 172 | blk.30.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 173 | blk.30.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 174 | blk.30.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 175 | blk.30.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 176 | blk.31.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 177 | blk.31.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 178 | blk.31.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 179 | blk.31.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 180 | blk.31.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 181 | blk.31.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 182 | blk.31.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 183 | blk.31.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 184 | blk.31.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 185 | blk.31.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 186 | blk.31.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 187 | blk.31.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 188 | blk.31.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 189 | blk.31.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 190 | blk.31.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 191 | blk.31.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 192 | blk.31.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 193 | blk.31.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 194 | blk.31.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 195 | blk.31.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 196 | blk.31.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 197 | blk.31.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 198 | blk.31.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 199 | blk.31.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 200 | blk.31.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 201 | blk.31.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 202 | blk.31.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 203 | blk.31.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 204 | blk.31.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 205 | blk.31.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 206 | blk.31.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 207 | blk.32.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 208 | blk.32.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 209 | blk.32.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 210 | blk.32.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 211 | blk.32.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 212 | blk.32.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 213 | blk.32.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 214 | blk.32.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 215 | blk.32.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 216 | blk.32.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 217 | blk.32.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 218 | blk.32.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 219 | blk.32.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 220 | blk.32.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 221 | blk.32.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 222 | blk.32.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 223 | blk.32.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 224 | blk.32.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 225 | blk.32.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 226 | blk.32.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 227 | blk.32.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 228 | blk.32.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 229 | blk.32.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 230 | blk.32.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 231 | blk.33.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 232 | blk.33.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 233 | blk.33.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 234 | blk.33.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 235 | blk.33.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 236 | blk.33.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 237 | blk.33.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 238 | blk.33.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 239 | blk.33.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 240 | blk.33.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 241 | blk.33.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 242 | blk.33.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 243 | blk.33.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 244 | blk.33.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 245 | blk.33.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 246 | blk.33.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 247 | blk.33.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 248 | blk.33.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 249 | blk.33.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 250 | blk.33.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 251 | blk.33.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 252 | blk.33.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 253 | blk.33.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 254 | blk.33.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 255 | blk.34.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 256 | blk.34.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 257 | blk.34.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 258 | blk.34.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 259 | blk.34.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 260 | blk.34.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 261 | blk.34.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 262 | blk.34.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 263 | blk.34.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 264 | blk.34.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 265 | blk.34.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 266 | blk.34.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 267 | blk.34.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 268 | blk.34.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 269 | blk.34.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 270 | blk.34.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 271 | blk.34.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 272 | blk.34.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 273 | blk.34.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 274 | blk.34.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 275 | blk.34.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 276 | blk.34.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 277 | blk.34.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 278 | blk.34.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 279 | blk.35.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 280 | blk.35.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 281 | blk.35.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 282 | blk.35.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 283 | blk.35.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 284 | blk.35.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 285 | blk.35.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 286 | blk.35.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 287 | blk.35.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 288 | blk.35.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 289 | blk.35.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 290 | blk.35.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 291 | blk.35.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 292 | blk.35.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 293 | blk.35.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 294 | blk.35.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 295 | blk.35.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 296 | blk.35.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 297 | blk.35.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 298 | blk.35.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 299 | blk.35.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 300 | blk.35.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 301 | blk.35.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 302 | blk.35.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 303 | blk.35.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 304 | blk.35.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 305 | blk.35.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 306 | blk.35.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 307 | blk.35.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 308 | blk.35.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 309 | blk.35.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 310 | blk.36.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 311 | blk.36.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 312 | blk.36.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 313 | blk.36.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 314 | blk.36.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 315 | blk.36.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 316 | blk.36.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 317 | blk.36.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 318 | blk.36.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 319 | blk.36.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 320 | blk.36.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 321 | blk.36.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 322 | blk.36.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 323 | blk.36.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 324 | blk.36.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 325 | blk.36.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 326 | blk.36.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 327 | blk.36.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 328 | blk.36.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 329 | blk.36.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 330 | blk.36.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 331 | blk.36.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 332 | blk.36.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 333 | blk.36.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 334 | blk.37.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 335 | blk.37.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 336 | blk.37.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 337 | blk.37.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 338 | blk.37.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 339 | blk.37.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 340 | blk.37.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 341 | blk.37.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 342 | blk.37.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 343 | blk.37.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 344 | blk.37.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 345 | blk.37.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 346 | blk.37.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 347 | blk.37.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 348 | blk.37.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 349 | blk.37.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 350 | blk.37.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 351 | blk.37.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 352 | blk.37.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 353 | blk.37.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 354 | blk.37.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 355 | blk.37.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 356 | blk.37.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 357 | blk.37.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 358 | blk.38.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 359 | blk.38.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 360 | blk.38.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 361 | blk.38.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 362 | blk.38.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 363 | blk.38.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 364 | blk.38.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 365 | blk.38.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 366 | blk.38.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 367 | blk.38.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 368 | blk.38.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 369 | blk.38.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 370 | blk.38.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 371 | blk.38.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 372 | blk.38.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 373 | blk.38.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 374 | blk.38.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 375 | blk.38.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 376 | blk.38.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 377 | blk.38.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 378 | blk.38.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 379 | blk.38.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 380 | blk.38.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 381 | blk.38.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 382 | blk.39.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 383 | blk.39.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 384 | blk.39.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 385 | blk.39.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 386 | blk.39.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 387 | blk.39.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 388 | blk.39.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 389 | blk.39.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 390 | blk.39.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 391 | blk.39.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 392 | blk.39.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 393 | blk.39.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 394 | blk.39.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 395 | blk.39.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 396 | blk.39.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 397 | blk.39.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 398 | blk.39.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 399 | blk.39.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 400 | blk.39.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 401 | blk.39.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 402 | blk.39.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 403 | blk.39.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 404 | blk.39.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 405 | blk.39.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 406 | blk.39.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 407 | blk.39.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 408 | blk.39.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 409 | blk.39.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 410 | blk.39.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 411 | blk.39.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 412 | blk.39.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 413 | blk.40.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 414 | blk.40.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 415 | blk.40.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 416 | blk.40.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 417 | blk.40.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 418 | blk.40.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 419 | blk.40.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 420 | blk.40.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 421 | blk.40.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 422 | blk.40.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 423 | blk.40.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 424 | blk.40.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 425 | blk.40.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 426 | blk.40.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 427 | blk.40.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 428 | blk.40.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 429 | blk.40.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 430 | blk.40.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 431 | blk.40.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 432 | blk.40.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 433 | blk.40.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 434 | blk.40.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 435 | blk.40.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 436 | blk.40.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 437 | blk.41.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 438 | blk.41.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 439 | blk.41.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 440 | blk.41.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 441 | blk.41.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 442 | blk.41.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 443 | blk.41.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 444 | blk.41.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 445 | blk.41.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 446 | blk.41.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 447 | blk.41.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 448 | blk.41.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 449 | blk.41.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 450 | blk.41.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 451 | blk.41.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 452 | blk.41.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 453 | blk.41.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 454 | blk.41.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 455 | blk.41.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 456 | blk.41.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 457 | blk.41.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 458 | blk.41.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 459 | blk.41.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 460 | blk.41.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 461 | blk.42.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 462 | blk.42.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 463 | blk.42.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 464 | blk.42.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 465 | blk.42.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 466 | blk.42.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 467 | blk.42.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 468 | blk.42.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 469 | blk.42.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 470 | blk.42.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 471 | blk.42.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 472 | blk.42.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 473 | blk.42.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 474 | blk.42.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 475 | blk.42.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 476 | blk.42.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 477 | blk.42.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 478 | blk.42.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 479 | blk.42.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 480 | blk.42.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 481 | blk.42.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 482 | blk.42.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 483 | blk.42.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 484 | blk.42.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 485 | blk.43.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 486 | blk.43.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 487 | blk.43.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 488 | blk.43.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 489 | blk.43.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 490 | blk.43.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 491 | blk.43.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 492 | blk.43.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 493 | blk.43.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 494 | blk.43.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 495 | blk.43.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 496 | blk.43.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 497 | blk.43.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 498 | blk.43.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 499 | blk.43.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 500 | blk.43.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 501 | blk.43.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 502 | blk.43.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 503 | blk.43.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 504 | blk.43.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 505 | blk.43.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 506 | blk.43.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 507 | blk.43.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 508 | blk.43.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 509 | blk.43.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 510 | blk.43.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 511 | blk.43.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 512 | blk.43.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 513 | blk.43.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 514 | blk.43.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 515 | blk.43.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 516 | blk.44.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 517 | blk.44.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 518 | blk.44.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 519 | blk.44.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 520 | blk.44.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 521 | blk.44.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 522 | blk.44.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 523 | blk.44.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 524 | blk.44.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 525 | blk.44.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 526 | blk.44.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 527 | blk.44.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 528 | blk.44.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 529 | blk.44.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 530 | blk.44.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 531 | blk.44.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 532 | blk.44.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 533 | blk.44.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 534 | blk.44.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 535 | blk.44.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 536 | blk.44.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 537 | blk.44.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 538 | blk.44.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 539 | blk.44.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 540 | blk.45.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 541 | blk.45.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 542 | blk.45.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 543 | blk.45.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 544 | blk.45.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 545 | blk.45.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 546 | blk.45.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 547 | blk.45.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 548 | blk.45.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 549 | blk.45.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 550 | blk.45.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 551 | blk.45.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 552 | blk.45.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 553 | blk.45.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 554 | blk.45.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 555 | blk.45.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 556 | blk.45.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 557 | blk.45.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 558 | blk.45.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 559 | blk.45.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 560 | blk.45.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 561 | blk.45.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 562 | blk.45.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 563 | blk.45.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 564 | blk.46.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 565 | blk.46.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 566 | blk.46.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 567 | blk.46.gdn.qkv | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 43025408 | 34636800 | — |  |
| 568 | blk.46.gdn.z | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 29172736 | 20784128 | — |  |
| 569 | blk.46.gdn.a | `p27::Tuple<p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Member<(iq3::Type)0, 48u, 2560u, 4u>, p27::Empty, p27::Empty>` | 988352 | 988352 | — |  |
| 570 | blk.46.gdn.conv | `p18::NgHost` | 4460568 | 266252 | — |  |
| 571 | blk.46.gdn.recurrence | `p82brec::Kernel<true>` | 5800524 | 1606220 | — |  |
| 572 | blk.46.gdn.gated | `p42::Kernel<(ng::Op)8, 0, 0>` | 272667160 | 37388 | — | LOW |
| 573 | blk.46.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 574 | blk.46.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 575 | blk.46.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 576 | blk.46.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 577 | blk.46.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 578 | blk.46.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 579 | blk.46.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 580 | blk.46.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 581 | blk.46.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 582 | blk.46.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 583 | blk.46.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 584 | blk.46.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 585 | blk.46.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 586 | blk.46.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 587 | blk.46.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 588 | blk.47.hc.a.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 589 | blk.47.hc.a.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 590 | blk.47.hc.a.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 591 | blk.47.qsa.qgate | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 49951744 | 41563136 | — |  |
| 592 | blk.47.qsa.k | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 593 | blk.47.qsa.v | `p28::Kernel<(iq3::Type)14, 2560u, 4u, 4u, false, false>` | 10125312 | 1736704 | — |  |
| 594 | blk.47.qsa.iq | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 4u, false, false>` | 11016192 | 2627584 | — |  |
| 595 | blk.47.qsa.ik | `p28::Kernel<(iq3::Type)30, 2560u, 4u, 1u, false, false>` | 9049344 | 660736 | — |  |
| 596 | blk.47.qsa.ik | `p28::split4 finish (device-only)` | 9049344 | 660736 | 2304 | LOW |
| 597 | blk.47.qsa.prepare | `p42::Kernel<(ng::Op)9, 0, 0>` | 272685592 | 55820 | — | LOW |
| 598 | blk.47.qsa.pool | `p42::Kernel<(ng::Op)10, 0, 0>` | 282331928 | 9702156 | — |  |
| 599 | blk.47.qsa.select | `round2::Kernel<(ng::Op)11, 0>` | 272901156 | 271384 | — |  |
| 600 | blk.47.qsa.select | `round2::Kernel<(ng::Op)11, 1>` | 272901156 | 271384 | — |  |
| 601 | blk.47.qsa.attention | `p49::Attention<0>` | 281457252 | 8827480 | — |  |
| 602 | blk.47.qsa.attention | `p49::Attention<1>` | 281457252 | 8827480 | — |  |
| 603 | blk.47.qsa.attention | `p49::Attention<2>` | 281457252 | 8827480 | — |  |
| 604 | blk.47.attention | `p49c::DenseKernel<(iq3::Type)14, 6144u, 4u, (p39::Kind)4, 0u, false>` | 29193236 | 20804628 | — |  |
| 605 | blk.47.attention | `p49c::attention-combine finish (device-only)` | 29193236 | 20804628 | 87048 |  |
| 606 | blk.47.hc.f.norm | `p60::Kernel<0, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 607 | blk.47.hc.f.low | `p60::Kernel<1, false, false, false, false>` | 284879124 | 8055060 | — |  |
| 608 | blk.47.hc.f.gate | `p60::Kernel<2, true, false, false, false>` | 284879124 | 8055060 | — |  |
| 609 | blk.47.router | `p49dvirtual::SmallKernel<4u>` | 9588226 | 9588226 | — |  |
| 610 | blk.47.route | `p78route::Kernel` | 272631116 | 1356 | 3648 | LOW |
| 611 | blk.47.expsgate | `p90exp::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>` | 558921940 | 10782932 | — |  |
| 612 | blk.47.expsact | `p18::NgHost` | 4232728 | 38412 | 38400 | LOW |
| 613 | blk.47.expsdown | `p100::Kernel<2u>` | 480311980 | 9280172 | — |  |
| 614 | blk.47.shexpact | `p18::NgHost` | 4198168 | 3852 | 3840 | LOW |
| 615 | blk.47.shexpdown | `p33::Kernel<0u, (iq3::Type)8, 640u, 1u>` | 10340608 | 1952000 | — |  |
| 616 | blk.47.moe | `integrated::Combine` | 56360 | 56360 | 56360 | LOW |
| 617 | blk.47.moe | `p18::NgHost` | 4209694 | 15378 | 15366 | LOW |
| 618 | blk.47.ffn.combine | `p18::SimpleNew<(integrated::Op)4, 0, 0, 0>` | 272655380 | 25620 | 46088 | LOW |
| 619 | final.norm | `specialised::Kernel<(ng::Op)2, 0, 2560, 4>` | 272711704 | 81932 | — |  |
| 620 | final.norm | `specialised::Kernel<(ng::Op)2, 1, 2560, 4>` | 272711704 | 81932 | — |  |
| 621 | final.low | `p39::Kernel<(iq3::Type)8, 10240u, (p39::Kind)2, 4u, 0u>` | 12301580 | 3912972 | — |  |
| 622 | final.gate | `p33::Kernel<0u, (iq3::Type)8, 320u, 1u>` | 12300928 | 3912320 | — |  |
| 623 | final.mix | `p18::NgHost` | 4240408 | 46092 | — | LOW |
| 624 | logits | `p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>` | 848211968 | 839823360 | — |  |
| 625 | argmax | `round2::Simple<(integrated::Op)17, 0, (flash::Scalar)0, 0, 0>` | 273126416 | 496656 | — |  |
| 626 | argmax | `round2::Simple<(integrated::Op)17, 1, (flash::Scalar)0, 0, 0>` | 273126416 | 496656 | — |  |
| 627 | commit.final | `p18::Glue` | 272629784 | 12 | — | LOW |
