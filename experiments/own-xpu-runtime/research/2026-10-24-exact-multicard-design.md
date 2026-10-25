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
