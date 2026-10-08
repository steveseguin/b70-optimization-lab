# Screen 1b: host-memory fit before another Flash-Next load

**Decision: needs the port first.** Do not repeat Screen 1 with a smaller
offload number and assume it is safe. Its generic offloader can temporarily
hold both a pageable and a pinned copy of each 12.8 GB PLE shard. Four such
copies overlap without a loader admission barrier. Removing that duplicate
allocation is the first change; proving four GiB of free VRAM on **every** card
is a separate requirement. No launch configuration currently satisfies both
requirements on the evidence inspected here.

This was a CPU-only source and receipt audit on `steve-b70s`. No container,
image inspection, GPU operation, installation, secret access, host-setting
change, Git branch, commit or runtime edit was performed. Only this note is
the deliverable. Proposed controller/runtime changes below are not installed.
Use **GB = 10^9 bytes**, **GiB = 2^30 bytes**. Interpret the requested hard
ceiling conservatively as **90,000,000,000 bytes = 83.819 GiB**, not 90 GiB.

## Evidence and citation convention

File:line citations use these explicit roots; patch citations refer to lines
in the patch artifact, including diff context, not reconstructed source lines.

- `V/` = `/home/steve/src/lumnus-20261008/vllm/`, clean inspected tree at
  `9d79d28d7e32f33bdbd115c85d116583ce679cb6`, branch `b70/v0.30.0-stable`.
  This is the requested V30-base source proxy with Lumnus overlays, **not** a
  claim that every file in it was mounted into the official image.
- `R/` = `/home/steve/llm-optimizations/`.
- `L/` = `R/experiments/qwen38-flash-next-fp8-b70/`.
- `S/` = `L/reopen-20261008/runs/screen1-mtp1/`.
- `C/` = `R/repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/`.
- `P/` = `R/patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/`.
- `E/` = `R/patches/qwen38-flash-next-fp8-b70/vllm-placement-mtp1-005dc578/`.
- `M/` = `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8/`; only small
  configuration metadata was read, not model tensor payloads.

The image/package receipt says vLLM `0.30.0+xpu`, torch `2.13.0+xpu`, Triton
`3.7.2+xpu`, kernels `0.1.14.1`; launch.json records the image digest and
individual bind-mounted sources. Those are the run identities, not a
container inspection performed by this audit. [S/runtime-versions.json:1;
S/launch.json:62–110]

**Evidence limitation:** `S/kernel-oom-and-fault-window.log:1` contains only
`-- No entries --`. The 67.9 GB unit peak, victim's 38.2 GB virtual size /
12.6 GB anonymous RSS, and global OOM are supplied incident facts and recorded
in `L/notes/2026-10-08-screen1-mtp1-host-oom-result.md:17–20`; that saved kernel
window does not independently substantiate them. No per-rank smaps, host
memory.stat, or allocation trace accompanies those numbers in the inspected
receipts. Do not invent a measured breakdown. Also, the reported GPU fault
window **14:04:34–42 precedes the 14:04:51 OOM kill**. Memory pressure is a
plausible common cause; “the OOM kill caused the CAT error” is not established.
[L/notes/2026-10-08-screen1-mtp1-host-oom-result.md:14–23]

## 1. What Screen 1 actually allocates

### Generic UVA budget and PLE ownership

The controlling flags are `--tensor-parallel-size 4`, expert parallelism,
`--offload-backend uva --cpu-offload-gb 16.25`, and the three selective suffixes
`ple_embedding.ngram_embedding.weight`, `mlp.experts.w13_weight`,
`mlp.experts.w2_weight`. The CLI's misleading `gb` spelling is converted with
`1024**3`. Each worker constructs its own offloader and counter. Therefore
16.25 GiB is **per rank**, nominally 65 GiB / 69.793 GB total; it is not a
shared 16.25 GiB pool. [S/launch.json:119–174;
V/vllm/model_executor/offloader/base.py:171–174;
V/vllm/model_executor/offloader/uva.py:40–64]

