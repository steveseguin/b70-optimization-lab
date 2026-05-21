# MiniMax M2.7 Next Plan After Isolated Trace Rejection

Date: 2026-05-21

## Current State

Accepted public best remains 93.443623 output tok/s on MiniMax M2.7 AutoRound
W4A16, TP4, 4x Intel Arc Pro B70, with strict quality clean.

The latest promoted-path control passed quality but measured 88.210663 output
tok/s, so it is a sanity control, not a new performance result.

The isolated llm-scaler trace fork is rejected for now because it produced
degenerate token id `0` output under the raw145 guard.

## Guardrails

- No LocalMaxxing submission without quality pass.
- No promotion without raw145 n64/n256, semantic suite, and repeated arithmetic
  passing.
- Any source fork must prove baseline quality before modification.
- Any apparent speedup that changes exact token hashes is treated as a quality
  failure until explained and revalidated.

## Work Items

1. Recreate a clean experimental llm-scaler fork from the promoted source path.
2. Run raw145 n64/n256 on that clean fork before edits.
3. Add a microbenchmark-only timing path for the MiniMax W4A16 kernels so timing
   does not perturb full generation.
4. Compare promoted source and rejected isolated source to identify why the
   isolated build produced NUL output.
5. Revisit decode-time collective overhead with exact-shape microbenchmarks and
   avoid full-generation wiring until synthetic tests show a real win.
6. Recheck prefill-only improvements separately; accept them only if decode
   output tok/s is neutral or better and quality remains exact-token clean.

## Hypothesis

The remaining gap to consistent 95+ tok/s is more likely in framework,
collective, or graph-capture overhead than in the small U4 decode branch tested
today. The next source changes should therefore be driven by clean
microbenchmark evidence rather than broad env toggles.
