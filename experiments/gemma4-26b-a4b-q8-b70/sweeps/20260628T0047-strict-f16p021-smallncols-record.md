# 2026-06-28 - F16 p021 small-ncols strict record

Goal: continue the Gemma 4 26B A4B `UD-Q8_K_XL` one-B70 lane under the fixed
realistic cold-response gate. All promoted rows here use the Q8-quality target
as verifier, Q4_0 MTP draft tokens verified by the target, no n-gram/history
acceleration, no response reuse, and `cached_tokens=0` for the promoted run.

Base identity for the successful lane:

- llama.cpp `c926ad098`, local B70 SYCL/AOT Gemma patch stack;
- target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- server:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`;
- `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`,
  `BATCH_SIZE=1024`, `THREADS=8`, `POLL=100`;
- `--parallel 1 --cache-ram 0 --no-spec-draft-backend-sampling
  --spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0`;
- `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`,
  `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`,
  `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`,
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`,
  `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`.

## Four-GPU screen, `MAX_TOKENS=128`

Timestamp: `20260628T004714Z`. Screen depth was `CANARY_REPEATS=8`,
`MAX_TOKENS=128`, strict realistic gate. All rows were fresh-response valid.

| Lane | Extra flag | Median 1-100 after TTFT | p10 | Mean | Full after TTFT | Wall full | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gpu0-strict-vdr2-q8mmvq-smallncols` | `LLAMA_SYCL_Q8_MMVQ_SMALL_NCOLS=1` | `87.501533170741` | `79.874679144461` | `87.464323620151` | `84.291586332464` | `74.256878287424` | negative |
| `gpu1-strict-vdr2-f16p021-smallncols` | `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1` | `97.464866276627` | `88.869884319146` | `96.218436497324` | `95.264765547902` | `83.004789073593` | lead |
| `gpu2-strict-vdr2-multitoken-filter-gateup` | `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FILTER=gate_up` | `86.884556524888` | `78.747349813282` | `87.314177989565` | `87.138382763430` | `77.521217281159` | negative |
| `gpu3-strict-vdr2-multitoken-filter-down` | `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FILTER=down` | `80.073995623020` | `73.995162986484` | `82.422102569697` | `81.204602396523` | `73.275345281168` | negative |

## Four-GPU confirmation, `MAX_TOKENS=128`

Timestamp: `20260628T005022Z`. Same strict gate, `CANARY_REPEATS=32`,
`MAX_TOKENS=128`, all rows valid with `cached_tokens=0`.

| Lane | Median 1-100 after TTFT | p10 | Mean | Full after TTFT | Wall full | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpu0` | `98.449597268647` | `88.543460918768` | `97.744603900147` | `96.505858375456` | `85.334716935424` | `180.891` |
| `gpu1` | `95.813072294786` | `88.415074284434` | `97.380800019325` | `96.037259668974` | `84.409975503093` | `182.630` |
| `gpu2` | `96.159328222645` | `88.496677649739` | `96.234440385947` | `92.838682103399` | `82.106188763643` | `181.035` |
| `gpu3` | `93.409617065926` | `85.403068511702` | `93.955308638725` | `93.787723041164` | `82.502353554361` | `181.592` |

The 128-token confirmation proved `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1` was a
real lead, but it was not submitted because promoted rows should also report
the full 512-token metric.

## Invalid full512 reconstruction

Timestamp: `20260628T005507Z`. This run is a negative artifact, not evidence:
it reconstructed the launch command manually and changed identity details
relative to the valid lane (`BATCH_SIZE=512`, `THREADS=16`, `POLL=50`,
missing `--no-spec-draft-backend-sampling`, missing draft thread flags,
missing `--ctx-checkpoints 0`, `ONEAPI_DEVICE_SELECTOR=level_zero:*`, and
accidentally set `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1`).

The rows measured `81.48-92.18 tok/s`, but the fixed gate rejected every lane:
`cached_tokens=[1, 1, ..., 1]`, `cached_tokens_all_zero=false`. Keep this as a
reminder that Gemma promotion runs must match the full benchmark identity, not
just the headline knobs.

## Promoted full512 confirmation

Timestamp: `20260628T010121Z`. Corrected full512 run matched the successful
128-token identity exactly and changed only `MAX_TOKENS=512`. All four lanes
passed the fixed realistic gate, `cached_tokens=0` for every prompt,
`CANARY_REPEATS=32` (`128/128` rows per lane), no prompt/KV/context/response
reuse, and no n-gram/history acceleration.

| Lane | Summary | Median 1-100 after TTFT | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpu0` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-smallncols-full512-exactconfirm-n3-nmin2-p00475-ub1024-20260628T010121Z/summary.json` | `95.81654623957742` | `85.28597771004382` | `96.33974873499733` | `91.02603986540491` | `86.95930322948115` | `179.682343499735` |
| `gpu1` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-smallncols-full512-exactconfirm-n3-nmin2-p00475-ub1024-20260628T010121Z/summary.json` | **`95.82453787677183`** | `85.50364602737247` | `95.60529298381927` | `91.14224184526994` | `88.26207892019767` | `179.72276301588863` |
| `gpu2` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-smallncols-full512-exactconfirm-n3-nmin2-p00475-ub1024-20260628T010121Z/summary.json` | `93.42169001279183` | `90.5456975696477` | `95.19134075504498` | `91.18290172822282` | `88.26043497841317` | `181.12219497561455` |
| `gpu3` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-smallncols-full512-exactconfirm-n3-nmin2-p00475-ub1024-20260628T010121Z/summary.json` | `95.56564013874495` | `85.3298256090267` | `95.96440964332642` | **`91.64639695308361`** | `87.47644909177413` | `179.94167003780603` |

Decision: promote `gpu1` as the headline because it has the best primary
metric. Confirmation floor is `93.42169001279183`; mean of medians is
`95.1571035669715`. Delta over the prior `90.98312252660529` record is
`+4.8414153501665425 tok/s` / `+5.321223558524069%`.

LocalMaxxing:

- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-smallncols-full512-20260628.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-smallncols-full512-20260628.submit.log`;
- LocalMaxxing ID: `cmqx3687103v4qr01ace1ft3m`, status `APPROVED`.

## Follow-up

`LLAMA_SYCL_F16_P021_SMALL_NCOLS=1` is now part of the promoted strict
Gemma 26B Q8 reproduction command. The Q8 MMVQ small-ncols and multi-token
filter variants are negative. Further progress should profile why `p021`
benefits from the small-column special case and look for analogous narrow-N
specialization opportunities in the target/verifier LM-head and MoE paths.
