# SC117 corrected-engine prefill map

Research/design only, 2026-10-24. No build, native execution, device query, service action or Git mutation was performed. Outputs are confined to this directory. All 184 source dependencies in the corrected build receipt matched their SHA256 values on read (`source-audit.json:1-8`). The reference binary is **5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4** (`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/evidence/native-build.json:1223`).

The measured service example is **1,756 prompt tokens in 63.475564 s**, or **27.6642 tok/s**; it is an observed request, not a promoted benchmark (`service-request8-receipt.json:1-17`). The map below separates source-derived weight bytes, recorded device-event times and recorded request wall time. The proposed implementation and gates are in [DESIGN.md](DESIGN.md).

Source line references below are physical file lines, **not** the misleading historical `#line` virtual paths. No source, binary, service, model weights or device was modified or run. `kernel-sites.tsv` is an exhaustive ordered map of the 938 rank-0 and 933 rank-1 plan sites, with each site's allocated weight bytes and distinct addressed bytes. Its source records are `D0/launch-plan.json:1`, `D1/launch-plan.json:1`, `D0/census.json:1` and `D1/census.json:1`; weights are assigned using the executed Builder source below. No measured DRAM-byte claim is made.

## Source aliases

|Alias|Exact path|
|---|---|
|L|`experiments/own-xpu-runtime/gsq-rco-iq3s`|
|R|`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s`|
|E|`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s/dense-packed-block/engine/build/source`|
|N|`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine`|
|P|`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet3/step/plan.hpp`|
|K|`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp`|
|A|`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/additive`|
|X|`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet10-kopt5/expanded.hpp`|
|D0|`/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-b/rank0`|
|D1|`/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-b/rank1`|

## Actual path, not inherited unused optimizations

`E/main.cpp:461-544` builds the raw GSQ plan and returns before the legacy fused HC/expert plan at `E/main.cpp:624-665`. `E/main.cpp:1562-1564` also bypasses `other_fused_site` and `fused_hc` in GSQ mode. Thus **do not map the current corrected engine to old p60 fused HC or fused expert_gate_up paths**. The actual GSQ linear dispatch is `E/generic_engine.hpp:30-59`: selected denseblock, selected iq3block, p33 expanded Q6/Q8, packed gsqn, otherwise kopt. Per-site state kernels use `packet18::submit_parallel` (`E/main.cpp:1531`), with QSA explicitly forced to implementation 12 (`E/main.cpp:1526-1527`).

Rank 0 owns layers 0–23, rank 1 owns 24–47 under the normal split (`K:40-54`); both have 18 GDN layers and six QSA layers, QSA at 3,7,...,47 in the retained plan (`D0/launch-plan.json:1`, `D1/launch-plan.json:1`). Rank 0 alone executes embedding/broadcast and PLE before layer 1. Rank 1 owns final HC, logits and argmax (`K:53`, `P:273-299`). Embedding/PLE lookup arrows below denote plan placeholders: their rows are prepared and uploaded by the host before plan execution; the GPU lookup sites are no-ops (`E/main.cpp:1277-1302,1564`). The exact schedule is:

1. Begin/error guard; rank-0 host embedding lookup and four-stream broadcast (`K:145-154`, `E/main.cpp:1277-1302`, `P:255-264`).
2. At layer 1 only: PLE hash → lookup → key/value projections → key/query norm → PLE gate → conv norm → sequential dilated conv → add (`P:220-245`).
3. HC attention input: norm four streams → down → SiLU/4 → up → sigmoid mix → inject (`P:104-117`).
4. GDN: qkv → z → a → b projections → sequential conv → sequential recurrent update → norm/gate → output projection (`P:123-145`); or QSA: qgate → k → v → index-q → index-k → norm/rotary → append/pool → select → split32 attention → output projection (`P:147-180`, `N/p49_qsa_submit.cpp:31-33`).
5. HC attention combine, HC FFN norm/down/SiLU/up/mix/inject, router, route, gather, gate/check/up/check/SiLU-product/down/check, shared gate/up/SiLU/down plus shared scalar gate, MoE combine and HC FFN combine (`P:119-121,182-218`, `D0/launch-plan.json:1`).
6. Commit position. On the final prompt position only, rank 1 additionally runs final HC norm/down/SiLU/up/mix, full head and argmax; fixture 0 skips `final.*`, logits, argmax (`K:175`, `P:293-299`).

