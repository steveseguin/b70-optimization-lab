# Exact tensor parallelism on two B70 cards: closeout (2026-10-25)

<!-- campaign-closeout -->

## Question and identity

The question: can exact tensor parallelism (TP) speed up SC117 decode on B70 cards? Exact means no output is a sum
split across cards, so each card computes whole rows or whole expert slots, and copies are bitwise.

The test setup:
- Model: SC117 Qwen3.8 Flash-Next IQ3_S, F32 exact mode.
- Workload: rank 1 of the service split (layers 23–47), run alone on cards 23:00.0 and 47:00.0 through
  [engine/tools/tp_rank1_driver.py](../../engine/tools/tp_rank1_driver.py), 16 decode halves on deterministic inputs.
- Engines: pf83–pf91.

## Outcome: closed. Exact and working, but no faster than one card.

| Rank 1 half-step (median, 16 steps) | ms | Exact against one card |
|---|---:|---|
| one card | 16.73 | — |
| two cards, everything replicated | 17.08 | yes, all 1,079 buffers |
| plus attention/qkv row split and gathers | 17.04 | yes |
| experts by id parity, pull gather | 17.25 | yes, 954 model-state buffers |
| experts by id parity, push/wait/select gather | 17.02 | yes |
| experts by slot position (every card holds every expert, 5/5 balance) | **16.72** | yes |

## What worked

- **Device layer.** `make_sycl_device_group`, `Device::peer_copy`, `peer_push` and `peer_wait` are exact, also in
  captured (prepared) form.
- **Engine.** `--tp-replicate` with `OWNRT_TP_SPLIT` and `OWNRT_TP_EXPERTS` builds the TP plan from the one-card rank
  plan. All of it is gated by bitwise card-against-card and card-against-one-card comparisons.
- **Single host thread.** One thread submits both cards with only 2% overhead, so per-card threads were not needed.

## What failed, and why

- **Gathers cost what splits save.** Exactness forbids splitting a sum, so every split matrix needs a gather. On B70 a
  gather costs about 13 µs per dense site and about 26 µs per expert layer (push, two waits, select), the same order
  as the work it splits.
- **Expert splits are uneven by id.** About 6 of 10 slots land on the busier card. Balancing by slot recovers that,
  but only reaches break-even.
- **Profiling fault.** A device-profiled TP run faulted both copy engines
  ([incident](incident-2026-10-25/)). That combination is now refused.

## Consequence for four cards

TP2×PP2 would give each pipeline stage roughly one card's speed, so four cards would bring about 1.0–1.1× for one
conversation, not 1.4×. Other uses of four cards:
- PP4 with deeper speculation, which needs guesses 2–3 positions ahead;
- two PP2 replicas, which doubles throughput for two users at once.

## Evidence and patches

- Measurements and design: [../2026-10-24-exact-multicard-design.md](../2026-10-24-exact-multicard-design.md).
- Results: [evidence/](evidence/).
- Code: owner layer (`stage2/packet194-expert-diet-engine/owner*.{hpp,cpp}`, `single_device.cpp`), engine
  (`main.cpp`, `generic_engine.hpp`, `rank.hpp`), kernels (`packet6-kopt/kernels.cpp`: `RouteMask`, `SlotSelect`).

## When to revisit

- A gather that costs well under 5 µs: the producing kernel writes straight into the peer's memory and signals one
  flag, or the hardware supports collectives.
- A model whose layers are dominated by a few very large GEMVs.
- More than two cards per stage with cheap gathers.