“Generic 16.25 GiB/rank” came from the reopening plan's **unmeasured admission
assumption**, not a V30 default, measurement, or certified setting. It meant
replacing selected expert-row placement with whole expert-tensor offload,
keeping token embeddings resident. The plan explicitly called for a separate
host fit and actual byte receipt. The certified number was 12.25 GiB for PLE
and token embeddings, plus separately placed experts; 16.25 is not a faithful
translation of those two mechanisms. [L/reopen-20261008/runtime-notes.md:40–69;
C/identity.json:73–94]

The offloader checks the budget **before** each parameter and then copies the
entire parameter. It can overshoot. It does not match the weight-scale suffixes.
With the inspected dimensions and module order, the static prediction is:

| Parameter | Bytes per rank | GiB per rank |
| --- | ---: | ---: |
| Native FP8 PLE shard | 12,800,061,440 | 11.920986 |
| One layer's w13, 128 × 1280 × 2560 FP8 | 419,430,400 | 0.390625 |
| One layer's w2, 128 × 2560 × 640 FP8 | 209,715,200 | 0.1953125 |
| Selected expert weights: seven complete layers plus next w13 | 4,823,449,600 | 4.4921875 |
| **Predicted completed generic offload** | **17,623,511,040** | **16.413174** |
| **All four ranks** | **70,494,044,160** | **65.652695** |

This is a source-derived allocation prediction, **not a completed-load receipt**:
Screen 1 never printed its final offloaded-byte total. Layer 0 experts precede
layer 1 PLE; within layer 1, PLE is registered before the MLP. The budget then
stops after layer 7 w13. Account for any future padded shapes, aliases or
registration-order changes by enumerating actual planned parameters, not by
rounding the CLI number. [V/vllm/models/qwen4_exp/nvidia/model.py:195–250;
V/vllm/model_executor/models/utils.py:875–883;
V/vllm/model_executor/offloader/uva.py:83–123;
V/vllm/model_executor/layers/quantization/fp8.py:560–619;
S/server.log:104–105]

PLE is **ETP vocabulary-sharded**, not one complete table per rank and not a
shared host allocation. DP is one here. The model has 16 n-gram heads,
160 columns/head, and 320,001,536 padded vocabulary rows: 80,000,384 rows per
rank at one byte/FP8 element. Total table storage is 51,200,245,760 bytes
(47.683945 GiB). This independently matches the old static byte receipt.
The FP8 method adds a small FP32 scale parameter, not a second BF16 table;
dequantization applies to looked-up rows. [M/config.json:18–20,82–112;
V/vllm/models/qwen4_exp/nvidia/ngram_embedding.py:502–538,748–802,2072–2118,2137–2154;
L/data/20260829-tp4-mtp0-4352-ple-only-static-budget.json:27–36]

The logged `Qwen4ExpPLEFp8EmbeddingMethod` describes the checkpoint format,
not the Lumnus optional external-table compression flag. All four logs say
`weight_device=xpu:N, pinned=False` at creation. `B70_PLE_FP8=0` and
`B70_PLE_INT8=0` do not turn native FP8 PLE into BF16. The device embedding is
selected with no external PLE path/Engram route; generic offload subsequently
moves its weight into pinned CPU storage, provided pinning/UVA are available.
**PLE is included in the generic budget. Do not add another 47.68 GiB to its
completed 65.65 GiB.** [S/server.log:106–109; S/launch.json:36–41;
V/vllm/models/qwen4_exp/nvidia/ngram_embedding.py:666–688,888–898,2180–2226;
V/vllm/model_executor/offloader/base.py:23–32]

### The large transient happens even before checkpoint staging

