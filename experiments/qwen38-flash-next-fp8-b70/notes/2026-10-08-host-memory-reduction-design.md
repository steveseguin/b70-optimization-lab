# Flash-Next: reduce host memory without changing the certified arithmetic

2026-10-08 — CPU-only design on `steve-b70s`. **Recommend file-backed native
FP8 PLE rows, a bounded 4 GiB total host row cache, and bounded loading.** The
planning calculation is **87.8 GB**, including explicit uncertainty allowances.
This is a candidate prediction, not a measured fit or permission to relaunch.
No GPU, Docker, server, installation, secret, host setting, Git branch/commit,
or port 8188 operation was performed. Only this design note was written.

The important correction is that **A367's PLE storage was already FP8:
51.200246 GB / 47.683945 GiB across four ranks**. The 95.37 GiB BF16 table is
the external W4A16 recipe's starting point, not the certified FP8 allocation.
Its BF16 size would be 102.400492 decimal GB. Neither that hypothetical table
nor a second accelerator-labelled UVA view belongs in A367's memory sum.
[S/CALIBRATION.md:26–46; X/patches/vllm/0008-b70-ple-int8-rowscale-pinned-table.patch:9–30]

## Evidence and citation roots

GB means 10^9 bytes; GiB means 2^30 bytes. Citations are **file:line** under
these roots; patch line numbers refer to the patch artifact, not the resulting
source file. Estimates and contributor reports are identified separately.

| Prefix | Absolute root |
| --- | --- |
| `L/` | `/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/` |
| `S/` | `/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/` |
| `C/` | `/home/steve/llm-optimizations/repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/` |
| `P/` | `/home/steve/llm-optimizations/patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/` |
| `E/` | `/home/steve/llm-optimizations/patches/qwen38-flash-next-fp8-b70/vllm-placement-mtp1-005dc578/` |
| `V/` | `/home/steve/src/lumnus-20261008/vllm/` |
| `X/` | `/home/steve/src/lumnus-20261008/b70-flash-next/` |
| `M/` | `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8/` (small config only) |

Inspected V30 proxy: `9d79d28d7e32f33bdbd115c85d116583ce679cb6`;
external recipe snapshot: `b103e0f4522316b6368e135586b69a8bd3d37cf0`.
The certified runtime is instead vLLM `6d872457`, kernel head `bbae3c5`,
torch 2.11.0+xpu and the pinned oneCCL build. Its 46.854250 tok/s result uses
MTP1, exact serial GDN, TP4/EP4, length 4,352, one sequence, 64 batched tokens,
and capture sizes [1,2]. Storage changes must preserve that arithmetic;
V30's current model, GDN, collectives and tuning do not inherit certification.
[C/README.md:11–50; C/identity.json:59–99; S/CALIBRATION.md:131–147]

This is static design review, using the repository's
`review-model-contribution` workflow. Lumnus's INT8 patch 0008 and NVMe patches
0013/0013b are acknowledged as specific external techniques, **community-reported**,
with no local performance validation or adoption in this task. The lab's
direct PLE allocation, v5 expert placement and certified arithmetic predate
this review. The proposed native-FP8 adaptation is new lab design work, not
a claim that Lumnus measured the certified FP8 lane.

## 1. Where the approximately 116 GB went

A367's 1,241 samples show MemAvailable falling from **132.425544 GB** to
**16.555667 GB**, a **115.869876 GB whole-host pressure increase**. The minimum
is at 04:11:42 UTC, after the four model-load messages at approximately
04:02:11 UTC. Thus it cannot be explained solely as a brief initial loader
copy. The trace records MemAvailable, not RSS, PSS, pin allocations or a
historical MemTotal. Calling the entire difference precisely measured
“unreclaimable RAM” is stronger than these counters establish: MemAvailable
is an availability estimate incorporating reclaimability. Retain 115.87 GB
as the measured pressure delta and conservative planning anchor.
[S/rescued-calibration.json:6–44; S/evidence/a367-host-pressure.tsv:2;
S/evidence/a367-host-pressure.tsv:700; S/evidence/a367-host-pressure.tsv:1240]

