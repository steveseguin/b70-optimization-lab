# Task B timing, memory and roofline research

All measurements below were read from existing files. No device was accessed and no model, compiler or service command was run. `timing-memory-summary.json` retains calculated subtotals and input SHA256 identities; `service-request8-receipt.json` snapshots the exact one-line commissioning receipt read from a live run directory.

## Evidence identity and missing measurements

The current corrected binary is `5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4` (`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/evidence/native-build.json:1223`). Its observed long service request has **1,756 prompt tokens / 63.475563649 s = 27.6642 prompt tokens/s**, 512 outputs / 27.064625902 s decode, and 4.097105331 s RESET. These are service observations, not benchmark certification (`/home/steve/own-xpu-runtime-results/sc117-lan/run-20261024T170537Z/requests.jsonl:8`; `experiments/own-xpu-runtime/gsq-rco-iq3s/serving/lan/RESULT.md:23-28`).

All `sites.jsonl` and `prefill-timings.jsonl` found in `gsq-recurrent-f32-{a,b,longer-a,prefix-a}` are **zero bytes**, and no `class-times*` file exists in those four run trees at this read. Their actual `timings.jsonl` files do contain per-half timing. The file inventory and sizes are captured in `timing-memory-summary.json` under `corrected_missing_profiles`; do not imply that corrected per-class or per-site profiling exists.

The closest class profile is **historical BF16 recurrent state**, `gsq-dense-packed-class-a`, 214 positions (86 prompt-only, one final-prompt/first-output, 127 subsequent decode). It totals **10,249.070221 ms summed event execution**, not request wall time and not a current corrected-F32 profile. This limitation is explicit in `experiments/own-xpu-runtime/gsq-rco-iq3s/profiling/dense-packed-class/RESULT.md:1-17` and `README.md:25-29`. Earlier combined-engine profile is even older (5a8c) and totals 13,743.110727 ms, also a mixed prompt/decode event sum (`profiling/current-combined/RESULT.md:10-16,48-50`).

## Where the time goes

Both historical class files are one-line JSON: `/mnt/usb-models/own-xpu-runtime-results/gsq-dense-packed-class-a/prompt-00-none/rank0/class-times.json:1` and sibling `rank1/class-times.json:1`. Sum both by exact class; percentages below use 10,249.070221 ms. These are diagnostic priorities, not a corrected speed prediction.

| Class/group | Event ms | Share |
|---|---:|---:|
| Expert down | 1,093.830 | 10.672% |
| Expert gate | 935.249 | 9.125% |
| Expert up | 922.951 | 9.005% |
| Routing (five launches/layer/position) | 700.882 | 6.838% |
| GDN QKV | 536.727 | 5.237% |
| Attention output projection class `attention` | 416.582 | 4.065% |
| GDN recurrence | 377.482 | 3.683% |
| HC feed-forward low | 369.678 | 3.607% |
| HC attention low | 364.574 | 3.557% |
| HC feed-forward inject | 357.450 | 3.488% |
| HC attention inject | 356.496 | 3.478% |
| GDN Z | 315.702 | 3.080% |
| HC feed-forward gate | 246.712 | 2.407% |
| HC attention gate | 246.496 | 2.405% |
| Gather | 236.429 | 2.307% |
| QSA Q/gate projection | 211.687 | 2.065% |
| Shared expert down/gate/up | 459.4849 | 4.483% |
| GDN A/B projections | 164.9038 | 1.609% |
| QSA sparse attention itself | 122.2155 | 1.192% |
| GDN convolution | 49.1742 | 0.480% |

Expert projections total **28.802%**. GDN QKV/Z/A/B total **1,017.3328 ms**, 2.695 times recurrence; recurrence+convolution total 4.163%. This supports leaving recurrence sequential as a first design, but the corrected recurrence changes storage from BF16 to F32 and its actual cost is not measured by this class profile. GDN output projection is additionally included in `attention` and cannot be separated by this aggregate class alone (same raw class sources above).

Corrected target-only B positions **1..85** (exclude first-use position0 and final prompt/head position86), arithmetic means:

| Rank | Half completion ms | Host enqueue ms | Wait ms | Prepare ms | Launches/position |
|---|---:|---:|---:|---:|---:|
| 0 | 24.41709 | 4.97933 | 18.67139 | 0.52771 | 1,143 |
| 1 | 23.76246 | 4.32926 | 19.41634 | 0.02311 | 1,130 |

Source: `/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-b/prompt-00-none/rank0/timings.jsonl:2-86`, sibling `rank1/timings.jsonl:2-86`. Position0 alone took 19,466.9 / 19,318.3 ms (`:1` each), so the 40,892.591911 ms prompt wall for this fresh-process request is not steady-state prefill. **Do not sum the two half-completion means into predicted service wall:** the controller overlaps rank work and those means are not a synchronized critical path. Host enqueue time overlaps GPU execution too; it is not an additive third cost.