V30's generic code does `cpu_data = p.data.to(device="cpu")`, followed by
`cpu_data = cpu_data.pin_memory()`, then installs the accelerator view. The
old pageable object remains alive while the pinned copy is made. This copies
even the enormous **uninitialized** PLE parameter. Construction occurs before
`load_weights`, so “Loading model from scratch” does not prove safetensors
were already being loaded. All four workers reached PLE construction within
the same logged second; the log ends there. The most direct source-supported
hazard is therefore concurrent PLE offload construction, not four full model
state dictionaries. [V/vllm/model_executor/offloader/uva.py:113–123;
V/vllm/model_executor/model_loader/base_loader.py:65–75;
V/vllm/v1/worker/gpu/model_runner.py:395–404; S/server.log:99–109]

The following is a **planning overlap scenario**, not a reconstructed measured
peak. First three rows are tensor sizes. The last three are explicitly chosen
uncertainty allowances; no receipt measures their amounts. Even setting all
allowances to zero fails the requested gate.

| Construction phase, four concurrent ranks | GiB | GB | Basis |
| --- | ---: | ---: | --- |
| PLE destination pinned storage | 47.683945 | 51.200246 | Four native FP8 shards |
| Pageable source copies during pinning | 47.683945 | 51.200246 | Four concurrent `to(cpu)` → `pin_memory()` lifetimes |
| Already offloaded layer 0 experts | 2.343750 | 2.516582 | Four × 629,145,600 bytes |
| **Tensor overlap subtotal** | **97.711639** | **104.917074** | Above 90 GB without other costs |
| Other private runtime memory + allocator retention allowance | 12.000000 | 12.884902 | Assumption, not 4 × victim RSS |
| Active file-cache/staging allowance | 4.000000 | 4.294967 | Assumption; hash cache remains reclaimable |
| Other host/kernel/driver allowance | 4.000000 | 4.294967 | Assumption; not a measured xe accounting value |
| **Illustrative predicted peak** | **117.711639** | **126.391910** | Exceeds 115 GiB (123.480310 GB) physical RAM |

Ranks need not reach maximum pinning simultaneously for a failure, but nothing
in the selected path bounds their overlap. Actual timing might give a smaller
peak; allocation failure kills the process before its planned peak can be
observed. If freed pageable PLE copies remain resident in the CPU allocator
until later, a more conservative envelope is completed pins + four PLE
temporaries + the same allowances = **143.169126 GB**. These are distinct
lifetime cases, not two quantities to add together. Source alone cannot
certify an upper bound on allocator/driver retention.

**RSS attribution:** pinned pages can already appear in a worker's RSS or in
runtime/driver/cgroup accounting. Its 12.6 GB anon RSS is strikingly close to
one PLE CPU copy, but it is not evidence of 12.6 GB of *additional overhead*.
The victim's 38.2 GB virtual mapping size is not resident RAM. Other possible
private costs are Python/torch imports, CPU allocator arenas and retained
copy buffers, communication/runtime state, and later loader conversions.
CCL was initialized before loading; the launch enables its allreduce and
allgatherv temporary buffers. Their byte sizes and accounting cannot be
deduced from these flags or the victim line. Keep them unknown until sampled,
not an invented fixed per-worker tax. [S/launch.json:20–25;
S/server.log:47–99; V/vllm/v1/worker/xpu_worker.py:160–166;
V/vllm/distributed/device_communicators/xpu_communicator.py:1–65]

**Loader/page cache:** the default iterator uses `safe_open(...).get_tensor`
one file at a time. EP filtering precedes `get_tensor`; it is not PLE
TP-range filtering. Lazy mmap pages are file-backed and physically shared
between mappings of the same file, although summed process RSS can count
them repeatedly. The `eager` option reads a whole shard into Python bytes
and then deserializes it; threaded loading can multiply live shard buffers.
Neither is a remedy here. Auto-prefetch is for recognized network filesystems
when the entire checkpoint fits under 90% of available RAM; forced prefetch
only warns on a bad fit. It cannot sensibly fit this 185.6 GB checkpoint in
115 GiB. Explicit `--safetensors-load-strategy lazy` makes the intent clear.
[V/vllm/model_executor/model_loader/default_loader.py:266–298;
V/vllm/model_executor/model_loader/weight_utils.py:875–949,951–1000]

