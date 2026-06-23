# 2026-06-23T2221 - CPU Cleanup, VMM/ubatch, and Fast Argmax

Goal: keep the Gemma 4 26B A4B Q8 draft-MTP lane fresh-response valid while
trying to improve the CPU-cleanup record from `20260623T2217`.

## Validity Rule

Headline fresh-response throughput must not depend on repeated continuation
history. These runs use draft-MTP from the Gemma MTP draft model on the current
request, not `ngram` or response-history speculation. The filled-long benchmark
does repeat the same prompt, so the conservative headline for promoted records
is the **first measured request after TTFT**. The repeated-request mean is kept
as supporting evidence only, and every benchmark row reported `cached_tokens=0`.

## Results

### CPU cleanup + VMM/ubatch/poll

Smoke:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-cpucleanup-vmm0-ub512-poll100-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222147Z`
- canary: 128/128 pass
- mean after TTFT: `91.95824544951785 tok/s`
- wall mean: `82.07561357409601 tok/s`
- first request after TTFT: `91.96682338962482 tok/s`

Full:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222328Z`
- config delta: `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`
- canary: 384/384 pass
- mean after TTFT: `91.87800806280497 tok/s`
- wall mean: `82.58835106965927 tok/s`
- first request after TTFT: `91.91746620038731 tok/s`
- decision: not an output-token record versus CPU cleanup (`91.89889994139259`
  mean), but it is a useful total/wall and TTFT improvement.

### CPU cleanup + fast argmax + VMM/ubatch/poll

Smoke:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222701Z`
- canary: 128/128 pass
- mean after TTFT: `92.25115667704165 tok/s`
- wall mean: `82.35529459492213 tok/s`
- first request after TTFT: `92.24651184304217 tok/s`

Full promotion run:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z`
- config delta from CPU-cleanup record:
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, `LLAMA_MTP_DRAFT_FAST_TOPK=0`,
  `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`
- canary: 384/384 pass
- conservative fresh headline, first request after TTFT:
  `92.39728860909672 tok/s`
- supporting independent repeated-request mean after TTFT:
  `92.76706524545781 tok/s`
- supporting wall mean: `83.28926542058376 tok/s`
- actual benchmark shape: 588 prompt tokens, 512 output tokens
- prompt cache: `cached_tokens=0` on all rows
- summary:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z.server.log`
- LocalMaxxing: approved as `cmqr82niq01hgqo01v42y7ue8`

## Decision

Promote the fast-argmax + CPU-cleanup + VMM/ubatch/poll stack as the current
fresh-response one-B70 Q8 record. It supersedes:

- `cmqr7ni7u01gxqo01wtqsrn3u`: CPU-cleanup fast-top-k record,
  `91.87689288153598 tok/s` first request / `91.89889994139259` mean;
- `cmqqsecuk01azqo018ahv0i1s`: earlier fast-top-k record,
  `91.25 tok/s` first request / `91.61894213332073` mean.

Next work should avoid history-populated `ngram` as a headline metric and test
fresh-valid MTP source/code changes. Active follow-ups launched after this
record: profile-off control, `n_max=8`, `n_max=9`, and lower `p_min=0.10`,
all with the promoted fast-argmax/CPU-cleanup/VMM stack.

## Follow-up Smokes

All of these were fresh-valid smokes with `CANARY_REPEATS=32`, so `128/128`
chat canary rows before measurement. None beat the conservative record
(`92.39728860909672 tok/s` first request after TTFT).

| Label suffix | Canary | First request tok/s | Mean after TTFT | Wall mean | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `n7-fastargmax-cpucleanup-vmm0-ub512-poll100-noprofile` | 128/128 | `91.5877236122735` | `92.07354331376756` | `82.13738059221009` | loss: profiling off did not help |
| `n8-fastargmax-cpucleanup-vmm0-ub512-poll100-noprofile` | 128/128 | `61.53343606885064` | `61.94564177867156` | `57.245510168961545` | loss: deeper `n_max=8` collapses throughput |
| `n9-fastargmax-cpucleanup-vmm0-ub512-poll100-noprofile` | 128/128 | `65.99304732789753` | `65.97025874877086` | `60.699805253663726` | loss: deeper `n_max=9` collapses throughput |
| `n7-fastargmax-cpucleanup-vmm0-ub512-poll100-noprofile-pmin010` | 128/128 | `91.17524912296552` | `91.75904318352174` | `81.81190752002762` | loss: lower `p_min=0.10` does not beat record |

Second batch, same `128/128` smoke gate:

| Label suffix | Canary | First request tok/s | Mean after TTFT | Wall mean | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `n7-fastargmax-cpucleanup-vmm0-ub512-poll100-verifyargmax` | 128/128 | `91.65464226831207` | `91.71848924790214` | `81.79462648338026` | loss: verifier greedy argmax did not help |
| `n7-fastargmax-cpucleanup-vmm0-ub512-poll100-dthreads64` | 128/128 | `91.68026392596823` | `92.67616945508459` | `82.51210089508774` | no promotion: repeated mean close to record, but first fresh request below record |
| `n7-fastargmax-cpucleanup-vmm0-ub512-poll100-dtb64` | 128/128 | `91.31291173860929` | `91.52882855956827` | `81.66312988084253` | loss |
| `n7-fastargmax-cpucleanup-vmm0-ub1024-poll100` | 128/128 | `91.51597253260275` | `91.55108749722172` | `81.68228695006815` | loss |

Next direction: source-level work in `common/speculative.cpp`, not more shallow
flag sweeps. The remaining useful ideas are to reduce verifier/draft memcpy
work, especially lazy copying of target `h_nextn` rows and skipping copies for
rows that will not be consumed.
