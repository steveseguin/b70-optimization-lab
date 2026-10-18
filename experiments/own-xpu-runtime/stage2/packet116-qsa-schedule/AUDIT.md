# Packet116 QSA schedule audit

CPU source audit, 2026-10-18. No device or service was opened. This describes
packet103's selected runtime, not packet47's superseded old-attention control.
The current source makes latency and instruction/synchronization overhead
plausible causes; useful-byte bandwidth alone does not prove a hardware stall
or spill mechanism. Device timing remains the kill gate.

## Current implementation and exact identity

The authoritative target arithmetic label is `iq3-p49-split32-v1`
([arithmetic.hpp](../packet103-record-bundle/arithmetic.hpp)). Although
[dispatch-speed6.json](../packet103-record-bundle/dispatch-speed6.json) retains
`qsa.attention=p30.attention.score_softmax`, `Engine::bind` in
[main.cpp](../packet103-record-bundle/main.cpp) overrides full-width target
attention to implementation 12. [adapter.cpp](../packet103-record-bundle/adapter.cpp)
routes that value to [p49_qsa_submit.cpp](../packet103-record-bundle/p49_qsa_submit.cpp).
The actual attention body is [p49_qsa_kernel.hpp](../packet103-record-bundle/p49_qsa_kernel.hpp),
a copy of the accepted packet47 split32 body. Selection is the two-stage
`round2` implementation in [round2.hpp](../packet103-record-bundle/round2.hpp)
and [round2_submit.cpp](../packet103-record-bundle/round2_submit.cpp).

Packet103 also selects split32 for the draft through its own selection binding;
that does not authorize claiming parity against the earlier draft tree. A
runtime schedule switch must cover every intended target/draft prepared capture
and preserve each registered reference path.

The target has 24 query heads of 256 components, two KV heads, and BF16 Q/K/V,
gates and outputs. Query head h reads KV head h/12. The indexer has four query
heads of 128 components and one pooled key per completed group of four tokens.
The ranked selected order is part of arithmetic identity, even below budget.
For occupied length C, the selected count is
`4*min(floor(C/4),512)+(C mod 4)`. It is 128 at C=128 and 2048 at C=4096;
2051 occurs at remainder-three lengths, not at C=4096.

## Current attention schedule

All three stages carry the same `qsa.attention` class label. Sum every event
per invocation before taking process medians.

1. Admission launches one work-item per row. It serially walks the selected
   IDs once, checks causal/capacity/launch bounds and writes counts. Inactive,
   sticky-error and invalid-position behavior must stay unchanged. Empty
   selections do not write attention output.
2. Tile launches one WG of 128 threads (four SG32) per row × query head ×
   fixed 32-selected-index block. At extent128 this is 96 WGs per row. At
   extent4096 the allocation/launch cap2051 gives 65 blocks and 1560 WGs;
   the last block returns when only2048 selections are occupied, leaving1536
   active WGs. Each subgroup computes eight score positions serially. Each
   score lane loads eight consecutive Q and K components, computes eight
   products and their adjacent tree, then the five-level adjacent SG32 tree.
   Three WG barriers separate scores, the lane-zero maximum, and exponential
   weights. Lane zero visits up to32 scores in selected order for the maximum.
   The first subgroup computes the denominator's fixed32 tree. Each of all128
   work-items serially loads32 selected V pairs, holds64 float leaves and
   reduces two independent fixed32 adjacent trees. It writes two numerator
   components plus the shared maximum/denominator in a258-float tile record.
3. Combine launches24 WGs per row, each128 threads. Lane zero visits up to65
   split maxima serially. Threads compute factors, then a shared denominator
   tree, with two initial WG barriers and one barrier per upper tree level
   (two levels for four occupied splits, six for64). Each thread serially
   gathers/reduces two component arrays with up to65 leaves. It divides once,
   rounds to BF16, multiplies the gate sigmoid, then rounds the output to BF16.

