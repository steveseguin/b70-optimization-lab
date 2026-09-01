# Qwen3.8 Flash-Next FP8 A37 cache-aware full-graph preregistration

Date: 2026-09-01
Status: frozen before model load

A37 retains A36's official FP8 model, TP4/EP4 placement, synchronous 12 GiB
PLE-only UVA offload per rank, 4,352-token limit, 128 MiB KV cache, untuned
Triton MoE, graph-safe public oneCCL, compilation-mode NONE, size-1
`FULL_DECODE_ONLY` graph, scheduler, seeds, prompts, exact hashes, full quality
battery, and teardown. It changes only fresh attempt/port/evidence paths
(attempt 37, port 19709), the pre/post runtime verifier, and one report-only
`TORCH_TRACE` diagnostic. The diagnostic is part of benchmark identity; the
run summary and `identity.txt` label it explicitly and do not treat its timing
as a promotable control until a trace-off repeat confirms the same speed.

The A37 verifier retains exact mapped oneCCL/kernel identities and graph
capture/dispatch proof. It records the isolated Torch cache rather than
requiring it to remain empty, requires `CompilationMode.NONE` plus the explicit
Inductor-disabled log receipt, and parses every isolated `TORCH_TRACE`
`dynamo_start` event. Only two exact source-hash-bound helpers are allowed:
TP-vocabulary masking and Qwen GDN input preparation. Any root-model `forward`,
unknown target, missing trace, source drift, or known whole-model compile
receipt fails closed. This distinguishes permitted nested-operator cache files
from the forbidden model-compilation mode that previously exhausted host
memory.

Frozen files:

- rewriter: `8ce5637d024992d9d3836f7cb6bb322c667e24e6fed09fdabc43024c52307fd3`;
- verifier: `be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a`;
- verifier tests: `f7b1e8ee4962a435a50f7d6d179f77dbf814a39bbec079cd7001fef4e19c41ff`;
- launcher: `4770b437848c5ed913d9ce74055b91dab0e7eaa3845e9b9ac42ea2777bc508a7`;
- client: `eb1e81820de1766b8e577dd3296bb800dcbfd7ca60d7e75f33e8ee3dda15bd1c`;
- supervisor: `2d7e0f2ec72c016f8fd79d4e75505fe87bcb0a8ccb1aea6a0ba266d03fcf75ec`.

Interpretation remains fail closed. A speed result receives no credit unless
the full battery passes, the post verifier observes actual size-1 FULL graph
dispatch, and a separately started repeat later confirms it. No reboot or
per-boot rule applies.
