# Gemma 4 26B Q8: no-bonus verifier row, n_max=4 negative

Date: 2026-06-28

## Result

Run:

- `data/gemma4-q8-gpu1-nobonusrow-n4-screen128-20260628T194001Z/summary.json`
- strict realistic suite, `MAX_TOKENS=128`, each prompt once, `cached_tokens=0`
- canary: pass, `128` rows
- validity: pass, fresh-response

Metrics:

- median tokens 1-100 after TTFT: `83.06365121638683 tok/s`
- p10 tokens 1-100 after TTFT: `72.36084817045743 tok/s`
- mean tokens 1-100 after TTFT: `82.95635729740759 tok/s`
- full-128 after TTFT median: `83.02304544689271 tok/s`
- wall full-128 median: `73.78256648587822 tok/s`
- TTFT median: `178.87196101946756 ms`

Baseline comparison:

- current valid strict full512 best:
  `98.34046474459183 tok/s` median 1-100 after TTFT
- prior no-bonus `n_max=3` screen:
  `84.9195 tok/s`

Decision: reject. Do not promote or submit.

## Config

Same current VDR2/F16-p021/bulk-sampled-ID quality lane except:

- `LLAMA_SPEC_VERIFY_NO_BONUS_ROW=1`
- `--spec-draft-n-max 4`

Important matching baseline knobs:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- `--spec-draft-n-min 2`
- `--spec-draft-p-min 0.0475`
- `--no-spec-draft-backend-sampling`
- `--spec-draft-threads 32`
- `--spec-draft-threads-batch 32`
- `--ctx-checkpoints 0`
- `UBATCH_SIZE=1024`, `BATCH_SIZE=1024`
- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`
- `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`
- `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`

## Patch Shape Tested

The temporary source patch added `LLAMA_SPEC_VERIFY_NO_BONUS_ROW`:

- `common_sampler_sample_and_accept_n(..., bool no_bonus=false)` allowed
  `idxs.size() == draft.size()` and skipped bonus-token sampling when enabled.
- `server_slot::handle_last_sampled_token()` still added the final draft token
  to the target batch but marked it `output=false`, so the verifier batch did
  not produce a logits/sampled-id row for that final draft token.
- `finish_speculative_accept()` attempted to account for no-bonus full accept
  by treating `accepted.size()==n_draft && accepted.back()==slot.spec_draft.back()`
  as full draft acceptance.

The source hook was reverted after this result. The harness may continue to log
`LLAMA_SPEC_VERIFY_NO_BONUS_ROW` for future negative-result reproduction, but
the runtime behavior should not remain active.

## Lesson

Plainly deleting the bonus verifier output row is not a valid performance win.
Even at `n_max=4`, the loss of the normal bonus-token pipeline more than
offsets the saved verifier output row. This is consistent with the earlier
`n_max=3` no-bonus negative.

The viable direction is not "no bonus"; it is "cheaper bonus": keep the emitted
bonus-token behavior, but compute the bonus decision with less target work
where possible, for example a head-only bonus over an already-produced hidden
state or another graph-compatible way to avoid the full extra verifier row.
