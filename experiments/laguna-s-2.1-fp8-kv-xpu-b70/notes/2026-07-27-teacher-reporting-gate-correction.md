# FP8 q1 teacher reporting-gate correction

Date: 2026-07-27 America/Toronto

Run:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/fp8-kv/teacher-q1-20260727T135446Z`

The first target-only FP8 teacher completed all 13 cold prompts and wrote its
full benchmark before the harness failed. The failure was not a model,
correctness, cache, or teardown failure. The harness required four copies of:

```text
Using Flash Attention backend
```

vLLM emits that backend-selection message through a once-only logger, so the
correct TP4 count is one. In contrast, the new post-load scale audit is emitted
by every worker and correctly appeared four times.

Raw result:

- 13 prompts, each invoked once;
- each completion has at least 100 returned token IDs;
- every row has `cached_tokens=0`;
- benchmark final gate passed;
- four target runtime scale-audit PASS records with the pinned calibrated
  digest;
- one FlashAttention selection marker;
- engine resolved `kv_cache_dtype=fp8`;
- no runtime errors;
- worker cleanup and post-idle capture both passed.

The artifact remains read-only with `original_status=2`; it is not silently
rewritten to PASS. The corrected standalone audit classifies its `bench.json`
as an admissible target-only FP8 oracle and explicitly records the original
failure. It is not a throughput record. Future legs require exactly one
backend-selection marker and four per-rank scale-audit records.
