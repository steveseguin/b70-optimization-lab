# 2026-06-27T12:16Z - fused final post-norm/residual screen

## Idea

Test a small Gemma4 FFN glue fusion:

- env flag: `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`
- source tree: `/home/steve/src/llama.cpp-gemma-record-repro-c926`
- binary: `build-sycl-b70-aot-bmg-g31/bin/llama-server`
- implementation adds `GGML_OP_RMS_NORM_SCALE_ADD`, used in `src/models/gemma4.cpp`
  to fuse final `rms_norm(branch_sum) * ffn_post_norm + attn_out`.

Expected upside from audit: small, roughly `+0.3` to `+1 tok/s` if the saved node
launch mattered. The patch is env-gated and default-off.

## Result

Run:

- label: `gemma4-q8-gpu0-fused-final-postnorm-residual-screen-20260627T121609Z`
- summary: `data/gemma4-q8-gpu0-fused-final-postnorm-residual-screen-20260627T121609Z/summary.json`
- canary: `16/16` repeats, `64/64` rows pass
- fresh-response headline: `102.57501996168193 tok/s` after TTFT
- wall throughput: `89.57948201393457 tok/s`
- cached tokens: `0`

Current valid record for this lane is `104.30919255569083 tok/s` from
`gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z`, so
this is a negative screen and was not promoted to full confirmation.

## Decision

Paired same-time controls confirm this is not useful for the main lane:

| label | flag | ubatch | fresh row0 tok/s | canary |
| --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-paired-control-ub768-20260627T121850Z` | off | 768 | `105.25176679186049` | pass |
| `gemma4-q8-gpu1-paired-fusedfinal-ub768-20260627T121850Z` | on | 768 | `102.19110272507926` | pass |
| `gemma4-q8-gpu2-paired-control-ub832-20260627T121850Z` | off | 832 | `104.07526037623865` | pass |
| `gemma4-q8-gpu3-paired-fusedfinal-ub832-20260627T121850Z` | on | 832 | `104.32103165513749` | pass |

The `UBATCH=832` fused screen is only `+0.012 tok/s` over the official record
and the same `UBATCH=832` lane already failed full confirmation
(`102.402 tok/s`), so it was not promoted. Keep the patch as a failed experiment
artifact because the op may be reusable for a larger branch-level fusion, but do
not enable it for headline runs.
