# Qwen3.8 27B Q8 TP2 shape-scoped MMVQ subgroup count

Date: 2026-08-17

Status: closed; reachability/verification passed, but the balanced confirmation
was negative (`-0.272%`) and the apparent first-screen gain was a run-position
artifact.

## Hypothesis

The accepted reordered-Q8 MMVQ uses eight SG16 subgroups per workgroup on
B70. A previous *global* launch-width sweep found SG4 statistically flat but
slightly positive (`+0.091%`) and SG16 slightly negative (`-0.045%`). That
global control changed every reordered MMVQ together, so it could hide a gain
in one dominant FFN family behind a regression in another.

Qwen3.8-27B repeatedly uses two dominant local TP2 FFN shapes:

- gate/up fused pair: K=`5120`, N=`8704+8704`;
- down projection: K=`8704`, N=`5120`.

This experiment independently selects SG4 for either exact family while all
other MMVQs retain the accepted hardware-derived SG8 geometry. It changes
launch population only: the accepted reordered weight layout, DP4A sequence,
FP32 accumulation and subgroup reduction, model, F16 KV, tensor split, and
target-only quality contract remain unchanged.

## Contract

- isolated source/build derived from the accepted Qwen3.8 Q8 stack;
- default-off same-binary doors for pair-only, down-only, and both;
- exact-shape admission plus once-per-device reachability logging;
- bounded `p64/n1` liveness/verification smoke under the established host-RAM
  cap;
- position-balanced `p64/n256/r3` screen with fresh processes;
- advance only a repeatable positive result outside run variance to the full
  cache-zero output oracle and semantic/long-context gates;
- preserve the accepted reproduction unless a candidate clears every gate.

The earlier global subgroup sweep and compile-time fixed-shape experiment are
controls, not duplicates: neither isolated subgroup population by FFN family.

## Implementation and smoke

Two default-off environment doors were added to an isolated build:

- `GGML_SYCL_MMVQ_Q8_SG4_PAIR=1` selects four SG16 subgroups only for the
  fused K=`5120`, N=`8704+8704` gate/up pair;
- `GGML_SYCL_MMVQ_Q8_SG4_DOWN=1` selects four SG16 subgroups only for the
  standalone K=`8704`, N=`5120` down projection.

The row body, integer dot-product sequence, FP32 accumulation order and SG16
reduction were unchanged. A TP2 `p64/n1` smoke with both doors enabled logged
both admitted families on both devices, completed at `36.874351 tok/s`, kept
the accepted fusion census live, and ended with `VERIFY_MISMATCH=0`. Both B70s
remained normal with no current-boot Xe/GuC fault, reset, timeout or hang.

## Four-arm screen

Fresh-process order was `control, pair, down, both, both, down, pair, control`,
each at `p64/n256/r3`, TP2 `1/1`, F16 KV, FlashAttention and `b1024/ub256`.

| Arm | Pooled sample mean (tok/s) | Delta vs control |
| --- | ---: | ---: |
| control | `37.010550` | -- |
| pair only | `37.006883` | `-0.0099%` |
| down only | `37.028383` | `+0.0482%` |
| both | `37.474033` | `+1.2523%` |

The individual doors were flat while both looked positive. The run sequence,
however, showed a strong alternating high/low state, so this was not promoted
without a position-balanced confirmation.

## Balanced confirmation

The confirmation used eight fresh `p64/n256/r5` processes in
`A-B-B-A, B-A-A-B` order, giving control and both-SG4 treatment two odd and
two even process positions each.

| Block | Control (tok/s) | Both SG4 (tok/s) | Delta |
| ---: | ---: | ---: | ---: |
| `A-B-B-A` | `36.800920` | `36.836240` | `+0.0960%` |
| `B-A-A-B` | `37.250500` | `37.013820` | `-0.6354%` |
| pooled | `37.025710` | `36.925030` | **`-0.2719%`** |

The two blocks disagreed and the pooled treatment regressed. No endpoint or
quality suite was run because the candidate failed the performance gate. Keep
the accepted hardware-derived SG8 policy and do not repeat these exact
shape-scoped SG4 doors unchanged.

## Reproduction artifacts

- structured result:
  [`../data/2026-08-17-q8-ffn-shape-scoped-sg4-negative.json`](../data/2026-08-17-q8-ffn-shape-scoped-sg4-negative.json)
- incremental patch after the fixed-shape experiment:
  [`../patches/q8-ffn-shape-scoped-sg4-negative-20260817.diff`](../patches/q8-ffn-shape-scoped-sg4-negative-20260817.diff)
- incremental patch SHA-256:
  `866fa0641ee74252d7ed0e28f12cf7b8080eac7b257b0d3c7ce5b62bb4ee9569`
- isolated source/build: `/mnt/fast-ai/src/llama.cpp-q38-q8-fixed-shapes`,
  `build-sycl-aot-bmg-g31-fixed-shapes`
- `libggml-sycl.so.0.19.0` SHA-256:
  `d7015cc44d8701020b802e2cf4586eb17637f2d36fd11e15e8a6f39d07055e54`
- `llama-bench` SHA-256:
  `5ad7c26b123d41194a72f127052c50414a58a558a120548f17f11d54dba61abb`
- raw local evidence:
  `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-shape-sg4/`
