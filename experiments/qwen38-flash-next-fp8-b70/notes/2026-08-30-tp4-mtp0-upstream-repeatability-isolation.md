# Qwen3.8 Flash-Next FP8 upstream repeatability isolation

Date: 2026-08-30
Status: fixed-input component paths pass; full-model boundary trace next

A15 proved that deterministic QSA group ordering was a real fix but not the
only reliability issue: short decode stayed exact and faster, while two 4K
rows on a fresh server diverged at generated token 2. The next checks therefore
held inputs fixed and repeated only operations exercised by the 4K path.

All checks were bit-identical across 100 repetitions:

- QSA scoring, stable selection, and sparse attention at real 4K dimensions;
- the full-shape local Triton FP8 MoE path with both synthetic and real layer-0
  checkpoint expert weights;
- TP4 XCCL all-reduce at `64x2560` in BF16 and FP32, with the same output hash
  on every rank.

This rules out direct fixed-input non-repeatability in those components. It
does not prove that their full-model inputs or state caches are identical.
The residual A15 failure must enter earlier in the long-prefill value/state
chain and is then amplified once QSA subset selection becomes active.

The next arm is a report-only, environment-gated trace of rank 0 during the
last 4K prefill chunk. It records exact tensor digests at the model input and
each decoder-layer boundary. Two fresh starts, with identical requests, will
identify the first differing layer before any treatment is proposed. No
weights, arithmetic, placement, scheduler setting, or protected result will
change inside the trace arm.

Structured receipt:
[`../data/20260830-tp4-mtp0-upstream-repeatability-isolation.json`](../data/20260830-tp4-mtp0-upstream-repeatability-isolation.json).
