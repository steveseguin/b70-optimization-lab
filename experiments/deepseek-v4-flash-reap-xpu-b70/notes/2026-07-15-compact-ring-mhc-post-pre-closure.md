# Compact TP4 ring + MHC post/pre closure

The compact 256- and 512-thread in-ring MHC post/pre candidates are rejected
for full-model nondeterminism. They are not promotion or speed results. The
trustworthy record remains **34.0671207 tok/s**.

## Why this looked promising

The old in-ring post/pre experiment used a 1024-thread workgroup and reached
only `27.0187 tok/s`. The fixed 8 KiB ring has nine active wires, while MHC-pre
uses only 256 work-items. oneCCL `88d90e0` therefore exposed default-off
256/512-thread launch geometries.

The 256-thread boundary passed 40 changing eager cases bitwise and measured
about `101.9-105.4 us` across ranks versus `222.7-248.4 us` for the honest
standard-ring plus promoted fused-MHC reference. That was far above the
required `6 us/boundary` integration gate.

## The missing topology was added

The model has exactly 87 `[1,4096]` BF16 TP reductions per decode token:

- one ordinary vocabulary-embedding all-reduce;
- 85 fused post/pre boundaries;
- one final post-only boundary.

Layers 1-42 reuse their destination tuple for both post/pre calls, so the
second call aliases residual/post/comb inputs to outputs. The XPU probe now
covers all 87 positions, this alias pattern, four changed graph replays,
rank-dependent delay kernels, and dependent producer kernels. All variants
remain bitwise exact in that isolated graph.

The alias was nevertheless a bad integration contract. vLLM `af8b8d776`
assigns stable attention and FFN buffer slots, removing the alias with only
about 1.4 MiB additional storage per rank. This changed the failure but did
not eliminate it.

## Full-model failures

No speed suite was run after any failure.

| Candidate | Sequential expected | Observed |
|---|---|---|
| 256 threads, original buffers | `1073, 437, 1073` | `1073, 57, 1483` |
| 256 threads, double buffers | `1073, 437, 1073` | `1073, 437, 1183` |
| 512 threads, double buffers | `1073, 437, 1073, 437, 1073, 437` | `1183, 437, 1073, 114, 1073, "114 * 23 = 437"` |
| 256 threads, double buffers, explicit producer barrier | `1073, 437, 1073, 437, 1073, 437` | `1853, 437, 1483, 437, 1053, "19 * 23 = 437"` |

The explicit event/barrier probe in oneCCL `8f415a1` adds negligible isolated
cost but does not repair the model. Repeated identical prompts can produce
different tokens, so this is nondeterminism rather than a fixed numerical
change.

## Decision

Close compact in-ring post/pre. The cheap synthetic graph is not a sufficient
oracle for this boundary even after matching collective count, buffer aliasing,
replay count, rank skew, and producer dependencies. A future retry requires
captured real-model intermediate tensors and per-boundary comparison against
the promoted path; another synthetic-only pass does not earn a server load.

The next optimization work returns to the measured non-collective path. Get a
fresh record-lane decode timeline and select a producer/consumer fusion that
does not replace the proven oneCCL collective. Do not enable speculation before
the nonspeculative lane reaches 40-50 tok/s.

Structured evidence is in
`../data/compact-ring-mhc-post-pre-20260715.json`.