## Weight bytes (distinct addresses, not instrumented DRAM transactions)

Actual expanded resident allocations can exceed addressed bytes. Q6 K=2560 p33 allocates 3,380 bytes/output but addresses 3,200: 2,560 codes + 640 FP32 scale bytes, leaving retained metadata unread. Q8 K=6144 p33 allocates 7,296 bytes/output but addresses 6,912: 6,144 codes + 768 scales (`X:11-21`; `N/p33_candidates.hpp:85-93`). Scalar loads may repeat a scale address in multiple lanes. Caches, line rounding, repeated control reads, and dequantization tables mean this is a bandwidth lower-bound inventory, not traffic telemetry. The table's “once” volume is summed from strictly `card0:weight:` target allocations (never `card0:draft:weight:`), with these corrections and only 10/512 expert slices (`P:199-218`, `D0/census.json:1`, `D1/census.json:1`).

|Site/family|Calls per target position|Distinct weight bytes per call|Aggregate bytes|
|---|---:|---:|---:|
|HC attention+FFN norm|96|40,960|3,932,160|
|HC down|96|6,553,600|629,145,600|
|HC up|96|6,553,600|629,145,600|
|HC inject|96|81,920|7,864,320|
|GDN qkv|36|13,926,400–32,768,000|958,464,000|
|GDN z|36|8,355,840–19,660,800|473,825,280|
|GDN a|36|245,760|8,847,360|
|GDN b|36|245,760|8,847,360|
|GDN conv|36|163,840|5,898,240|
|GDN recurrence|36|384|13,824|
|GDN norm/gate|36|512|18,432|
|GDN output|36|17,694,720|637,009,920|
|QSA qgate|12|16,711,680–39,321,600|329,318,400|
|QSA k|12|696,320–1,075,200|12,523,520|
|QSA v|12|901,120–1,075,200|12,554,240|
|QSA index q|12|2,621,440|31,457,280|
|QSA index k|12|655,360|7,864,320|
|QSA prepare gains|12|2,560|30,720|
|QSA pool gains|12|512|6,144|
|QSA output|12|17,694,720|212,336,640|
|Router|48|2,621,440|125,829,120|
|Routed gate|48|5,248,000–8,704,000 (10 experts)|290,688,000|
|Routed up|48|5,248,000–8,704,000 (10 experts)|290,688,000|
|Routed down|48|4,608,000–9,216,000 (10 experts)|400,896,000|
|Shared gate|48|870,400–1,344,000|49,779,200|
|Shared up|48|870,400–1,344,000|50,700,800|
|Shared down|48|1,740,800|83,558,400|
|Shared scalar gate|48|5,120|245,760|
|PLE key/value|1 each|52,428,800 /13,107,200|65,536,000|
|PLE key/query/conv norm|3|40,960|122,880|
|PLE conv|1|163,840|163,840|
|Other elementwise/control/select/attention|as in TSV|0 model-weight bytes|0|
|Final HC norm/down/up (only head positions)|1 each|40,960 /6,553,600 /6,553,600|13,148,160|
|Final logits (only head positions)|1|794,624,000 addressed;839,321,600 allocated|794,624,000|

Per intermediate prompt position: rank0 **2,649,294,080**, rank1 **2,678,017,280**, total **5,327,311,360** distinct addressed weight bytes. Common weights **4,345,039,360**; selected expert weights **982,272,000**. Corresponding target layer allocation/sliced-bank inventory is 5,441,589,760; subtract 114,278,400 of untouched expanded metadata. Host embedding/PLE lookup reads and draft are excluded. Host lookup outputs are 5,120 bytes each and are uploaded per position, no GPU lookup kernel (`P:227-231`, `E/main.cpp:1277-1302,1564`). The TSV assigns GPU weight read zero for those sites; it does not claim zero host traffic.

