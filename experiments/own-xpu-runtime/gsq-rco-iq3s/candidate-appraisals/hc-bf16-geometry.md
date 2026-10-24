# HC BF16 geometry appraisal on qualified a0f9 (source only)

The current class diagnostic attributes 1,448.613 ms to HC low/inject (11.513% of 12,582.182396 ms). Low contributes 734.469 ms; inject 714.144 ms. Each of the four labels has 10,272 events (48 layers × 214 positions). These are whole-request class durations, not a prefill/decode partition or predicted savings.

| Actual sites | Packed type | N × K | Weight bytes/site | Current SG32 / 4-SG workgroups | Proposed 1-SG groups |
| --- | --- | --- | ---: | ---: | ---: |
| 48 hc.a.low + 48 hc.f.low | BF16 | 320 × 10,240 | 6,553,600 | 80 | 320 |
| 48 hc.a.inject + 48 hc.f.inject | BF16 | 4 × 10,240 | 81,920 | 1 | 4 |

Inject has small N, **not small K**. Both use the same 10,240-element long dot. The actual a0f9 entry's GSQ linear early return reaches `iq3::kopt::gemv(...,32)` for BF16; all selected quantized exceptions bypass these sites. Old `small.hc` fusion is disabled for GSQ. The source hashes below match the native build closure.

The p6 raw-format path already reads aligned BF16 weight/input vectors directly from global memory. It does not stage weights into local memory. It nevertheless allocates a 16-byte local stride per row (64 bytes/workgroup) and executes the generic workgroup barrier. This is a different issue from the losing IQ4 removal of useful quantized staging.

A narrow candidate could retain the entire BF16 vector dot and tree and change only row-to-workgroup mapping from four independent SG32 rows to one SG32 row per workgroup. Keep the existing barrier for the first discriminator, avoiding another simultaneous change. Each lane still processes base=8*lane+256*b, b=0..39, eight ordered products per tile (320 ordered additions/lane); preserve weight NaN quieting, activation conversion, multiply then add without contraction, adjacent tree widths1/2/4/8/16, BF16 conversion, live bindings and all guards. Do not use split-K, SG16, FMA or a different accumulation chain. Weight layouts, allocations and output storage do not change. Local scratch becomes16 bytes/group; total logical subgroup work stays320/4 respectively.

More workgroups can spread the four inject subgroups beyond one workgroup's placement, but four total subgroups still sharply limit parallelism. Low has enough independent rows for a plausible scheduling difference. Similar observed low/inject event means (about35–36 versus34.7–34.8 microseconds despite80× different weight volume) motivate testing launch/scheduling cost; they do not establish occupancy as the measured bottleneck. The compiler may generate different instruction ordering, so native exact-bit comparisons remain mandatory even with unchanged source arithmetic.

The existing p30 `small.hc` is **not** an exact drop-in: its Low is Q8_0, Inject F32, both Split4. Reusing it would change types/arithmetic and scope. A future fused BF16 low+inject might share a launch/input, but that adds capture/order changes and is not the minimal geometry experiment.

**Compared with route early exit:** current route is700.988 ms across all five route phases; the expensive integer ranking phase is not separately attributed. `simple_body<route,3>` compares all512 probabilities, while existing `p33::route_rank<512,10>` can stop losing ranks after reaching10, preserving selected ranks/ties and all FP stages. That offers more certain removable work but a smaller class envelope and additional data-dependent branch behavior. HC one-SG geometry is the smaller arithmetic/control-flow delta and addresses a larger observed envelope, so it is the preferred bounded next discriminator if root selects it; neither has a predicted speedup.

Minimal future proof: strict selector census for192 exact BF16 sites, identical per-lane index/address sequence for both shapes, unchanged vector conversion/tree/output/alias and stale-binding guards, then one fixed layer's low and inject cases in the established same-owner AB/BA harness with positive backend ACK and all output bytes exact. No model allocation growth, fusion, full arithmetic reproof or new attribution campaign is needed. No implementation, build, device action or model/state payload read was performed for this appraisal.

## Source bindings

- `experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/evidence/native-build.json` — `33b6add96c907a24a95b9b3161f96b1b78fb9edc4e9d4a050b11edf8e5f8c6ab`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/build/source/main.cpp` — `c35f1271033658e6384bf6d8cc1fab62014c2fe5d942f21e238abd2995f2e565`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/build/source/generic_engine.hpp` — `703d1769df8c789c591ce4d4fe23e1ec85f82ac2092b6b30bc19f6f6ccf95ae7`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet6-kopt/kernels.cpp` — `08f249a46ae60aed5b5fdb139a5a38b5d4a512c5090e35d93200fa007829fc5e`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p30_small.hpp` — `53f55123d0c726c8347150dde63c520111a632bc075092505a20de0e82bcbc53`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p30_small.cpp` — `43506373b17569020417ef6e80a30c15f41c0706b2cfea7ca1bc3996714c9dd6`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/adapter.cpp` — `f4d1d947107c1d8a8e2b2fc0d05d50216a9fb39e11ae3e4b4c2740f04e70b625`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p33_candidates.hpp` — `e0b9e9185b973a957acfd9808223a3c5159f297b84d251a2d0d06317c02e38ea`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/graph/new-plan.json` — `4d37ea499b0994a69664309d8f3c88aefc908e5034ac441b63f02e02151cf78b`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/metadata/new-census.json` — `b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/profiling/dense-q6-class/launch-b/evidence/device-b/review.json` — `30ed538b78040d04367fe7e99956c8ff2e483cef99194de1445f1476226bd039`