Thus, head × position-block parallelism already exists. Naming it again is
not a new lever. The short case has only96 tile WGs, and the combine has only24;
the tile still performs serial score positions and long private value trees.
Dynamic private arrays, repeated shuffles, deterministic exponentials, serial
maxima, WG barriers and the serial admission all consume time beyond useful
memory traffic. Compiler spill/occupancy evidence is needed before asserting
that any particular one dominates. At4096 there are already1536 useful tile
WGs, so a claim of universally too few groups would be unsupported.

## Current selection schedule

Both stages launch one SG32 WG per row × potential completed four-token block:
`tokens*ceil(launch_extent/4)`. Only blocks below the actual completed count do
score/rank work. At occupied128/4096 the counts are32/1024.

Stage0 computes four tree128 dot products in fixed head order. Each WG has two
uniform guard barriers, then for each head one fill barrier, seven tree-level
barriers and one post-tree barrier:38 WG barriers for the active score body.
Each lane supplies four product leaves. The scalar head sum starts at +0,
adds `std::max(0.f,dot)` for heads0..3, then divides by deterministic sqrt128.
Its scratch score is FP32 and must be compared byte-for-byte.

Stage1 has two guard barriers. Every work-item independently scans all B block
scores for finiteness; the source therefore expresses32 redundant scans/WG.
Lane zero alone then counts outranking scores through a second serial B-loop.
There are B² ranking predicates, plus the redundant validation, even though
only the best512 blocks are retained. The2048 selected-token limit does not
bound the cost of ranking all completed blocks. At4096 B²=1,048,576.

Rank is `x>v || (x==v && other_block<block)`: descending FP32 score, increasing
original block ID on ties (including +/-0). Each chosen block writes its four
tokens in chronological within-block order. WG0 alone appends the unfinished
0..3-token suffix and writes the remaining2051-ID allocation to -1. Those
writers are deliberately disjoint from selected ranks. A nonfinite block
score makes WG0 fill all IDs with -1 and set sticky error; other WGs must not
write selected IDs. Input NaNs are not equivalent to a nonfinite block score:
`std::max(0.f,NaN)` can suppress a NaN dot. Do not reject raw inputs early.

## Fixed arithmetic that a new schedule must reproduce

[Packet47 ORACLE.md](../packet47-qsa-attn/ORACLE.md) and the independent scalar
[p49_qsa_reference.hpp](../packet103-record-bundle/p49_qsa_reference.hpp) define:

- Every score is the adjacent256-leaf product tree divided by sqrt256.
- Split b owns selected positions32b..32b+31. Its maximum visits valid leaves
  in ascending selected order. Every valid exponential uses the existing
  deterministic `detmath::exp(score-local_max)`.
- Denominator and each weighted-value numerator use exactly32 leaves, +0
  padding for missing leaves, and all five lower tree levels, even for one
  valid position. No online softmax or reassociation is equivalent.
- Global maximum visits occupied split maxima in increasing split order.
  Factors are `exp(split_max-global_max)`. Upper numerator/denominator leaves
  multiply original partials by these factors, then use the adjacent tree
  over the actual split count. Every missing right child adds +0; stop at the
  actual upper root rather than padding to the allocation's65 splits.
- Divide the final numerator by denominator once. Preserve the BF16 boundary
  before sigmoid multiplication and the final BF16 output store.
- Preserve ordinary multiply/add separation and exact operand positions;
  use `-fno-fast-math -ffp-contract=off -fno-associative-math`. The explicit
  fused operations inside detmath remain part of that implementation.

`std::max(m,x)` is not replaceable with fmax, an unordered reduction, or a
reversed-operand max: it ignores a NaN second operand and retains the first
on equal values, including signed zero. Device score source spells K*Q while
the independent scalar reference spells Q*K; finite results agree, but NaN
payload selection can depend on operand placement and compiler lowering.
Packet47's original gates explicitly did not qualify nonfinite model inputs.
Packet116 must compare raw production/candidate bytes under GNU and Intel
separately, including each compiler's NaN payloads; cross-compiler payload
normalization is forbidden. Infinity cases also reach `Inf-Inf` in exp.

