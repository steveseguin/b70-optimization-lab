# Laguna draft graph capture — root cause found, route still closed

Date: 2026-07-28 America/Toronto

Status: **rejected, but now understood.** `VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH=1`
remains default-off and is again refused by the DFlash FP8 contract. The
refusal now rests on measurement rather than on the fact that the combination
had never been tried.

## Why this was worth chasing

The drafter runs eager at roughly **9.0 ms of a ~30.5 ms decode cycle** while
accounting for about **3% of the cycle's weight traffic**; its streaming floor
is near 1 ms. It is the most disproportionate single item in the decode path,
and the only lever measured this campaign with double-digit upside rather than
the ±2% every other axis has offered.

## The false wins, explained

Two earlier runs reported enormous throughput and were rejected on exactness:

| run | tok/s | exact | acceptance |
| --- | ---: | ---: | --- |
| 2026-07-26 draft capture | 198.702807 | 0/13 | 95.91%, nearly flat |
| this session, first attempt | 537.388545 | 0/13 | 100.0%, flat |
| this session, after drift fix | 550.903357 | 0/13 | 100.0%, flat |

All three have one cause. The drafter's graph is captured during a warmup that
enters the forward context with `attn_metadata=None`, so it records a graph
that never saw the attention tensors it is replayed against. Replay reads
capture-time memory and emits **token id 0** for every request; the target
consumes those zeros and echoes them; the verifier then compares zeros against
zeros and accepts everything.

**A flat per-position acceptance curve is the reliable tell.** Real acceptance
decays with depth. A curve that does not decay means the verifier stopped
checking, whatever the rate says.

## How it was established

A probe logging the drafted ids, the sampled ids, and both storage pointers
showed row 0 exact for 47 tokens — while capture was still executing real ops —
and every later row diverging at index 0 with `actual: 0`. Turning on
`enforce_static_inputs` for the drafter's wrapper converted the silent
corruption into a raised error on all four ranks. Printing both sides of the
signature comparison showed every drifted path reading `captured=None`: the
tensors were not at different addresses, they were absent at capture entirely.

## What was fixed, and what still blocks it

Fixed, and kept:

- the drafter's outer attention tensors (`block_table`, `query_start_loc`,
  `seq_lens`, `slot_mapping`) copy into buffers allocated once at their worst
  case, so a longer prefill or an extra block cannot move an address;
- the block table is handed over at full capacity, because it must keep a
  constant shape and not merely a constant address; the kernel bounds its reads
  by `seqused_k`;
- the warmup is given metadata shaped like the real decode, so capture and
  replay agree on identity. **Drift went from 9 reports to 0.**

Still blocking:

The FlashAttention launch configuration is derived at capture time from
`max_seq_len`. The warmup captures at sequence length 12 while real decode runs
at hundreds of tokens, so the graph is specialised to the length it was
captured at. Matching buffer addresses cannot repair that, which is why the
final run had zero drift and still produced 0/13.

Reaching this requires the drafter's own **prebuilt exact-attention metadata** —
the mechanism the target already has behind
`VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA` — not buffer pinning. That is
a real piece of work, not a small fix, and it is the honest next step for
anyone resuming this route.

## Kept regardless

`enforce_static_inputs=True` on the drafter's wrapper. Silent replay against
stale memory now raises instead of printing an impressive number. Two sessions
lost time to that failure presenting as a win.

## Corrections recorded

- `keep_output_alive` was proposed as the cause and was wrong; reverted.
- `dflash_fp8=0` with `width12_stack=1` is **not exact** (12/13, row 9 diverging
  at generated token 0). It cannot serve as a control.
- `DFlashProposer` overrides both `dummy_run` and
  `build_per_group_and_layer_attn_metadata`. Edits to the base class reach the
  second only because it delegates to `super()`.