| Component | Rank 0 / 1 / 2 / 3, decimal GB | Four-rank GB | What is established |
| --- | --- | ---: | --- |
| Pinned PLE table | 12.800061 each | **51.200246** | Source-derived storage: 80,000,384 rows/rank × 160 FP8 bytes. One global FP32 scale per embedding owner is negligible here. No persistent BF16 expansion. |
| Pinned expert weight rows, w13+w2 | 2.668954 / 2.885222 / 2.703360 / 2.880307 | **11.137843** | 543 / 587 / 550 / 586 experts across layers. Each expert is 4,915,200 FP8 bytes; scales remain on device. Derived from the certified mask; older A314 receipts support rounded placement amounts. |
| Pinned input token embedding | 0.317850 each | **1.271398** | 62,080 × 2,560 BF16/rank, shared with the draft; count once. “Device” in an old summary is not proof of physical device residency. |
| **Identified host tensor subtotal** | **15.786865 / 16.003133 / 15.821271 / 15.998218** | **63.609487** | Allocation reconstruction, corroborated by sequential CPU shape allocations; not a measured XPU allocator total. |
| Worker private anon RSS excluding the above pages: Python/torch, CPU allocator retention, CCL, graph/runtime host state | **Unknown per rank** | **Unknown** | No surviving worker smaps/RSS series. Cannot assign the OOM victim's 12.6 GB to each worker or treat it as extra overhead. Graph device pools are not host RSS. |
| Loader/conversion staging and retained allocations | **Unknown at A367's peak** | **Unknown** | Final v5 avoids staging the whole expert model. PLE direct allocation avoids the initial pageable duplicate. Remaining loader/conversion lifetimes were not measured. |
| Driver/kernel, other processes, active file pages and availability-estimator effects | **Not rank-attributable** | **Unknown** | Included only in the unresolved difference below, not invented as a fixed per-worker tax. |
| **Unattributed difference, covering the preceding three rows together** | — | **52.260389** | **Residual estimate** = 115.869876 − 63.609487. This is not “52 GB torch overhead,” nor three additional budgets to add. |
| Clean reclaimable checkpoint page cache | Shared physical pages; not four independent copies | **Excluded as a permanent allocation** | Do not add the 185.6 GB checkpoint or sum file-backed RSS across workers. Active/non-reclaimable effects cannot be removed exactly from this trace. |
| **Measured whole-host pressure increase** | — | **115.869876** | Tensor subtotal plus unresolved residual reconciles to this value; absolute host pressure additionally includes the prelaunch baseline. |

Storage evidence: `S/placement_plan.py:14–42`, `S/CALIBRATION.md:26–80`,
`C/identity.json:72–94`,
`L/data/20260907-tp4-mtp1-a314-placement-load-receipt.txt:1–8`.
Native FP8 dequantization is a gather followed by cast and scale multiply,
not conversion of the entire PLE table:
`P/0001-Merge-02f2b4c15dd987d9436e125aab29604447c77405-into-.patch:18869–18887`
and `V/vllm/models/qwen4_exp/nvidia/ngram_embedding.py:748–802`.

Today the supplied host facts are approximately 124 GB MemTotal after blocks
53–57 were offlined, with no 2026 RAM replacement. That is not enough margin
for this historical pressure plus the OS. Screen 1's 14:04 UTC failure is
recorded as a 67.9 GB unit peak and 12.6 GB victim anon RSS; those narrower
accounting scopes neither contradict nor measure A367's whole-host peak.
The saved kernel window was incomplete, and the fault timestamps precede
the OOM kill. Do not infer a precise causal sequence or add the unit peak to
the PLE allocation. [L/notes/2026-10-08-screen1-mtp1-host-oom-result.md:10–19;
L/notes/2026-10-08-screen1b-host-memory-fit.md:42–50,160–198]

## 2. Lossless choices, ranked by useful GB saved relative to risk

All savings below are estimates unless expressly called byte counts. Code-size
ranges are planning estimates, including integration but excluding tests.
No per-token timing was measured here. “Lossless” describes the intended
storage contract; passing the certified output gates remains mandatory.

