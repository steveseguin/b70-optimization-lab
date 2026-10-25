# Exact multi-card execution for SC117: measurements and design (2026-10-24)

Owner direction (2026-10-24): four GPUs in this host now, six later, eight possible. Keep the current model. Quality
must be lossless whatever the optimization, the goal is maximum speed, and the engine must grow toward any TP
(1/2/4/6/8).

## Measured cross-card cost (cards 23:00.0 → 47:00.0, our microbenchmark [p2p/p2p.cpp](p2p/p2p.cpp))

Each figure is the median of 400 host-waited operations. Peer access is available in both directions.

| Size | Peer copy | Host-staged (device → pinned → device) | Two waited empty kernels (sync floor) |
|---:|---:|---:|---:|
| 4 KB | 8.7 µs | 9.3 µs | 12.9 µs |
| 40 KB (one token's 4 F32 HC streams) | 12.7 µs | 11.3 µs | 10.8 µs |
| 160 KB | 15.1 µs | 25.3 µs | 10.8 µs |
| 640 KB | 36.9 µs | 58.4 µs | 10.7 µs |

A hand-off of one token's activations costs about 10–13 µs, mostly synchronization. Larger transfers favour the peer
copy.

## What can be exact

Exact means each output keeps its single-card arithmetic.
- **Allowed.**
  - **Row splits.** Each card computes whole output rows of a matrix (its own rows, unchanged lane order and tree),
    then the outputs are copied exactly.
  - **Expert placement.** Each card holds and computes whole experts. Their outputs are combined on one card in the
    original slot order, with the original epilogue.
  - **Pipeline stages.** Each card runs whole layers, as today.
- **Not allowed.** Splitting K across cards, because adding partial sums changes the summation order.
  - Any all-reduce of partial results.
  - Any reordering of the expert combine.

## Options for four cards

1. **Pipeline, 4 × 12 layers.** Easiest: generalise today's 2-rank split and controller to N ranks.
   - Prompt reading gains, because batched chunks overlap across stages (up to about 2× over two stages).
   - Single-user decode gains little: one token still crosses all 48 layers, plus 2 more hand-offs (about 25 µs). Only
     deeper speculation could use the extra stages, and depth-2 lost before (packet71c).
2. **Exact expert placement plus row splits ("TP4-exact").** Every card holds 1/4 of each layer's experts (whole
   experts) and 1/4 of the rows of the large dense matrices.
   - Per layer: compute the router on all cards (replicated, identical); each card computes the selected experts it
     holds; gather the expert rows onto every card (or one owner) for the fixed-order combine.
   - Large dense projections (GDN qkv/z, QSA, attention output, shared expert) are split by rows and all-gathered.
   - Small ops are replicated.
   - Estimate:
     - Per-token GPU time is about 46 ms of kernel work across today's two cards, so ideally about 1/4 of the weight
       work per card.
     - Sync cost is about 3–4 gathers per layer × 48 layers × about 12 µs ≈ 2 ms per token.
     - Experts are not uniform per token: the 10 selected may sit unevenly across cards (up to 10 on one). Balance is
       expected, not guaranteed, so the gain is bounded by the busiest card. That needs a route-statistics measurement
       on real prompts.
   - This is the lever with the largest decode gain. It needs:
     - a multi-card plan builder;
     - per-card weight placement;
     - device-side peer copies;
     - one controller.
3. **Hybrid (two pipeline stages × two-way exact split).** Keeps today's two-stage MTP speculation and halves each
   stage's work.

## Prerequisites before building

- **Route statistics.** Measure how the 10 selected experts per token would spread over 4 cards under a static
  placement (by expert id and by measured frequency) on the 12-prompt suite. The busiest card sets the step time.
- **Device-side synchronization.** Use cross-queue event dependencies (no host wait) between cards. If they are
  cheaper than the host-waited 10–13 µs above, the sync budget shrinks.
- **The owner's decision on cards 27:00.0 and 43:00.0**, which currently hold the protected vision server.