Large projection GEMVs have approximately 2*K*O operations against O*row_bytes and one activation row, hence low arithmetic intensity and potential weight-bandwidth/dequantization limits. This is a source/roofline inference, not a hardware-counter finding. GDN recurrence reads/writes approximately 6,291,456 bytes of F32 state per layer per position (48*128*128*4 twice), against only 384 weight bytes (`P:136-141`, `N/kernels.hpp:127-143`). Its cost is state traffic, normalization/reduction, exponentials, and launches, not weight bandwidth. Attention has zero learned-matrix bytes in its attention kernel and reads BF16 KV at a row-specific causal prefix, plus index selection (`N/p49_qsa_kernel.hpp:29-76`).

## Bandwidth classification

The large HC down/up, GDN/QSA projections, selected expert projections, shared projections and final head are **weight-bandwidth/dequantization candidates**, not proven bandwidth-bound kernels: the retained evidence has event times but no DRAM or occupancy counters. Small gains, norm vectors, control operations, routing and elementwise kernels should be treated as launch/reduction candidates. GDN recurrence is state-bandwidth/compute work; attention is prefix-KV/softmax work. These classifications follow the byte table above, `N/p33_candidates.hpp:85-100`, `E/block.hpp:27-41`, `N/kernels.hpp:127-149` and `N/p49_qsa_kernel.hpp:29-77`. They do not justify assuming every class scales as 1/M.

## Evidence identity and missing measurements

The current corrected binary is `5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4` (`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/evidence/native-build.json:1223`). Its observed long service request has **1,756 prompt tokens / 63.475563649 s = 27.6642 prompt tokens/s**, 512 outputs / 27.064625902 s decode, and 4.097105331 s RESET. These are service observations, not benchmark certification (`/home/steve/own-xpu-runtime-results/sc117-lan/run-20261024T170537Z/requests.jsonl:8`; `experiments/own-xpu-runtime/gsq-rco-iq3s/serving/lan/RESULT.md:23-28`).

All `sites.jsonl` and `prefill-timings.jsonl` found in `gsq-recurrent-f32-{a,b,longer-a,prefix-a}` are **zero bytes**, and no `class-times*` file exists in those four run trees at this read. Their actual `timings.jsonl` files do contain per-half timing. The file inventory and sizes are captured in `timing-memory-summary.json:645-814` under `corrected_missing_profiles`; do not imply that corrected per-class or per-site profiling exists.

The closest class profile is **historical BF16 recurrent state**, `gsq-dense-packed-class-a`, 214 positions (86 prompt-only, one final-prompt/first-output, 127 subsequent decode). It totals **10,249.070221 ms summed event execution**, not request wall time and not a current corrected-F32 profile. This limitation is explicit in `experiments/own-xpu-runtime/gsq-rco-iq3s/profiling/dense-packed-class/RESULT.md:1-17` and `L/profiling/dense-packed-class/README.md:25-29`. Earlier combined-engine profile is even older (5a8c) and totals 13,743.110727 ms, also a mixed prompt/decode event sum (`L/profiling/current-combined/RESULT.md:10-16,48-50`).

## Where the time goes

Both historical class files are one-line JSON: `/mnt/usb-models/own-xpu-runtime-results/gsq-dense-packed-class-a/prompt-00-none/rank0/class-times.json:1` and `/mnt/usb-models/own-xpu-runtime-results/gsq-dense-packed-class-a/prompt-00-none/rank1/class-times.json:1`. Sum both by exact class; percentages below use 10,249.070221 ms. These are diagnostic priorities, not a corrected speed prediction.

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

## Separate draft map (never included in target bytes)

Define `D = R/integration/build/private/source/diet-native/native-src/mtp.hpp`. The retained corrected-B census places draft on **rank0**, and its choices are all `production` (`D0/census.json:1`, `D0/draft-kernel-choices.json:1`); do not infer placement from the older default `draft_rank=1` code. This is a separate single QSA-layer model. `D:161-164` builds `{true}`, removes embedding/broadcast plan nodes and pairs expert gate/up. `D:193-198` prepends embedding norm, hidden norm, embedding projection, four-row hidden projection and merge add. It consumes the previous confirmed target's final four streams plus the next known token embedding (`D:228-233`). Every confirmed prompt transition advances its own KV/raw/pool state even when no draft token is requested. Only final HC/head/argmax are omitted when `head=false` (`D:235,242,255-256`). Skipping the draft body until the last prompt would lose the draft cache and its position chain (`D:229`).

