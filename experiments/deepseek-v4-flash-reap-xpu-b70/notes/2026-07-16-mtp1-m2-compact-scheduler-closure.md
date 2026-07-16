# MTP1 M=2 compact MXFP4 scheduler closure

Date: 2026-07-16

## Outcome

The benchmark-only Xe2 compact scheduler is bitwise exact but does not clear
the predeclared `0.50 ms` whole-verifier integration gate. It is rejected
before vLLM integration or another TP4 service load.

On B70 card 0, all 84 changed-input correctness cases passed. Coverage
includes same/disjoint experts, cross-row overlap, within-row duplicates, all
duplicates, twelve distinct local routes, and a valid all-remote EP rank. Both
production routed MXFP4 shapes were checked:

- GEMM1: M=2 route structure, N=4096, K=4096;
- GEMM2: M=2 route structure, N=4096, K=2048.

The candidate was also checked against an independent fixed-M1 arithmetic
oracle and direct slot-order gather, rather than trusting the formerly racy
generic grouped-GEMM graph as the sole reference.

## Design tested

The generic persistent grouped-MXFP4 scheduler scans 40 local experts and uses
a global atomic work counter. The candidate launches directly over the twelve
M=2/top-k-6 route slots and N tiles. On device it derives each local expert's
row count and remapped-row prefix from `topk_ids` plus `expert_map`; occurrence
0 and 8 own the two WG-M=8 tiles in the all-duplicate case. It preserves the
generic expert-grouped activation layout and cross-row weight reuse.

The implementation is preserved on XPU branch
`codex/deepseek-v4-m2-compact-scheduler`, commit `ae1cbd472dced30741b5bdcd297fd5fd62a68f3d`.
It remains benchmark-only: no fake/meta registration or production M=2 vLLM
dispatch was added.

## Performance gate

The control was explicitly pinned to the promoted N64 policy. Timing alternated
generic and candidate fixed-address XPU graph replays and used the minimum
projected saving across every declared route pattern.

| Route pattern | Projected saved ms / 43 layers |
|---|---:|
| same typical | 0.4691 |
| disjoint typical | 0.7405 |
| cross-row overlap | 0.4586 |
| within-row duplicate | 0.8297 |
| all duplicate | 0.5073 |
| twelve local routes | 0.4924 |
| all remote | 0.2618 |

The valid all-remote case is the fail-closed minimum. Running only favorable
route patterns or averaging away this case would overstate real EP behavior.
Because card 0 already failed the gate, cards 1-3 and service integration were
not run.

Raw evidence is in
`../../../data/deepseek-v4-reap-mxfp4-m2-compact-scheduler-20260716/card0.json`.
The reusable probe is
`../scripts/probe-mxfp4-m2-compact-scheduler.py`.

## Decision and next boundary

Do not promote, submit to LocalMaxxing, or spend another service load on this
scheduler alone. The candidate proves that removing only the persistent
scheduler is still too small and route-dependent.

The next architectural screen should combine this scheduling idea with removal
of the M=2 remap and final permuted-gather boundaries while preserving grouped
expert reuse. The eager cycle profile attributes about `0.156 ms` to remap and
`0.151 ms` to gather per verifier cycle; combining those boundaries with the
measured scheduler saving is the first remaining noncollective hypothesis with
a plausible `>=0.50 ms` ceiling. It still requires an exact real-shape
upper-bound gate before production integration.
