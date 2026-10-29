# Exact two-card TP with a kernel-direct exchange (2026-10-28)

**Question.** The October 25 exact TP broke even because each copy gather cost 13–26 µs. Now that a producer kernel can
store straight into the peer card's memory and raise one flag ([p2p/direct-store-2026-10-28](../../p2p/direct-store-2026-10-28/RESULT.md)),
does exact within-layer splitting pay off inside the engine?

**Answer so far: yes.** With the GDN blocks split by key group (Stage 2) and compact expert slots (Stage 2b), rank 1 runs
**10.74–10.84 ms per decode half on two cards against 12.25 ms on one card (1.13–1.14×)**, bitwise exact on the full
1,079-buffer dump with no exclusions. Stage 2 alone gave 10.82–10.96 ms; Stage 1 alone 11.35–11.38 ms (1.075–1.078×).
Stage 1 needed two things together:
- the direct exchange (one kernel per card per exchange, about **6.1 µs** each in the engine, against 13 µs per dense
  gather and 26 µs per expert layer for the copy path);
- one host submission thread per card. With one thread the direct exchange is **slower** than one card (13.94 ms),
  because the host then sets the pace (12.8 ms of enqueue per half).

The October 25 copy path on the same binary gives 12.64 ms (0.97×). The 1.075× matches the sizing model's
"O2, calibrated, g = 5 µs" projection (1.07×, [SIZING.md](../../pp4-review-2026-10-28/within-layer-sizing/SIZING.md)).

## Setup (identical for every arm)

- SC117 rank 1 (layers 23–47 plus head), split 23, F32 activations, context 4096, the live service's rank-1 command and
  flags ([rank1-launch-c4096.json](rank1-launch-c4096.json); changes listed in its `changes` field), driven alone by
  [engine/tools/tp_rank1_driver.py](../../../engine/tools/tp_rank1_driver.py): 16 decode halves on deterministic
  input streams, then a full state dump. Medians are over halves 3–16, as on October 25.
- One card: 0000:23:00.0. Two cards: 23:00.0 (card 0) and 47:00.0 (card 1), one shared context.
- Every run: `systemd-run --user -p LimitNOFILE=1048576`, both card locks (`flock -n`), `taskset -c 0-3,16-19`,
  `--timing token` (no profiling queues; the engine now refuses anything else with `--tp-replicate`), kernel log
  checked before each phase (24 h) and after every arm ([run_arms.sh](run_arms.sh), [logs/](logs/)).
- `EnableDeferBacking=0` (with `NEOReadDebugKeys=1`) in all arms, and `OWNRT_QSA_RAW_RING=0` so both arms hold the same
  buffers (TP never used the ring).
- Binaries: `f5a7d39752e3…` (timing phase 1) and `5c92875f439e…` (phase 3; adds only the exchange-only diagnostic), both
  built from `engine/src` with `engine/build.py` into fresh `/dev/shm/engine-build-tp-direct-20261028-r{2,4}` (r1–r3
  archived to `/mnt/raid-models/ownrt-experiment-archives/2026-10-28/engine-builds/`).

## What was built (all opt-in; default paths unchanged)

| Flag | Effect |
|---|---|
| `OWNRT_TP_EXCHANGE=direct` | Each October 25 gather becomes one `Device::exchange` kernel per card. Dense row halves (`tp_xgather`): store own rows locally and into the peer's `y`, then wait for the peer's flag. Experts by slot (`tp_xslot`): store own slots into the peer's staging, wait, copy the peer's slots from local staging into `y`. |
| `OWNRT_TP_THREADS=1` | Card 1's prepared commands are issued by their own host thread; the half's thread issues card 0's. Needs `direct` (no host event crosses cards). The join has a deadline. |
| `OWNRT_TP_EXCHANGE=direct-replicated` | Exact diagnostic: nothing split or masked, the same exchanges overwrite identical rows. Measures the exchange cost alone. |
| `OWNRT_TP_EXCHANGE=copy` / unset | October 25 copy gathers. |

