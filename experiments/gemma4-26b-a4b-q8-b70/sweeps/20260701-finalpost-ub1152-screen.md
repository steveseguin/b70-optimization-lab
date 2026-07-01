# 2026-07-01 Final-Postnorm + UBATCH 1152 Screen

Status: closed negative. Strict128 A/B only. Do not submit or promote.

## Question

Does the earlier `BATCH_SIZE=1152`, `UBATCH_SIZE=1152` local-positive
microbatch setting become useful after the current promoted
`LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1` recipe?

The prior FA-on/VMM UBATCH screen showed `1152/1152` was valid and faster than
same-window `1024/1024` controls, but it was tested before the final-postnorm
record became the promoted recipe and did not beat the then-current headline.
This screen tests only that specific interaction; it is **not** a renewed
UBATCH sweep.

## Current Headline

- `123.67689864739785 tok/s` median generated-token throughput for tokens
  1-100 after TTFT.
- Evidence:
  `data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json`.
- LocalMaxxing: `cmr01nnet000mld01x2tt6qds`.

## Shared Identity

All lanes should use:

- fixed realistic cold suite, each prompt once;
- `cached_tokens=0` required for every request;
- UD-Q8_K_XL target/verifier, Q4_0 MTP draft verified by the target;
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`, f16 KV;
- `n_max=3`, `n_min=2`, `p_min=0.0475`, `--ctx-checkpoints 0`;
- promoted source flags:
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`.

## Screen Layout

Strict128 screen:

- GPU0/GPU2 controls: `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`;
- GPU1/GPU3 candidates: `BATCH_SIZE=1152`, `UBATCH_SIZE=1152`;
- `MAX_TOKENS=128`, `CANARY_REPEATS=32`.

Decision rule:

- If both candidates clearly beat both controls and one candidate is close to
  or above the current headline, run a full512 confirmation before any
  LocalMaxxing action.
- If mixed or below current-record territory, close as valid no-change.

## Result

All four lanes passed the fixed realistic cold gate, had `cached_tokens=0`,
and completed the 128-row canary. The `1152/1152` candidates did **not** beat
the same-window `1024/1024` controls.

| GPU | batch/ubatch | median tok/s 1-100 | p10 | mean | full tok/s | TTFT ms | decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 1024/1024 control | 121.88626919341718 | 106.36508630155902 | 119.38199601166441 | 117.25705432783124 | 178.66977700032294 | control |
| 1 | 1152/1152 candidate | 111.13257897167367 | 102.82593879138409 | 112.65623132776369 | 112.44680362552134 | 179.4535859953612 | loss |
| 2 | 1024/1024 control | 117.32450078824291 | 108.34477047786281 | 117.56055121718542 | 116.50444206699873 | 178.39018302038312 | control |
| 3 | 1152/1152 candidate | 118.75276241034763 | 103.19913934099961 | 117.56137950572338 | 117.65824612036549 | 178.5893264459446 | mixed, below record |

Summary:

- control average: `119.60538499083004 tok/s`;
- candidate average: `114.94267069101065 tok/s`;
- best candidate: `118.75276241034763 tok/s`, below the current
  `123.67689864739785 tok/s` headline and below the best same-window control.

Decision: close as valid no-change. Do not run full512 confirmation, do not
submit to LocalMaxxing, and do not renew the UBATCH search around `1152/1152`
unless a separate source/runtime mechanism changes the shape again.

Artifacts:

- `data/gemma4-q8-gpu0-finalpost-ub1024-control-strict128-20260701T020818Z-finalpost-ub1152/`
- `data/gemma4-q8-gpu1-finalpost-ub1152-on-strict128-20260701T020818Z-finalpost-ub1152/`
- `data/gemma4-q8-gpu2-finalpost-ub1024-control-strict128-20260701T020818Z-finalpost-ub1152/`
- `data/gemma4-q8-gpu3-finalpost-ub1152-on-strict128-20260701T020818Z-finalpost-ub1152/`
