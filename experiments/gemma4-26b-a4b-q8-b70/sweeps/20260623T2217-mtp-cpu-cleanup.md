# 2026-06-23T2217 - MTP CPU Cleanup Record

Goal: reduce exact CPU overhead in the fresh-response Gemma 4 26B A4B Q8
draft-MTP lane without changing model precision, draft source, sampler quality,
or validity rules.

## Patch

Patch artifact:

- `patches/gemma4-llamacpp-mtp-cpucleanup-record-stack-20260623.patch`

The patch file is the full current llama.cpp source diff from upstream
`c926ad098`, because the local tree already includes the promoted fast-top-k,
profiling, and verifier helper stack. The new incremental CPU-cleanup delta in
this experiment is:

- direct single-seq `batch_add_one()` fills in the MTP loop instead of hot
  `common_batch_add(..., { seq_id }, ...)` temporary vector construction;
- sequence range discovery in `process()` changed from `n_tokens * n_seq` scan
  to direct `batch_in.seq_id[k][0]`;
- `drafting` vector made persistent instead of allocated per `draft()`;
- each `verify_h` buffer reserves `(n_max + 1) * n_embd`.

No source-level quality shortcut is introduced. The target model still verifies
the draft-MTP proposal.

## Fresh-Response Validity

This is a valid fresh-response draft-MTP result:

- draft source is the Gemma MTP draft model for the current request;
- no `ngram`, history table, response reuse, or warmed continuation is used for
  the promoted `tok_s_after_ttft` result;
- benchmark rows report `cached_tokens=0`;
- the first measured request is reported separately and is in-family with the
  mean.

## Runs

Smoke:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-cpucleanup-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T221453Z`
- canary: 128/128 pass
- mean after TTFT: `91.64525045277611 tok/s`
- wall mean: `71.22575548109108 tok/s`
- summary:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-cpucleanup-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T221453Z/summary.json`

Full promotion run:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-cpucleanup-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T221705Z`
- canary: 384/384 pass
- mean after TTFT: `91.89889994139259 tok/s`
- first request after TTFT: `91.87689288153598 tok/s`
- wall mean: `71.48537236571929 tok/s`
- actual benchmark shape: 588 prompt tokens, 512 output tokens
- prompt cache: `cached_tokens=0`
- summary:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-cpucleanup-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T221705Z/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-cpucleanup-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T221705Z.server.log`

## Decision

Promote as the current fresh-response one-B70 Q8 record. It supersedes the
previous LocalMaxxing-approved fast-top-k record
`cmqqsecuk01azqo018ahv0i1s` (`91.61894213332073 tok/s`).

Next fresh-valid stack to test: combine this CPU-cleanup patch with the prior
near-best runtime knobs `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, and
`POLL=100`.