Exchange kernel ([single_device.cpp](../../../engine/src/stage2/packet194-expert-diet-engine/single_device.cpp)
`submit_exchange`): plain stores into peer USM, system-scope release fence, per-site work-group counter (gives the epoch;
no reset needed), last group stores the epoch into the peer's flag word between system-scope fences (no peer atomics).
Waits poll the local flag with system-scope atomic loads, **at most 2^22 polls (about 0.5–0.7 s; xe job timeout 5 s)**;
a timeout sets the engine's sticky `error` and an abort word so later waits skip. Readers are later, fresh kernels.
Wait statistics land in `tp-exchange.json` at the dump.

## Stage 1 results (rank 1, ms per half, median of halves 3–16)

| Arm | Host threads | Half ms | vs one card | Host enqueue ms | Exact vs one card |
|---|---:|---:|---:|---:|---|
| one card (phase 1 / phase 3, each run twice) | 1 | **12.247 / 12.249**; 12.240 / 12.247 | 1.000 | 3.6 | reference; reruns 1079/1079 equal |
| one card on 47:00.0 instead (phase 4, twice, bracketed by 23:00.0 at 12.242 / 12.229) | 1 | 12.260 / 12.261 | 0.999 | 3.5–3.9 | 1079/1079 |
| replicated, two cards | 1 | 12.490 | 0.981 | 9.6 | 1079/1079 |
| replicated, two cards | 2 | 12.438; 12.492 | 0.985; 0.980 | 5.6; 6.3 | 1079/1079 |
| split + slots, **copy** gathers (Oct 25 path) | 1 | 12.640 | 0.969 | 11.5 | 954/954 (+125 masked) |
| split + slots, **direct** | 1 | 13.941 | 0.878 | 12.8 | 954/954 (+125 masked) |
| dense split only, direct | 1 | 12.116 | 1.011 | 10.4 | 1079/1079 |
| slots only, direct | 1 | 11.922 | 1.027 | 10.4 | 954/954 (+125 masked) |
| **split + slots, direct** | **2** | **11.367; 11.382** | **1.077; 1.075** | 6.1; 5.9 | **954/954 (+125 masked)** |
| exchanges only, no split (diagnostic) | 2 | 12.846 | 0.953 | 6.2 | 1079/1079 |

