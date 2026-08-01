# Laguna target inline prefix full-gate bisection

Date: 2026-08-01 America/Toronto

Status: **preregistered non-scored bisection; no score is authorized.**

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
