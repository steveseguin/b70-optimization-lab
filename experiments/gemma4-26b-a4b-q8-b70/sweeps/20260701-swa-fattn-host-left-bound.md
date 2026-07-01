# Gemma 4 26B Q8 B70: Host-Derived SWA FlashAttention Left Bound

Date: 2026-07-01

Status: **service-lane win with a strict threshold**. The patch is not a
LocalMaxxing headline decode record, but `MIN_Q=2048` gives a repeated
long-context prefill win while keeping the protected MTP full512 decode guard
flat/positive in paired A/B and cross-over.

## Question

Earlier SYCL FlashAttention `KV_min` experiments proved that skipping old
masked sliding-window KV tiles can improve long-context prefill by about
`+4.7%` to `+6.1%`, but the direct mask-scanned implementation regressed the
fixed short-decode guard and the isolated template retry was negative. This
experiment keeps the same idea but moves the left bound out of the tile mask
scan:

- host code builds an exact I32 per-query left-bound input from the existing KV
  cells and the same SWA/mask keep predicate;
- graph code attaches that tensor to `ggml_flash_attn_ext` only for Gemma-style
  standard SWA, causal flash-attn, no ALiBi, and at least the configured query
  threshold per stream;
- SYCL tile FlashAttention uses the conservative minimum bound over the query
  columns in a tile to skip fully masked old KV blocks;
- vector FlashAttention accepts the argument but does not use it;
- the feature is default-off behind
  `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`.

This is intended as a prompt-processing / long-context service optimization,
not a LocalMaxxing headline decode record. Promotion requires no quality
regression and no short-context decode regression against the protected Gemma
Q8 lane.

## Patch Artifacts

