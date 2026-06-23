# Gemma 4 26B A4B Q8: MTP Fast Draft Sampler-State Skip

Date: 2026-06-23

## Question

The promoted MTP path uses `LLAMA_MTP_DRAFT_FAST_TOPK=1`, which bypasses the
normal draft sampler and directly scans the already-materialized host logits.
This experiment tested whether skipping unused draft sampler state updates in
the MTP fast path improves fresh-response throughput.

Patch snapshot:
`patches/gemma4-llamacpp-mtp-skip-fast-sampler-state-neutral-20260623.patch`

Source tree tested:
`/home/steve/src/llama.cpp-latest-gemma`, llama.cpp `c926ad098`, on top of
the existing local Gemma research patches.

## Validity

This is a fresh-response MTP result, not history-accelerated n-gram reuse.
The benchmark prompt reports `cached_tokens: 0`. The repeated benchmark outputs
are deterministic, but the draft source is the model's MTP draft model and does
not depend on having previously observed the same continuation.

## Runs

Smoke:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-skipsamplerreset-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T213227Z`
- summary:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-skipsamplerreset-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T213227Z/summary.json`
- canary: 128/128
- fresh-response throughput after TTFT: mean `91.652 tok/s`, first request
  `92.514 tok/s`

Full validation:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-skipsamplerreset-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T213421Z`
- summary:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-skipsamplerreset-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T213421Z/summary.json`
- canary: 384/384
- fresh-response throughput after TTFT: mean `91.426 tok/s`, first request
  `91.353 tok/s`
- wall throughput mean: `71.163 tok/s`

## Decision

Neutral / slight loss. The full run did not beat the promoted valid record
(`91.619 tok/s` mean after TTFT), so the patch was not promoted and the source
tree was reverted to the prior research baseline.

This result supports the current bottleneck diagnosis: sampler bookkeeping is
not the meaningful cost. The next useful patch needs to attack full-vocab host
logits transport for MTP draft rows or reduce draft decode work.