The prelaunch hash pass streams the model and can fill clean page cache;
it does not require the whole model to stay resident. Do not count all
185.6 GB as anonymous memory, or treat clean cache as permanently pinned.
Do not drop caches or alter swap. Count the active non-reclaimable/in-flight
portion once, and observe `MemAvailable` after hashing. [L/reopen-20261008/screen.py:224–227;
C/identity.json:23–30]

**Comparison with 67.9 GB:** it is a partial unit peak at an aborted load,
not a complete-host peak or completed pin allocation. It cannot be added to
the generic budget or to four RSS values. Docker's daemon/container cgroup,
the controller's systemd unit, kernel/driver pages, and unrelated host usage
must be identified before comparing scopes. On a 115 GiB host, a global OOM
with a smaller reported unit peak is entirely possible. The missing raw
window prevents an exact accounting reconciliation; the construction
overlap is sufficient reason to refuse the configuration, not proof of the
precise fault mechanism.

## 2. What made the certified lane smaller

The certified A367 identity offloads PLE and token embeddings with a
12.25 GiB cap (actual expected 12.217GiB/rank), keeps ordinary hot expert
rows on device, and places a census-selected subset on pinned host memory.
Selected rows remain callable through an address table; they are never
pruned. The Triton tile/K loop, expert index and scale indexing must remain
the same. [C/identity.json:73–96;
L/notes/2026-09-05-per-expert-host-placement-design.md:12–33]

**Correct the shorthand “rank-serialised bounded loading”:** patch 0003
serialised *post-load global compaction*, staging all a rank's expert rows.
It was an OOM failure, not the final fit mechanism. A204 tried to pin about
28.7 GB with only about 24 GB available. Patch 0004 switched to per-layer
staging; allocator fragmentation remained. Patch 0005 replaced that with
**load-time placement**: release unfilled full tensors, allocate resident-size
device tensors and final host rows, and make the loader write through
`row_view`. Patch 0006 explicitly adds `device="cpu"` to pinned allocations.
Port those final semantics, not the historical stage-everything code.
[E/0003-XPU-Q38_EXPERT_HOST_PLACEMENT-rank-serialized-global.patch:25–39,127–135;
E/0005-XPU-Q38_EXPERT_HOST_PLACEMENT-v5-on-the-promoted-lin.patch:51–61,103–146;
E/0006-XPU-Q38_EXPERT_HOST_PLACEMENT-pinned-host-rows-alloc.patch:19–31;
L/notes/2026-09-05-day-summary.md:214–245]

| Certified storage component | Rank 0 | Rank 1 | Rank 2 | Rank 3 | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| PLE, GiB | 11.920986 | 11.920986 | 11.920986 | 11.920986 | 47.683945 |
| Input embedding, GiB | 0.296021 | 0.296021 | 0.296021 | 0.296021 | 1.184082 |
| Placed expert count | 543 | 587 | 550 | 586 | 2,266 |
| Placed FP8 expert bytes, GiB | 2.485657 | 2.687073 | 2.517700 | 2.682495 | 10.372925 |
| **Expected pinned storage, GiB** | **14.702663** | **14.904079** | **14.734707** | **14.899502** | **59.240952** |

The last row is **63,609,487,360 bytes / 63.609487 GB**, derived from the
manifest and placement map, not a host-RSS measurement. One expert occupies
`3 × 2560 × 640 = 4,915,200` FP8 weight bytes; scales remain on device. The
file's “3p5gib” label is a ceiling, not 3.5 GiB actually occupied on every
rank. A314's load receipts independently show 2.69, 2.52 and 2.68 GiB for
ranks 1–3; the census note gives all four rounded amounts. These receipts
support the placement mechanism, not a new A367 memory measurement.
[C/identity.json:79–94; L/data/20260906-q38-expert-host-placement-3p5gib-per-rank.json:1;
L/data/20260907-tp4-mtp1-a314-placement-load-receipt.txt:1–8;
L/notes/2026-09-07-a316-decode-window-census-and-the-rebuilt-placement.md:5–12]