Source patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/llama-cpp-swa-fattn-host-left-bound-active-stack-20260701.patch`
- sha256:
  `7961325e0d986998632cb62562cd8e27be5f287f843e8d69fd275b5553b77782`
- lines: `2335`

Harness metadata patch:

- `patches/gemma4-26b-a4b-q8-b70/gemma-runner-swa-left-bound-env-record-20260701.patch`
- sha256:
  `2a9db993d014b41b921c508584351b02d3afddb6be22bacdd058007c53ce14eb`
- lines: `35`

Caveat: the source patch is against the active dirty Gemma/B70 llama.cpp record
stack at `/home/steve/src/llama.cpp-gemma-record-repro-c926`, not a clean
upstream-only patch.

## Common Identity

- model: Gemma 4 26B A4B IT `UD-Q8_K_XL` target/verifier;
- runtime: llama.cpp `c926ad098` plus local Gemma/B70 stack;
- build: `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`;
- hardware: one Intel B70 per lane, four lanes in parallel;
- context: `CTX_SIZE=32768`;
- attention: `FLASH_ATTN=on`;
- VMM: `GGML_SYCL_ENABLE_VMM=1`;
- protected short-lane quality: fixed realistic suite, one cold response per
  prompt, `cached_tokens=0`, `REALISTIC_METRIC_TOKENS=100`;
- long-context quality: deterministic long-context JSON retrieval suite,
  one cold request per case/lane, `cached_tokens=0`.

No LocalMaxxing submission is appropriate for this service/prefill lane unless
it also produces a verified fresh-response short decode record, which it has
not done.

## Short Strict128 Screen

Artifact:

- `data/gemma4-swa-leftbound-short-ab-20260701T064212Z-swa-leftbound-short-ab2.json`

Common env:

```bash
CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1
LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1
BATCH_SIZE=2048 UBATCH_SIZE=1024
MAX_TOKENS=128 CANARY_REPEATS=8
REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100
```

All four lanes passed canary, fresh-response validity, and `cached_tokens=0`.

| Group | Median 1-100 tok/s by lane | Average |
| --- | ---: | ---: |
| control | `114.042437`, `117.345583` | `115.694010` |
| left-bound on | `117.123674`, `120.145634` | `118.634654` |

Readout: no short strict128 regression in this screen. This is not sufficient
for promotion because the protected headline lane uses full512 output.

## Long-Context A/B

Artifact:

- `data/gemma4-swa-leftbound-long-ab-20260701T064333Z-swa-leftbound-long-ab1.json`

Common env:

```bash
CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
LLAMA_PREFILL_UBATCH_SIZE=2048
BATCH_SIZE=2048 UBATCH_SIZE=1024
MAX_TOKENS=96 CANARY_REPEATS=2
LONG_CONTEXT_GATE=1
LONG_CONTEXT_CASE_IDS="lc-12288-early lc-16384-late lc-22000-middle"
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000
```

All four lanes passed the long-context gate, canary, prompt uniqueness, and
`cached_tokens=0`.

| Group | Median prefill tok/s by lane | Average |
| --- | ---: | ---: |
| control | `1055.095998`, `1056.824685` | `1055.960342` |
| left-bound on | `1109.552467`, `1126.127657` | `1117.840062` |

Delta: `+5.8600%` prefill.

This is the first host-derived SWA left-bound run to reproduce the earlier
long-prefill gain without an immediate short strict128 regression.

## Full512 Short Guard

The first full512 attempt was invalid:

- `data/gemma4-swa-leftbound-full512-ab-20260701T064742Z-swa-leftbound-full512-ab1.json`
- per-lane canaries passed, but no realistic-suite rows were produced;
- root cause: the runner was edited while the four shell processes were still
  reading it, and Bash hit `--api-mode: command not found`;
- do not use this as a model or patch result.

The valid plain/no-spec rerun completed:

- `data/gemma4-swa-leftbound-full512-ab-20260701T065024Z-swa-leftbound-full512-ab2.json`
- common env:

```bash
CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1
LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1
BATCH_SIZE=1024 UBATCH_SIZE=1024
MAX_TOKENS=512 CANARY_REPEATS=32
REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100
```

All four lanes passed canary, fresh validity, and `cached_tokens=0`. This was
not the protected headline decode recipe because it omitted the MTP/spec stack,
so it cannot prove no regression against the current `123.68 tok/s` record. It
is still useful as a no-spec service sanity check:

| Group | Median 1-100 tok/s by lane | Average |
| --- | ---: | ---: |
| control | `26.756230`, `26.719285` | `26.737757` |
| left-bound on | `26.733715`, `26.804329` | `26.769022` |

Delta: `+0.1169%` no-spec full512, effectively neutral.

The first required MTP full512 guard completed:

- `data/gemma4-swa-leftbound-mtp-full512-ab-20260701T065701Z-swa-leftbound-mtp-full512-ab1.json`
- common protected-record env includes the MTP draft model and the record stack:

```bash
EXTRA_LLAMA_ARGS="--parallel 1 --cache-ram 0 --spec-type draft-mtp \
  --spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
  --spec-draft-n-max 3 --spec-draft-device SYCL0 --spec-draft-ngl all \
  --spec-draft-type-k f16 --spec-draft-type-v f16 --spec-draft-n-min 2 \
  --spec-draft-p-min 0.0475 --no-spec-draft-backend-sampling \
  --spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0"
