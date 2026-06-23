# 2026-06-23 15:25Z: fast top-k p-min neighborhood

Goal: tune the confidence threshold around the promoted fast-top-k recipe.

Baseline record:

- `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z`;
- `91.618942 tok/s` after TTFT, `71.287464 tok/s` wall;
- `384/384` canary;
- LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`.

Common identity:

- llama.cpp `c926ad098`, SYCL/Level Zero AOT `bmg-g31`;
- UD-Q8_K_XL main GGUF plus official Gemma MTP draft GGUF;
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_BACKEND_SAMPLING=0`,
  `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`,
  `MTP_DRAFT_FAST_TOPK=1`, `MTP_DRAFT_TOP_K=10`,
  `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `BENCH_PROMPT_MODE=filled-long`, actual 588 prompt / 512 output tokens;
- `CANARY_REPEATS=96` -> 384 chat canary rows.

Stamp: `20260623T152542Z`

| GPU | `MTP_P_MIN` | Canary | tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record | Decision |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| 0 | 0.115 | 384/384 | 90.969882 | 70.801315 | 1603.392 | -0.649060 | loss |
| 1 | 0.120 repeat | 384/384 | 91.211850 | 71.022060 | 1595.756 | -0.407092 | loss |
| 2 | 0.125 | 384/384 | 90.990348 | 70.876687 | 1596.821 | -0.628594 | loss |
| 3 | 0.130 | 384/384 | 91.005272 | 70.854472 | 1600.089 | -0.613670 | loss |

Decision: no LocalMaxxing submission. The promoted `0.12` record remains valid,
but the repeat here shows the record is a high-water result within a noisy
family rather than a new stable mean shift from p-min alone.

Follow-up:

- Treat `MTP_P_MIN=0.12` as the best known value for fast-top-k=10.
- Move to thread scheduling / draft-loop overhead interactions with the
  fast-top-k patch: draft threads `28/36` and draft batch threads `28/36`.
