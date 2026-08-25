# Qwen3.8 Q4_K_M TP2 exact-depth HTTP R1 result

Status: **qualified exact-depth profile**.

The single preregistered attempt completed all six active-context points on
the exact promoted Q4_K_M TP2 binary and model identity. Both B70s were used
with equal tensor split, F16 KV, target-only generation, one HTTP slot, prompt
cache disabled, and a 33,024-token configured capacity.

| Exact active prompt tokens | Decode tok/s | TTFT ms |
| ---: | ---: | ---: |
| 2,048 | 49.489490 | 1,945.046 |
| 4,096 | 49.010307 | 3,860.132 |
| 8,192 | 48.300393 | 7,861.681 |
| 16,384 | 47.030572 | 16,299.778 |
| 24,576 | 45.534561 | 25,347.311 |
| 32,768 | 44.437281 | 35,058.738 |

Every row returned exactly 128 token IDs, reported the exact requested prompt
length, had zero cached prompt tokens, and passed the no-truncation/context
gate. The server cleaned up and both cards returned idle. The accepted source
retained exactly its pre-existing three-file patch state.

The fixture is evidence grade C: repeated registered tokens for exact context
shape, not natural prose. These measurements are additive to the package's
realistic short-prompt headline. There is no zero-context point and no value
is interpolated or extrapolated.

Evidence:

- [preregistration](2026-08-25-qwen38-q4km-tp2-http-depth-r1-preregistration.md)
- [structured summary](../data/qwen38-q4km-tp2-http-depth-20260825-r1-attempt1/summary.json)
- [complete retained attempt](../data/qwen38-q4km-tp2-http-depth-20260825-r1-attempt1/)