## Route statistics (measured 2026-10-24)

Source: the CPU reference's per-layer top-10 selections on four suite texts (prompt plus 512 output tokens each, about
100,000 layer-token decisions). Tool: [route-stats/route-stats.cpp](route-stats/route-stats.cpp).

**Static placement, one copy per expert.** Mean experts on the busiest card per (layer, token); ideal is 10/N.

| Cards | Ideal | By id | Contiguous | Frequency-balanced (held-out prompt) | Expert speed-up vs 1 card |
|---:|---:|---:|---:|---:|---:|
| 2 | 5.00 | 6.23 | 6.24 | 6.20 | 1.6× |
| 4 | 2.50 | 4.18 | 4.19 | 4.13 | 2.4× |
| 6 | 1.67 | 3.44 | 3.42 | 3.36 | 3.0× |
| 8 | 1.25 | 3.00 | 3.02 | 2.93 | 3.4× |

**With replicas.** Each expert is held on two cards (or all cards), and each token uses the least-loaded holder. The
experts are still computed whole, so this stays exact.

| Cards | 1 copy | 2 copies | every card |
|---:|---:|---:|---:|
| 4 | 4.19 | 3.37 | 3.00 |
| 6 | 3.44 | 2.68 | 2.00 |
| 8 | 3.00 | 2.32 | 2.00 |

Placement policy hardly matters. Replicas help; four cards have room for two copies of every expert.

## Honest estimate for TP4-exact decode

Today's per-token GPU work is roughly:
- 35% dense projections, which split by rows (÷4);
- 30% experts (÷3 with two copies);
- 30% small ops and launches, which are replicated on every card and do not shrink;
- 5% other.

Adding about 2 ms of syncs gives roughly 0.55× of today's per-token GPU time. It also loses today's two-stage MTP
overlap. Expected: about 1.5–1.8× decode. The replicated small ops cap it, so fusing small ops (fewer, cheaper
launches) is worth doing first: it helps every configuration and raises this ceiling.

## Device-side hand-off cost (measured 2026-10-25)

Tool: [p2p/p2p_events.cpp](p2p/p2p_events.cpp). Setup: cards 23:00.0 and 47:00.0 in one SYCL context, one in-order
queue each, 200 round trips. Each round trip is a kernel on A, a peer copy to B, a kernel on B, and a peer copy back.

| Block | Device-event chain (no host wait) | Host wait after every copy | Two kernels on one card |
|---:|---:|---:|---:|
| 4 KB | 24.7 µs | 44.7 µs | 7.6 µs |
| 40 KB | **20.0 µs** | 39.9 µs | 5.6 µs |
| 160 KB | 25.7 µs | 45.9 µs | 5.5 µs |

With device-side dependencies, a one-way cross-card hand-off costs about **7 µs** (host-waited: about 17 µs).

For an exact two-way split of one pipeline stage:
- syncs: about 8–10 all-gathers per layer, each about 7 µs, so about 1.5 ms per stage per token (host-staged: about
  3.9 ms);