Order: prepare embedding + copy previous target final streams → embedding/hidden normalization → embedding projection → four-stream hidden projection → merge-add → single-layer HC-attn → qgate/k/v/iq/ik → QSA prepare/pool/select/attention → output projection → HC combine → HC-FFN → router/top10/gather → paired INT8 gate/up + checks → activation → INT8 down +check → shared gate/up/activation/down +scalar gate → MoE combine → HC combine → optional final HC/head/argmax → commit (`D:161-198,228-246`, `P:104-218,293-299`). `D:66-75,106-155` binds production or selected draft kernels; all recorded choices are production, so do not silently substitute target GSQ packed kernels for the draft BF16/INT8 arithmetic (`D0/draft-kernel-choices.json:1`).

|Draft per-position family|Distinct addressed weight bytes|Source|
|---|---:|---|
|Embedding norm|10,240|`D:178,194`; `D0/census.json:1`|
|Hidden norm over four streams|40,960|`D:69,178,195`; `D0/census.json:1`|
|Embedding projection|13,107,200|`D:178,196`; `D0/census.json:1`|
|Hidden projection|13,107,200 distinct;52,428,800 across4 separate input applications|`D:197`, `D:127-141`; `D0/census.json:1`|
|HC attention and FFN norms/down/up/inject|26,460,160|`D:161,172-175`; `D0/census.json:1`|
|QSA qgate /k /v /index-q /index-k|62,914,560 /2,621,440 /2,621,440 /2,621,440 /655,360|`D:161,173`; `D0/census.json:1`|
|QSA prepare/pool gains|3,072|`D:175-176`; `D0/census.json:1`|
|QSA output projection|31,457,280|`D:161,173`; `D0/census.json:1`|
|Router|2,621,440|`D:161,173`; `D0/census.json:1`|
|Paired gate/up experts|40,960,000 touched,2,097,152,000 resident bank bytes|`D:100-102,163-164`; `D0/census.json:1`|
|Expert down|20,480,000 touched,1,048,576,000 resident bank bytes|`D:100-102,173`; `D0/census.json:1`|
|Shared gate/up/down/scalar|3,276,800 /3,276,800 /3,276,800 /5,120|`D:161,173`; `D0/census.json:1`|
|Other draft state/elementwise/control kernels|0 learned-weight bytes|`D:66-75`; `P:104-218`|
|Optional final HC norm/down/up|13,148,160|`D:82,235,242`; `D0/census.json:1`|
|Optional full expanded Q6 head|794,624,000 addressed;839,321,600 resident|`D:62,179-190`; `N/p33_candidates.hpp:85-93`; `D0/census.json:1`|

No-head draft body: **229,517,312 distinct weight addresses**, or **268,838,912 application-weight bytes** counting the four hidden projection rows separately. Those are source inventories, not DRAM counters; all four hidden rows use the same13,107,200-byte matrix. Head-enabled draft adds807,772,160 distinct bytes. Rank0 has a separate copied full head allocation `card0:draft:shared-head-host`; rank1 placement can alias the target head when present (`D:187-189`). Target and draft state must remain separate when batching; preserve every target-row final stream until the associated draft transition consumes it. The target-only5.327GB model excludes this body, protocol and cache cost and cannot be quoted as end-to-end MTP prefill speed.


### Target mapping readback

A strict census/plan cross-check found **612 rank0 and606 rank1 target layer weight names**, all mapped, with no missing/excess referenced target weight. The TSV uses only exact `card0:weight:` labels; the disjoint `card0:draft:weight:` namespace is accounted above. Matrix format names come from `L/graph/new-directory.tsv` (one tensor per line); the corrected graph retains these weight bytes while changing recurrence/history storage, as shown by the matching target census and frozen plan. Types12/13/18/23/42 take `gsqn` when not selected for specialised kernels; other types (including IQ3_S) take kopt (`E/generic_engine.hpp:45-57`, `A/device_formats.hpp:12,23`). Thirty-four IQ3_XXS gate/up sites use the selected `iq3block::BlockKernel` (`R/expert-iq3xxs-block/selection.hpp:4-38`),116 selected dense sites use denseblock,90 p33 target sites include89 per-layer projections plus the head. These are static dispatch counts, not timing shares.

