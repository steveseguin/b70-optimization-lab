# Packet51 independent source review

Reviewed the packet45 engine, packet48/48b adapters and packet51 candidate,
layer harness, build, seal, admission and summary code. The reviewer ran no
compiler, CPU test, GPU program, service or health probe. The root agent runs
the serial gates and records their results separately.

| Area | Finding |
| --- | --- |
| Control | Uses the actual packet45 Engine with only the accepted p48b expert gate/up and down replacements. Unaccepted dense replacements are excluded. |
| IQ2 gate/up | The compact table preserves all eight magnitudes. Finite scale/sign expressions, each lane's ordered product/add chain, adjacent SG32 reduction and BF16 stores match p48b. Exceptional scale calls defer to the unchanged p48 decoder. Gate and up have separate subgroups; no arithmetic is shared between them. |
| HC | Low preserves four split accumulators, their original merge, BF16 rounding and activation. Gate preserves the K320 single chain. Inject remains unchanged; replacing its global partials with local memory would alter captured workspace bytes. |
| Route | Stage1 computes one exponential per item and preserves each adjacent 16-value sum in one half of SG32. Its shared maximum uses the original serial maximum loop; stable control values make the barrier uniform. Stage2 caches probabilities after the original division. Comparing unnormalized exponents could alter ties; the adversarial CPU case covers this. Integer ranks, index tie-breaking, descriptors, four passes and global scratch remain unchanged. |
| Attention | Retains four partials, two device passes and the original global scratch slots. Shared inject factors use the unchanged expression; BF16 rounding remains before stream combination. The host adapter follows the original host control's one-pass behavior. |
| GDN QKV | Loads packed groups together while retaining the original scale multiplication and eight ordered products per lane. |
| M=2 | The target Engine has no two-token matrix batch dimension. Its routed matrix count means ten experts. Packet51 measures two independent serial token-row calls and sums both event sets. State is restored independently; this is neither continuous recurrence nor batched weight reuse. |
| Gates | CPU arithmetic and fixture checks cannot establish device subgroup/barrier behavior or model quality. E1/E2/T1/T2 and later unchanged full-model oracles remain required. |

Review corrections incorporated into preparation:

- Pass the zombie-tolerant memory sensor explicitly to the inherited supervisor.
  Assigning its module attribute alone leaves Python's old default argument bound.
- Re-read exact-window native captures before admitting timing companions.
- Bind the full production class census and require both M=2 row records.
  M=2 cannot pass the primary M=1 performance bar.
- Revalidate CPU gate inputs when sealing, including changed source and binary
  identities. Reserve 18 GB of disk and enforce the 1.5 GB packet build cap.
- Bind standalone operator-test source mirrors and compiler identities; require
  identical admitted-domain phase digests across GNU, Intel and sanitizer runs,
  and identical full diagnostic digests across fresh repeats of each compiler.
  Failed attempts write failed receipts instead of leaving a stale passing result.
- Add negative checks for changed companions, missing/failed gates, live tasks
  missing RSS, incomplete events/rows, and the alternate 1.5x gate-only bar.
- Match route submission's production alias contract. Its three-input form
  intentionally repeats explicit error/active inputs in the tail controls.
  Tail scratch/control allocations remain mutually distinct; scratch remains
  disjoint from inputs/outputs, and outputs remain disjoint from all operands.

The first full-layer CPU comparison stopped safely at 24 comparisons because
the initial route submission validator rejected those legitimate repeated
controls. Isolated arithmetic tests call `route42::Args` directly and cannot
detect this binding error. The correction matches `route42_submit.cpp`'s
admission contract without changing arithmetic. This is why full production
composition is a separate required gate; the failed receipt is not a seal.

The first Intel operator run exposed a real direct-decoder mismatch for a NaN
scale (half `0x7e01`, scale nibble 0, codebook index/sign 155); GNU had passed.
The revised exceptional branch calls the unchanged decoder with the original
bytes. It does not canonicalize a NaN, relax the comparison or change repacking
admission. The reviewer checked that its predicate includes infinite scales
and preserves the finite path, including signed zeros and subnormals. The
retained failed attempt and rerun receipts determine the final gate status.

After this fix, all 282,713 original-vs-candidate checks passed separately
under GNU, Intel and sanitizers. The independent reviewer read the retained
`evidence-cpu/20261017T054436Z/` phase receipts: GNU and Intel differ only in
`weight_half_32257` (`0x7e01`). This is the unchanged decoder's cross-compiler
NaN payload behavior. All finite-weight phases, signed zeros/subnormals,
nonfinite activation cases, route cases and dense/HC cases agree.

The allowed weight domain comes from the unchanged packet48 repacker: it
rejects all infinite/NaN weight scales before writing the destination. Final
qualification must retain every direct-decoder case and its per-compiler
exact comparison, enforce the complete phase inventory, and compare every
admitted-domain phase across compilers. Unsupported weight-scale diagnostic
hashes remain visible and are not a universal cross-compiler output identity.
Exhaustive rejection tests cover all 2,048 nonfinite half encodings and verify
that refusal leaves the destination unchanged. This does not relax model
output equality or exclude nonfinite activations from the checks.

The full-layer fixture uses deterministic synthetic weights. Its timing can
select kernels for model integration; it cannot supply a model throughput
headline. Independent isolated CPU cases cover codebook/sign combinations,
special IQ2 scales and inputs, route ties and controls, and original dense
lane/split identities. Final executable identities and outcomes are in the
CPU/build receipts and seal.
