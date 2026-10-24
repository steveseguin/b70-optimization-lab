# Corrected SC117 kernel reading notes

Research only, 2026-10-24. Source line references below are physical file lines, **not** the misleading historical `#line` virtual paths. No source, binary, service, model weights or device was modified or run. `kernel-sites.tsv` is an exhaustive ordered map of the 938 rank-0 and 933 rank-1 plan sites, with each site's allocated weight bytes and distinct addressed bytes. Its two source records are the existing corrected run's `launch-plan.json:1` and `census.json:1`; weights are assigned using the executed Builder source below. No measured DRAM-byte claim is made.

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

Rank 0 owns layers 0–23, rank 1 owns 24–47 under the normal split (`K:40-54`); both have 18 GDN layers and six QSA layers, QSA at 3,7,...,47 in the retained plan (`D0/launch-plan.json:1`, `D1/launch-plan.json:1`). Rank 0 alone executes embedding/broadcast and PLE before layer 1. Rank 1 owns final HC, logits and argmax (`K:53`, `P:273-299`). The exact schedule is:

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

## Arithmetic that a batched version must retain

**Packed dense and IQ3 expert rows.** `E/block.hpp:27-41,71-76` uses one 32-lane workgroup/output; lane l walks block b then group g, k=256b+32g+l. Each product is FP32, followed by an explicit FP32 add; tree widths 1,2,4,8,16 are adjacent lane additions; a single BF16 conversion writes the row result. `A/packed.hpp:16-21,46-52` and IQ3 block's `block.hpp:16-27,54-59` follow that same lane sequence, with their exact format decode. A new `template<T,R> batched_packed(W,X,Y,M,K,O,x_stride,y_stride)` can use one 32-lane WG/output and token tile R, with private `float sum[R]`; decode each weight once, then for r=0..R-1 do `product=weight*bf16(X[r,k]); sum[r]=sum[r]+product`. Apply the original lane tree independently to each accumulator. This shares loads/decode across R, not magically across M when R<M. M16/32/64 need register/occupancy measurement; R4/8 is a sensible first microkernel. No FMA, reassociation, BF16 product, matrix instruction, or split-K change.

**Expanded dense p33.** Its lane walks k=lane*8+256*t, then j=0..7, **not** k=lane+32*t (`N/p33_candidates.hpp:85-100`). Keep `value=scale*code; product=value*input; sum=sum+product` and the 32-lane adjacent tree, with Split=1 in the currently admitted variant6 (`N/p33_submit.cpp:53-64,86`). Sharing W across token accumulators is compatible in principle; treating this as a generic packed kernel silently changes summation order. A signature analogous to `batch_expanded<T,R>(W,X,Y,M,K,O,strides,variant6)` needs the current row stride and distinct codes/scales offsets. Never use four split-K partial sums, tensor cores or a vendor GEMM as an identity substitute.

**HC.** Rank-independent rows can be batched, but the four stream terms inside each row stay ordered. HC mix is `sum=0; for h=0..3 sum += sigmoid(gate[h])*norm[h]; bf16(sum/4)` (`N/kernels.hpp:159-162`); combine is `bf16(stream + branch*(2*sigmoid(inject/4)))` (`N/adapter.cpp:142`). Preserve down/up output BF16, SiLU/4 BF16, and norm's adjacent tree. This is not the unused legacy fused-HC arithmetic.

**MoE.** Routing remains independent per row: 512-way probabilities, top10 tie break by lower expert ID, normalized selected probabilities (`N/adapter.cpp:151-162,193-203`). Stable grouping by expert is allowed only as a schedule transformation; record `(position,original_slot)` and scatter outputs to those slots before the original combine. Keep gate/up/down per-row dot order, per-output BF16 and SiLU boundary. The actual combine has two kernels: `E/main.cpp:1575-1576` invokes `mixture`, then `E/main.cpp:1497-1498` substitutes that BF16 mixture and scalar1 into the shared-branch combine. `N/performance.cpp:71-72` selects `iq3::kopt4::epilogue`; its contract is explicit FP32 product/add in slots0..9 then BF16 (`N/../packet9-kopt4/reference.hpp:16-24`), followed by the existing shared-branch BF16 boundaries (`N/kernels.hpp:162`). Keep slot order; no atomic accumulation in expert execution order. Uniform independent routing would give U(M)=512*(1-(502/512)^M) distinct experts; effective weight reuse10*M/U is only ~1.15/1.34/1.75 at M16/32/64, not M. This is a hypothetical overlap model, not a measured routing distribution. Reuse must be measured from retained real routes.

