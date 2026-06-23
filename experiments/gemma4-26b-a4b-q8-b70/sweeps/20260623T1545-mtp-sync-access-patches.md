# 2026-06-23 15:45Z: MTP output access / sync patches

Goal: reduce host/API overhead in the fast top-k MTP draft loop without changing
the Q8 quality lane or draft acceptance semantics.

Baseline record:

- `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z`;
- `91.618942 tok/s` after TTFT, `71.287464 tok/s` wall;
- `384/384` canary;
- LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`.

Common run identity:

- llama.cpp `c926ad098`, SYCL/Level Zero AOT `bmg-g31`;
- UD-Q8_K_XL main GGUF plus official Gemma MTP draft GGUF;
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`,
  `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `MTP_DRAFT_FAST_TOPK=1`,
  `MTP_DRAFT_TOP_K=10`, `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `BENCH_PROMPT_MODE=filled-long`, actual 588 prompt / 512 output tokens;
- `CANARY_REPEATS=96` -> 384 chat canary rows.

## Patch A: remove explicit pre-logits sync

Patch artifact:

- `patches/gemma4-llamacpp-mtp-draft-fast-topk-nosync-loss-20260623.patch`

Hypothesis: `draft_fast_topk_sample()` called `llama_synchronize(ctx_dft)` and
then `llama_get_logits_ith()`, whose public API also synchronizes. Removing the
explicit sync should avoid one redundant synchronization per draft step.

Result stamp: `20260623T154517Z`

| GPU | Canary | tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | 384/384 | 90.246898 | 70.382657 | 1601.212 | -1.372044 |
| 1 | 384/384 | 89.834686 | 70.129172 | 1601.613 | -1.784257 |
| 2 | 384/384 | 90.052260 | 70.285569 | 1599.039 | -1.566682 |
| 3 | 384/384 | 90.182245 | 70.387761 | 1596.678 | -1.436697 |

Decision: reject. Quality held, but throughput regressed significantly.

## Patch B: single row helper for logits + NextN embedding

Patch artifact:

- `patches/gemma4-llamacpp-mtp-draft-rowhelper-loss-20260623.patch`

Hypothesis: `llama_get_logits_ith()` and `llama_get_embeddings_nextn_ith()` each
synchronize and call `output_reorder()`. A staging helper returning both rows
after one synchronization should reduce per-draft-step API overhead. The MTP
loop was also changed to fetch the embedding row only after the drafted token
passed confidence gates.

Result stamp: `20260623T155907Z`

| GPU | Canary | tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | 384/384 | 90.513031 | 70.484992 | 1607.412 | -1.105911 |
| 1 | 384/384 | 90.902598 | 70.835744 | 1595.586 | -0.716344 |
| 2 | 384/384 | 90.917426 | 70.817153 | 1598.456 | -0.701517 |
| 3 | 384/384 | 90.888885 | 70.785680 | 1599.866 | -0.730057 |

Decision: reject. Quality held, but still below record. The remaining bottleneck
is not fixed by reducing public API synchronization around logits/embeddings.

## Follow-Up

- Keep the original fast-top-k patch with explicit sync as the promoted source
  patch.
- Do not retest sync-removal or row-helper patches unless another change
  alters the logits/embedding materialization path.
- The next source-level candidate is more invasive: avoid full-vocab host
  logits movement by producing top-k candidate IDs/logits in the graph/backend
  output path.