| Rank / change | Expected saving | Per-token cost | Exactness argument and implementation size |
| --- | --- | --- | --- |
| **1 — (a) Native FP8 PLE on NVMe; bounded row cache** | **About 40.6 GB** after a 4 GiB host cache, explicit metadata/staging and 4 GiB active-file allowance; about 45.2 GB without that file/staging allowance. Durable host saving. | Planning **0.25–2 ms/output token** with concurrent reads; higher tails possible. A serial cold mmap path can take several ms/step. | Copy identical 160-byte rows and retain the certified owner mask, reduction, cast and scale arithmetic. Medium/large: roughly 500–1,000 Python lines across storage/index, cache, loader and pre-forward integration; graph-safe transport is the difficult part. |
| **2 — (b) Direct destination allocation plus serialized bounded copy sections** | Versus stock V30: remove up to **51.2 GB** of simultaneous pageable PLE copies. Serialization alone reduces that particular overlap by at most **38.4 GB**, leaving one 12.8 GB temporary. **Credit 0 GB durable saving against A367**, which already used direct PLE allocation/v5. | **0 decode cost**; possibly longer startup. | Copy original bytes once into final storage, with full coverage and synchronization. Small/medium incremental work, roughly 100–300 lines beyond the prepared Screen 1b guard/loader; do not serialize collectives. |
| **3 — (c) Release actual duplicate loader/source storage** | **0 GB proven additional saving** in A367. Any measured excess retention is upside, not part of the fit claim. | **0** after completed copies; allocator release may cost startup time. | Release only a distinct allocation after its last reader. Audit roughly 50–150 lines of hooks/instrumentation; fixes depend on what owns the storage. Never free a live UVA backing store. |
| **4 — (e) Host workspaces, KV capacity and capture trims** | **0 GB credited** for the certified configuration; perhaps sub-GB host savings if measured unused buffers exist. KV totals only 1.506279 GB **on device**. | None for truly unused host storage; eager execution or different capture shapes can cost latency and are not presumed exact. | Keep [1,2], full 16-bit KV, the 4,352 capacity and certified compute path. Small audit/flag work, roughly 20–100 lines; narrower buffer lifetimes need synchronization tests. |
| **5 — (d) Page cold expert rows from files into a smaller pinned cache** | Up to **11.137843 GB gross**; approximately **8–10 GB net** with 1–2 GiB cache/staging. Cannot alone meet a 20–30 GB reduction. | Roughly **2–6 ms per cold expert miss**, potentially hundreds of ms when many layers miss. | Same FP8 weights/scales and same Triton tiles/K-loop; resolve every routed expert before compute. High risk/large work: roughly 800–1,500 lines plus routing/cache/stream tests. |

The numerical GB/risk ratio is not a measured scalar: this ranking prioritizes
durable fit against the certified line. Direct allocation is the lowest-risk
startup repair, but it is already in that line and must not be subtracted
from its 115.87 GB a second time.

### (a) PLE lookup geometry, mmap and the critical path

There is **one PLE layer, model layer 2**. N-gram size 3 and eight heads per
n-gram give 16 heads: eight bigram and eight trigram. Each head gathers one
160-element row, then the 16 rows flatten to 2,560 elements. The table is
vocabulary-sharded over ETP4, not replicated four times.
[M/config.json:18–20,98–113;
V/vllm/models/qwen4_exp/nvidia/model.py:195–209;
V/vllm/models/qwen4_exp/nvidia/ngram_embedding.py:502–538,2072–2118,2338–2349]

| Target step | Logical row lookups across all ranks | Raw FP8 row payload | Cold file traffic if each lookup faults on a different page |
| --- | ---: | ---: | --- |
| One target input token | 16 | 2,560 B | Usually about 64 KiB; at most 128 KiB for two-page rows |
| MTP1 two-row verifier step | 32 | 5,120 B | Usually about 128 KiB; at most 256 KiB |
| Certified maximum 64-token prefill chunk | 1,024 | 163,840 B | Usually about 4 MiB; at most 8 MiB |