## Memory and bounded row buffers

Ledger bytes are confirmed by actual B census: rank0 **31,083,481,994 B**, rank1 **29,995,470,740 B** (`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/operating/candidate-ledger.json:8-23`; `/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-b/rank0/census.json:1`, sibling `rank1/census.json:1`). Both census `unmeasured_driver_shadow_bytes` and `unmeasured_library_pool_bytes` are null. Thus logical arithmetic headroom is not an allocation admission or measured free VRAM.

| Logical device category | Rank0 B | Rank1 B |
|---|---:|---:|
| Weights | 30,187,873,536 | 29,590,904,064 |
| Workspace | 304,776,290 | 287,470,228 |
| Recurrent state | 118,407,184 | 58,834,944 |
| KV | 67,895,296 | 58,195,968 |
| Runtime overhead | 404,529,688 | 65,536 |
| **32,000,000,000 minus logical** | **916,518,006** | **2,004,529,260** |
| **32 GiB minus logical** | **3,276,256,374** | **4,364,267,628** |

All values above are sums/subtractions of the same census allocations, not memory queries. Keep the GB/GiB distinction explicit instead of asserting the larger value as usable.

A reusable layer tile avoids duplicating every layer. The census has 334,218 B ordinary GDN-layer workspace, 331,222 B QSA-layer workspace, and 467,466 B maximum PLE-layer workspace. All target-layer workspaces sum 8,136,504 B rank0 / 8,003,256 B rank1. Existing shared allocations include 268,435,456 B operator scratch, 8,388,608 B GEMV workspace, 696,320 B prepared FP32 input and 20,480 B stream vector (same census sources). Do not replicate these large shared arenas for every row.

For a deliberately conservative new **one-layer reusable** tile budget, reserve `M*(467466 + 2*20480 + 696320)` bytes: largest layer intermediates, two BF16 stream tiles, and full prepared-input capacity per row. This treats the existing scalar storage as unavailable for aliasing, so it is an incremental upper budget before padding and extra schedules. The per-row sum is 1,204,746 B.

| M | Reusable layer/streams/preparation tile B | MiB | If instead cloning every rank0 layer, `(M-1)*8136504` B |
|---|---:|---:|---:|
| 16 | 19,275,936 | 18.383 | 122,047,560 |
| 32 | 38,551,872 | 36.766 | 252,231,624 |
| 64 | 77,103,744 | 73.532 | 512,599,752 |

Initial batching can run each row's attention sequentially and reuse the current scalar attention scratch. If attention is also widened, its partial workspace must be budgeted separately (kernel agent's exact formula: `M*24*ceil(launch_slots/32)*258*4 + align_up(4*M,16)`). The actual launch slots are `min(launch_extent,budget+3)`, so at context4096 with budget2048 this caps at2051 slots/65 splits, not128 splits. At M64 the corrected proposed allocation is **103,035,136 B**; adding the conservative tile gives **180,138,880 B**. The existing helper hardcodes16 count bytes and must be generalized to `align_up(4*M,16)` before M>4 (`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/kernels.hpp:23`, `p49_qsa_submit.hpp:6`; sibling `native-src/strict_snapshot.hpp:141`). This is a proposed layer-tile/QSA subtotal, not the full integration peak or a validated allocation. Existing 256 MiB operator scratch may be reusable for nonoverlapping stages only after liveness and state-capture review. Preserve scalar final workspace/last-writer semantics for every full-state-hashed buffer; do not assume that only recurrent/KV state matters.

For the full integration, reserve a separate **256 MiB private scratch arena + 8 MiB control/guard allowance**, in addition to the activation tile. This is a proposed conservative allowance to preserve the unchanged engine's full scratch last-writer state; it is not measured free memory or a claim that all256MiB are necessarily needed. QSA partials can live within this private arena only after proving nonoverlapping lifetimes; do not add another103MB if that same storage is already reserved. The resulting provisional bounded allocation budgets are below. They are conditional on compact interval-overlay metadata fitting the8MiB control allowance. A naive per-byte writer map does not satisfy that allowance; if the exact masks/lifetimes cannot be represented within it, fail admission and explicitly rebudget before implementation:

| M | Activation tile + 256MiB private scratch + 8MiB controls B | MiB |
|---|---:|---:|
|16|296,100,000|282.383|
|32|315,375,936|300.766|
|64|353,927,808|337.532|

