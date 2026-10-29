# Exact two-card TP with a kernel-direct exchange (2026-10-28)

**Question.** The October 25 exact TP broke even because each copy gather cost 13–26 µs. Now that a producer kernel can
store straight into the peer card's memory and raise one flag ([p2p/direct-store-2026-10-28](../../p2p/direct-store-2026-10-28/RESULT.md)),
does exact within-layer splitting pay off inside the engine?

**Answer so far: yes.** With the GDN blocks also split by key group (Stage 2), rank 1 runs **10.82 ms per decode half
on two cards against 12.24–12.29 ms on one card (1.131×)**, bitwise exact. Stage 1 alone gave 11.35–11.38 ms (1.075–1.078×).
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

## Remaining stages

- **Stage 3 (QSA two-KV-group split):** not started.

## Next

1. **Follow-up: compact 5-slot expert launches** instead of masked 10-slot ones. Masked slots are not free: about 47%
   of an expert launch does not shrink (SIZING.md). The `tp_xslot` exchange would scatter the compact slots directly,
   like `tp_xheads`. This is the largest remaining split inefficiency.
2. **Stage 3:** QSA two-KV-group split (7 rank-1 layers).
3. Shared expert on one card with an uneven routed split (6/4), once compact slots exist.

## Files

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
