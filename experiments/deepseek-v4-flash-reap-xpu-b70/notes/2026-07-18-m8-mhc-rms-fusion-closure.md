# Fixed M=8 MHC Post/Pre + RMSNorm Fusion Closure

Date: **2026-07-18**

Status: **correctness and performance rejected before four-card or model load**

## Outcome

The existing fixed-M8 MHC post/pre kernel and the following BF16 RMSNorm were
combined into one guarded native XPU operation. The candidate reused the
already-preserved M=1 fused geometry at M=8: 512 work-items per token, exact
BF16 producer rounding before variance accumulation, and the standalone
RMSNorm cast/multiply boundary.

The first B70 gate failed both required conditions:

- over 40 changing inputs, residual output remained bitwise exact, but post
  mix accumulated 113 FP32-bit mismatches, comb mix 2,378 FP32-bit
  mismatches, and normalized output 10 BF16-bit mismatches;
- the reference fixed-M8 MHC plus standalone RMSNorm measured **21.455988 us**
  median, while the fused candidate measured **22.620183 us**;
- the candidate therefore regressed by **1.164195 us/boundary**, projecting a
  **0.098957 ms/cycle loss** over 85 boundaries.

The arithmetic mismatch is the same class previously exposed by the rejected
M=1 fusion: changing subgroup/workgroup geometry changes the floating-point
reduction tree. The performance result independently closes this exact
implementation even if its last ULPs could be repaired.

## Evidence and identity

- XPU experiment commit: `2cc25d0ca08d3a76de27ee50c6dda258350e93e8`;
- gate script: `../scripts/bench-m8-mhc-rms-fusion.py`;
- raw result:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m8-mhc-rms-fusion-gate-20260718T2105Z/card0.json`;
- process exit code: `1`, deliberately failing closed;
- no service was loaded and no LocalMaxxing submission was made.

The operator remains unused and default-off. It is preserved as negative
source evidence, not a production selector.

## Decision

Do not spend the other three cards or a model load on this implementation.
Do not retry the same 512-work-item fused reduction geometry at M=8. The
remaining low-risk arithmetic option is the already-exact BF16 DPAS DSpark W2
projection in the incumbent collective path, but its optimistic ceiling is
only about 0.184 ms/cycle and it must be treated as a portfolio component.
The larger strategic work remains a fixed-address decoder transaction that
removes device work and framework turns without adding eager synchronization.