## Exact parallel mechanisms worth testing

Retain the current three-stage attention dependency boundary and fixed32
workspace layout. Increase independent score-position work inside each tile
and/or parallel ownership of value components without moving a single floating
node. A subgroup can own each independent score with the same eight-leaf
per-lane tree and SG32 tree. For value leaves, fixed subtrees can be evaluated
in parallel and combined at their original nodes, or computed through a
compile-time adjacent tree that shortens live register arrays without changing
operands. Any subgroup/WG decomposition must preserve NaN payload choices in
compiled-production comparisons. Reuse the current combine first so the micro
isolates the tile change; a new combine can independently preserve its upper
nodes if needed. Adding a new launch may erase a short-context gain.

For selection, keep the exact score arithmetic and distribute each block's
rank comparisons over32 lanes. Integer addition and boolean OR can combine
lane-local rank and nonfinite flags without a floating reassociation. Every
WG can establish row finiteness by its parallel full scan before any selected
write; this avoids an extra launch and preserves all-ID rejection. An early
rank cutoff must never omit finiteness validation. Existing packet42 work
already recorded serial rank as a mistake; count against the actual round2
control and avoid reviving an older alias as a purported new win.

## Test and interpretation traps

The brief's frozen packet110/107 complete-layer harness is an allowed synthetic
measurement source; use it unchanged or copy it. Real captured state is needed
if choosing the separate attention/select-only alternative. Keep occupied128
and4096, both arm orders and two fresh device processes. Retain all state:
selected IDs and -1 suffix, block-score scratch, counts, all written split
partials, outputs, error/active/position, KV, untouched score/probability slots
and unused scratch/tails. Compare same-backend private workspace bytes; do not
mask scratch differences because final BF16 outputs agree. Cover split/tail
boundaries, shuffled rankings, ties, signed zeros, multiple NaN payloads and
infinities, inactive/sticky-error and invalid-ID behavior. M=2 operator support
is not proof that the full engine batches verification rows.

The kill gate is per fresh process: at occupied128,
`median(sum attention+select events for candidate call) <= 0.6 * production`.
Sum all events first; the denominator is the same-process same-shape control.
Report4096 separately. Neither a favorable average across processes nor a
long-context-only win passes. The published source medians total68.255 us at128
and587.605 us at4096; 40% savings of those anchors is an opportunity estimate,
not a measured candidate result. The source useful-byte rates (1.8% and0.2% at
128;3.4% and0.3% at4096) are not hardware DRAM-counter rates.

Packet47 ordered attention lost (0.54–0.69x); do not repeat it unchanged.
Packet46 launch fusion was neutral. Packet107 KV-sharing remains a different
unmeasured arm. Preserve current full BF16 KV and oracle identity throughout.
The v5 one-load bracket may be prepared in parallel, but must refuse launch
until both fresh micro processes satisfy equality and the short-context gate.
Only views actually scheduled need startup/reference materialization; all
required startup windows for those views still apply, including KD.

## DO-NOT-REPEAT census

Repository-wide filename census plus case-insensitive `qsa|attention|select`
content search was read, including surrounding paragraphs for every match.
The list below records every matching file and its SHA256 at audit time.
Packet103's additional boundary file was also read even though it uses
`split32` without those search terms. The audit does not reopen the other
models' closed levers. Core constraints above specifically carry forward
packets20/30/38/40/42/44/45/47/49/49b/49c/54/59c/62/66/67/82/98c/103/107/110/112.