Counts are before duplicate-ID elimination and cache hits. A rank owns about
four heads/token; provision for the full 16/token rather than relying on exact
head-boundary balance. MTP's one draft layer is after the target's 48 layers,
not another layer-2 PLE; do not multiply table reads by every MoE layer or
allocate a draft PLE table. Rejected verifier rows are still read, so divide
per-step overhead by **actual committed tokens**, usually one or two for
MTP1, not by a promised two. [M/config.json:87–113;
V/vllm/models/qwen4_exp/nvidia/mtp.py:167–190]

Use read-only mappings of the **existing checkpoint shard row ranges** and a
small manifest of tensor offsets, row coverage, dtype, hashes and global scale.
This avoids a second 51.2 GB file and any full-table startup copy. A row can
cross a page or a tensor/shard boundary; map the owning shard correctly.
Map on the CPU, gather only missing rows into bounded pinned buffers, then
copy raw bytes to the existing graph-owned input buffer. Ordinary pageable
`mmap` is **not** an XPU UVA pointer: a device kernel cannot safely fault in
arbitrary NVMe pages through the old pinned-pointer path. Never pin/mlock
the whole mapped file or mutate it into private anonymous pages.

Clean mapped pages may occupy free RAM and are reclaimable. **mmap does not
enforce a 4 GiB page-cache cap.** The 4 GiB active-file amount in the budget is
an allowance to test, not a kernel guarantee. Use small read windows and
bounded concurrent requests; observe reclaim/major-fault latency. Do not
drop caches, change readahead/swap/sysctls or rely on pre-warming the table.
If bounded pressure cannot be maintained, a later application-level direct-I/O
reader is an alternative, not permission to change host settings.
[V/vllm/model_executor/model_loader/weight_utils.py:875–949;
L/notes/2026-10-08-screen1b-host-memory-fit.md:173–190]

**Read-latency assumptions:** budget 50–200 microseconds per cold 4 KiB
completion on an otherwise idle local NVMe, plus CPU dispatch, faults,
synchronization and transfer. This is a sensitivity range, **not a measured
property of this host**. Thirty-two serial faults would cost 1.6–6.4 ms before
that overhead. Concurrent rank-local batches can reduce this to a few I/O
waves; plan 0.5–2 ms/step initially, measure p50/p95/p99 and allow longer
tails under reclaim or disk contention. At 46.85 tok/s the average output
interval is about 21.34 ms; even 1 ms/token matters. No predicted tok/s is a
benchmark or a replacement for the certified number.

Lumnus reports 0.5 ms p50 / 1 ms p99 host bubbles and 97–98% cache hits under
its agent traffic, with 2–5 misses/step. Its NVMe versus pinned-INT8 comparison
reports a 2–4% decode loss and identifies host synchronization as the main
cost. Those are **external W4A16/INT8 measurements**, not our cold realistic
suite, our SSD, or evidence of exact parity to native FP8. Its implementation
uses `O_DIRECT` and a pinned host cache, not mmap page-cache faulting and not
a device cache. Its native-reader path compiles at first use; none of it was
executed here. [X/docs/ple-nvme.md:8–40;
V/vllm/models/qwen4_exp/nvidia/ple_nvme.py:3–60]

**A small device cache cannot guarantee hiding lookup latency.** For example,
64 MiB/card holds about 419,430 raw rows before tags, only 0.52% of that rank's
80 million rows. Bigram locality could help; a uniform unseen trigram stream
will mostly miss. No archived certified row-hit distribution supports an
assumed high hit rate. Known prompt rows can be prefetched a chunk ahead;
decode rows become known only after actual token/draft selection. There is
only the work before layer 2 to hide the current step's read. A synchronous
host pre-forward hook stalls even on a device-cache hit unless its integration
avoids that synchronization. Start **without a persistent device hot cache**;
only tiny double-buffered gather outputs are needed. Add a device cache later
only with measured benefit and VRAM admission.

