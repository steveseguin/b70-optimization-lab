# Gemma 4 26B Q8: Spec-Profile Diagnostic and Next Lanes

Date: 2026-07-02

## Purpose

Capture a fresh-response spec-profile run for the current Gemma 4 26B A4B Q8
record recipe and use it to choose the next optimization lane. This is a
diagnostic run only, not a LocalMaxxing submission candidate.

## Run

Command:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=18941 LABEL=gemma4-q8-gpu0-specprofile-20260702T053810Z \
CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1 \
CANARY_REPEATS=8 MAX_TOKENS=128 REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
LLAMA_SERVER_SPEC_PROFILE=1 \
bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Evidence:

- `data/gemma4-q8-gpu0-specprofile-20260702T053810Z/summary.json`
- `data/gemma4-q8-gpu0-specprofile-20260702T053810Z/realistic-suite.json`
- `data/gemma4-q8-gpu0-specprofile-20260702T053810Z/chat-canary.json`
- raw server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-specprofile-20260702T053810Z.server.log`

## Validity

- fixed realistic prompt suite
- each prompt sent once as a cold response
- `cached_tokens=0` for every prompt
- no n-gram/history acceleration, response reuse, prompt cache reuse, context
  checkpoints, or warmed repeated prompts
- Q8 target/verifier lane unchanged; Q4_0 MTP draft only
- canary: `32/32` rows pass
- realistic final gate: pass

The run is headline-eligible in policy terms, but it is below the current
record and was run primarily to inspect the timing profile.

## Metrics

Primary metric, generated tokens 1-100 after TTFT:

- median: `117.22735440926772 tok/s`
- p10: `108.33082484629 tok/s`
- mean: `118.40998205892453 tok/s`

Full generated output after TTFT:

- median: `116.08782890514314 tok/s`
- p10: `104.95154395659344 tok/s`
- mean: `117.07139285956792 tok/s`

Wall-clock full-output throughput:

- median: `99.63037979573883 tok/s`
- p10: `90.73417555104032 tok/s`
- mean: `99.69751780712829 tok/s`

TTFT:

- median: `179.3142100214027 ms`
- p10: `172.6448519155383 ms`
- mean: `190.23526317323558 ms`

Decision: **diagnostic only / no record**. The current record remains
`124.97714084813418 tok/s` from
`data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.

## Profile Breakdown

Final cumulative server profile lines:

- draft: `1891.391 ms`, `752` calls, `1948` draft tokens,
  `2.515 ms/call`
- target decode: `19876.893 ms`, `752` calls, `4731` tokens,
  `26.432 ms/call`, `4.201 ms/token`
- target prompt: `6593.777 ms`, `88` calls, `2119` prompt tokens,
  `74.929 ms/call`, `3.112 ms/token`
- target generation: `13283.116 ms`, `664` calls, `2612` generation tokens,
  `20.005 ms/call`, `5.085 ms/token`
- process/sample/common-accept/emit overheads are all negligible
- draft acceptance: `651` generated drafts, `511` accepted drafts,
  `1948` draft tokens, `1204` accepted tokens, mean acceptance length `2.85`,
  acceptance by position `(0.785, 0.610, 0.455)`

## Interpretation

The profile rules out several tempting but low-value directions:

- Draft and accept bookkeeping are too small to explain the remaining gap.
- More config roulette around `p_min`, sampler copy paths, or MTP wrapper
  plumbing is unlikely to create a durable record.
- Prior adaptive MTP, bonus-row, late-head, sampled-egress, one-column LM-head,
  no-bonus, and top1-epilogue variants are already closed negative or
  instrumentation failures in the sweep ledger.

The useful cost centers are still target-side decode and prompt/prefill work.
Short-decode improvements likely require a real backend change that reduces
verified LM-head / target-generation work without breaking the full-match bonus
pipeline. Service/prompt improvements should remain separate from the short
decode record and must preserve short decode speed.

## Next Lanes

1. **Prompt/service lane: exact FlashAttention right-bound / KV-max work.**
   Investigate whether the current mask-derived `KV_max` scan can be replaced
   or bypassed for large global causal prefill with an exact host/analytic
   bound, while keeping SWA and chunked-prefill correctness. This is
   service/prefill only; require exact long-context validation and a short
   decode guard before promotion.

2. **Short-decode lane: exact row-adaptive verifier design.**
   Only revisit accept-prefix / row economics if the backend can avoid real
   LM-head work for skipped rows while preserving one target decode boundary
   and the full-match bonus token. Serialized row-by-row heads and post-hoc
   masking are closed negative.

3. **No LocalMaxxing submission from this run.**
   Submit only if a future full realistic cold-suite run beats the current
   `124.97714084813418 tok/s` record with `cached_tokens=0` on every prompt.
