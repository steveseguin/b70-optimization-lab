# 2026-06-23 15:20Z: fast top-k neighbors and ubatch stack

Goal: try to beat the promoted fast-top-k record by tuning around
`LLAMA_MTP_DRAFT_TOP_K=10` and stacking the earlier `UBATCH_SIZE=512` TTFT/wall
throughput partial win.

Baseline record:

- `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z`;
- `91.618942 tok/s` after TTFT, `71.287464 tok/s` wall;
- `384/384` canary;
- LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`.

Common identity:

- llama.cpp `c926ad098`, SYCL/Level Zero AOT `bmg-g31`;
- UD-Q8_K_XL main GGUF plus official Gemma MTP draft GGUF;
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`,
  `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `MTP_DRAFT_FAST_TOPK=1`;
- `BENCH_PROMPT_MODE=filled-long`, actual 588 prompt / 512 output tokens;
- `CANARY_REPEATS=96` -> 384 chat canary rows.

Stamp: `20260623T152033Z`

| GPU | Variant | Canary | tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 0 | `TOP_K=8` | 384/384 | 91.230212 | 71.064826 | 1592.578 | -0.388730 | loss |
| 1 | `TOP_K=12` | 384/384 | 90.565023 | 70.525986 | 1606.294 | -1.053919 | loss |
| 2 | `TOP_K=10`, `UBATCH_SIZE=512` | 384/384 | 91.319565 | **82.100452** | **632.203** | -0.299377 | after-TTFT loss, wall/TTFT win |
| 3 | `TOP_K=10`, `CTX_SIZE=4096`, `UBATCH_SIZE=512` | 384/384 | 91.281144 | **82.091327** | **630.248** | -0.337798 | after-TTFT loss, separate 4K-context wall/TTFT win |

Decision: no LocalMaxxing submission because no after-TTFT record. Preserve the
ubatch result because it is a real TTFT/wall-throughput improvement under the
same quality gate, but do not treat it as the promoted decode-rate record.

Follow-up:

- Do not spend more immediate lanes on `TOP_K=8/12`; both missed the promoted
  record, and `TOP_K=2/4/20` had already lost.
- `UBATCH_SIZE=512` is useful for latency/wall throughput, but does not improve
  the promoted after-TTFT metric on this repeated filled-long shape.
- Next best record attempt is the `MTP_P_MIN` neighborhood around the promoted
  fast-top-k recipe: `0.115`, `0.120` repeat, `0.125`, `0.130`.
