# Laguna target inline prefix full-gate bisection

Date: 2026-08-01 America/Toronto

Status: **closed negative at prefix 24; captured target collectives are closed.
No score was run or authorized.**

Prefix 48 passed two 400-token requests but failed the broader gate: request 0
was exact for 512 tokens and request 1 diverged at token 0. The full-96 and
one-hole treatments also fail. The remaining bounded question is whether a
smaller prefix is robust across the entire 13-request service lifetime.

Run the same 13×512 non-scored gate at prefix 24, with required target
`122/121` and draft `14/13`. Preserve every raw response before validation and
retain all cache, speculation, activation, topology, and teardown checks.

- If prefix 24 fails, close captured target collectives; no further prefix
  bisection is justified.
- If prefix 24 passes all 13 requests, the next diagnostic limit is 36, then a
  midpoint bisection between the highest full-gate pass and lowest full-gate
  failure. Never retry an unchanged limit.
- A full-gate pass is still non-scored. It authorizes a separate score
  preregistration and a first-result cold score.

Any runtime/device error or dirty teardown stops the lane without recovery.
The fixed model, BF16 KV, width/depth, teacher, sampler, verification, prompts,
and cache policy remain unchanged.

## Result

Prefix 24 failed the first 512-token request. The service returned all 512
tokens with `cached_tokens=0` and a normally decaying speculative-acceptance
curve, but the first q=1 token mismatch was index 331 (`72` instead of `372`).
The treatment activated on all four ranks and produced exactly the
preregistered target `122/121` and draft `14/13` capture topology. There was no
runtime or device error, and teardown was clean:
`original_status=1 stop_status=0 worker_status=0 idle_status=0`.

Artifact:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-target-inline-prefix24-full-exactness-20260801T173202Z`.

Durable source and structured result:

- `patches/laguna-s-2.1-xpu-b70/vllm-laguna-target-inline-gather-prefix-bisection-b63557f78-20260801.bundle`;
- `data/laguna-target-inline-gather-prefix-bisection-negative-20260801.json`.

This satisfies the preregistered stop rule. No smaller prefix, endpoint score,
or additional fixed-address/lifetime variant is justified. Captured target
collectives remain a useful localization result but are closed as an
optimization route until a first-divergent-tensor trace explains the
model-specific replay dependency.