The cache must store raw immutable **weight rows**, never prompt/KV/answer
state. Record cache occupancy, hit/miss counts and cold-start state; do not
train it on the scored suite or repeat prompts to manufacture hits. Slot
lifetimes must cover in-flight current/previous graph work, with completion
events before eviction; sequence boundaries, EOS, padding and speculative
rollback must give identical row IDs. Preserve the old raw-byte owner
reduction and `FP8 -> output_dtype`, then scale cast and multiply. Do not
substitute a fused dequantization/LUT just because it appears equivalent.
The certified prefetch patch is a useful contract for this split; V30's host
hook is an integration example, not an arithmetic authority.
[P/0035-Add-opt-in-XPU-async-UVA-PLE-prefetch.patch:583–660;
P/0001-Merge-02f2b4c15dd987d9436e125aab29604447c77405-into-.patch:18873–18887;
V/vllm/v1/worker/gpu/model_runner.py:1913–1928]

### (b) What serialization actually removes

Stock V30 runs `p.data.to(cpu)` and then `cpu_data.pin_memory()`. During the
second operation both full 12.8 GB PLE allocations can exist per rank, even
though these are uninitialized weights and checkpoint iteration has not
begun. Four overlapping ranks mean 51.2 GB pins + 51.2 GB pageable copies;
already-offloaded layer-0 experts bring that construction overlap to about
104.9 GB before other costs. This is a source-derived possible overlap,
not a measured reconstruction of the interrupted OOM peak.
[V/vllm/model_executor/offloader/uva.py:83–123;
L/notes/2026-10-08-screen1b-host-memory-fit.md:121–158]

Allocate final storage directly, serialize only collective-free allocation
and copy sections, and limit live temporary copies across ranks to 256 MiB.
Lazy checkpoint views, row-range filtering and full shard-coverage checks
must survive. Rank serialization alone leaves one huge copy and does not
release allocator-retained storage. `max_parallel_loading_workers=1` is
explicitly ignored in V30. The lab's old patch 0003 serialized **post-load
whole-rank expert compaction** and failed; final v5 instead writes directly
into compact resident/host destinations. Do not reintroduce that failed arm.
[V/vllm/config/parallel.py:1013–1017;
P/0010-Avoid-copying-uninitialized-PLE-weights-during-offlo.patch:130–175;
E/0005-XPU-Q38_EXPERT_HOST_PLACEMENT-v5-on-the-promoted-lin.patch:51–61,103–146;
S/overlay/vllm/models/qwen4_exp/common/ple.py:68–83;
L/notes/2026-10-08-screen1b-host-memory-fit.md:213–225,257–266]

### (c) Duplicate copies: distinguish storage from aliases

The certified PLE accelerator view aliases its pinned CPU allocation. v5's
`_q38_host_cpu` and `_q38_host_storage` similarly name the CPU allocation and
its accelerator view; they are not two copies. The resident expert tensor
contains the complementary rows. `_q38_placed_*` keeps attributes on the
same storage through parameter replacement, with a pointer equality check.
Deleting those owners can leave graph/address-table pointers dangling.
There is **no demonstrated giant tensor held both pinned and resident** in
the certified layout. [E/0005-XPU-Q38_EXPERT_HOST_PLACEMENT-v5-on-the-promoted-lin.patch:107–146,156–177;
V/vllm/model_executor/offloader/uva.py:95–123]

Audit unique storage pointers, sizes, backing type and last-use events, then
release distinct checkpoint conversion buffers and draft embedding allocations
only where sharing is proven. V30 initially constructs a draft embedding;
that alone does not prove a lasting duplicate or host placement. Keep no
entire state dictionary or BF16 materialization “for convenience.”
[V/vllm/models/qwen4_exp/nvidia/mtp.py:179–190; S/CALIBRATION.md:30–46]

### (d) Fewer pinned expert rows, with misses fetched on demand

Simply reducing the placement mask moves weights to almost-full cards and
does not meet the proposed memory tradeoff. Merely unpinning anonymous
weights leaves their resident host bytes. Actual host savings require a
file-backed backing store plus a bounded cache for evicted expert rows.