GGML_SYCL_DISABLE_OPT=0
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
POLL=100
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1
LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7
LLAMA_MTP_DRAFT_FAST_ARGMAX=1
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1
LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1
LLAMA_SYCL_F16_P021_SMALL_NCOLS=1
LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
```

All four lanes passed canary, fresh validity, and `cached_tokens=0`.

| Group | Median 1-100 tok/s by lane | Average |
| --- | ---: | ---: |
| control | `118.076875`, `117.832396` | `117.954636` |
| left-bound on | `116.805372`, `112.557713` | `114.681543` |

Delta: `-2.7749%` against the protected MTP recipe.

Because the first assignment used GPUs `0/2` as control and `1/3` as
candidate, a cross-over was required before final judgment.

MTP full512 cross-over, same low threshold (`>1`, effectively applies to MTP
decode):

- `data/gemma4-swa-leftbound-mtp-full512-xover-20260701T065946Z-swa-leftbound-mtp-full512-xover1.json`

| Group | Median 1-100 tok/s by lane | Average |
| --- | ---: | ---: |
| control | `123.805242`, `117.226111` | `120.515677` |
| left-bound on | `120.550137`, `119.520895` | `120.035516` |

Delta: `-0.3984%`.

Combined with the first assignment, applying the left-bound path to MTP decode
is not acceptable. It is a repeated mild regression and cannot be promoted.

### Threshold Isolation

The source was changed to make the query threshold configurable:

```bash
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=<N>
```

The first configurable-threshold build used an explicit `MIN_Q=128`. That
still affected ordinary realistic prompt prefill and was not acceptable:

- `data/gemma4-swa-leftbound-minq128-mtp-full512-ab-20260701T071955Z-swa-leftbound-minq128-mtp-full512-ab1.json`

| Group | Median 1-100 tok/s by lane | Average |
| --- | ---: | ---: |
| control | `121.332909`, `119.201922` | `120.267416` |
| left-bound on | `114.683098`, `111.538754` | `113.110926` |

Delta: `-5.9505%`. Do not use `MIN_Q=128` for the protected MTP service.

The viable threshold is `MIN_Q=2048`, which leaves short realistic prompt
prefill and MTP decode alone while still covering large long-context prefill.
The source patch now defaults the threshold to `2048` when
`LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1` is enabled without an explicit
`LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q`.

MTP full512 A/B:

- `data/gemma4-swa-leftbound-minq2048-mtp-full512-ab-20260701T072233Z-swa-leftbound-minq2048-mtp-full512-ab1.json`

| Group | Median 1-100 tok/s by lane | Average |
| --- | ---: | ---: |
| control | `118.117549`, `114.836552` | `116.477051` |
| left-bound on | `119.082933`, `117.501125` | `118.292029` |

Delta: `+1.5582%`.

MTP full512 cross-over:

- `data/gemma4-swa-leftbound-minq2048-mtp-full512-xover-20260701T073012Z-swa-leftbound-minq2048-mtp-full512-xover1.json`

| Group | Median 1-100 tok/s by lane | Average |
| --- | ---: | ---: |
| control | `117.377872`, `114.443211` | `115.910541` |
| left-bound on | `116.109348`, `116.087545` | `116.098447` |

Delta: `+0.1621%`.

All MTP `MIN_Q=2048` lanes passed canary, fresh-response validity,
`cached_tokens=0`, and headline Q8 eligibility. Treat the small positive
deltas as noise; the important result is no detected short-decode regression.

## Min-Q 2048 Long-Context Repeat

The final service lane uses:

```bash
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048
```

Long-context A/B:

- `data/gemma4-swa-leftbound-minq2048-long-ab-20260701T072452Z-swa-leftbound-minq2048-long-ab1.json`

| Group | Median prefill tok/s by lane | Average |
| --- | ---: | ---: |
| control | `928.756837`, `933.410415` | `931.083626` |
| left-bound on | `1093.770310`, `1105.289689` | `1099.529999` |

Delta: `+18.0914%`.

Long-context cross-over:

- `data/gemma4-swa-leftbound-minq2048-long-xover-20260701T072733Z-swa-leftbound-minq2048-long-xover1.json`

| Group | Median prefill tok/s by lane | Average |
| --- | ---: | ---: |
| control | `917.060447`, `924.780512` | `920.920480` |
| left-bound on | `1109.495759`, `1112.799828` | `1111.147793` |

Delta: `+20.6562%`.

All long-context `MIN_Q=2048` lanes passed the long-context gate, exact JSON
retrieval quality, canary, prompt uniqueness, and `cached_tokens=0`.

## Decision

Promote only as an **experimental long-context service optimization**, not as a
headline decode record:

- use `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`;
- set `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`, or rely on the
  current patch default of `2048`;
- keep it disabled for headline short-decode record claims unless the run
  explicitly uses the `MIN_Q=2048` guard and passes the fixed realistic suite;
- do not use a low threshold such as `MIN_Q=128` for MTP decode or ordinary
  short-prompt service because it regresses the protected MTP lane.
