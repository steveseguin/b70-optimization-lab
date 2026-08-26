# Qwen3.8 FP8 dynamic MTP R3 p192 result

The 192-token service cap did **not** increase concurrent request residency.
R3 is closed before aggregate measurement under its ordered stop rule.

## Direct measurements

- R2 at max length 256: 12,595 reported cache tokens and **49.20×** maximum
  concurrency;
- R3 at max length 192: 9,446 reported cache tokens and **49.20×** maximum
  concurrency;
- excluded R3 conditioner: 59.330 tok/s after TTFT;
- first eligible fresh R3 single-user row: **82.564 tok/s after TTFT**;
- frozen single-user gate: **82.810 tok/s**.

The eligible row returned all 128 requested tokens after a 40-token prompt and
reported zero cached prompt tokens. It missed the gate by 0.246 tok/s. Per the
preregistration, the wrapper stopped before either c64 batch. R3 therefore has
no aggregate result.

## What this resolves

Reducing ordinary context capacity does not free speculative Mamba/GDN state
rows. vLLM reduced its displayed cache-token count in exact proportion to the
service length, leaving maximum sequence residency unchanged. The dynamic
service still reserves its configured maximum MTP2 state width even while
multi-request traffic selects MTP1.

The container stopped cleanly with no GDN crash or inference runtime error.
The next credible treatment is dynamic per-request Mamba speculative-state
allocation. The p192 route is closed; its missing c64 value must remain
explicitly unmeasured.

Raw evidence and checksums are in
`../data/qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r3-p192-20260826/`.