- `experiments/own-xpu-runtime/stage2/packet101-draft-geometry/DO-NOT-REPEAT.md` — `aa6c804479d5a72900cf478d8ce471cc3ac628ffc1b46218d92e86f924464af4`
- `experiments/own-xpu-runtime/stage2/packet104-tile-transpose/DO-NOT-REPEAT.md` — `e8bb8c40216df576a17a65bf38e77bdfecd573fe4d7e79696ec4bc7ebf16b7ac`
- `experiments/own-xpu-runtime/stage2/packet105-head-split/DO-NOT-REPEAT.md` — `7b90ccf15263183f8e09536a5fc79472614403325909a7f16d03d66dc9a057ce`
- `experiments/own-xpu-runtime/stage2/packet105b-head-split/DO-NOT-REPEAT.md` — `49a1e0c230b87d63a380137b8058b3469e96e8932f1d0d67a1089686f75719a4`
- `experiments/own-xpu-runtime/stage2/packet106-draft-split/DO-NOT-REPEAT.md` — `50a0cbe1ab59c25be81899984ba5e60d7e74f972ca8ed7b9de9c70350e4cd849`
- `experiments/own-xpu-runtime/stage2/packet106b-draft-split/DO-NOT-REPEAT.md` — `9320dadd93528e0195e95d3294f9bbbefec1028b76e3a4c937ef216742ad73e4`
- `experiments/own-xpu-runtime/stage2/packet107-specialised-layers/DO-NOT-REPEAT.md` — `4f4a163364058cdd80255e5d7ef438fa4707ad2fb952124bde706cb8a74829bc`
- `experiments/own-xpu-runtime/stage2/packet108-draft-loads/DO-NOT-REPEAT.md` — `cfb690d766ec74a2d1226507a4b993a28a7c0ad6235f63c01612b96b9a05dec0`
- `experiments/own-xpu-runtime/stage2/packet11-kopt6/DO-NOT-REPEAT.md` — `40bc2f27d334247a73901e4e30f2336afee2b885dd2ebaf67acce984b9d32bb5`
- `experiments/own-xpu-runtime/stage2/packet110-class-roofline/DO-NOT-REPEAT.md` — `e5250dde7522efa2a847635d72ccdaba973ad4f1eca836e7d00afdcc74ff8fc4`
- `experiments/own-xpu-runtime/stage2/packet112-route-select/DO-NOT-REPEAT.md` — `998a8132b305c44e9a657ae2b52848ec189506a10eeb43f7688356f30749d366`
- `experiments/own-xpu-runtime/stage2/packet114-draft-prefix/DO-NOT-REPEAT.md` — `0882558fc17d68df5e55b1c3f76fe516d5b90f62f281f60f6e7a9056b2bfc247`
- `experiments/own-xpu-runtime/stage2/packet12-peer/DO-NOT-REPEAT.md` — `57a2df6688f80bcc1bb4f7f7ea64bd713d72c3c597a71beb06c14f14fea91e80`
- `experiments/own-xpu-runtime/stage2/packet16-decode/DO-NOT-REPEAT.md` — `bc30ebcc80cd140f31707529210fce33896a7111fba85809ec1b111cee2c6d1c`
- `experiments/own-xpu-runtime/stage2/packet20-launch/DO-NOT-REPEAT.md` — `b80375767870f51c8b3f1db9aabd046f564bf1a629e57491b8c4a28b7abccfed`
- `experiments/own-xpu-runtime/stage2/packet27-round2/DO-NOT-REPEAT.md` — `cc1b60907c35acd1ba7bc21f805c34ea8e54deea3caf9d0c360900bf4e2daf85`
- `experiments/own-xpu-runtime/stage2/packet29-merged/DO-NOT-REPEAT.md` — `a980407aa23c3ea09c37eaa83dd95010848ffd7fbff3ceb3a924b3fa345f1072`
- `experiments/own-xpu-runtime/stage2/packet30-leftovers/DO-NOT-REPEAT.md` — `e5d3dcab4eb49e629a609296e2275ec8771e02c284c9cb47866aa176426be740`
- `experiments/own-xpu-runtime/stage2/packet32-pipeline/DO-NOT-REPEAT.md` — `32aadd161a5c99132a93d318f28ebdcef9d882598855badfee6f9b5b6d11eb83`
- `experiments/own-xpu-runtime/stage2/packet33-codegen/DO-NOT-REPEAT.md` — `a1cbf3bf204e77bff46252a363bc6e56290fc8c3f699c443c838e8f4f5c15f66`
- `experiments/own-xpu-runtime/stage2/packet34-replay-bench/DO-NOT-REPEAT.md` — `af2507d38da38b4dd39a85d7a4650b6264d4a67fa14413ea7d98e065f669d5bb`
- `experiments/own-xpu-runtime/stage2/packet35-hostpath/DO-NOT-REPEAT.md` — `d67eb9a9f2836ad0769b84012b7f072957e9225add0c1740278492732ebe98f9`
- `experiments/own-xpu-runtime/stage2/packet37-merged2/DO-NOT-REPEAT.md` — `89402c487370bc6a56a6dfc9dca2fca3f0a82a2bb05a178b9f8712f7f54719f1`
- `experiments/own-xpu-runtime/stage2/packet38-integrated/DO-NOT-REPEAT.md` — `8a2fac7cfe29db7e072871a0925adcc811069596d1288a3d039e9d7089ab6eb5`
- `experiments/own-xpu-runtime/stage2/packet40-suite/DO-NOT-REPEAT.md` — `f506971ce81c56b4d62ffbf7a020fd37deb122008a5b56e0ed538750dd6b357a`
- `experiments/own-xpu-runtime/stage2/packet42-codegen2/DO-NOT-REPEAT.md` — `5f5756bebf697fc147cd449542f12f4c63a2f23317463716c0fb7d576fa90de7`
- `experiments/own-xpu-runtime/stage2/packet44-context/DO-NOT-REPEAT.md` — `203c1c517b07c1b76da32d07fdca29e98aabf0a3cc3b7723588e025ac88eb82f`
- `experiments/own-xpu-runtime/stage2/packet45-merged3/DO-NOT-REPEAT.md` — `cdf4f0419d162e4344ed8e383d36c77c0570177f2afd88b0bc57e3e3b9ecdc08`
- `experiments/own-xpu-runtime/stage2/packet46-specialized/DO-NOT-REPEAT.md` — `8a7479aee52d1468cf4eb895b7b1b3c2ef3ca51e30d4942cc03597bcbd93105a`
- `experiments/own-xpu-runtime/stage2/packet48-gemv/DO-NOT-REPEAT.md` — `435073af10ccf5cff75c310e6de30726e2ce266092b6ff73b5d0792306674b2c`
- `experiments/own-xpu-runtime/stage2/packet49-integrate/DO-NOT-REPEAT.md` — `65b5ffcf86fe65dba57b9378f948ff1647d8fb7a4f7de92d0c5b46f4b3b7730d`
- `experiments/own-xpu-runtime/stage2/packet49b-gemv/DO-NOT-REPEAT.md` — `2a31c8b9ad46624fe1190c39530821dd8947a03c8c29ac4b0892b1a554bbd5e4`
- `experiments/own-xpu-runtime/stage2/packet49c-round2/DO-NOT-REPEAT.md` — `e403b5716ef647cf65ed3b0ed0a5d66ec97898c1f0fb0545644d42403f9fa5a2`
- `experiments/own-xpu-runtime/stage2/packet49d-round3/DO-NOT-REPEAT.md` — `2c3cb98fa6fc5085eb46221035a2d894a779553e270f6772802f9f611ab3f158`
- `experiments/own-xpu-runtime/stage2/packet52-freeorder/DO-NOT-REPEAT.md` — `68de6ab07834c6774739b89c89b2e4bcef96c745ebd673ef78bae247cc9ce849`
- `experiments/own-xpu-runtime/stage2/packet53b-virtual/DO-NOT-REPEAT.md` — `026483e48ad0f37c94d68d64e9907998abeeb90221255685f36f1032862ffc63`
- `experiments/own-xpu-runtime/stage2/packet54-compute/DO-NOT-REPEAT.md` — `f837ecd8759195b21870b874b7dc740d126abb6827cd2c5dc4442fc1d3fe7aaa`
- `experiments/own-xpu-runtime/stage2/packet58f-onecard/DO-NOT-REPEAT.md` — `c77a59c27dfbca127993b48a3d675d9c277f669cf7384a705335f9f28eb2ad62`
- `experiments/own-xpu-runtime/stage2/packet58g-onecard/DO-NOT-REPEAT.md` — `e32919941849b770002f5dd8528a437948ddde6084d7cf4f685aa16871e15056`
- `experiments/own-xpu-runtime/stage2/packet58j-onecard-port/DO-NOT-REPEAT.md` — `a840ba87fa9ccfc5796187f5419514aaba78b9399291699086121fe31d2c0fc4`
- `experiments/own-xpu-runtime/stage2/packet58k-onecard-screen/DO-NOT-REPEAT.md` — `acf5d2b98d5307c3f2590f282ff90d86abd34ab2cea62eb33043a7d9cc71bb2b`
- `experiments/own-xpu-runtime/stage2/packet58n-onecard-loo/DO-NOT-REPEAT.md` — `8f92c04e335edef44b149351578d0fb9b163a89732dc7003d8faac00ec71b6e1`
- `experiments/own-xpu-runtime/stage2/packet59c-draft-select/DO-NOT-REPEAT.md` — `ace33d80f6429fffe258cc5bf53c4932c458a2b291a232baa43f86b22987ac93`
- `experiments/own-xpu-runtime/stage2/packet62-miss-path/DO-NOT-REPEAT.md` — `18bf87772368517eb401c4eb09b50e8eb6277f430abcdc33405de70a20bbf9e7`
- `experiments/own-xpu-runtime/stage2/packet63-balance/DO-NOT-REPEAT.md` — `fb6c7f5a2e49ed70ef516974ad85dd7b43496840eb9b411b225df65c961e678c`
- `experiments/own-xpu-runtime/stage2/packet64-attribution/DO-NOT-REPEAT.md` — `3938a20762e55e2c8e51e215b35d2e70879b39866c72a80b13c8417fee3b6879`
- `experiments/own-xpu-runtime/stage2/packet64-record-bundle/DO-NOT-REPEAT.md` — `9f78ae8f6773b8001e4756ac0c1e7d5fa458d91a3c73f22e0ae44ef14f6f0ebb`
- `experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe/DO-NOT-REPEAT.md` — `0739cc491b2e4f78db85351718e3faecd7c700614982bf810ce00ded4cc3c8ae`
- `experiments/own-xpu-runtime/stage2/packet67-roofline/DO-NOT-REPEAT.md` — `32bd2ce4ff4c665064664d0b273d11856c192319f191fbd9dc8168a3025f2b11`
- `experiments/own-xpu-runtime/stage2/packet69-rank1-head/DO-NOT-REPEAT.md` — `3b2fd703b9c09155a9bb9c68bcf535ea8ea326f6950e6626403bb1f026d6c30b`
- `experiments/own-xpu-runtime/stage2/packet70-record-bundle/DO-NOT-REPEAT.md` — `f2989edff3f1854938dd390ab85f7a210307c48c6ad32b9765f3ff004a1b10ef`
- `experiments/own-xpu-runtime/stage2/packet71-depth2-engine/DO-NOT-REPEAT.md` — `dc072800efe4dd18d226f2d49b5a6fe81cfe3bf1faf1197a6b870c4fc4f3a257`
- `experiments/own-xpu-runtime/stage2/packet71b-depth2-engine/DO-NOT-REPEAT.md` — `284467289be3f7bbabb4cbc98a4a2f47be1e24c3de39f5806d59812d8bda2579`
- `experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/DO-NOT-REPEAT.md` — `ba5ffd35713c5dc1c9e31e7607b9e62605833dac7bcb190ed016b4389023803b`
- `experiments/own-xpu-runtime/stage2/packet72-occupancy/DO-NOT-REPEAT.md` — `03e8eb6663dd9f0e2d03f73d4fced9d3ea55578fc82733f2fc7f8efeb9a3d15c`
- `experiments/own-xpu-runtime/stage2/packet74-packed-dense/DO-NOT-REPEAT.md` — `46e220caa23f56a37987c70a50ebd7f679a42991f354b899f9bef2c80c72547e`
- `experiments/own-xpu-runtime/stage2/packet75-record-bundle/DO-NOT-REPEAT.md` — `114d3f1b77af9c2d185bae421b304ff5a18ca0d427fe72318c2343571ac0adfa`
- `experiments/own-xpu-runtime/stage2/packet78-small-kernels/DO-NOT-REPEAT.md` — `14899c3f333d5e1f1f9e02084573cf74df6d21d9353c73c92d3914f5555c8208`
- `experiments/own-xpu-runtime/stage2/packet8-kopt3/DO-NOT-REPEAT.md` — `ee450cb92622f26495ab71eb4769f0e97211aa29ebc033bd6c1ce90f94bf083e`
- `experiments/own-xpu-runtime/stage2/packet80-record-bundle/DO-NOT-REPEAT.md` — `a163b8f89a2de4d0d74031c214aff6ce3b0e6a344f28617b1ab712f2c1bdb6df`
- `experiments/own-xpu-runtime/stage2/packet82-recurrence/DO-NOT-REPEAT.md` — `b307b68d316371bbd5b13c2ba9fca504824d6ab428633656b7d17a9148fca0b7`
- `experiments/own-xpu-runtime/stage2/packet83-draft-bytes/DO-NOT-REPEAT.md` — `5741dd7653ae98a7e9befcec36cb7778a0565c822ccfbec3994d8aa5071776e3`
- `experiments/own-xpu-runtime/stage2/packet84-record-bundle/DO-NOT-REPEAT.md` — `737852abf261ebefebaf828719638bf00eec269d4bdc89c341ffe42f06e50606`
- `experiments/own-xpu-runtime/stage2/packet88-miss-path/DO-NOT-REPEAT.md` — `f3c080f44e45dc03f498b1cd68dc534f87559f7c9344bd2280d997e50d11b1f9`
- `experiments/own-xpu-runtime/stage2/packet9-kopt4/DO-NOT-REPEAT.md` — `242caa50e5b89da744e6f2af7ab4c7a97f4d8a5c8527574e110ddf703641d3dc`
- `experiments/own-xpu-runtime/stage2/packet91-record-bundle/DO-NOT-REPEAT.md` — `af4504a2021b556baf46a04c70ea044b21412782eab303cfed5cc3805f459de6`
- `experiments/own-xpu-runtime/stage2/packet96-dual-guess-model/DO-NOT-REPEAT.md` — `9364752cfd6700b70125cb5ca484b1b435edb959516d918fc34b2d9aeaf23098`
- `experiments/own-xpu-runtime/stage2/packet97-record-bundle/DO-NOT-REPEAT.md` — `bb31a2abd7d8ca407c7b54405d1377a755558cea66881cedf085ae8413aaf6ad`
- `experiments/own-xpu-runtime/stage2/packet98c-v5-native/DO-NOT-REPEAT.md` — `08b777c5a21d200a83355c6dcd5e0998c8a3d86375f739936e820e07106a4187`
- `experiments/own-xpu-runtime/stage2/packet99-iq2-grid/DO-NOT-REPEAT.md` — `81faadaa14cb40bb8f8f9893d15b2ceb30d772ce5a0dff7042ffa7b8f200dc79`
- `experiments/qwen38-27b-b70/DO-NOT-REPEAT.md` — `45ad059dac08b81d5732af4cbd02cd585966e84ee91b3e4afc9caa9b4d491907`
- `experiments/qwen38-flash-next-ud-iq3xxs-b70/DO-NOT-REPEAT.md` — `b40a2795f1e527e4448d508442102cc483ea3effbe077a2067a812797bed4083`
