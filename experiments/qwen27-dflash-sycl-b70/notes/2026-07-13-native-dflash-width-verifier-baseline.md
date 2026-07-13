# Native DFlash widths and Xe2 verifier baseline

Date: 2026-07-13 UTC

## Purpose

Native DFlash restored valid long-block speculation once its draft K/V cache
was kept in F16. This experiment moves the verifier work from the old MTP-only
M=4/8 assumptions to the real native DFlash target widths: M=6, M=9, and M=16
for `n_max=5/8/15`.

## End-to-end width timing

Q8 native DFlash, F16 draft KV, FA enabled, graphs off, favorable merge-sort
code prompt, with cycle timing enabled:

| Verifier width | Target verify median | Draft block median | Feature/process median | Request decode | Mean emitted length |
|---:|---:|---:|---:|---:|---:|
| 6 | 58.189 ms | 10.515 ms | 1.056 ms | 76.23 tok/s | 5.57 |
| 9 | 107.626 ms | 66.467 ms | 2.301 ms | 18.23 tok/s | 8.35 |
| 16 | 138.877 ms | 69.085 ms | 2.758 ms | 58.60 tok/s | 12.85 |

The width-9/16 draft path has a second major discontinuity in addition to the
target verifier. Longer blocks cannot win merely through acceptance until both
the target and five-layer DFlash small-M projection paths use the packed Xe2
kernel family.

## Exact-production comparator extension

The experiment-only benchmark hook and comparator were extended to M=6/9/16.
The candidate remains the existing joint-2 DPAS design with eight K splits and
a global partial buffer plus second reduction kernel. It is not yet the desired
single-launch SLM design.

M=6 results, including activation quantization and every candidate submission:

| Shape KxN | Production total | DPAS total | Speedup | Max candidate/production difference | Gate |
|---|---:|---:|---:|---:|---|
| 5120x5120 | 268.043 us | 137.508 us | 1.949x | 0.0335 | pass |
| 5120x17408 | 419.077 us | 230.152 us | 1.821x | 0.0370 | pass |
| 17408x5120 | 355.127 us | 189.345 us | 1.876x | 0.0651 | correctness gate miss |

This is the first candidate to beat the exact production verifier by more than
1.5x on the real native-DFlash width-6 square and up-projection shapes. It is a
material milestone, but runtime integration remains blocked on resolving or
bounding the down-projection numerical difference and replacing the global
partial/reduction sequence.

M=9 is mixed: 2.010x square, 1.385x up, and 1.808x down with the same
approximately 0.066 down-projection difference. M=16 is only 1.08-1.10x; two
DPAS repeat-8 calls and the current global reduction design lose the expected
multi-row advantage. Width 16 needs a different register/SLM ownership mapping.

## Impact on the 100/200 objectives

At favorable DFlash5 mean length 5.57, TP1 needs the width-6 verifier below
about 44.2 ms for 100 tok/s. A projection path that is consistently near the
measured 1.8-1.95x comparator speedup is sufficient in principle, although the
whole verifier will not scale by the projection microkernel ratio alone.

For 200 tok/s, verifier latency must be about 16 ms at the same acceptance, or
longer blocks must retain high acceptance with near-flat M=9/16 execution.
That remains a packed-verifier plus TP3/TP4 objective, not a claim from this
microbenchmark.

## Next action

1. Build one ESIMD workgroup per N tile with K-split workers, SLM partials, one
   barrier, and in-kernel reduction.
2. Resolve the 17408x5120 numerical delta against exact Q4_0/Q8_1 semantics.
3. Pack only FFN tensors initially; a full duplicate target pack does not fit,
   while the 195 FFN tensors require about 9.146 GiB.
4. Integrate behind BMG + Q4_0/Q8_1 + M=6 guarded dispatch only after full
   projection correctness and `>=1.5x` total speed hold.

## Single-launch SLM successor

The next prototype eliminates the global partial buffer and second reduction
kernel. One workgroup owns two adjacent N16 tiles; eight ESIMD work-items split
K, stage their partials in SLM, synchronize once, and work-item zero performs
the final reduction and store.

Measured on B70 GPU3:

- M=6 5120x5120: 1.78-2.05x total across stability repeats; pass.
- M=6 5120x17408: 1.834x total; pass.
- M=6 17408x5120: 1.934x speed, but the existing 0.0651 summation-order
  difference remains; the SLM and global-partial candidates have identical
  differences, so SLM did not introduce the discrepancy.
- M=9 5120x5120: 2.153x total; pass.
- M=16 5120x5120: 1.404x; below gate because the two-repeat/register footprint
  still hits a width-16 cliff.

On the first M=6 square run, single-launch SLM reduced the candidate path from
about 103.63 us to 95.72 us and produced a 2.051x exact-production total
speedup. This establishes gate/up-only M=6 as the first guarded integration
target. Down remains disabled until its numerical gate is resolved; width 16
needs a different ownership/register design.
