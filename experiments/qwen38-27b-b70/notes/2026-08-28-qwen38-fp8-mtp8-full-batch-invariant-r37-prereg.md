# Qwen3.8 FP8 MTP8 full batch-invariant R37 diagnostic

Date: 2026-08-28

R36b validly reached packed per-row FP8, RMSNorm, and GDN treatments and moved
the first `risk-register` target divergence from token 128 to token 441, but
did not achieve exact output. R37 asks whether the remaining packed-shape
difference is in a runtime operation covered by vLLM's global batch-invariant
mode, such as attention or a collective.

Keep the complete R36b eager profile fixed and change only
`VLLM_BATCH_INVARIANT=1`. Use the same R36 image, MTP8→MTP1 schedule, TP2,
empty runtime cache, 1,024-token singleton service, serial packed FP8,
serial packed RMSNorm, and serial GDN. Startup must explicitly accept the
batch-invariant backend; the R36 packed-FP8 and both R35 GDN markers must fire
on the request.

Run only the unchanged `risk-register` 512-token, seed-42, temperature-zero,
top-p-one, token-ID, cache-zero sentinel. Pass requires 512/512 equality with
qualified MTP0 R15. Backend refusal, missing markers, or any divergence closes
this treatment. This remains correctness-only and cannot publish a speed.

## Result

Pinned vLLM `ac7509e2b` refused startup because `GDN_ATTN` did not declare
batch-invariant support. No request or GPU inference ran. R37b separately
preregistered and tested the lab's existing fail-closed capability declaration.