**Host RSS:** not recorded as a usable total/peak in the inspected A364–A367
summaries, identity and guide. Do not turn the pin-byte estimate into RSS.
The larger-context A382 variant records **MemAvailable trough 8.08 GB**, and
A394 a trough of **8.11 GB**; these are different context/placement settings,
not A367 RSS, and emphatically not evidence of a 90 GB fit on today's host.
The “5gib-mc2” map actually selects 780/814/867/847 experts: 3.571/3.726/3.969/
3.877 GiB per rank, total PLE+embedding+expert pins **68.731126 GB**.
[L/notes/2026-09-13-a382-32k-context-ladder-mtp1-exactgdn-result.md:3–6,27–28;
L/notes/2026-09-13-a394-32k-mtp1-fresh-server-repeat-result.md:3–6;
L/data/20260913-q38-expert-host-placement-a315-census-5gib-mc2-per-rank.json:1]

The useful PLE source contracts are:

| Contract to preserve | Exact source and applicability |
| --- | --- |
| No initial garbage copy | `P/0010-Avoid-copying-uninitialized-PLE-weights-during-offlo.patch:130–175`: explicitly marked checkpoint-backed PLE allocates directly with `empty_like(device="cpu", pin_memory=...)`. Only safe with complete load coverage. This directly addresses Screen 1's construction transient. |
| Complete row/shard loading | `P/0027-Require-complete-Qwen4Exp-PLE-shard-coverage.patch:49–69`; `P/0030-Validate-Qwen4Exp-PLE-shards-after-root-load.patch:40–79`: validation belongs after the root loader; missing and unexpected shards fail. V30 common overlap copying exists (`V/vllm/models/qwen4_exp/common/ple.py:23–99`), but copying overlaps and checking the FP8 scale are not a complete shard-coverage gate. |
| Validate the real owner | `P/0031-Skip-PLE-shard-coverage-on-GPU-placeholders.patch:35–49`: a process-offload placeholder must not claim to have loaded the table. Does not authorize skipping coverage for Screen 1's real table. |
| Filter before materialization | `P/0033-Filter-PLE-offload-weights-before-materialization.patch:227–245,344–385`: index/name filtering, lazy safetensors, no threaded/eager fallback. Originally for the separate PLE worker; adapt TP-owned range filtering to the actual owner, rather than adding an unnecessary full-table process. |
| Correct destination device | `P/0007-Fix-PLE-target-device-selection-across-accelerators.patch:67–78`: CPU for the offload worker, actual accelerator and index otherwise; never hard-code CUDA for XPU. |
| Transport and bounded waits | `P/0003-Support-eager-PLE-offload-transport-on-XPU.patch:4–13`; `P/0032-Bound-XPU-PLE-offload-waits.patch:178–190,267–269`: XPU-aware transport and finite waits if that separate-worker route is used. The A367 identity selects direct UVA parameter offload; these historical process-transport features are not extra A367 table copies or required resident helpers. |

## 3. Candidate changes and the two independent fit gates

The old lane fitting its hardware does **not** establish four GiB of VRAM
headroom. Its historical pre-placement weight estimate was 31.57 GiB/card
against 31.89 GiB physical. Moving only 2.49–2.69 GiB of experts cannot prove
the requested four GiB reserve, even before new-runtime KV, MTP, capture,
allocator slack and workspaces. Use physical device capacity from a preserved
receipt, not the nominal “32 GB” label. [L/notes/2026-09-05-day-summary.md:91,214–245]

For each rank, compute both construction and serving peaks:

```text
Vpeak[r] = max_over_phases(resident weights + duplicate/repack tensors
                         + draft weights + full-16-bit KV + GDN state
                         + graph/private pools + workspaces
                         + allocator slack + communication/driver reserve)
require Vpeak[r] <= physical_VRAM[r] - 4 * 2**30
```

Do not count weights twice when draft embeddings are shared, and do not omit
vision components merely because prompts are text-only: Screen 1 logged ViT
construction. The V2 runner loads its speculator after the target. No receipt
here measures the new path's complete Vpeak. [S/server.log:100–101;
V/vllm/v1/worker/gpu/model_runner.py:420–433]

| Candidate | Output effect | Effort | Fit assessment |
| --- | --- | --- | --- |
| **(a) Lower `cpu-offload-gb` / restrict suffixes** | Placement alone should preserve bytes; new path still needs exact gates. | Small flag edit. | **Low/no joint-fit confidence.** Reducing the cap while it still selects PLE does not shrink its 12.8 GB copy. Removing PLE moves 11.92 GiB/rank back onto nearly full cards. Reducing expert offload trades host RAM for VRAM and worsens the four-GiB reserve. |
| Lower max length / KV / utilization | Same inputs can be lossless within retained capacity, but shrinking below the registered suite changes the screen. Compressed KV is excluded. | Small. | **Not a host-load fix.** KV is explicitly only 376,569,856 bytes/rank (0.350708 GiB). Even deleting it cannot recover four GiB/card. A smaller max length alone does not reduce that explicit allocation. The explicit KV byte setting overrides utilization-based KV sizing. |
| PLE device/pinned flags only | Native table placement can be lossless; external compressed tables are separate inputs and excluded. | Small if supported, otherwise a port. | **No proven safe switch.** Engram config is CUDA-only. `PLE_TABLE_PATH` loads external data and the XPU pinned-class default first allocates pageable storage then materializes pinned slabs. `B70_PLE_DIRECT_PINNED=1` alone does not replace the native device/generic-UVA route. Disabling pinning sacrifices the qualified transport without establishing resident-memory/VRAM bounds. |
| Lazy, non-threaded loader | Preserves checkpoint bytes; coverage still required. | Small. | Useful explicit constraint, **insufficient alone**: the giant copy precedes checkpoint iteration. Avoid eager/prefetch/full CPU-model initialization. |
| **(b1) Port direct PLE allocation + coverage/filter semantics** | Intended lossless storage/lifetime change; validate every row/scale, padding and exact output on V30. | Small-to-medium Python port; no native rebuild inherently needed for the allocation change. | **High confidence it removes the identified 51.2 GB four-rank duplicate; medium confidence in overall fit.** Generic completed pins remain ~70.49 GB, leaving only 19.51 GB for everything else under the hard ceiling. VRAM still unresolved. |
| **(b2) Port final v5 expert placement + embedding offload** | Intended lossless; retain callable host rows, logical expert count, scales, original Triton arithmetic and post-load attributes. | Medium-to-large Python/Triton port into V30's modular MoE hooks; not merely setting the old environment name. | More controllable placement and final allocation sizes. **Medium plausibility, no certified fit.** Old mask pins 63.61 GB but does not prove four GiB/card reserve. A larger mask costs additional host memory. |
| **(c) Serialise bounded construction/load sections** | Should preserve loaded bytes; gate exactness independently. | Medium Python/executor work and cancellation design. | **Useful alongside b1/b2; low confidence alone.** With generic pins plus one whole PLE temporary, a conservative envelope is already 83.294 GB before overhead. A one-rank full-expert staging buffer is still forbidden. `--max-parallel-loading-workers 1` is explicitly ignored in this V30 source. |

Flag/loader references: `V/vllm/config/cache.py:228–235`;
`V/vllm/config/engram.py:65–82`;
`V/vllm/models/qwen4_exp/nvidia/ngram_embedding.py:1030–1068,2189–2204`;
`V/vllm/config/parallel.py:1013–1017`.

