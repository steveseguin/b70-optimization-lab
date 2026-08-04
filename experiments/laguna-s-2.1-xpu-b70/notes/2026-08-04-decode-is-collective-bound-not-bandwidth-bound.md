# Decode is collective-bound, not bandwidth-bound

Date: 2026-08-04 America/Toronto

Status: **measured. Four-rank kernel trace of 15 decode steps at 32,640 tokens,
q12, cold cache, util 0.80. Overturns the bandwidth-roofline framing in every
prior note in this campaign.**

## Result

Device-time breakdown per rank, 15 decode steps:

| rank | collective | attention | gemm | other | total device |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 193.1 ms (78.1%) | 39.0 | 11.0 | 4.0 | 247.2 |
| **1** | **34.4 ms (36.9%)** | 43.2 | 11.3 | 4.4 | **93.2** |
| 2 | 209.9 ms (79.4%) | 39.4 | 11.0 | 4.2 | 264.5 |
| 3 | 198.1 ms (78.6%) | 38.8 | 11.0 | 4.2 | 252.1 |

The single largest kernel on three of four ranks is `oneccl_allgatherv_pcie`,
at **72.8% of all device time on rank 0**.

## The collectives are mostly waiting, not transferring

Every rank issues the identical **1,470** `allgatherv` calls. The per-call mean
is not identical:

```
rank 1:   20.0 us   <- the straggler; this is the real transfer cost
rank 0:  122.4 us
rank 2:  ~125 us
rank 3:  ~118 us
```

Same call count, same bytes, 6x the duration. The extra ~100 us per call on
ranks 0/2/3 is **idle time inside the collective, waiting for rank 1 to
arrive**. Actual transfer is roughly `20 us x 1470 = 29.5 ms` per rank across
the 15 steps; the remaining ~165 ms is pure synchronisation loss.

## Why this overturns the roofline framing

Prior notes modelled decode as memory-bandwidth-bound and argued about how many
distinct experts a step touches -- 97 in the original estimate, ~27 after the
timing back-solve. **Both were answering the wrong question.**

The MoE and linear GEMM work is `gemm_kernel` at **11.0 ms across 15 steps**,
about **4.4%** of device time. Expert-weight streaming is not the constraint.
Attention is ~39-43 ms (~15%). Even on rank 1 -- the rank that waits least and
therefore sets the critical path -- total device work is 93.2 ms over 15 steps,
i.e. **6.2 ms per step against a measured step of ~26.5 ms**.

So roughly **77% of a decode step is not device compute at all.** The bandwidth
utilisation figures in
[`2026-08-04-speculation-is-required-not-wasteful.md`](2026-08-04-speculation-is-required-not-wasteful.md)
(1.3 TB/s of 2.12 TB/s, "61% of peak") were computed from assumed bytes-per-step
rather than measured kernel time, and do not survive this trace. The ~147 tok/s
ceiling derived in
[`2026-08-04-routing-is-correlated-ceiling-is-higher.md`](2026-08-04-routing-is-correlated-ceiling-is-higher.md)
rests on the same assumption and should be treated as unfounded rather than
merely uncertain -- the binding constraint is elsewhere.

What survives untouched: every measured throughput number, and the finding that
speculation is required rather than wasteful (M=1 measures 0.34x). That one is
now better explained -- more rows per step amortise a fixed per-step collective
and synchronisation cost.

## Why rank 1 is the straggler

Not yet established. Its attention is only ~4 ms heavier than the other ranks,
which does not account for ~165 ms of waiting elsewhere. The most likely
explanation is host-side work that a device-time view cannot see: sampling,
scheduling, drafter bookkeeping, or Python on the critical path, with the other
three ranks parked in the collective while rank 1 is off-device. Confirming this
needs the host-side (`cpu_op` / `user_annotation`) spans from the same traces,
which are present and unexamined.

## Levers, in evidence order

1. **Close the imbalance.** ~165 ms of the ~250 ms device time on three of four
   ranks is idle wait, about **11 ms per step**. This is the largest single
   quantity in the trace and it buys nothing.
2. **Overlap collectives with compute.** Even perfectly balanced, the ~20 us x
   1470 transfer is serialised against compute today.
3. **Try other `--all2all-backend` values.** Currently `allgather_reducescatter`
   over PCIe with no XeLink; `oneccl_allgatherv_pcie` is 72.8% of rank-0 device
   time, so the backend choice is worth a sweep on its own.
4. **Cut collective count.** 1,470 allgatherv over 15 steps is 98 per step
   across 48 layers, roughly two per layer.
5. **Revisit disabling expert parallelism.** It TP-shards experts and trades
   all2all for all-reduce. It previously failed a contract check, but that was
   rejected on the assumption that EP was free; this trace says it is not.

Deliberately *not* on this list: expert-gather coalescing and INT4 dequant
tuning. At 4.4% of device time they cannot deliver a meaningful speedup, and the
campaign was about to spend its next effort there.

## How the trace was obtained

Eleven launches were needed; ten failed on environmental defaults rather than
anything about the model. The blocker that mattered was XPU allocator
fragmentation -- init refused 192 MiB, then 96 MiB, both with an identical
13.22 GiB free, while a direct probe showed all four cards allocating 28x1 GiB
chunks when idle. `PYTORCH_ALLOC_CONF=expandable_segments:True` cleared it, and
`profile_run` then reported 2.92 GiB of KV cache against the reference run's
2.89 GiB. See
[`2026-08-04-long-context-run-recipe.md`](2026-08-04-long-context-run-recipe.md).

## Boundaries

Cold cache, TP4, util 0.80, q12, depth 11, no quantisation change, no caching or
speculation setting used to inflate any number. Profiling adds overhead, so the
**relative** breakdown is the result here, not an absolute step time; the
absolute per-step figures used above come from the separately measured 26.5 ms
step. The protected `125.4619731637751 tok/s` conventional short-decode record
is untouched.
