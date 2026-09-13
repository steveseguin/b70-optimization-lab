# Result: A393 - the selectors catch prefill tail chunks; why a lossless many-users cell needs a new authority

Preregistration: `2026-09-13-a393-row-wise-selector-shape-log-prereg.md`. Diag head `e12f6adb`
(= `dc11a3a0a` + logging of every input entering a row-wise branch), eight-sequence MTP0 server, selectors
at 8, port 20010. Server healthy at 17:46:37 UTC; two exact-2K rows (`afffd211…` both), two full oracle passes.

## What entered the row-wise branches

| when | site | shape | reading |
|---|---|---|---|
| graph capture (sizes 8/4/2) | all_reduce | [M, 2560] bf16 and [M, 16, 160] int8 | decode token rows, as intended (the int8 tensor is the QSA index sync; integer sums are order-free) |
| single-user oracle prompts | all_reduce | [7, 2560] bf16, [6, 2560] bf16 (and [4, …]) | **prefill tail chunks** of the 71-, 70- and 68-token prompts (71 mod 64 = 7, 70 mod 64 = 6, 68 mod 64 = 4) |
| anywhere | hc_norm | none | the HC-norm selector never engaged; the four-stream state is not row-leading at these sites |

The three prompts whose single-user outputs changed on `dc11a3a0a` (A390, A393: identical to each other,
different from A392/A383) are exactly the three with a 2..8-token prefill tail; the five with tails of
10-29 tokens are unchanged. At `max_rows=2` (the MTP1 lineage's certified setting) only a 2-token tail
would be affected, and the exact-2K/4K prompts are multiples of 64, so it never showed.

## Consequences

1. A selector keyed on `shape[0]` is wrong above 2 rows. A corrected selector must apply only to
   decode-only steps (the decode graphs), never to prefill chunks; that fix restores one-row identity and
   is still the right shape for the MTP verify step.
2. Even with that fix, a multi-user server cannot be bit-identical to the certified single-user stream on
   this stack: the single-user line's prefill uses batched collectives whose shapes follow the 64-token
   chunking of each prompt, while the scheduler of a multi-user server mixes prefill chunks and decode
   rows of different requests in one step, changing every collective's shape for the same prompt. Making
   prefill row-invariant too (one collective per token) would itself change the single-user authority and
   multiply prefill collectives 64x. The early first-divergence positions in A383/A390/A392 (tokens 1, 2,
   11, 14) are consistent with prefill-level differences.
3. Therefore the "Many users" cell stays withheld under the lossless rule, and the way to a qualified cell
   is a deliberate new authority: a batch-invariant serving line certified as its own identity (its own
   single-user pins, quality battery and fresh-server repeats), with the aggregate rates already measured
   (47 / 58 / 82 tok/s at 2 / 4 / 8 users). That is a user decision, recorded here and in the handoff.
4. `dc11a3a0a` and `e12f6adb` are diag heads only (branches `q38-mtp0-rowwise`, `q38-mtp0-rowwise-diag`).

Evidence: A393 server log (`Q38_ROWWISE_DIAG` lines), `concurrency-oracle-pass{1,2}.json` in the A393 run dir.
