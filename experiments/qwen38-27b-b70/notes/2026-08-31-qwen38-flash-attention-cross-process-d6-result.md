# Qwen3.8 paged FlashAttention cross-process D6 result

Date: 2026-08-31

Status: **negative causal screen; every case exact**

Production `reshape_and_cache_flash` plus causal paged FP16 FA2 repeated
exactly at all 12 actual strict-suite prompt lengths. Four identical prefill
calls per length, a 32-step recurrent M=1 decode trajectory per length, full
KV-cache hashes, all inputs, and all four complete process receipts were
bitwise identical across four fresh containers.

This rules the screened paged-KV insertion and FA2 kernel shapes out as the
source of the current TP1 branch flips. It does not establish whole-model
determinism.

The audit following D6 found that D1 tested explicitly preregistered TP2
component widths, then over-broadly described them as all production shapes.
The failing TP1 model uses larger stacked runtime widths. D7 must test those
exact TP1 widths before further model-level treatments.

Structured result:
`../data/2026-08-31-qwen38-flash-attention-cross-process-d6-result.json`.

Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-flash-attention-cross-process-20260831-d6`.
