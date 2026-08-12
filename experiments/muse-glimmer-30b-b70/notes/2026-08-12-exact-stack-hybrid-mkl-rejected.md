# Exact stack plus narrowed oneMKL: rejected

Date: 2026-08-12

## Decision

Reject the hybrid. It is 2.21% faster than the exact stack on the fixed suite,
but the speculative prose output does not match the same configuration with
speculation disabled. The target numerical identity depends on batch width.

## Result

| Arm | Prose | Code | JSON | Arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| exact stack | 45.777 | 66.482 | 80.288 | 64.182 |
| exact stack + oneMKL N=2..16 | 45.446 | 71.288 | 80.071 | 65.602 |
| improvement | -0.72% | +7.23% | -0.27% | **+2.21%** |

The narrowed oneMKL path uses oneDNN for N=1 decode and oneMKL for N=2..16
verification. Hashes were:

| Class | Speculative hybrid | No-spec hybrid | Verdict |
| --- | --- | --- | --- |
| prose | `08d41ea2f47c863b` | `a71ceb1ecf6a3e43` | fail |
| code | `b4a2bda611510441` | `b4a2bda611510441` | pass |
| JSON | `4f813a9706abc163` | `4f813a9706abc163` | pass |

Because prose fails target-self-consistency, the candidate is not eligible for
a wider quality gate or production. Restoring oneMKL at N=1 would recover a
consistent alternate identity observed in the earlier experiment, but that
path regresses no-spec decode and the combined speculative gain here is only
2.21%; it does not change the route to 100 tok/s.

Raw result:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/exact-stack-hybrid-mkl-ab-20260812.jsonl`;
- SHA-256 `f4d30142aea440b4d55fd91289b6477c26ee000612563afbc6dba5a14f54e781`.

Production was restored on the incumbent binary. The exact oneDNN stack at
64.012 tok/s remains the campaign champion.