One logical expert needs w13 (3,276,800 B) and w2 (1,638,400 B): **4.9152 MB**.
At an assumed effective small-extent NVMe rate of 1–3 GB/s, a miss costs
1.64–4.92 ms of reads plus dispatch. If copied to device staging, allow
another approximately 0.25–0.5 ms at an assumed 10–20 GB/s H2D rate; if left
in a pinned slot, keep the existing UVA compute cost instead. Hence plan
**2–6 ms/miss**, not a 4 KiB PLE latency. These bandwidths are assumptions,
not host measurements. There are 10 selected experts × 48 target layers =
480 selection opportunities/token (up to 960 for a two-row verifier before
deduplication), so a broad miss pattern is unacceptable for decode.
[S/placement_plan.py:16–39; M/config.json:101–103]

The certified cold mask was selected from two censuses, not a proof that
those experts are impossible to route to. On every miss, fetch and wait;
never substitute zeros, prune, fall back to a different GEMM or let captured
pointers reference an evicted slot. Keep scales and logical expert IDs intact.
This needs an integration point between routing and the existing MoE kernel,
making it considerably riskier than PLE, whose IDs depend only on tokens.
[C/identity.json:84–96;
E/0005-XPU-Q38_EXPERT_HOST_PLACEMENT-v5-on-the-promoted-lin.patch:127–146]

### (e) KV, graphs and workspace trims

The certified device KV allocation is **376,569,856 bytes/rank**, only
1.506279 GB total. Removing it all could not supply a 20–30 GB host saving;
shrinking it below the registered workload is not a compatible screen.
An explicit byte budget also prevents a smaller max-length flag from being
assumed to shrink allocation automatically. Keep BF16/FP16-family KV and
the model's FP32 recurrent state. There is no certified 128 GB CPU KV tier
to remove; that belongs to Lumnus's different serving setup.
[C/README.md:50; C/identity.json:64–71;
L/notes/2026-10-08-screen1b-host-memory-fit.md:295–306; X/README.md:9–14]

Capture [1,2] is already narrow. Measure host and device capture deltas
separately, retaining the same graph buffers, kernel choices and CCL algorithm.
Trimming unused host buffers is lossless; disabling graphs, changing batch
geometry or CCL settings is not assumed bit-identical merely because the
weights are unchanged. No multi-GB saving is supported for these knobs.
[C/identity.json:59–81; S/CALIBRATION.md:37–39;
V/vllm/v1/worker/gpu/model_runner.py:1017–1065]

## 3. Output-changing alternatives: owner's decision and new authority

**All three options change numerical values and can change generated tokens.
They are not lossless reductions of the certified line and would need an
owner-approved new quality authority.** A semantic pass or a higher speed
does not preserve the A367 exact-output authority.

| Option | Savings and scope | Why it changes outputs |
| --- | --- | --- |
| **INT8 PLE, Lumnus 0008** | 164 B/row: 160 int8 + FP32 row scale. **52.480252 GB** total. Saves **49.920240 GB** against a hypothetical 102.400492 GB BF16 table, but **increases A367 native-FP8 storage by 1.280006 GB**. No host saving against this lane's PLE. | Symmetric per-row quantization reconstructs different embedding values. Lumnus reports 0.66% relative L2 error against its BF16 table versus 2.66% for its FP8 conversion; that is nonzero error, not parity with our publisher FP8 bytes/global scale. |
| **W4A16 AWQ / AutoRound** | Routed-expert raw payload across 48 × 512 experts would fall from about 120.796 to 60.398 GB: **60.398 GB gross weight saving**, less scales/zeros and changed nonexpert formats. With the old host mask, only about **5.57 GB gross host** saving is automatic; newly freed device space might eliminate the remaining expert pins for up to **11.14 GB host** saving versus A367. No measured complete-host fit is supplied. | Requantized experts and different GEMMs change the target. Lumnus reports **87.9 tok/s AWQ / 90.4 tok/s AutoRound** with MTP3, INT8 PLE/NVMe and its own tests. Those are separate community-reported results, not an FP8 speedup or exactness proof. |
| **FP8 KV** | At fixed token capacity the absolute best-case halving of all 1.506279 GB is **0.753140 GB device** saving; actual saving is smaller if part is recurrent state, padding or uncompressed data. **0 GB direct host** saving here. Keeping the same byte budget instead buys capacity, not RAM savings. | Cache rounding/scales change attention values; support and quality must be established separately. Never compress recurrent state by implication or treat this as the default. |

