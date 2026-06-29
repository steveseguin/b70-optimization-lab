# Gemma 4 26B Q8 Defer Verifier Pending-H Copy

Date: 2026-06-29

## Idea

The current record stack uses `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`, but the MTP
`process()` path still copies the final verifier row into `pending_h` for
verifier batches. The follow-up idea was to skip that copy for verifier batches
under `LLAMA_MTP_DEFER_VERIFIER_PENDING_H_COPY=1`, relying on `accept()` to
copy the exact accepted row before the next draft.

Expected upside was small but low-risk: remove a redundant verifier-side hidden
state copy without changing target verification or the bonus pipeline.

## Patch Artifacts

- Source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/20260629-defer-verifier-pending-h-copy-current-stack.patch`
  (current dirty llama.cpp Gemma research stack context, not an isolated
  upstream patch).
- Harness identity patch:
  `patches/gemma4-26b-a4b-q8-b70/20260629-defer-verifier-pending-h-copy-harness-identity.patch`.

Server logs confirm the flag was active in the flag-on lanes:

- `defer_verifier_pending_h_copy=1` in the MTP constructor log for GPU1/GPU3
  first screen and GPU0/GPU2 cross-over screen.

## Run Identity

All lanes used the current Gemma Q8 record stack:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one complete model replica per B70;
- `--spec-draft-n-max 3 --spec-draft-n-min 2 --spec-draft-p-min 0.0475`;
- `--ctx-checkpoints 0`, no prompt/KV/response/ngram/history reuse;
- `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`;
- graph enabled, VMM off, f16 KV;
- `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`;
- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`;
- `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`;
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`;
- `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1`.

Gate: fixed realistic cold suite, `MAX_TOKENS=128`, `CANARY_REPEATS=32`.
Every lane passed the fresh-response validity gate with `cached_tokens=0` and
passed the canary.

## Results

First paired screen (`20260629T203527Z`):

| GPU | Variant | Median tok/s 1-100 | p10 | Mean | Valid |
| --- | --- | ---: | ---: | ---: | --- |
| 0 | control | 115.186033 | 105.250697 | 113.886716 | pass |
| 1 | defer pending-h | 118.109598 | 103.232145 | 116.371183 | pass |
| 2 | control | 113.343527 | 101.880240 | 113.437361 | pass |
| 3 | defer pending-h | 110.133751 | 102.463188 | 112.878336 | pass |

Cross-over screen (`20260629T203707Z`):

| GPU | Variant | Median tok/s 1-100 | p10 | Mean | Valid |
| --- | --- | ---: | ---: | ---: | --- |
| 0 | defer pending-h | 111.143635 | 105.551568 | 113.436730 | pass |
| 1 | control | 113.074649 | 107.086622 | 113.452323 | pass |
| 2 | defer pending-h | 110.300256 | 101.965620 | 111.742251 | pass |
| 3 | control | 116.208496 | 98.965666 | 113.931489 | pass |

Aggregate strict128 medians:

- controls: `[115.186033, 113.074649, 113.343527, 116.208496]`, mean
  `114.453176`;
- flag-on: `[111.143635, 118.109598, 110.300256, 110.133751]`, mean
  `112.421810`.

## Decision

Closed negative. The first GPU1 flag-on lane looked promising, but the
cross-over invalidated it: when moved to GPU0/GPU2 the flag lost, and GPU3
control became the best lane. Do not run full512 promotion and do not submit to
LocalMaxxing.

The result reinforces the profile conclusion: verifier target decode is the
bottleneck, while host/process/handoff copies are too small and noisy to be a
record-breaking lever in the current stack.