**Minimal defensible preparation:** port b1 first, add a real bounded
allocation/copy scheduler and safe abort path, then recompute the entire
four-rank plan. Generic whole-tensor experts can remain for a diagnostic screen
if both gates pass; b2 is needed if their granularity/layout cannot meet the
VRAM limit within the host budget. Do not port all nine historical placement
patches literally. For illustration, PLE+embedding plus **5 GiB of expert
rows/rank** would pin 73.946481 GB and leave just **16.053519 GB (14.951 GiB)**
for all runtime, staging, cache, driver and host overhead. That is a remaining
budget, **not evidence those costs fit**, and neither existing placement file
actually supplies five GiB on every rank.

Serialisation must cover PLE **construction/pinning**, not just safetensors
iteration, and retain only bounded row chunks. Use host-side coordination
around collective-free sections after distributed initialization; blindly
serialising the entire model constructor can deadlock collective setup.
Count retained allocator buffers across stages; a barrier alone does not
release them. Preserve original dtype, full 16-bit KV, model/PLE bytes,
FP8 scales and target verification. Memory qualification never certifies
V30 GDN/QSA arithmetic against the old output pins.

## 4. Required prediction check and loading-stop design for screen.py

The current controller checks `MemAvailable >= 100 GiB` before launch and
stops below **8 GiB** during loading. It has no tensor/lifetime host prediction.
Its health polling and journal call share the same loop; health calls can
block for two seconds and the loop then sleeps two seconds. This is too late
and too coarse for four ~12.8 GB copies. [L/reopen-20261008/screen.py:159–161,247–265,308–317]

Add a CPU-only plan builder immediately before launch, after hash verification,
and run it again if flags, source hashes, model metadata or placement change.
It must not import torch/vLLM or discover a GPU. Inputs are:

1. Exact launch flags/environment; model config and bounded safetensors-header
   metadata/index; tensor dtype, shape, scale sizes and alias identities.
2. TP/ETP/EP partitions, module registration order, offloader matching and
   overshoot behavior; actual selected expert IDs, not mask filename budgets.
3. A source-bound phase/lifetime manifest: construction, pinning, checkpoint
   copy, postprocessing, MTP load, KV allocation, compilation/capture, serving.
   Specify maximum concurrent ranks, chunk bytes, live copy count and retained
   CPU allocator/pinned-pool bytes. Unknown retention is not zero.
4. Conservative bounded private runtime, CCL, allocator, driver, active
   non-reclaimable file/staging, controller/API/compiler and unrelated-host
   costs. Record their source/receipt and whether they are assumed or measured.
   Current evidence is insufficient to fill these with certified V30 values.
5. `/proc/meminfo` before and after hashing, accessible relevant cgroup
   `memory.current`, `memory.peak`, `memory.stat`, `memory.events`, process
   `smaps_rollup`/status, and preserved physical-VRAM capacities. Missing
   required observations/permissions fail closed; no sudo/token workaround.

Use one owner per physical allocation; file mappings, UVA views, RSS and
cgroup totals are observations of that ownership, not additional allocations:

```text
Hphase = B_other_host
       + sum_r(P_final_live[r] + A_private_excluding_P[r]
               + T_pageable_or_pinned_copies_live[r] + A_retained[r])
       + F_active_unique + K_driver_unattributed + safety_allowance
Hpred = max(Hphase for all construction/loading/serving phases)

reject if any required bound is unknown or source/config identity mismatches
reject if Hpred > 90_000_000_000
reject if any Vpeak[r] > Vphysical[r] - 4 * 2**30
reject if post-hash MemAvailable cannot cover the remaining committed growth
          plus the reserved shutdown/host margin
```

For a simple deliberately conservative bound, sum all final pins once, all
independent runtime overhead, the **maximum concurrently live** staging
allocations and allocator retention. A finer phase schedule may reduce that
bound only with enforced allocation ordering. Do not subtract clean cache
twice via both `MemAvailable` and a bespoke reclaim estimate. The 90 GB gate
covers the complete host pressure budget, not merely the controller unit.
Write `host-memory-prediction.json` with byte values, phase maxima, source
hashes, uncertainties, VRAM bounds and refusal reasons. This note specifies
the check; it does not claim the check has been implemented.