## Coverage and limitations

The ordered [kernel-sites.tsv](kernel-sites.tsv) lists all 1,871 plan sites, including zero-weight operations, with rank, plan index, label, operator, weight names, resident bytes, distinct addressed bytes, kernel family and Builder/source evidence. A plan site is not necessarily one physical launch: for example split32 attention has three passes and norms have multiple passes (`N/p49_qsa_submit.cpp:49-50`; corrected per-half launch counts above). Final-head rows are present in the map but skipped for intermediate prompt positions (`K:175`). Host token/PLE row reads and the separate draft are explicitly outside the target weight-byte totals; the draft executes every confirmed prompt transition, as mapped in `protocol-state-notes.md:33-37`.

The corrected engine's earlier short target/MTP pair matched full state, but its longer independent-reference comparison diverged at output token71. This design preserves corrected-engine arithmetic and does not claim to resolve that separate fidelity issue (`experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/operating/launch-b/RESULT.md:3-13`; `experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/operating/longer-a/RESULT.md:3-9`).

## Physical kernel passes behind the ordered site map

The TSV now records `physical_launches_when_site_executed`. Default dispatch classes are explicit in `N/dispatch.hpp:14,42-44`; GSQ bypasses old fused-plan paths but retains these normal operator choices, with attention forced to12 (`E/main.cpp:1525-1531`). Therefore the repeated per-layer sequence above expands as follows; model-weight bytes remain the per-site byte table, not a second whole-matrix read for a reduction's finish pass.

|Operation/site|Actual kernel/pass sequence|Physical launches|Source|
|---|---|---:|---|
|HC/final/PLE norms|specialised::Kernel<ng::norm,0> then stage1|2|`N/specialised_submit.cpp:23-47`|
|Top10 route|SimpleNew<route,0..4>|5|`N/adapter.cpp:193-203,237-240`|
|Expert gather|SimpleNew<expert_gather,0..1>|2|`N/adapter.cpp:212-215,237-240`|
|HC combine, PLE add, stream broadcast|SimpleNew<selected op,0>|1|`N/adapter.cpp:275-283,237-240`|
|SiLU, HC mix, GDN norm/gate, QSA prepare/pool/select|ng::Kernel / ng::group|1|`N/native.cpp:21-34`; `N/adapter.cpp:299-309,329`|
|F32 GDN/conv|ng::Kernel with ordered position loop|1 each|`N/native.cpp:21-34`; `N/kernels.hpp:127-149`|
|QSA attention|p47 admit → tiles<true> → combine<true>|3|`N/p49_qsa_submit.cpp:30-33,49-50`|
|MoE combine|kopt4::epilogue → ng::moe_combine|2|`E/main.cpp:1497-1498,1575-1576`; `N/performance.cpp:71-72`|
|Argmax|SimpleNew<argmax,0..1>|2|`N/adapter.cpp:204-208,237-240`|
|Begin/commit/hash/check/PLE gate|packet18::Glue/simple|1 each|`N/adapter.cpp:262-268,317`|
|Host lookup placeholder|no kernel|0|`E/main.cpp:1277-1302,1564`|
|Each current target linear site|its TSV dense/routed kernel|1|`E/generic_engine.hpp:30-59`|

Summing these expanded passes, excluding skipped head sites, gives **1,143 rank0 / 1,130 rank1 launches per intermediate prompt position**, exactly matching the existing corrected timing rows. This cross-check validates the site/pass expansion, not GPU occupancy or a new measurement (`calculations.json:96-99`; corrected timing rows cited above). Each norm's existing two-stage scratch tree must also remain unchanged when batching; a generic one-pass norm is not a replacement for that bit-identity gate (`N/specialised_submit.cpp:31-47`).
