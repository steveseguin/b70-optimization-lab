# Preregistration: A340 / A341 - is the data-dependent MoE all-reduce cost still on the promoted MTP0 line?

## Question

A146 / A151 / A154 (2026-09-05, overlay `f8c7c0ee`, before headroom placement, expert host
placement, Triton HC glue and the fused QSA pre-indexer) decomposed the 72.7 ms graph MTP0 decode
step at exact-2K as: ~22 ms with the MoE GEMMs skipped, 32.9 ms with the MoE final all-reduce a
no-op, 34.2 ms with the all-reduce on a static zero buffer, 72.7 ms real. About 40 ms of the step
sat at the 48 MoE all-reduces only when the reduced data was the real trajectory. The promoted line
has since halved its step (headroom: 37.0 ms/step, A179) and moved on three overlays. Does that
term survive on the line as promoted (`2a372e86`, W13-N64 map), and how large is it now?

## Arms

Both derive from the promoted MTP0 packet A336 (W13-N64, graph, placement, 4352 capacity) with
three additions on a diagnostic head `ae0e5650c` = `2a372e86` + the step-timing, per-site
all-reduce GPU-event, skip and memory-note hooks ported from the diagnostic lineage (pure
report-only code; the promoted code paths are untouched when the flags are off):

- **A340 (control, real):** `Q38_STEP_TIMING_LOG=10`, `Q38_ALLREDUCE_EVENT_TIMING=1`,
  `Q38_MEM_NOTE=1`. Outputs must equal the promoted line's (exact-2K hash `afffd211…`).
- **A341 (zero-input all-reduce):** A340 plus `Q38_DIAG_SKIP=moe_allreduce_zero_input`. Timing
  only; outputs are garbage by construction and are not compared.

Workload: three exact-2K rows through the frozen depth harness (the same rows the A146 series
used), one server per arm, launched serially through `q38-launch-frozen-attempt.sh`.

## What is read

Per step: `Q38_STEP_TIMING` forward/sample/draft ms; per all-reduce site: GPU event sums and
counts (`allreduce_moe_*`, `allreduce_other_*`) reported at each timed step. The verdict is the
graph-step median at 2K, A340 minus A341, and the per-site event share of the step.

## Predictions, written first

- If the data-dependent term is still there: A340 median well above A341 (the 09-05 series
  showed 72.7 vs 34.2), and the MoE-site event sum accounts for most of the difference.
- If it is gone: A340 and A341 within ~3 ms (same graphs, same GEMMs), and the next lever is the
  M=2 verify path (A124/A125), not the collective.

## Stop rules

- A340's exact-2K hash != `afffd211…`: the diagnostic head changed numerics; stop and fix the port.
- Either server fails its supervisor's preflight/health: stop, follow the lane's post-fault rule
  (reload xe before any relaunch after a Fault response).