### Stop before pressure becomes an OOM

For the future patched loader, use an independent lightweight watchdog at
**250 ms** intervals, started before workers allocate. A conservative initial
stop trigger is **whole-host accounted pressure >= 80 GB OR MemAvailable
<= 32 GiB**, whichever happens first; also stop when the next admitted
allocation/chunk would cross either threshold. These early trip points leave
space below the 90 GB prediction ceiling for observation delay and drainage.
They may refuse a borderline otherwise-small-enough plan; do not lower them
silently to force a run through. Bound the largest in-flight copy to, for
example, **256 MiB total**, one admitted copying rank at a time. A plan that
still needs an uninterruptible 12.8 GB duplicate cannot claim this safety
margin. Measure/record the stop latency before relaxing any allowance.

On a trip: latch no-new-allocation/no-new-request state; request cooperative
loader cancellation; send **one SIGINT to the identified server entry
process**, not a PID pattern or the entire GPU cgroup. Loader cancellation
must finish/synchronize outstanding transfers before releasing their source
storage, acknowledge idle, then unwind workers. Keep the monitoring process
alive and record PID/start-time identities, last admitted allocation, pressure
samples and signal/exit receipts. If it does not drain, preserve evidence and
seek owner intervention; no automatic kill escalation, reset or relaunch.

**SIGINT alone is not a guarantee.** The existing controller avoids Docker's
timeout-to-SIGKILL stop, but V30's executor itself waits its configured grace,
sends SIGTERM, waits four seconds, then calls `p.kill()`. Worker signal
handlers raise `SystemExit`, which is not a loader copy-drain protocol.
The death-pipe monitor is also installed after worker construction/loading,
so do not assume it cancels an in-progress initial load. Audit/port a
loading-aware no-hard-kill shutdown and cooperative copy completion before
calling the stop safe. Increasing `VLLM_WORKER_SHUTDOWN_TIMEOUT_SECONDS`
only delays escalation; it does not remove it.
[L/reopen-20261008/screen.py:280–298;
V/vllm/v1/executor/multiproc_executor.py:451–519,660–680,857–873,916,969–976]

Never use a low cgroup RAM cap, SIGKILL, swap manipulation or cache drops as
the memory controller. No polling watchdog can promise “never OOM” under
unbounded concurrent allocations or unrelated host pressure. The defensible
design is **refusal before launch + bounded allocation admission + early
cooperative stop**, with memory and copy lifetimes enforced inside the loader.
Any subsequent device fault retains the first-fault/second-fault boot rule;
this note neither runs a probe nor authorizes another launch.

## Ten-line summary and recommendation

1. Screen 1 has no demonstrated host/VRAM fit; its saved kernel window is empty.
2. The 16.25 GiB flag is per rank, selected by the plan, and can overshoot to 16.413 GiB.
3. Native FP8 PLE is 12.800 GB/rank, sharded, and included in that generic budget.
4. Concurrent pageable-to-pinned PLE copies can put tensor pressure alone at 104.917 GB.
5. A stated 20 GiB overhead allowance gives a 126.392 GB construction scenario, not a measured peak.
6. Do not add the 67.9 GB unit peak, victim RSS, PLE and generic offload as separate costs.
7. Certified placement expects 63.609 GB of pins; its final mechanism is load-time row placement.
8. Rank-serial global expert staging failed historically; V30's loading-worker flag is ignored.
9. Require a complete <=90 GB prediction, >=4 GiB/card reserve, bounded copies and an early drained stop.
10. **Recommended Screen 1b: needs the port first—direct-allocation PLE with coverage and bounded loading/shutdown; add final v5 placement if required by the two fit gates.**
