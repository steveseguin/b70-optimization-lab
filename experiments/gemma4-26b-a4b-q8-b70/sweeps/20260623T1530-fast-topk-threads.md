# 2026-06-23 15:30Z: fast top-k draft thread neighborhood

Goal: test whether the promoted fast-top-k recipe interacts with draft thread
and draft batch thread counts differently from the pre-fast-top-k runs.

Baseline record:

- `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z`;
- `91.618942 tok/s` after TTFT, `71.287464 tok/s` wall;
- `384/384` canary;
- LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`.

Common identity:

- llama.cpp `c926ad098`, SYCL/Level Zero AOT `bmg-g31`;
- UD-Q8_K_XL main GGUF plus official Gemma MTP draft GGUF;
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`,
  `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_FAST_TOPK=1`,
  `MTP_DRAFT_TOP_K=10`, `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `BENCH_PROMPT_MODE=filled-long`, actual 588 prompt / 512 output tokens;
- `CANARY_REPEATS=96` -> 384 chat canary rows.

Stamp: `20260623T153045Z`

| GPU | Variant | Canary | tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 0 | draft threads 28, batch 32 | 384/384 | 90.884620 | 70.751205 | 1603.114 | -0.734322 | loss |
| 1 | draft threads 36, batch 32 | 384/384 | 90.839766 | 70.725103 | 1603.121 | -0.779176 | loss |
| 2 | draft threads 32, batch 28 | 384/384 | 90.672937 | 70.638178 | 1601.567 | -0.946005 | loss |
| 3 | draft threads 32, batch 36 | 384/384 | 90.943585 | 70.835632 | 1598.179 | -0.675357 | loss |

Decision: no LocalMaxxing submission. The pre-fast-top-k optimum
`MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32` remains the best known
thread identity.

Follow-up:

- Stop spending lanes on nearby thread counts without another code or runtime
  change.
- Next useful work should be source-level draft-loop overhead reduction, not
  more small environment sweeps.
