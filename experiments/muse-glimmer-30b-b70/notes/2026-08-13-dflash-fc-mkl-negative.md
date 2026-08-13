# DFlash encoder FC-only oneMKL: rejected

Date: 2026-08-13

A default-off exact-name/shape gate sent only DFlash encoder `fc.weight`
(`[33280,6656]`, batch 2--16) through the existing direct oneMKL BF16 path.
The target verifier remained on oneDNN.

The canonical 64-token off/on smoke measured:

| arm | prose | code | JSON | mean |
|---|---:|---:|---:|---:|
| off | 68.865 | 114.636 | 222.053 | 135.185 |
| on | 69.018 | 114.665 | 218.528 | 134.070 |

Hashes, proposals, and acceptance were identical. The candidate was flat on
prose/code, regressed JSON, and lost arithmetic mean throughput. It does not
warrant a full run.

- source experiment: `463ea2654`;
- revert: `cdc7d6650`;
- config: `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-fc-mkl-smoke64.json`.

Decision: preserve and revert.

