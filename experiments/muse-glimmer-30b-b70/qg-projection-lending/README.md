# Muse TP4 Q/gate projection-lending screen

This standalone two-B70 screen tests a narrow attention load-balancing idea.
The incumbent non-mirrored TP4 layout computes two `M=2048, N=16, K=6656`
projections serially on an attention owner.  The candidate splits each
projection into two `M=1024` row halves, runs one half on the owner and one on
an otherwise idle helper, then pulls/scatters the helper's two F32 halves back
to the owner.  K/V, FlashAttention, O projection, and allreduce are outside
this screen and would remain unchanged in a model integration.

The candidate includes the reciprocal helper-queue handback needed to prevent
the next iteration from overwriting helper output while the owner is still
reading it.  It is therefore an honest command-chain screen rather than a
GEMM-only ceiling.

Advance only when both gates pass:

- every F32 output bit equals the two full-width incumbent projections;
- the candidate saves at least `0.040 ms` per layer (about `2.08 ms` over 52
  layers) after warmup.

The benchmark is an experiment artifact, not a production recipe.  GPU runs
must hold `/run/lock/muse-glimmer-gpu-exclusive.lock` and production must be
restored and health-checked afterward.

## Result: exact, below integration gate

The two-B70 800-iteration screen measured:

| path | time per layer |
| --- | ---: |
| pooled full-width control | `0.100870 ms` |
| split owner/helper plus scatter/handback | `0.063938 ms` |
| saving | **`0.036932 ms`** |

Every Q and gate F32 output bit matched; all four hashes were identical.
The speed gate nevertheless failed because the saving was below the
preregistered `0.040 ms/layer` threshold.  Scaling the measured delta over 52
layers gives only `1.920 ms/pass`, short of the approximately `9.94 ms/round`
needed by the current `80.879 tok/s` champion and below the threshold for a
large asymmetric meta/model integration.  Preserve the harness but do not
integrate this topology.

Raw log:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/qg-projection-lending/qg-projection-lending-20260813.log`,
SHA-256 `2d7a7b521a091a1b7dbaae70f943a97038123ae7e232750c67b786186914df4b`.
