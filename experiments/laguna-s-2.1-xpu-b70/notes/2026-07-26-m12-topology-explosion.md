# Laguna M=12 — the blocker is a 4.7x graph-topology explosion, not memory

Date: 2026-07-26 America/Toronto

Status: **structural negative. Not promoted. Goal of 102 tok/s not met.**
Approved record remains **94.920039** tok/s.

## The finding

At width 12 the Breakable graph does not merely fail to capture — it captures a
fundamentally different and far worse topology:

```
Breakable graph topology changed: saw graphs/eager=(685, 684), expected (146, 145)
```

That is **4.7x** the audited M=8 topology, and it is the real blocker. The
out-of-device-memory failure seen earlier is a downstream symptom of it, not an
independent problem, and lowering `gpu_memory_utilization` does not address it.

## Arithmetic identifies the cause

`685 - 146 = 539`, and `539 = 11 x 49`. Eleven extra boundaries per decoder
layer across 48 layers plus one embedding boundary is exactly `(M - 1)` extra
per layer. That is the signature of **per-row serialization**: the MoE taking
the `exact_spec_rows` path, which runs
`torch.cat([self._forward_flat(h[row:row+1]) for row in range(rows)])` and
therefore issues one collective per row instead of one batched collective per
layer.

It also explains the single-row `(1, 1, 3072)` collective observed earlier: a
serialized per-row `o_proj` all-gather.

The width environment reaches the model correctly —
`envs.VLLM_XPU_LAGUNA_EXACT_MAX_M = 12` and `xpu_laguna_exact_max_m() = 12`
were verified in-process — so `1 <= 12 <= 12` holds and the remaining
possibility is that `batched_exact_rows` is false for another reason, leaving
`exact_spec_rows` to serialize. A gated MoE branch probe was added to settle
which condition fails; it has not yet produced output because the width-12
server has begun hanging at XCCL initialization before reaching a forward.

## Correction to an earlier change

Making the collective gather count "learned and asserted stable" allowed the run
to progress past the 96-slot assertion, but that was the wrong instinct: it
normalizes a 4.7x regression rather than surfacing it. The count assertion was
doing useful work. This change must not be treated as a fix, and no measurement
taken with an expanded topology can support promotion.

The correct goal is to restore a topology close to 146/145 at width 12 by
keeping the MoE on its batched path, not to accept hundreds of single-row
collectives.

## Second, separate problem

Width-12 startup now hangs intermittently at XCCL initialization: the server log
freezes after the CCL topology warnings, workers spin near full CPU, the health
endpoint never listens, and the leg's 15-minute timeout fires. Cleanup is clean
each time (`stop_status=0`, `worker_status=0`, `idle_status=0`, all four cards
returning to 43 MiB). This is unrelated to the topology explosion and must be
diagnosed separately.

## Arithmetic on the objective, unchanged

+6.9% emitted per cycle on the approved 94.920 record projects roughly
**101.5** tok/s at unchanged cycle time — and an expanded topology guarantees
cycle time will be worse, not unchanged. M=12 alone cannot reach 102 even once
it works; the width-two tree remains required.

## Next

1. Land the MoE branch probe on a run that survives startup, and determine which
   condition of `batched_exact_rows` fails at twelve rows.
2. Restore the batched MoE path at width 12 and require the captured topology to
   stay near 146/145 rather than learning whatever it produces.
3. Diagnose the XCCL startup hang at width 12 independently.
4. Only then measure, and only then consider the tree.