- stage time: about 5 ms of matrix work (half of today's) + 4.6 ms of replicated small ops + 1.5 ms of syncs, plus the
  1.45 ms draft on stage 0;
- that is about 11–12.6 ms against 17.4 ms today, about **1.35–1.4×**, misses included (a miss redoes the shorter
  stage 0).

Feasibility blockers to solve before building:
- **Device-side events need one process driving both cards of a stage.** On this host every GPU buffer in a multi-B70
  process also costs its size in host RAM. Two two-card processes at about 26 GB per card would need about 100 GB of
  the host's roughly 107 GB, next to the vision server. Options:
  - Level Zero IPC memory and events between single-card processes;
  - a check whether the shadow applies to device-local USM in a shared context. It was observed with the older
    multi-card engine path.
- The engine's plan and launch machinery is one card per process. A stage split needs:
  - row-range GEMVs;
  - row-half weight loading;
  - a gather op;
  - GDN split by heads;
  - expert placement with a fixed-order gather before the combine;
  - a four-rank controller, with prefill and MTP draft placement.

## Host-RAM shadow of multi-card contexts (measured 2026-10-25)

Tool: [p2p/mem_shadow.cpp](p2p/mem_shadow.cpp). It allocates and fills 4 GiB per card and reads `/proc/meminfo`.

| Context | `GPUActive` | `MemAvailable` |
|---|---:|---:|
| One card | +0.00 GiB | −0.01 GiB |
| Two cards (one SYCL context) | **+8.00 GiB** | −8.75 GiB |

`NEOReadDebugKeys=1` with any of `EnableMultiStorageResources=0`, `UseKmdMigration=0` or
`OverrideMultiStoragePlacement=0` leaves the shadow unchanged. Peer copies still work with the first one. The cost
appears to come from the kernel driver's placement for multi-device buffers.

Consequence for TP2×PP2 on four cards:
- each two-card stage process holds about a quarter of the model per card (about 13–15 GB);
- so each process shadows about 28 GB of host RAM, about 56 GB for both, out of about 101 GB available.

That fits, but it is a real cost; record it in `CURRENT.md` if deployed. The alternative is single-card processes with
Level Zero IPC memory and events, at higher engineering cost.

## Implementation plan (engine), 2026-10-25

**Approach: plan rewriting, not new executors.** The engine already keeps per-card buffers, weights and devices
(`buffers[c]`, `weights[c]`, `dev(c)`), and a launch carries `l.card`. For a TP2 stage, the plan is rewritten:
- **Split matrix launches.** Each large dense GEMV becomes two launches, card 0 on rows [0, n/2) and card 1 on
  [n/2, n), each with its own row-sliced weight. GGUF rows are contiguous, so a slice is an offset and a row count.
- **Routed experts.** Each card holds experts with `id % 2 == c`. Its routed launch computes only the slots whose expert
  it holds and leaves the other slots for the peer.
- **Gathers.** A new `gather` op peer-copies the peer's half (or its expert slots) into the local full buffer, waiting
  on the producer's device event.
- **Replicated launches.** Every other launch is duplicated for card 0 and card 1, each on its own full buffers. That
  covers norms, HC glue, GDN (first replicated, later split by heads), QSA, route, combine and status checks; the same
  arithmetic runs on both cards.
- **Exactness.** Every output row and every expert output is computed whole by one card, and copies are bitwise. The
  F32 oracle comparison and the prefill gate apply unchanged (the state is compared on card 0 plus the gathered
  buffers).

**Development steps.** Each is verified on today's two cards as TP2×PP1 (one stage holding all 48 layers, about 26 GB
per card, about 52 GB of host shadow), against the F32 oracle:
1. one process driving two cards in rank mode, everything replicated (no split): it must reproduce the oracle;
2. dense GEMV row splits plus gathers;
3. expert placement plus the slot gather;
4. GDN split by heads (optional);
5. the controller and adapter for TP2×PP2, plus prefill and MTP draft placement. Deployment needs cards 27/43.

