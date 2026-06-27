# Gemma4 26B Q8 RMS-Reuse Config Neighborhood Screen (2026-06-27 08:58 UTC)

## Context

This sweep screened small launcher/configuration moves around the current valid
fresh-response record:

- record run:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
- fresh row0 headline: `104.30919255569083 tok/s` after TTFT;
- wall row0: `90.85119259916031 tok/s`;
- canary: `6144/6144`;
- LocalMaxxing id: `cmqw1tgzx0366qr01g4lkv7f1`.

All runs below used the current record source stack and the fresh-response
validity policy: row0 only is the headline because the benchmark prompt is
repeated; later rows are support-only even when `cached_tokens=0`.

Common identity:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one Intel Arc Pro B70 per run, one model replica per GPU;
- f16 KV, `CTX_SIZE=8192`, graph enabled, VMM disabled;
- `MTP_N_MAX=7`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`;
- `--no-spec-draft-backend-sampling`, `--ctx-checkpoints 0`;
- `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`;
- `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`;
- `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`;
- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`;
- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`;
- `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`;
- `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`;
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`;
- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`;
- `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`;
- `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`;
- `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`.

Screen depth: `CANARY_REPEATS=16` (`64/64` canary rows) and
`BENCH_REPEATS=2`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`,
`BENCH_PROMPT_MODE=filled-long`.

## Results

| Run | GPU | Batch / UBatch | Canary | Fresh row0 tok/s | Wall row0 tok/s | Support mean tok/s | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-rmsreuse-control-repeat-20260627T085803Z/` | 0 | `1024 / 768` | `64/64` | `104.41654643214254` | `90.46243398997564` | `104.34554246502323` | Candidate only; same config as record, full validation required. |
| `data/gemma4-q8-gpu1-rmsreuse-ub704-20260627T085803Z/` | 1 | `1024 / 704` | `64/64` | `104.15826087469326` | `90.39266985001146` | `104.04906675927657` | Loss versus record. |
| `data/gemma4-q8-gpu2-rmsreuse-ub832-20260627T085803Z/` | 2 | `1024 / 832` | `64/64` | `102.21583527655493` | `88.69959964708298` | `103.2625164982752` | Loss versus record. |
| `data/gemma4-q8-gpu3-rmsreuse-b1536u768-20260627T085803Z/` | 3 | `1536 / 768` | `64/64` | `104.31417455378934` | `90.40806035416419` | `104.23988084709634` | Tiny screen-only edge; below GPU0 candidate and likely noise. |

All four summaries reported `cached_tokens=[0, 0]` and
`headline_eligible_for_gemma_q8=true`.

## Interpretation

The actual config variants did not create a new optimization lane:

- `UBATCH_SIZE=704` is below record;
- `UBATCH_SIZE=832` is worse for row0 and noisier;
- `BATCH_SIZE=1536` with `UBATCH_SIZE=768` is essentially flat and only
  `+0.004982 tok/s` over the prior full record on a two-row screen.

The only meaningful candidate is the GPU0 control repeat at `104.416546 tok/s`.
Because it is the same config as the existing full record and only a shallow
screen, treat it as variance unless the matching full validation
(`CANARY_REPEATS=1536`, `BENCH_REPEATS=8`) also beats `104.30919255569083`.

## Follow-Up

- Full validation launched as
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-rerun-20260627T090038Z/`.
  It passed the promotion-depth chat canary (`1536` repeats / `6144` rows) but
  did **not** produce a benchmark result: the harness exited before bench with
  `unexpected EOF while looking for matching '"'`. The current script now
  passes `bash -n`, so this was likely a transient edit-state failure while the
  run was active. Treat the rerun as a useful canary artifact only, not as a
  record attempt.
- Do not submit any of the four screen runs to LocalMaxxing.
- The sweep outcome is config-neighborhood noise. Keep the next engineering
  focus on verifier economics / Q8 expert matmul rather than batch/ubatch
  tuning.