- "Split" = row halves of the 33 rank-1 Q8_0 `attention` (QSA and GDN output projections) and Q6_K `gdn.qkv` sites;
  "slots" = experts by slot position (5/5; `RouteMask` zeroes the peer's slots). 58 exchanges per half.
- The 125 masked buffers (`routes`, `routes.down`, `expsgate`, `expsup`, `expsact` of 25 layers) differ by design: they
  hold the masked routes and the per-slot intermediates of slots the other card computes (same as October 25). Every
  model-state buffer, the expert output, and all 16 tokens are bitwise identical. Card 1 equals card 0 on every other
  buffer (`tp-replicate-compare.json`).
- **In-engine exchange cost:** (12.846 − 12.492) / 58 = **6.1 µs per exchange**, both cards, including the extra launch
  and lockstep skew. Microbenchmark: 1.6–3.3 µs added at 10–40 KB.
- **Host submission:** one thread costs 9.6–12.8 ms per half for two cards, which is the whole budget once the cards
  synchronise on device flags; per-card threads bring it to 5.9–6.3 ms. Why direct + one thread enqueues 2 ms more than
  copy + one thread is not established (the devices wait on each other, so submissions likely hit idle queues).
- **Waits:** 0 timeouts and 0 aborts in 74,476 waiting work-groups over the 13 exchange runs (both cards). Card 0
  polls in 89–99% of its waits, card 1 in 11–74%: card 1 (47:00.0) usually arrives later (with one host thread it
  is always submitted second; with two threads the split is 90% / 68–74%). Card 47 alone is only 0.15% slower than card 23 (12.26 vs 12.24 ms), so the 0.2–0.25 ms that the
  replicated two-card arms lose against one card is a two-card process cost, not card speed.

**Device safety.** Kernel log clean (0 xe/GuC/CAT/reset/fault lines) before every phase and after every arm. Host-side
failures on the way, none on the device:
1. first smoke: engine segfault at load (my bug: control words uploaded before the card's staging slab existed; fixed);
2. two smokes: `std::bad_alloc` at layer 27 of the load, both cards. Cause: the systemd user unit's 1024 open-file
   soft limit (a two-card process holds a descriptor per shared buffer). Fixed with `-p LimitNOFILE=1048576`;
   `EnableDeferBacking=0` alone did not fix it;
3. a timing-only "no exchange" diagnostic stopped at its first half with the engine's sticky error (stale peer rows
   produced invalid routes); replaced by the exact exchange-only diagnostic.

## Stage 2: GDN blocks split by key group (`OWNRT_TP_GDN=heads`)

**Design (as built).** SC117 maps value head h to key h%16 (`adapter.cpp`: `flags|=4` when `packed_heads`). So card c
owns keys [8c, 8c+8) and the 24 value heads {h : h%16 in [8c, 8c+8)} (three runs of 8). Each card is then a GDN with 8 key
and 24 value heads and key = h'%8, and every head's arithmetic is unchanged. Per GDN layer and card:
- **qkv, z, a, b GEMVs:** only that card's rows. The weight is loaded as whole-row runs: qkv as `[q_c; k_c; v_c]`
  (five runs of 1024 rows), z three runs of 1024, a and b three runs of 8. Each output row keeps its kernel and
  arithmetic. This covers the dense-block Q4_K/Q5_K qkv and z sites through a per-card weight slice of whole rows
  (`denseblock::policy(..., tp_rows)`), the p33 Q6_K sites, and the kopt F16 a/b pair.
- **conv:** runs on that card's 5120 channels, with the conv1d rows and conv history in the same order.
- **recurrence (round2 with `OWNRT_GDN_PREP`) and gated norm:** run on the card's 24 heads (`Launch::heads`,
  `key_heads`). State, y and outputs are compact in the full-size buffers.
- **`tp_xheads`:** one direct exchange (strided mode: three runs of 1024 values, 2048 apart) places the gated rows into
  the global gated vector on both cards. The output projection keeps its Stage 1 row split.

Exchanges per half: 25 output projections + 18 gated + 25 expert layers = 68 (Stage 1: 58).

**Kernel parameterization, not forks.** `ng::Shape` gains GDN head geometry: `extra = key heads`, `heads = value heads`;
`extra == 0` means the model's 16/48. The 10240/2048/4096/48/16 constants in `round2_submit.cpp` (recurrence + prep),
`round2.hpp` (`gdn_host`, prep size), and `kernels.hpp` (generic GDN, `groups`, `required_bytes`, gated norm) now
come from that geometry. A split shape is refused on any other GDN or norm implementation.
- **Full-geometry path unchanged:** the one-card Shape and argument bytes are the same. The new binary's one-card dump
  equals the Stage 1 binary's one-card dump: **1079/1079 buffers**, 16 halves (`t5-one` vs `t3-one`), and 2 halves
  (`s8-one` vs `s4-one`).
- **CPU unit test** ([heads_unit_test.cpp](heads_unit_test.cpp), [output](heads_unit_test.out)): the generic kernels
  and `round2::gdn_host`, full geometry vs the two compact halves reassembled, are bitwise equal for conv, history,
  y, state and gated output. A negative control (contiguous value-head halves) differs, as it must.

**Gate.** The dump reassembles the one-card layout of every compact buffer from both cards: qkv, z, a, b, conv,
history, state, y; 144 buffers, each element exactly once (`Engine::head_split_layout`). So the driver's bitwise
compare against the one-card run is unchanged.