These leave decimal32GB-minus-logical-minus-reservation margins of620,418,006 /601,142,070 /562,590,198 B on rank0, before unmeasured driver/library overhead and other guards. Actual admission remains a future device task, outside this research authorization.

## Roofline calculations: projections, not measurements

The corrected strict target-only weight join (`card0:weight:` prefix, excluding `card0:draft:weight:`) derives **5,327,311,360 B** unique addressed target-layer weights per scalar position: rank0 **2,649,294,080 B**, rank1 **2,678,017,280 B**. Common weights are **4,345,039,360 B** and selected expert slots account for **982,272,000 B**. The corresponding allocated/sliced-bank footprint is5,441,589,760 B; subtract114,278,400 B unused expanded metadata. Source and calculation detail: `kernel-notes.md:33-74`, `kernel-sites.tsv`, and the corrected source/census joins identified there. This corrects an intermediate draft/target-name collision; old5.373GB totals are invalid. These are optimistic unique addressed-byte counts, not DRAM counters. Intermediate prompt positions already skip the839,321,600 B target output head; do not credit removing it as a new gain (`kernel-notes.md:74-80`).

Let logical chunk length be M and actual register/SLM sharing row tile be B. A multirow kernel with independent work-groups for B-row tiles can guarantee at most **B-fold common-weight reuse**, even if M is64. It cannot claim M-fold reuse from caches across work-groups. Expert traffic depends on overlap: for independent uniform top10 of512 routes, expected distinct experts within B rows are `U(B)=512*(1-(502/512)^B)`. Actual routes are unknown and this is an explicit workload model; worst-case `U=min(10B,512)`, identical-route best case `U=10`. Every selected slot keeps its own original arithmetic. Top10/512 and the per-position slot behavior are sourced in `kernel-notes.md:37-74`.

Ideal bytes per row `W(B)=W_common/B + W_expert*U(B)/(10B)`; bandwidth-only speed ceiling `W(1)/W(B)`. If effective bandwidth is beta GB/s, ideal weight time per row is `W(B)/beta` nanoseconds, subject to unchanged arithmetic/issue and sequential-state floors. No external peak bandwidth is assumed.

| Logical M with B=M (optimistic) | Expected distinct experts | Ideal GB/row | Weight-only ceiling | If implementation has B=8, ceiling |
|---|---:|---:|---:|---:|
|16|138.569|1.122269|4.747x|3.647x|
|32|239.636|0.871368|6.114x|3.647x|
|64|367.113|0.631336|8.438x|3.647x|

For B4, W=2.040127 GB/row and weight-only ceiling2.611x. Uniform routing amortizes experts only about1.03x at B4 /1.07x at B8, so the common dense projections are the reliable first bandwidth target; routing grouping alone does not produce an eightfold MoE saving. These values are direct evaluations of the stated formulas, not evidence of actual route overlap.

The arithmetic count is **unchanged**. A long per-lane array of64 accumulators can spill and erase the byte gain; register pressure, occupancy, replicated nonlinearities, sequential state, launch submission and two-rank transfer latency all remain. A numerical sensitivity illustration uses unchanged-wall fraction f=0.30 and batched-region compute floor c=0.25 or0.50 of its prior time: `S=1/(f+(1-f)*max(W(B)/W(1),c))`. These f/c values are assumptions, not extracted corrected measurements. With B=M16/32/64, c=.25 yields **2.105x** in every case; c=.50 yields **1.538x**. With B8, c=.25 gives **2.033x**. Applied only as a planning illustration to63.4756s, those correspond to30.151s,41.259s and31.227s. The planning range is therefore roughly1.5–2.1x for this explicit model, **not a benchmark forecast or commitment**. With no compute floor and f=.30, optimistic M16/32/64 numbers become2.235/2.413/2.611x. The complete model and assumptions are shown to avoid silently converting a weight-byte ceiling into an end-to-end claim.

### Separate cost of losing rank overlap

The unchanged-fraction formula above cannot absorb a *new* serialization penalty: with unchanged kernels it otherwise predicts1x despite changing the schedule. Using only the corrected target-only half means as an idealized two-stage sensitivity, `lambda=(24.4170918+23.7624647)/max(24.4170918,23.7624647)=1.97319`. Thus a completely serialized chunk schedule has `S_net=S_work/lambda`: the illustrative1.538–2.105 work speedup becomes **0.780–1.067x**, and the B8/c=.25 example becomes about **1.030x**. These are not actual service predictions: the raw means cover a different short target-only request; real MTP, copies, context and startup costs differ (`/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-b/prompt-00-none/rank0/timings.jsonl:2-86`; sibling `rank1/timings.jsonl:2-86`). They show why the initial serial schedule is an identity milestone, while a measured double-buffer schedule is necessary before forecasting substantial service gain.
