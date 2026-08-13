# DDTree budget-15 branch-layout probe

Date: 2026-08-13

## Result

The real unified-KV, multi-sequence target layout is correct, but the complete
measured layout/bookkeeping cost means budget-15 DDTree still does not clear
the honest 100 tok/s bar on the current retained stack.

The diagnostic ran an additional 16-row target pass before each ordinary
linear verifier pass. It copied canonical sequence 0 to temporary leaf
sequence IDs, decoded the exact best-first budget-15 tree with descendant-leaf
memberships, sampled the target rows through the existing batched backend
sampler, removed every temporary sequence, and then ran the unchanged linear
pass. Canonical serving output therefore remained authoritative; aggregate
request throughput from this diagnostic is intentionally not a performance
number.

At the last periodic report (160 eligible rounds):

- target parity checks: 1,139;
- mismatches: 0;
- average leaves: 6.74;
- steady shadow-minus-linear target time, excluding the first two cold rounds:
  +0.234 ms/round;
- tree construction: 0.009 ms/round;
- unified-KV prefix forks: 0.213 ms/round;
- temporary-sequence cleanup: 0.172 ms/round.

The directly measured total is therefore about +0.628 ms/round before the
remaining production tree-walk/output bookkeeping is implemented. Applying
that uniform cost to the prior zero-bookkeeping projection
75.650/103.569/120.610 tok/s gives approximately
74.735/102.321/119.130 tok/s, arithmetic mean 98.728 tok/s. Reaching 100 under
the same assumptions requires another approximately 0.657 ms/round exact
saving, plus whatever the missing integration itself costs.

## Correctness

All three canonical 256-token outputs and acceptance counts were preserved:

| class | hash | accepted | drafted |
|---|---|---:|---:|
| prose | `914f754747d0edaa` | 172 | 1199 |
| code | `cf2b2c4fd9e36fe5` | 197 | 811 |
| JSON | `4f813a9706abc163` | 207 | 684 |

The displayed request rates (30.383/45.252/52.706 tok/s) include the duplicate
target pass and must not be compared with retained serving rates.

## Identity and artifacts

- source diagnostic: `5d4244234` (`server: add DDTree branch-layout diagnostic`);
- env gate: `LLAMA_DDTREE_BRANCH_LAYOUT_PROBE=1`;
- required proposal width: `LLAMA_DFLASH_CANDIDATE_TOP_K=15`;
- config: `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-ddtree-branch-layout-probe256.json`;
- raw JSONL: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-ddtree-branch-layout-probe256-20260813.jsonl`, SHA-256 `cbcd0b5cb88cfa91d07b24b99fc13d9601d1a4d9b8f7637291a65036ede8e3b1`;
- server log: `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-dflash-ddtree-branch-layout-probe256-20260813-branch-shadow.log`, SHA-256 `e1d662f89a5622072a142f94d916291b95e09cf8c0273f59c7beb7c3e7e22989`;
- restored production health: `data/muse-health-20260813-ddtree-branch-probe256-restore.json`, SHA-256 `8a35a063a16af874d91e5d4b2b7fee1ac0d539d7ad7fcf83f8bf7c6f92584299`.

## Decision

Keep the diagnostic default-off. Do not implement or promote the production
tree path yet. First reduce the measured metadata/kernel cost by at least
about 0.7 ms/round with exact, independently benchmarked changes. The first
bounded targets are a bulk unified-KV fork/remove scan and the compact k=15
top-k private-state specialization.