**Results** (binary `ed28afad67d8…`, same harness, setup and arms as Stage 1; [results-stage2.json](results-stage2.json)):

| Arm | Half ms (median, halves 3–16) | vs one card | Host enqueue ms | Exact vs one card |
|---|---:|---:|---:|---|
| one card (start / end of phase) | **12.237 / 12.286** | 1.000 / 0.996 | 3.6 / 4.6 | reference; 1079/1079 |
| Stage 1: rows + slots, direct, 2 threads | 11.348 | 1.078 | 6.2 | 954/954 (+125 masked) |
| **Stage 2: + GDN head split** (two runs) | **10.824 / 10.824** | **1.131** | 6.0 / 6.4 | **954/954 (+125 masked)** |
| GDN head split only (nothing else split) | 11.906 | 1.028 | 6.0 | 1079/1079 |

- The 954 compared buffers include all 144 reassembled GDN buffers (state and history included); all 16 tokens equal
  one card. Card 1 equals card 0 on the 935 buffers both cards hold in full, apart from the 125 masked slot
  intermediates.
- Stage 2 takes 0.52 ms off Stage 1 (−4.6%). Host enqueue stays at about 6 ms, below the device time, so the
  devices set the pace.
- 0 timeouts and 0 aborts in 44,556 waiting work-groups over the Stage 2 smoke and timing runs (both cards). Kernel
  log clean before each phase and after every arm.
- Runs: smoke (`s8-one`, `h-smoke`, 2 halves) then timing (`t5-*`). The first device run of the head split was
  exact on its first attempt; no incidents in Stage 2. Run directories (276 files, 1,730,255,644 bytes) moved to
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-28/tp-heads-20261028/` (count and bytes verified).

## Stage 2b: compact expert slots (`OWNRT_TP_EXPERTS=compact`)

**Design.** Instead of masking the peer's slots in a 10-slot launch, card c launches its expert GEMVs on its own slots
c, c+2, … only, as dense 5-slot launches (`Launch::slots`):
- `tp_route_compact` copies those slots' routes into `routes#tp` / `routes.down#tp`. The original routes stay unmasked.
- gate, up, act and down run with count 5. Each slot keeps its kernel, tile and reduction order; only the slot count and
  route list change. The IQ3_XXS block policy admits fewer than ten slots only in this mode.
- The activation and the merged status check cover the card's 5 slots.
- Down writes compact rows to `expsdown#tp`. One strided direct exchange (the `tp_xheads` kernel: runs of 2560 values,
  5120 apart) places them at their canonical slot rows of `expsdown` on both cards before the unchanged combine. This
  replaces the staging copy and the local select of `tp_xslot`.
- The per-slot buffers (gate, up, act and the three statuses; 150 buffers) are compact on each card and reassembled
  in slot order at the dump.
- Exchanges per half: 68 (25 output projections, 18 gated, 25 expert layers). Each now waits in one work-group, so
  1,088 waits per card over 16 halves, against 7,088 with `tp_xslot`.

**Gate.** The two-card dump now equals one card on **all 1,079 buffers with no exclusions** (smoke and all four timing
runs). The 125 masked-intermediate exclusions of Stages 1 and 2 are gone. Card 1 equals card 0 on all 785 buffers both
cards hold in full. The new binary's one-card dump equals the earlier binaries' (1079/1079).

**Results** (binary `d4cc86fdb8e8…`; same harness, setup and arms; four interleaved Stage 2 / Stage 2b pairs;
[results-stage2b.json](results-stage2b.json), [results-stage2b-pairs.json](results-stage2b-pairs.json)):