Expected per stage (rank 0's 23 layers today):
- matrix 10.1 → about 5.6 ms (experts unbalanced: the busiest card holds about 6.2 of the 10 selected);
- small ops 3.9 ms (replicated);
- gathers about 1.45 ms (about 9 per layer at about 7 µs).

That is about 11 ms, or 12.4 ms with stage 0's draft, against 17.4 ms: about 1.4×, i.e. about 66 tok/s on the suite.

## Code map for TP2 in one rank process (survey, 2026-10-25)

What already carries a card index: plan buffers and launches (`l.card`), `buffers[c]`, `weights[c]`, `owned_bytes[c]`,
and the weight loader (`gsq_load` → `upload(c, …)`).

What is hard-wired to one card:
- **Device layer.** `SyclDevice` (`stage2/packet194-expert-diet-engine/single_device.cpp:41-63`) makes its own
  zeContext and one in-order queue per card.
  - `Arena::row` rejects foreign allocation ids (`owner.cpp:283-287`).
  - Cross-queue dependencies are rejected (`assert_local_dependencies`, `Device::issue`).
  - `dev(c)` throws for c≠0 (main.cpp:1030).
  - So gathers need a shared context. `stage2/packet14-tp2/backend.hpp` has one (two queues, peer-access check,
    `peer_from`), but it has no prepared or ordered submission.
- **Engine.**
  - One `tail`/`drain()` (main.cpp:857-921), plus a drain on every card switch (:1824, :1840).
  - Banks and `state_spares` on card 0 (main.cpp:1231-1260, 1642; rank.hpp:73-95).
  - Card 0 is assumed by: rank I/O (`put(0,"token"/"streams")`, `integer(0,…)`), cancel observers, `strict_snapshot`,
    `prefill_engine`, `state_dump`, census, and the draft (`mtp.hpp` shares `weights[0]["output.weight"]`).
- **Admission.**
  - Hard limits: `a.cards==1` (main.cpp:304), `pipeline::split` forces card 0, `prefill_allocate` needs one card.
  - Exact site-count admits (IQ3 34, dense block 116, Q6 19, attention 48, QKV 22) and exact storage sizes
    (`generic_engine.hpp:113-117`).
  - Tensor-owner uniqueness (`write_plan` :1904).
  - 30 GiB caps in four places.
- **Python.** `adapter6.py` and the packet195 pipeline pass `--cards 1 --card 0`, set the per-rank
  `ZE_AFFINITY_MASK`/`FilterBdfPath`, and gate memory per rank (`memory_gate.py` split 0/23/24, 30 GiB).

Build order:
1. Device layer: a shared context, a queue per card, cross-card event dependencies and a prepared peer copy.
   Microbench against `p2p/p2p_events.cpp` (about 7 µs per device-side hand-off).
2. Rank 1 on `--mini` with every launch replicated on two cards. The gate is card 0 equal to card 1, and both equal to
   the one-card run.
3. Row splits plus gathers (a half-size output and a gather into the full buffer); slice-aware storage checks.
4. Expert placement by id parity, plus the slot and status gather.
5. Rank 0 (banks, snapshots and lookups per card), the draft head (keep a full copy on card 0), and the Python
   per-rank `--cards`.

## Step 1 result: engine peer copy (2026-10-25)

Built:
- `make_sycl_device_group` (one shared Level Zero context, one in-order queue per card, peer access checked);
- `Device::peer_copy(source, …)`, which runs after all work submitted to the source card;
- `Device::peer_wait(peer)`, a marker after the peer's latest work, which protects a buffer the peer still reads.

Both have prepared (captured) forms. Test: [p2p/owner_peer.cpp](p2p/owner_peer.cpp), cards 23:00.0 and 47:00.0.

| Bytes | Copy + wait round trip | Copies only | Host-waited round trip |
|---:|---:|---:|---:|
| 10,240 | 26.7 µs (enqueue 27.8) | 13.3 µs (enqueue 13.2) | 20.9 µs |
| 40,960 | 30.8 µs (enqueue 29.4) | 16.3 µs (enqueue 13.5) | 28.2 µs |
| 163,840 | 29.1 µs (enqueue 29.7) | 22.6 µs (enqueue 13.5) | 34.2 µs |

All bytes are bitwise-equal after 800 hops.

- **The limit is host submission, not the GPU.** Each SYCL submit with a cross-queue dependency costs about 6.7 µs on
  the host, and the enqueue time equals the total.
- **Consequence for TP in one process.** One host thread would submit for both cards. That is about twice today's ~758
  launches per half: rank 0's enqueue loop is already 3.7 ms per half, and gathers come on top. Single-threaded
  submission would make the host the bottleneck before the GPUs.
- **TP therefore needs** one submission thread per card, or replayed command lists (XPU graph capture works on the
  B70), before the row-split work pays off.
- **Next:** measure the prepared (captured) issue path per card from two threads, and check that cross-card event
  dependencies stay correct between threads.
