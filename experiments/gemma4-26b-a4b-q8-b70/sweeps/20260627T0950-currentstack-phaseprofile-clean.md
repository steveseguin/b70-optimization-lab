# Gemma4 26B Q8 Current-Stack Phase Profile, Clean Run (2026-06-27 09:50 UTC)

## Question

Where is time still going in the current Gemma4 26B Q8 record stack, after
route timing and prequant route-row experiments showed that routed-row plumbing
is not the main bottleneck?

Current valid one-B70 fresh-response record for comparison:

- run:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
- fresh row0 after TTFT: `104.30919255569083 tok/s`
- wall row0: `90.85119259916031 tok/s`
- canary: `6144/6144`
- LocalMaxxing: `cmqw1tgzx0366qr01g4lkv7f1`

This profile is diagnostic only. It used `MAX_TOKENS=128`, canaries before the
bench request, and profiling flags, so its throughput is not a record result.

## Run

- data:
  `data/gemma4-q8-gpu1-currentstack-phaseprofile-clean-20260627T095056Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu1-currentstack-phaseprofile-clean-20260627T095056Z.server.log`
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- common identity: current record stack, `UBATCH_SIZE=768`,
  `MTP_N_MAX=7`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`, graph enabled, VMM off,
  route cache on, RMS reuse on, fused assistant output argmax on, verifier
  backend argmax IDs on
- profiling flags: `LLAMA_MTP_DRAFT_PROFILE=1`,
  `LLAMA_MTP_DECODE_PHASE_PROFILE=1`
- canary: `16/16`
- diagnostic row: `99.10261505564615 tok/s` after TTFT on a 128-token bench
  row, not headline-comparable

Important launcher identity detail:

- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`
- `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=<unset>`
- `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`

Do not infer from the unset verifier fused-output flag that it is an untested
easy win. Prior screens already rejected the target fused-output path as much
slower:

- `data/gemma4-q8-gpu1-fusedtargetguard-screen-20260624T224213Z/`:
  `16/16`, `89.366338 tok/s`
- `data/gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin0136-fusedoutargmax-screen-20260625T034837Z/`:
  `512/512`, `90.428922 tok/s`

## Final Profile Snapshot

MTP acceptance:

- generated drafts: `50`
- accepted drafts: `50`
- generated draft tokens: `350`
- accepted draft tokens: `264`
- mean accepted length: `6.28`
- per-position acceptance:
  `(1.000, 0.980, 0.880, 0.780, 0.620, 0.520, 0.500)`

Target decode phase:

- calls: `85`
- tokens: `1609`
- total: `6613.356 ms`
- `process_ubatch_ms`: `6479.261`
- `post_extract_ms`: `127.178`
- `sampled_extract_ms`: `127.149`
- per-token: `4.110 ms`

Draft decode phase:

- calls: `51`
- tokens: `52`
- total: `333.856 ms`
- `process_ubatch_ms`: `305.661`
- `post_extract_ms`: `25.914`
- `h_nextn_extract_ms`: `5.553`
- `sampled_extract_ms`: `20.353`
- per-token: `6.420 ms`

The direct path remains ID-only:

- `fast_topk_calls=50`
- `vocab_scanned=0`
- `sampler_calls=0`
- `hidden_rows=0`
- `handoff_rows=0`
- `avg_top1_p=1.000000`
- `avg_logit_gap=0.000000`

## Interpretation

The remaining material cost is target/verifier `process_ubatch`, not route
setup, sampler overhead, logits host transfer, or draft precision. In this
clean run target `process_ubatch_ms` is about **21x** draft
`process_ubatch_ms` (`6479 / 306`). Sampled-ID extraction is visible but small
relative to model compute.

This aligns with:

- `20260627T0850-mulmatid-route-timing.md`: decode-like routed-MoE samples are
  `93-97%` expert matmul body, only `~18-21 us` route overhead;
- `20260627T0939-prequant-route-rows-negative.md`: guarded prequant
  route-row/direct-MMVQ path was correct but below record at
  `104.0281678873085 tok/s`;
- `20260627T0614-direct-argmax-top2-scores.md`: real top2 confidence made deep
  unrolls valid but much slower, best `84.58980110621081 tok/s`.

## Decision

Do not repeat these lanes unchanged:

- p-min / gap-only sweeps on the current direct-ID path;
- blind direct-unroll depth increases;
- MTP draft quant changes;
- route/gather/scatter cleanup around `MUL_MAT_ID`;
- prequant route-row direct MMVQ without a new kernel that avoids the extra
  prequant pass;
- existing `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` target path.

Next useful work must change target/verifier economics. Plausible but still
unproven directions:

1. a new exact verifier candidate-vs-max LM-head op that avoids materializing
   full logits while preserving greedy correctness;
2. a narrow expert-matmul improvement for the actual Q8 `MUL_MAT_ID` body, not
   route setup;
3. a fresh-valid speculation source that increases accepted tokens without
   using repeated-output history.

