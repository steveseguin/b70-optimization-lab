# Chunk-corruption mechanism program: preregistration (capped)

Date: 2026-08-23. Follows the
[dose-8 reproduction](2026-08-22-qwen38-longkv2-closure-and-chunk-corruption-finding.md)
(d7 green / d4 red re-confirmed on the unchanged lane, 20260823-repro2 roots).
Discipline: one contract per door, interpretations frozen here before any
instrumented run; program capped in advance.

## Door D0 - scratch allocation census (ALREADY EXECUTED, no new run)

The `get_gdn_spec_decode_scratch` cache emits a TORCH_WARN per allocation, so
the existing repro logs are the instrument. Result: **96 allocations = 48 GDN
layers x 2 ranks, all at warmup, 96 distinct owner keys, byte-identical
between the green (d7) and red (d4) runs, zero allocations during dose
processing.** Frozen interpretation applied: allocation-lifecycle mechanisms
(cache churn, owner-pointer address reuse, shape-collision false hits) are
**DEAD**. The corruption lives in the REUSE of stable shared state, not in
entry lifecycle.

## Remaining suspects (from code reading, no instrumentation yet)

- GDN per-request recurrent/conv state slots: chunked prefill must carry
  recurrent state across chunk boundaries via a state slot; a fixed slot pool
  with a leak of one slot per multi-chunk request would produce an exact
  dose threshold. "Exactly 8" is not yet matched to a literal: the
  spec-decode index tensors are sized `decode_cudagraph_max_bs =
  min(max_num_seqs*(num_spec+1), max_cudagraph_capture_size) = 6` on this
  lane, so the pool to census is the hybrid KV manager's GDN state-block
  pool, not the cudagraph batch clamp.
- `has_initial_state` handling at chunk boundaries: the scratch allocates it
  as ones; a path that reads it without a fresh per-call write would carry
  stale continuation flags into a new request.

## Doors D1/D2 (the ONE instrumentation patch, report-only, default off)

- **D1 state-slot trace** (`VLLM_XPU_GDN_STATE_SLOT_TRACE=1`): log, per
  scheduler step, the GDN state indices consumed
  (`spec_state_indices_tensor` / `non_spec_state_indices_tensor` population
  in `gdn_attn.py` build) and the state-block allocation/free events in the
  hybrid KV-cache manager. Frozen interpretation: if the slot sequence shows
  monotone exhaustion or a wrap that first reuses a live/unfreed slot exactly
  at the 8th multi-chunk request, the slot-lifecycle mechanism is CONFIRMED;
  if slots recycle cleanly through all 8 doses, this door is DEAD.
- **D2 initial-state audit** (`VLLM_XPU_GDN_INITSTATE_AUDIT=1`): log
  `has_initial_state` as observed by the kernel call per request/chunk.
  Frozen interpretation: a chunk-1 (fresh) computation observing
  `has_initial_state=1`, or a chunk-2 observing 0, at any dose, CONFIRMS
  stale/missing continuation flags; all-correct flags through dose 8 kills
  this door.

## Cap (frozen)

ONE report-only patch (both doors, no behavior change, off by default),
TWO instrumented runs (d7 and d4 with both doors on), one analysis pass.
No behavior-changing doors in this program; any fix is a separate
preregistered arc with its own gates. If both doors die, the program stops
and the next hypothesis round needs a fresh preregistration.
