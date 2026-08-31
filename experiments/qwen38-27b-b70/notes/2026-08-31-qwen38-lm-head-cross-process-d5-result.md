# Qwen3.8 actual LM-head cross-process D5 result

Date: 2026-08-31

Status: **negative causal screen; exact across four fresh processes**

The real model's BF16 `[248320,5120]` `lm_head.weight`, converted to the
server's FP16 runtime dtype, produced one complete-logit hash and one top token
across 64 calls in four fresh containers. All four process receipts were also
byte-identical. The direct model verification gate passed before tensor load.

This rules the M=1 output projection out as the source of the strict TP1
fresh-server branch flips. It does not establish whole-model determinism or
authorize a speed, quality, MTP, or publication claim.

The next discriminator is a fresh TP1 eager repeat of the same strict
12-prompt suite on the immutable official `f01e24f6...` runtime. If that parent
repeats 12/12, the current overlay/kernel stack is a regression; if it also
fails, the fault is inherited from the official Intel execution path and the
next localization target is the full attention path.

Structured result:
`../data/2026-08-31-qwen38-lm-head-cross-process-d5-result.json`.

Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-lm-head-cross-process-20260831-d5`.
