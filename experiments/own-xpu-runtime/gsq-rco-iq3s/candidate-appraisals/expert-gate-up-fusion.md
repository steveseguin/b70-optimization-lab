# Expert gate/up launch fusion: source appraisal

A narrow two-output fusion is feasible, but no existing current API provides it unchanged. Start with the 17 IQ3_XXS layer pairs using the already-qualified block arithmetic. A fixed native micro comparing two original launches against one paired launch is warranted before Engine changes. This is a source appraisal, not an implementation or performance prediction.

## Actual current paths

The qualified dense-Q6 Engine takes `gsq_build_plan` and returns before the older `expert_gate_up` graph rewrite. Its gate/up remain `gate → gate.check → up → up.check → silu_product`. All 48 pairs have identical gathered per-slot input and Route allocations, shape `[10,640,2560]`, 512 experts, span640, distinct weights and distinct BF16/status outputs. Keep the gather and all ten slot positions, including duplicate expert IDs and row slices.

| Both projection formats | Layer pairs | Current numerical implementation | Split24 ranks 0 / 1 |
|---|---:|---|---:|
| IQ3_XXS | 17 | qualified `iq3block::BlockOperation` | 8 / 9 |
| IQ2_S | 20 | original p6 routed GEMV | 14 / 6 |
| IQ3_S | 10 | original p6 routed GEMV | 2 / 8 |
| IQ4_XS | 1 (layer47) | `gsqn::PackedOperation<23>` | 0 / 1 |

There are no mixed-format gate/up pairs in this census. The IQ3_XXS layers are 0,7,12,14,16,18,20,22,30,31,33,37,38,41,42,43,46. The graph/census join checked all48 matching inputs/shapes/cards and intervening checks. The structural graph's byte summaries are not resident-bank allocation sizes.

Older `experts(...,{gate,up},true)`/p28/p33 APIs and the historical graph rewrite are not drop-in numerical controls: current GSQ dispatch bypasses them. In particular, current p6 exposes `fused_gemv`, but native `Multiply::run` explicitly refuses `matrices != 1`; its dense fused facade also does not bind routed inputs/status. Simply selecting it will fail.

## Two concrete variants

**Concatenated projection workgroups:** one launch maps its first groups to gate and remaining groups to up, each running the literal original row loop, tree and output conversion. This removes one command per pair without reducing arithmetic or weight traffic; resources per workgroup can remain unchanged. For p6, preserve four rows per workgroup, staged packed rows, barrier and adjacent SG32 tree. For the block path preserve one row per workgroup. This is the smallest numerical-risk comparator.

**Same-row dual accumulators:** one workgroup computes both projections for a fixed slot/output row, reusing each BF16 input load/conversion and route/address calculation. Keep two independent accumulators, with every original multiplication/addition boundary and each accumulator's original iteration order. IQ3_XXS consumes block→group→lane order; p6 consumes lane*8, stride256, then eight sequential elements. Do not interchange those schemes. Each weight bank has independent scales, signs and codebook indices: their decoded values cannot be shared merely because format/expert ID match. Weight reads and decode work remain twice the one-projection work.

The dual path may save input/address work, but doubles accumulator/decode live values. For p6, staging both rows concurrently increases SLM usage (and register pressure); serial staging within the paired workgroup has a different tradeoff. Neither source counts nor the earlier HC near-zero result predicts benefit. Compiler register scheduling can also change NaN operand priority despite apparently equivalent expressions; preserve exceptional-output bit tests and exact native comparisons.

## Semantics and ownership constraints

Current GEMV facades bind weights/input/output/routes/status, **not** global active/error. `packet26::checked` checks capture size, not runtime active/error. Existing GEMVs therefore still write outputs/status on inactive or already-failed requests; status checks and activation consult active/error separately. Moving up ahead of gate.check is numerically defensible only while preserving those exact bindings and leaving both checks in original order before activation. Invalid/zero-count routes must retain canonical NaN tails and the original status values. No new early-return-on-error should silently change saved state.

Validate both banks and outputs before submission. Permit only the explicitly shared input/Route IDs; reject all crossed output/status aliases and writable aliases against either bank/input/routes. Capture both descriptors and pointer values by value, bind every live allocation to Device, retain guards/dependencies/event timing, and prove release/caller-rebind refusal using the existing capture boundary. Do not use host metadata alone as lifetime validation.

Resident memory delta can be **zero**: preserve both packed banks, the 51,200-byte input,120-byte routes, two12,800-byte outputs and two40-byte statuses. No concatenated weight copy, cache expansion or new device workspace is necessary. Additional descriptor/event metadata and any per-workgroup register/SLM cost must be measured separately. Two full IQ3_XXS banks occupy642,252,800 bytes for a bounded micro.

## Minimum useful proof and limit

Use one fixed actual IQ3_XXS layer0 pair, exact retained gathered input/ten routes and both original outputs/statuses. Compare the qualified gate then up operators against the paired operation, preserving all6,400 BF16 values and10 statuses per projection. Pre-register balanced AB/BA; A is the sum of two original device-event durations, B the paired event. Include the inherited positive backend ACK and safe close. A small CPU/source check should cover duplicate/permuted expert IDs, nonzero row_begin, partial/zero/invalid routes, exceptional decode/BF16 behavior, cross-alias guards and unchanged captured descriptors. Other three formats remain unqualified until their own original arithmetic is retained and checked.

For17 eligible IQ3 pairs the candidate removes17 compute submissions per token position; extending all48 removes48. At214 positions these are3,638 and10,272 submissions respectively, not predicted speedups. Gate938ms plus up925ms is roughly14.8% of the recorded whole class total, including real arithmetic; only a subset is removable launch overhead.

Defer activation fusion. Exact BF16 gate/up intermediate rounding **and writes** must remain for state identity. Activation additionally depends on active/error after status checks; a single kernel has no general cross-workgroup barrier to preserve that whole-launch ordering. It is a separate, substantially larger proof than merging two independent projection launches.

No model/state payloads, compiler, native executable, or Device operations were used for this appraisal.

## Source identities

- `experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/build/source/main.cpp` — `c35f1271033658e6384bf6d8cc1fab62014c2fe5d942f21e238abd2995f2e565`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/build/source/generic_engine.hpp` — `703d1769df8c789c591ce4d4fe23e1ec85f82ac2092b6b30bc19f6f6ccf95ae7`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/graph/new-plan.json` — `4d37ea499b0994a69664309d8f3c88aefc908e5034ac441b63f02e02151cf78b`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/metadata/new-census.json` — `b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/expert-iq3xxs-block/block.hpp` — `99c32706cefe5a3cd850ed3ef74eb577e439335fd99fc1d9bb595c48ed718cff`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/expert-iq3xxs-block/selection.json` — `457bba214c9f0380b854312a334456f35fad5ae86b004c9aa6fab86b23c672b1`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/native-formats/packed.hpp` — `4afcfb8a12bc9704ccb6a1f5b17bc5d315c69c894caaa5fd5e4140e106372c4f`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet6-kopt/kernels.cpp` — `08f249a46ae60aed5b5fdb139a5a38b5d4a512c5090e35d93200fa007829fc5e`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet6-kopt/reference.hpp` — `e27efad0b87b2c4e845265d98b6ff26cda458c582f146510276821db7e232f33`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/adapter.cpp` — `f4d1d947107c1d8a8e2b2fc0d05d50216a9fb39e11ae3e4b4c2740f04e70b625`