| Arm | Half ms, median of halves 3–16 (each run) | vs one card | Host enqueue ms | Exact vs one card |
|---|---|---:|---:|---|
| one card (start / end of phase 1) | 12.246 / 12.256 | 1.000 | 3.5–3.9 | reference |
| Stage 2: GDN heads + rows + masked slots | 10.834, 10.838, 10.904, 10.962 | 1.12–1.13 | 6.0–6.8 | 954/954 (+125 excluded) |
| **Stage 2b: compact slots** | **10.735, 10.837, 10.767, 10.747** | **1.13–1.14** | 6.3–7.1 | **1079/1079** |

- Stage 2b is faster in all four pairs, by 0.001–0.215 ms. Mean 10.77 against 10.88 ms: about −1%. The masked
  10-slot launches were already close to 5-slot cost on these kernels; masked work-groups do no weight reads.
- 0 timeouts in 65,680 waits; kernel log clean before each phase and after every arm.
- Incident: the first smoke stopped at load on a host-side policy check: the IQ3_XXS block site required the original
  `routes` input name. Fixed by admitting the compact copy in this mode. No device work had run; kernel log clean.
- Run directories (458 files, 2,804,334,509 bytes) moved to
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-28/tp-compact-20261029/` (count and bytes verified).

## Stage 3 design: QSA split by KV group (not built; for review)

**Split.** Card c owns KV head c and query heads [12c, 12c+12) (query head h reads KV head h/12). Every head's
arithmetic stays local. From the source (`plan.hpp` `qsa()`, generic `kernels.hpp`, `p49_qsa_kernel.hpp`):

| Site (rank 1: 7 layers, 23, 27, …, 47) | Per card | Change |
|---|---|---|
| `qsa.qgate` GEMV (12288 rows, per head 256 q + 256 gate) | rows [6144c, 6144c+6144), **one contiguous run** | Stage 1 row slice, no exchange |
| `qsa.k`, `qsa.v` GEMVs (512 rows) | rows [256c, 256c+256) | row slice |
| `qsa.iq`, `qsa.ik`, `qsa.select`, raw/pooled index | **replicated** (shared selector; the same selected ids on both cards) | none |
| `qsa.prepare` (30 groups per token: 24 q, 2 k, 4 index) | 12 q + 1 k + 4 index groups | head geometry in `ng::Shape` (as for GDN) |
| `qsa.pool` KV append (512 values per token) | 256 per token: **half the KV cache per card** | KV-head count in the shape |
| `qsa.attention` (p49 split32, implementation 12, with `OWNRT_ATTN_HEADS`/`COMBINE2`) | 12 heads over KV head 0 of the compact cache | parameterize 24 heads, the `id*2+h/12` KV stride and the `tokens*24*tiles*258` partials (about 22 literals) |
| `qsa.y` (24 x 256) | compact 12 heads = global [3072c, 3072c+3072), **contiguous** | `tp_xgather` exchange (existing contiguous mode) |
| `attention` output projection | unchanged Stage 1 row split | none |

- **Exchanges:** 3 per QSA layer, as for GDN: y, output projection, experts. One more than today.
- **Gate:** the dump reassembles q, gate, kn, the k/v GEMV outputs and keys/values. keys/values use one run per
  position and card, in the [position][KV head][256] layout. y is global after its exchange. One-card identity is
  required as in Stage 2, with the full-geometry Shape unchanged (heads/extra = 0).
- **CPU unit test:** generic prepare and pool, and the p49 reference (`p49_qsa_reference.hpp`), full vs two halves.
- **Expected value at 4K context:** about 95 µs per layer is splittable: the qgate GEMV (12288 x 2560, 50 µs on the
  Q6_K layers) and attention (about 40 µs; 43.8 µs measured historically). Halving it on 7 layers saves at most about
  0.3 ms; less 7 exchanges (about 0.04 ms) and the attention kernel's fixed costs, about **0.2–0.3 ms (2–3%)**.
  Selection stays replicated and grows with context/4. The larger benefit is capacity: each card keeps half the QSA
  KV cache (`qsa-kv-head-shard-feasibility.txt`: 6 GiB instead of 12 at 262K for the 12 layers).
- **Risks:** p49's variants (`ATTN_HEADS`, `COMBINE2`, guard) all index the 24-head layout. A split shape must be
  refused on any variant that is not parameterized, as `adapter.cpp` does for GDN.

## Four cards, TP2 inside each pipeline stage: host RAM and the rank-0 plan (2026-10-29, steps 1–2)

### Step 1: host RAM

The two-card shadow comes from NEO's deferred backing, and `NEOReadDebugKeys=1 EnableDeferBacking=0` removes it. This
is a per-process placement key, not a host memory setting.

| Measurement | `GPUActive` | `MemAvailable` | Process RSS |
|---|---:|---:|---:|
| `mem_shadow` 4 GiB per card on 23+47, default ([log](logs/host-ram-shadow.log)) | **+8.00 GiB** | −7.72 GiB | — |
| same with `EnableDeferBacking=0` | **+0.00 GiB** | −0.02 GiB | — |
| rank 1 one card, 4K, after load (`t6-one`, 28.5 GiB VRAM) | 11.9 MB | +0.01 GB | 0.26 GB |
| rank 1 TP two cards, 4K, after load (`t6-compact`, 2 × 28.0 GiB VRAM, `EnableDeferBacking=0`) | 15.3 MB | −0.23 GB | 0.27 GB |
| service (two one-card ranks, 64K), after load: rank 0 / rank 1 | 23.8 MB | 105.3 → 76.3 GB | **28.7 GB** / 0.26 GB |

- The DRM fdinfo `drm-resident-gtt` of 29 GB per card in TP runs is import bookkeeping of the peer's VRAM, not host
  pages; `GPUActive` and `MemAvailable` do not move.
- **Projection, rank 0 and rank 1 as two 2-card processes at 64K, with `EnableDeferBacking=0`.** About 29–30 GB of
  host RAM, as today: rank 0's 28.7 GB is its host lookup tables and snapshots, held once per process. That leaves about
  75 GB available after load, against the service's 98.8 GB start floor (checked before load, as today) and 8 GiB
  running floor. **It fits.**
- **Without the key**, each process would also shadow its full VRAM, about 2 × 31.5 GB, so +126 GB in all. It needs about
  156 GB against about 105 GB, **short by about 50 GB**. So `EnableDeferBacking=0` must be in both TP ranks'
  environment and run identity. No memory or swap setting changes.
- **VRAM per card:** TP saves 0.45 GiB per card from the row and head splits (4K: 28.46 → 28.01 GiB). Rank 1 at 64K
  (30.05 GiB today, with the raw ring) also loses its 0.23 GB QSA raw ring under TP (TP excludes the ring today), so
  it nets about −0.2 GiB and still fits. Rank 0 uses 25.0 GiB at 64K and has room.

### Step 2: rank-0 TP plan

**What splits** (rank 0: layers 0–22, 17 GDN and 6 QSA, plus embedding/PLE lookups and the MTP draft):
- **Layers:** exactly as Stages 1–2b, unchanged code. GDN by key group, output projections by rows, experts as compact
  slots, with the direct exchange and per-card submission threads. PLE, HC and the rest are replicated.
- **Lookups:** replicated. `prepare_token` must upload the token's embedding/PLE rows to both cards; today it writes
  card 0 only.
- **MTP draft (1.73 ms):** first on card 0 only, with card 1 idle. Later, split the draft head's vocabulary rows: each
  card does an argmax over its rows, then one exchange of (value, index) with the lowest-index tie rule. Exact.
- **Prefill:** one-card arithmetic on card 0. The state then moves to card 1 by exact run copies: replicated buffers
  whole, head-split GDN state, history and KV in the `head_split_layout` order. The reverse direction is needed
  before a new prompt follows decode. TP decode kernels are decode-only today.

**What must become per card** (all one-card today; `rank.hpp` and `strict_snapshot.hpp` have about 40 `dev(0)` /
`buffers[0]` sites):
1. admission: `--tp-replicate` is refused on rank 0 (`main.cpp`);
2. the miss banks (`banks()`: alternate GDN/conv state per card, swapped on both cards);
3. `SpeculativeImage`: snapshot and restore on both cards, static host tables per card;
4. **cancellation:** a speculative miss cancels a half at a launch boundary. Both cards must stop at the same site,
   or the exchange epochs drift and later waits time out. The card-1 thread would issue only up to a release index
   that the half's thread publishes after each layer's cancel check; on cancel, both stop at that layer, then both roll
   back.
5. sessions and checkpoints stay refused under TP (as now).

**Estimate.**
- Rank 1 saved 59 µs per layer (12.25 → 10.77 ms over 25 layers, two-card costs included).
- Rank 0's 23 layers give about 10.67 → **9.3–9.6 ms per half**. With the 1.73 ms draft on card 0, stage 0 is about
  11.0–11.3 ms against stage 1's 10.8 ms.
- **Pipeline period:** about 11.0–11.3 ms against today's 12.4–12.5 ms, **about 1.10–1.13× decode**.
- With the draft head split by vocabulary, about 0.4–0.6 ms less on stage 0 brings both stages near 10.8 ms: about
  **1.15×**. Moving the split point is a further lever.
- These are projections from the rank-1 measurement, not measurements.

**Size of step 3.** Of the five items, the cancellation handshake, the per-card speculative image and the prefill state
transfer are the risky parts. Each is bitwise-gated by the rank-0 harness (`research/rank0-gdn-c43/tp_rank0_driver.py`,
which runs non-speculative halves). Speculative rollback also needs a harness mode with forced misses, so that
cancellation and restore are exercised.

## Rank-0 TP, step 1: speculative halves on two cards (2026-10-29)

Built (binary `edacb87846a8…`; Stage 2b layout on rank 0: GDN heads, rows, compact slots, direct exchange, two
submission threads; the MTP draft on card 0):
- **Admission** of `--tp-replicate` on rank 0.
- **Recurrent banks per card.** `banks()`, `swap_state_banks` and `rotate_spare_bank` move both cards' banks together;
  outputs bind each card's own spare.
- **Speculative image per card.** The card-0 image keeps the host state, bank rotation and protocol. It forwards device
  capture, restore and redo to a card-1 image, which has its own backup and static copy table.
  - `RedoBankProof` counts only its card's writer and the compact head extent.
  - The exchange control words are excluded: their epochs advance identically on both cards.
- **Cancellation handshake.** A cancel is taken only before a card-0 launch. The card-1 thread issues only below the
  last index whose cancel check passed. On a cancel at index k, both cards stop below k, so every (card 0, card 1)
  exchange pair runs on both cards or on neither.
- **Fixes on the way:**
  - Under TP the draft's GPU time is not measured. The shared-context queues have no profiling, and the first TP smoke
    stopped at the first draft with "profiling disabled".
  - Reset fills and snapshot copies record their card's tail.
- **Harness:** [tp_rank0_driver.py](tp_rank0_driver.py), a copy of the rank-0 lab harness with `--tp` and forced
  speculation patterns:
  - `h`: hit;
  - `m`: completed miss, rolled back and redone;
  - `c`: miss published before the half, so it cancels at its first launch;
  - `x`: miss published by a timer 1–8 ms into the half, so it cancels mid-half or completes.
  - Device builds refuse `--cancel-launch`.

**Gates** (context 4096, decode from position 0; [evidence/rank0/](evidence/rank0/), [logs/](logs/)):

| TP run | Pattern | Events | vs one card, same pattern | vs one card, no speculation |
|---|---|---|---|---|
| `r0s3-tp`, 3 halves | n | — | 1029/1029 target, 71/71 draft, tokens equal | (same run) |
| `r0m-tp`, 8 halves | hmcn | 1 hit, 2 misses, 3 cancelled at first launch, 5 redos | 1029/1029, 71/71, tokens equal | 1029/1029, 71/71, tokens equal |
| `r0x-tp`, 10 halves | x | 8 cancelled mid-half, 2 completed misses, 10 redos | 1029/1029, 71/71, tokens equal | 1029/1029, 71/71, tokens equal |

- Card 1 equals card 0 on all 710 buffers both cards hold in full. 0 exchange timeouts. Kernel log clean after every arm.
- **Speed (not yet the measurement of step 3)**, median of 3–10 halves from position 0:
  - rank-0 half: 9.24–9.42 ms on two cards against 10.47–10.48 ms on one card;
  - draft: 1.31 ms against 1.71 ms. The one-card process runs profiling queues, as the service's rank 0 does; the TP
    process cannot.
- Incidents: none on the device. Host-side refusals on the way:
  - the harness drafted at position 0;
  - draft GPU timing was requested without profiling queues;
  - `--cancel-launch` is refused in device builds.

## Remaining stages

- **Stage 3 (QSA two-KV-group split):** designed above, not built.

## Next

1. **Stage 3:** QSA two-KV-group split (7 rank-1 layers); designed above, not built.
2. Shared expert on one card with an uneven routed split (6/4), now that compact slots exist.

## Files

- Stage 2b source: `packet6-kopt/kernels.{hpp,cpp}` (`RouteCompact`), `api.hpp` (`Launch::slots`), `main.cpp` (slot
  count, per-slot sizes, `tp_route_compact`), `expert-iq3xxs-block/.../block.hpp` and `policy.hpp` (compact admission),
  `rank.hpp` (`OWNRT_TP_EXPERTS=compact` plan and layouts).
- Stage 2 source: `kernels.hpp`, `round2.hpp`, `round2_submit.cpp`, `adapter.cpp` (head geometry), `packet3/kernels/api.hpp`
  (`Launch::row_runs`, `heads`, `key_heads`), `main.cpp` (`tp_runs` loaders, `tp_xheads`, `head_split_layout`),
  `generic_engine.hpp` (run-aware GSQ loads, dense-block rows), `dense-packed-block/.../block.hpp` and
  `dense-q6-p33/.../policy.hpp` (TP row counts), `rank.hpp` (`OWNRT_TP_GDN=heads` plan, dump reassembly), exchange
  strided mode in `owner_api.hpp`/`owner.cpp`/`single_device.cpp`.
- Source: [owner_api.hpp](../../../engine/src/stage2/packet194-expert-diet-engine/owner_api.hpp) (`exchange_layout`,
  `Backend::Exchange`, `Device::ExchangeSpec`), [owner.cpp](../../../engine/src/stage2/packet194-expert-diet-engine/owner.cpp)
  (`Device::exchange`), [single_device.cpp](../../../engine/src/stage2/packet194-expert-diet-engine/single_device.cpp)
  (kernel), `gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp` (`tp_xgather`/`tp_xslot` sites, control
  words, drain guard, profiling guard), `gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp` (plan, `TpWorker`,
  `tp-exchange.json`).
- Evidence: [results-stage1.json](results-stage1.json) (phase 1), [results-stage1-timing3.json](results-stage1-timing3.json)
  (phase 3), [results-card47.json](results-card47.json) (phase 4, one card on each card), [logs/](logs/) (phase logs and kernel-log checks), [analyze.py](analyze.py) (tables and comparisons).
  Run directories (state dumps, 833 files, 4,950,606,710 bytes) were moved on 2026-10-28 23:10 to
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-28/tp-direct-20261028/runs/` (count and bytes verified) to free
  host RAM for the four-card screen.
- The live service receipt `57744505eabc` already did not match `engine/src` before this work (16 sources differ);
  the service unit was not touched.
