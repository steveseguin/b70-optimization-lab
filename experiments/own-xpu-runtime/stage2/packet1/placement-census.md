# Flash-Next residency and streaming census

**Arithmetic from the local header contract, not a new measurement or admission.**
The checked [placement arithmetic](placement-arithmetic.json) accompanies the
[complete tensor contract](tensor-contract.json). Follow
[DESIGN's placement and lifetime rules](../../DESIGN.md#expert-streaming-uva-and-host-shadow):
count physical allocations once, preserve every expert and its scales, retain
full 16-bit KV, and budget staging, runtime-created host shadows and graph peaks.
The certificate belongs to TP4/EP4; hypothetical TP2/EP2 remains unqualified.

## What the certified four-card line actually uses

A367 offloads the FP8 PLE table and BF16 input embedding through UVA, and
parks the [certified expert mask](../../../qwen38-flash-next-fp8-b70/data/20260906-q38-expert-host-placement-3p5gib-per-rank.json)
in pinned host storage. EP4 gives each rank 128 of the 512 full experts per
layer; the expert matrices are not each divided by four as TP projections
are. Parked expert *weights* move; their scale tensors stay on device.
Every expert remains callable. Zero-hit observations on old routing censuses
are not a guarantee for new requests or permission to omit a routed expert.

| Item | Logical bytes, all ranks before replication | Certified residency |
| --- | ---: | --- |
| FP8 PLE table (128 partitions) | 51,200,245,760 | Host-UVA, vocabulary-sharded; 12,800,061,440/rank |
| Input embedding, shared with MTP | 1,271,398,400 | Host-UVA, 317,849,600/rank |
| Target + MTP routed experts with stored scales | 123,327,590,400 | EP4; 11,137,843,200 weight bytes on host, scales stay on device |
| Remaining text weights/metadata | 8,805,135,898 | Optimistic balanced TP except known HC replicas |
| Vision | 897,862,112 | Excluded, not a text allocation |
| HC down/up matrices within the text total | 1,310,720,000 | Replicated per rank; add three copies for TP4, one for TP2 |

| Rank | Host experts | Host expert weight bytes | Total identified host tensor bytes | Optimistic device weight floor bytes | Historical load delta (GiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 543 | 2,668,953,600 | 15,786,864,640 | 31,347,267,974 | 29.57 |
| 1 | 587 | 2,885,222,400 | 16,003,133,440 | 31,130,999,174 | 29.37 |
| 2 | 550 | 2,703,360,000 | 15,821,271,040 | 31,312,861,574 | 29.54 |
| 3 | 586 | 2,880,307,200 | 15,998,218,240 | 31,135,914,374 | 29.38 |

The device floor is `(184,604,370,458 text bytes + 3 × 1,310,720,000 HC
replica bytes)/4 − host tensors[r]`, rounded down as an optimistic aggregate
partition. It includes stored scales and excludes vision. It does not include
all replicated small tensors, padding, KV, recurrent/QSA state, graph pools,
scratch or runtime overhead, and is not an exact rank allocation plan.
The known KV budget alone adds **376,569,856 bytes/rank**. A367's rounded
model-load deltas above come from the
[rescued calibration](../../../qwen38-flash-next-fp8-b70/reopen-20261008/CALIBRATION.md#rescued-supervisor-evidence-and-load-only-follow-up).
They are allocator deltas, not complete VRAM peaks; the gap above the header
floor is not attributable to a single cause.

The [“cards are full” note](../../../qwen38-flash-next-fp8-b70/notes/2026-09-13-a375-a376-32k-context-ladder-prereg.md#why-the-placement-widens)
reports **0.11–0.35 GiB free/card on A369**, a later diagnostic control in the
same lineage. It is not A367's measured per-card reserve. Historical idle
XPU snapshots are also not live headroom. No device query was made here.

The later `PLACEMENT:` option in the
[diagnostic generator](../../../qwen38-flash-next-fp8-b70/tools/rewrite-q38-a338-to-diag-mtp1-step-timing.py)
swaps the mask; it does not make more memory or change expert arithmetic.
The 32K attempt initially tried a 5-GiB max-count-8 mask and failed its host
floor. Its later max-count-2 mask parks about 3.57/3.73/3.97/3.88 GiB per
rank. Those are different context/placement runs, not A367's mask. Likewise,
October's [1,000/1,100/1,200-expert options](../../../qwen38-flash-next-fp8-b70/reopen-20261008/CALIBRATION.md#enumerated-v30-placements)
are unqualified planning alternatives. None supplies a two-card fit measurement.

## What two cards would need

This scenario preserves the original FP8/BF16 tensors, MTP block, full target
head and all experts. PLE and the input embedding stay off-device. We use
**34,242,297,856 bytes/card** only because the lane retained that historical
rank-0 capacity; treating it as both cards' capacity is an explicit scenario,
not a present-day capacity reading. Even nominal 32 GiB/card is insufficient.

| Requirement | Four-card certified accounting | Two-card arithmetic |
| --- | --- | --- |
| PLE/embedding host bytes | 52,471,644,160 total | Same logical total; half each under vocabulary split |
| EP-owned experts/layer/rank before placement | 128 | 256 |
| Text bytes excluding PLE/embedding, before HC replicas | 132,132,726,298 | 132,132,726,298 |
| Extra known HC replicas | 3,932,160,000 | 1,310,720,000 |
| All-resident device weight floor before expert offload | 136,064,886,298 | 133,443,446,298 |
| Capacity scenario | 136,969,191,424 | 68,484,595,712 |
| Certified host expert weights | 11,137,843,200 | Keeping only these off-device still leaves 53,821,007,386 bytes too many |
| Minimum extra host placement from an all-resident expert plan | Certified mask above | **64,958,850,586 bytes weight-only** |
| Gap including the same KV byte budget per rank | Already separate from weights | **65,711,990,298 bytes**, before state/graphs/scratch |

At least **13,215 whole expert triplets plus their BF16 scales** must be
nonresident somewhere across the 49 target/MTP blocks in the weight-only
scenario. Keeping all scales on device, as A367 does, requires at least
**13,216 weight triplets** off-device. These are aggregate capacity lower
bounds, not chosen expert IDs or balanced rank plans. Exact IDs and sufficient
per-card reserve require a later placement plan; naming arbitrary experts as
intrinsically impossible to retain would be misleading. What cannot coexist
on two cards is the full routed-expert bank alongside these dense components.
The tensor directory gives every affected `model.language_model.layers.L.mlp.experts.E`
and `mtp.layers.0.mlp.experts.E` gate/up/down weight and scale name.

With nominal **32 GiB/card**, the corresponding weight-only gap is
**64,723,969,562 bytes** (60.28 GiB). With the historical capacity scenario it
is **64,958,850,586 bytes** (60.50 GiB). Both already assume off-device PLE
and input embeddings and account for known HC duplication. They still omit
some replication and every transient/runtime allocation. Simply halving the
four-card load numbers is not a valid two-card estimate.

## Bytes crossing the host/device boundary

The FP8 expert weights total 4,915,200 bytes/expert; BF16 scales add 600 bytes.
The largest selected-expert transfer budget when all selected experts miss
residency is therefore:

| Work | FP8 weights | BF16 scales if transferred | Total bytes |
| --- | ---: | ---: | ---: |
| Top 10, one layer | 49,152,000 | 6,000 | 49,158,000 |
| One target token, 48 layers | 2,359,296,000 | 288,000 | **2,359,584,000** |
| One MTP proposal, one layer | 49,152,000 | 6,000 | **49,158,000** |

If scales remain resident, subtract that scale column from PCIe traffic.
If scales are expanded to FP32 and transferred, double it. These totals
exclude block padding, bus transaction amplification and activation traffic.
UVA demand reads and explicit whole-expert staging have different actual bus
traffic; only a measured native census can choose their budgets.

For a partially resident plan, actual host traffic is
`sum(host_selected_experts[layer]) × (4,915,200 + transferred_scale_bytes)`.
Static capacity cannot tell which top-10 IDs are selected. The honest bounds
are zero to the full selected-expert budget, with no guaranteed zero-hit
placement for arbitrary prompts. Do not multiply the total model size by
10/512: dense/shared/HC/head tensors and PLE lookups obey different rules.

PLE adds **2,560 logical FP8 row bytes per target token**, sixteen 160-byte
rows; the input embedding adds **5,120 bytes**. MTP has no second PLE layer.
Storage-page reads can be much larger than row bytes. Every host hit must
be served exactly; no predicted routing, dropped expert, prompt warming or
response reuse is allowed. Stable UVA backing must remain alive until all
referencing queues drain. Explicit miss handling may force segmented replay;
this packet does not promise a single captured transaction with host-managed
misses. Timing per emitted MTP token also depends on accepted/rejected rows.

## Host-shadow consequence

The certified PLE, embedding and expert host allocations total
**63,609,487,360 bytes**. Its measured whole-host pressure increase was
**115,869,876,224 bytes**, leaving a **52,260,388,864-byte unresolved
residual** above those tensor allocations. The
[host-memory note](../../../qwen38-flash-next-fp8-b70/notes/2026-10-08-host-memory-reduction-design.md#1-where-the-approximately-116-gb-went)
does not establish that residual as pure GPU shadow: loader lifetimes,
allocator/runtime overhead, page pressure and other host activity contribute.
Do not add the residual again as several different allocations.

For two cards, the **optimistic minimum host tensor backing is
117,430,494,746 bytes**: PLE + input embedding + the weight-only device gap.
This nearly consumes the roughly 124 GB usable-host figure in the lane notes,
before OS, staging, graph/runtime overhead or host shadows. Putting *all*
experts and scales on the host with PLE/embedding needs **175,799,234,560 bytes**,
already larger than the machine's nominal 128 GiB RAM.

If each resident device weight also needs one distinct host shadow, the
combined host weight demand reaches **185,915,090,458 bytes** (text payload
plus the extra TP2 HC copy), before non-weight allocations. This is a
conditional accounting scenario, not a measured driver property. A two-card
implementation therefore needs bounded file-backed PLE/expert storage and/or
proven removal of host duplicates/shadows, plus an admitted cache/staging
budget. An ordinary file mmap is not a pinned device UVA pointer. Reclaimable
page cache is pressure to observe, not another full permanent checkpoint copy.

The [96-GB guard and newer host-memory plan](../../../qwen38-flash-next-fp8-b70/reopen-20261008/README.md)
remain historical/current-lane evidence, not authorization or a guaranteed
budget for our runtime. Native work must measure joint per-card residency,
RSS/PSS, pinned bytes, GPUActive and cgroup peaks under orderly teardown.
No host-memory setting changes, cache drops or live actions were used here.