INT8 evidence and specific credit:
`X/patches/vllm/0008-b70-ple-int8-rowscale-pinned-table.patch:9–37,93–113`;
`V/vllm/models/qwen4_exp/nvidia/ngram_embedding.py:843–850`.
W4A16 evidence: `X/README.md:54–75,77–96,98–113` (different checkpoint,
MTP depth, benchmark lengths and host); expert-byte formula:
`S/placement_plan.py:16–39`. KV baseline: `C/identity.json:64–71`.
Do not add W4 savings to the native-FP8 plan or use external download sizes as
runtime memory measurements.

## 4. Recommended lossless plan and the first load measurement

Keep all certified expert bytes/placement, token embeddings, FP8 scales,
MTP1 verification, full 16-bit KV, GDN/QSA/HC/MoE arithmetic and capture shapes.
Replace **only PLE storage/transport** with the unchanged-byte file-backed
path, plus bounded construction/loading. The first implementation should use
one **1 GiB pinned row cache per rank**, no persistent device hot cache,
and the same small stable device gather buffers across replay.

The following conservative **scenario** preserves the entire unexplained
A367 residual instead of replacing it with the old arbitrary 20 GiB estimate:

| Host budget component | Decimal GB | Basis |
| --- | ---: | --- |
| A367 measured pressure increase | 115.869876 | Historical whole-host delta |
| Remove full native FP8 PLE pins | −51.200246 | Source-derived table size; credit once |
| Add 4 GiB total pinned raw-row cache | +4.294967 | Proposed fixed allocation |
| Add cache metadata | +1.736347 | Conservative dense map: 320,001,536 × 4 B; slots: floor(4 GiB / 160) × (8 B ID + 1 B ref + 8 B epoch), rounded upward |
| Add global copy/staging limit | +0.268435 | 256 MiB; bound across ranks, not per rank |
| Add active file-page allowance | +4.294967 | Scenario assumption, not an enforced page-cache ceiling |
| Add approximate prelaunch OS/host baseline | +2.500000 | Assumption from supplied approximately 135 GB historical host and 132.43 GB available; replace with current measurement |
| Add runtime/driver difference contingency | +10.000000 | Explicit uncertainty allowance, not measured overhead or proof of an upper bound |
| **Predicted whole-host pressure** | **87.764347 GB (81.74 GiB)** | **Below the requested 95 GB; unqualified** |

The scenario replaces 51.2 GB with about 10.595 GB of explicitly budgeted
cache/metadata/staging/active pages: **40.606 GB net structural saving**.
No duplicate-removal, expert paging or workspace saving is needed to make
this scenario fit. The 10 GB contingency covers possible runtime growth,
not permission to ignore an observed excess. A 20 GB runtime delta instead
would predict 97.8 GB and reject the plan. At approximately 124 GB MemTotal,
87.8 GB leaves approximately 36 GB available-equivalent margin, subject to
the accounting definition and other workloads.

Metadata must not be forgotten: the external cache really allocates dense
`row2slot`, `slot2row`, reference and epoch arrays. A sparse index could reduce
it, but no such unimplemented saving is credited.
[V/vllm/models/qwen4_exp/nvidia/ple_nvme.py:827–854]

**Certified arithmetic is a separate prerequisite.** The prepared V30 port
retains native fused GDN and a different model/collective/compiler context;
it cannot yet promise unchanged outputs. Port or retain the certified exact
arithmetic overlay and gate it under a pinned identity. On V30 this includes
the serial GDN verifier, QSA/HC paths, MoE geometry/scales and reduction order,
not just model bytes. Do not replace the old oracle with new answers to make
a failing port pass. A load fit alone does not qualify the candidate.
[C/README.md:11–34,45–50; S/README.md:41–46]

**Screen 1b-load would first measure allocation lifetime and host fit, not
tokens/s.** After the CPU implementation/row-byte checks and a separately
authorized exclusive launch window, use the prepared `calibrate-load`
structure: start sampling before construction, load once, capture, hold a
20-second ready plateau without generation, then one graceful stop. Record:

1. Absolute `MemTotal − MemAvailable` and baseline-relative pressure;
   pre/post-hash values; per-worker RSS/PSS/anon/file/locked breakdown;
   container cgroup current/peak and anon/file/unevictable categories;
   Mlocked/Unevictable and driver accounting where readable. Never sum
   overlapping RSS, pins and cgroup totals. Missing fields stay unknown.
2. Phase boundaries for allocation, checkpoint copy, postprocessing, MTP,
   KV and capture; unique pinned/storage counters proving that no 12.8 GB
   PLE shard is allocated, no BF16 expansion exists, and live staging stays
   within 256 MiB. Capture retained allocations after each phase, not just
   the final ready footprint. Half-second samples alone can miss short peaks;
   combine them with cgroup peak and allocation-event counters.
3. Per-card complete memory peak/reserve, including graphs and workspaces;
   unchanged expert placement does not create new VRAM. The old approximately
   29.4–29.6 GiB load deltas exclude complete graph/KV/driver peaks and cannot
   establish the controller's four-GiB reserve.
4. Clean shutdown, no fault/OOM, no watchdog or allocation-guard override,
   and byte/hash-bound identities for checkpoint rows, scale, placement,
   runtime, arithmetic overlay and cache parameters.

The existing load controller already specifies 0.5-second samples, the ready
plateau and one stop. RSS/PSS attribution and allocation-event detail above
are **additional proposed instrumentation**, not claims about its current
receipt. Existing limits remain: ≤90 GB observed loading pressure,
plateau × 1.15 ≤90 GB, ≥4 GiB free/card for admission, with stricter internal
loader checks and current boot/ownership guards. The **95 GB design target
does not override those rules**. At 87.8 GB the 15% plateau margin would fail;
only a measured passing receipt can admit generation. This task changes no
guard and attempts no launch. [S/README.md:73–78,87–140]

There is also a known reserve conflict: the V30 static inventory gives the
certified mask only **2.140 GiB maximum possible worst-card reserve**, before
unmeasured runtime costs. Moving host PLE to disk does not improve that device
floor. Thus this host-memory design alone cannot satisfy the unchanged
four-GiB generation-admission rule. Any additional expert placement needed
for that rule must be separately budgeted and gated; it is not a free saving
inside the 87.8 GB estimate. The load-only screen can diagnose actual usage
but may stop at its two-GiB safety floor. [S/CALIBRATION.md:94–123;
S/README.md:118–140]

A load-only pass **cannot measure NVMe decode latency**: V30's external
pre-forward row hook explicitly skips dummy/profile/capture calls. Before
any generated-answer performance run, separately verify raw-row byte equality
at TP, shard and page boundaries, n-gram IDs across EOS/request boundaries
and rejected drafts, forced misses/evictions/short reads, and exact output
pins/repeats on fresh servers. Then measure the complete cold varied suite,
actual cache misses and I/O tails alongside prefill, TTFT and decode. No
historical speed is projected into that result.
[V/vllm/v1/worker/gpu/model_runner.py:1913–1922;
C/README.md:29–43,53–60]

## Ten-line summary

1. A367 lost 115.87 GB of MemAvailable; that is host pressure, not a worker-RSS breakdown.
2. Its native FP8 PLE table occupied 51.20 GB, not a 95 GiB BF16 allocation.
3. Expert pins used 11.14 GB and token embeddings 1.27 GB; 52.26 GB remains unattributed.
4. Clean checkpoint page cache is not an extra permanent 185.6 GB allocation.
5. File-backed identical PLE rows with a 4 GiB cache offer about 40.6 GB net structural saving.
6. Loading fixes remove V30 transient copies but add no proven steady saving over A367.
7. Device caches cannot hide every cold lookup; budget and measure NVMe and host-sync tails.
8. INT8 PLE, W4A16 and FP8 KV change outputs and require a new owner-approved authority.
9. The explicit plan predicts 87.8 GB, but existing memory, VRAM and exactness gates still apply.
10. Screen 1b-load must measure real phase peaks and teardown before any speed experiment.

**Single recommended next action:** implement and CPU-test the unchanged-byte
FP8 PLE mmap/4 GiB-cache adapter with bounded loading and allocation receipts;
do not relaunch Flash-Next yet.
