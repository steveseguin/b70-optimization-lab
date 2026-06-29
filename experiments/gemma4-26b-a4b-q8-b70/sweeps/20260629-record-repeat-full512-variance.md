# 2026-06-29 Full512 Record Repeat Variance

## Goal

Repeat the current promoted Gemma 4 26B A4B Q8 one-B70 record recipe across all
four B70 GPUs under the realistic final gate. This was a confirmation/variance
check after the `115.8466634928202 tok/s` LocalMaxxing submission, not a new
optimization attempt.

## Recipe

Promoted reproduction wrapper:

```bash
repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Important identity:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`
- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`
- `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`
- `--spec-draft-n-max 3 --spec-draft-n-min 2 --spec-draft-p-min 0.0475`
- `UBATCH_SIZE=1024`, `--ctx-checkpoints 0`
- `REALISTIC_GATE=1 MAX_TOKENS=512 REALISTIC_METRIC_TOKENS=100`

## Results

All four runs passed the realistic gate, had `cached_tokens=0` for every prompt,
and passed the 2048-row canary body. None beat the current record.

| label | median tok/s 1-100 | p10 | mean | gate | canary |
|---|---:|---:|---:|---:|---:|
| `gemma4-q8-gpu0-record-repeat-full512-20260629T164251Z` | `113.81030306585805` | `101.90991122791674` | `114.0702464214753` | pass | `2048/2048` |
| `gemma4-q8-gpu1-record-repeat-full512-20260629T164251Z` | `113.22741933370843` | `106.48913763356119` | `115.3584549852613` | pass | `2048/2048` |
| `gemma4-q8-gpu2-record-repeat-full512-20260629T164251Z` | `107.32906366406199` | `101.62344788667554` | `110.20100731535541` | pass | `2048/2048` |
| `gemma4-q8-gpu3-record-repeat-full512-20260629T164251Z` | `114.82854728313862` | `107.25962029479567` | `116.92907233970607` | pass | `2048/2048` |

## Decision

No LocalMaxxing submission: the best repeat (`114.82854728313862`) is below the
current valid record (`115.8466634928202`). Keep `115.8466634928202 tok/s` as
the headline and treat this sweep as useful variance evidence for the promoted
recipe.

## Later 2026-06-29 Refresh

A second four-GPU refresh was run before the EOG/SPEC_HEAD patch screen to
anchor the current binary/host variance. Same promoted recipe, same fixed
realistic cold suite, `MAX_TOKENS=512`, `REALISTIC_METRIC_TOKENS=100`,
`cached_tokens=0` every row, and 2048 canary rows passed. None beat the record.

| label | median tok/s 1-100 | p10 | mean | full512 after-TTFT median | wall full512 median | TTFT median ms | gate | canary |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| `gemma4-q8-gpu0-record-refresh-full512-20260629T173232Z` | `111.21916062672508` | `99.78856875978933` | `111.56511798894492` | `105.58528513213375` | `101.67915279241663` | `180.547297000885` | pass | `2048/2048` |
| `gemma4-q8-gpu1-record-refresh-full512-20260629T173232Z` | `110.72061102442606` | `104.37974153293142` | `113.39530661856975` | `105.91216242026465` | `101.34245500867142` | `182.21637496026233` | pass | `2048/2048` |
| `gemma4-q8-gpu2-record-refresh-full512-20260629T173232Z` | `112.5375264355806` | `101.73740856532514` | `111.94601456975215` | `104.6920617829633` | `100.13362090325921` | `181.84104096144438` | pass | `2048/2048` |
| `gemma4-q8-gpu3-record-refresh-full512-20260629T173232Z` | `112.5154069781288` | `101.73899070213969` | `112.73396487351484` | `104.99013423926795` | `101.26572367005576` | `180.63995148986578` | pass | `2048/2048` |

Decision remains unchanged: no LocalMaxxing submission; keep
`115.8466634928202 tok/s` as the current valid Gemma Q8 headline.