**GDN/conv.** `ng::Shape.tokens` already exists; `N/kernels.hpp:127-149` explicitly loops positions inside each state-owning workgroup/channel. `recurrent_f32/recurrent_policy.hpp:10-11` rejects nonzero implementation for F32 recurrence; generic corrected ng is required, while the older specialised GDN still uses BF16 accessors (`N/specialised.hpp:130-136`). Do not reuse that old specialised path. Within GDN one WG owns `(value-head,output-dimension)`, preserving dot128's 4 adjacent products per lane and 32-lane tree (`N/kernels.hpp:108-110`), F32 state after each position, BF16 emitted y. Conv history remains F32; GDN conv has dilation1 and PLE dilation3 and different pre-SiLU BF16 rounding (`N/kernels.hpp:145-149`). No parallel scan, chunk algebra, or reassociated recurrence.

**Attention.** Start with per-position unchanged prepare/pool/select/split32 attention calls while batching only projections. The actual attention is `p49::Attention<0,1,2>` → admit/tiles<true>/combine<true> (`N/p49_qsa_submit.cpp:31-33,49-50`), with a fixed32 tile softmax and fixed per-tile tree (`N/p49_qsa_kernel.hpp:47-77`). Generic softmax is not an identity substitute. `N/p49_qsa_submit.cpp:39` admits at most2 positions and its scratch offset is hardcoded +16 (`:30`), so widening the limit alone corrupts counts for M>4. A future M version must reserve aligned 4*M counts and unchanged M*24*ceil(launch_slots/32)*258*4 partial bytes, while retaining the per-position count/order. KV remains BF16. Pool only finalizes groups of4; select sees floor((pos+r+1)/4) groups and appends the incomplete-group tokens (`N/kernels.hpp:181-201`). Source suggests completed future pools can be ignored by smaller row prefixes; nevertheless first integration keeps pool/select/attention sequential because full-state scratch tails and prefix-specific availability must match, and a causal mask alone proves neither.

**State banks and dump identity.** The current full dump includes every plan allocation, including overwritten intermediates, plus alternate recurrence/history banks (`K:253-257`). Rank0 swaps after each half (`K:204`), so a batched final-only recurrent update is insufficient: preserve the serial penultimate state/history in the correct alternate bank, exact M parity, last-row values for every old per-layer intermediate, same keys/values/raw/pooled tails and IDs, token/history/position/error/status, and stale head values on skipped-head chunks. The existing ng multirow loop writes final recurrence only; add a separate penultimate capture or preserve the exact per-position bank schedule. Matching only emitted tokens or final streams does not satisfy the contract.

## First-stage recommendation

An isolated multirow **expanded p33 variant6 Q6 qkv** microkernel, not a full engine prefill rewrite, is the highest-value credible <1-day first discriminator. Its22 sites touch720,896,000 distinct bytes/position (22*10240*3200); extend the same explicit lane-order template to all48 expanded Q8 attention outputs,849,346,560 bytes (`R/qkv-q6-p33/engine/build/source/policy.hpp:3-128`, `N/p33_candidates.hpp:85-93`). Together these two families touch1,570,242,560 bytes,29.48% of target layer weight addressing. With R8 reuse, the optimistic weight-only whole-target speed ratio is5,327,311,360/(5,327,311,360-1,570,242,560+1,570,242,560/8)=1.348. This is a lower-bound traffic model, not measured wall speed or a promised integration result.

Use `batch_expanded<T,R>` preserving k=lane*8+256*t then j0..7 and all original scale/product/add/32-lane tree/BF16 boundaries (`N/p33_candidates.hpp:85-100`, `N/p33_submit.cpp:53-64`). Gate Q6 first on R1/4/8, M16/32/64 and tails, retained real activation rows plus finite adversarial rows; compare every BF16 output byte to repeated unchanged variant6 submissions before timing. A device identity failure closes that exact arm without tolerance. Gate Q8 next only if the shared template and Q6 exact proof finish inside the day. Do not promise the full controller/protocol/state rewrite in the same day. Full-target token and byte/state gates are mandatory when integrating; a projection microgate is only one prerequisite.

The packed Q4_K/Q5_K/IQ4_XS denseblock family is a useful alternative/next stage with a smaller code surface but636,887,040 addressed bytes across116 sites (22 z198,574,080;14 qkv237,568,000;7 qgate132,710,400;remaining shared/k/v68,034,560; `R/dense-packed-block/selection.hpp:6-123`). Its stride32 lane order differs from p33. Per-class timing does not resolve formats, so these byte counts cannot be called measured speed shares.


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
