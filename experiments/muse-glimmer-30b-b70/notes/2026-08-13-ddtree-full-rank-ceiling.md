# DDTree full-rank ceiling: negative on TP4 BF16 Muse

Date: 2026-08-13

## Decision

Do not implement a wider DDTree in the Muse server.  Even the exact full-rank
proposal coverage cannot pay for wider BF16 target verification on this
four-B70 stack.  Keep verifier/kernel work as the primary lane.  Preserve only
budget 15 as a conditional supporting option: it holds the current 16-row
verifier width and raises the same-cost ceiling to `82.68 tok/s`, but still
needs an independently measured `10.73 ms/round` verifier reduction before the
combination can reach 100.

No drafter training or weight change was performed.

## Why this was tested

Official DFlash generates all draft positions in a single all-mask forward
pass.  A second partially denoised pass is not the published inference
algorithm, so that idea was closed before implementation.  DDTree is a
compatible no-training alternative: it builds a best-first tree from the same
per-position DFlash distributions and verifies the tree once with the target.

Primary references:

- DFlash: <https://arxiv.org/abs/2602.06036>;
- DDTree paper: <https://arxiv.org/abs/2604.12989>;
- official DDTree code: <https://github.com/liranringel/ddtree>.

## Exact prefix diagnostic

Source commits:

- `c13cb7ac6`: log DFlash candidates with sufficient probability precision;
- `0f2ff2384`: default-off `LLAMA_DFLASH_CANDIDATE_TOP_K` diagnostic, used at
  `128` so the scorer is not constrained by llama.cpp's normal top-10 sampler.

`scripts/analyze-muse-ddtree-prefix-trace.py` mirrors the official best-first
heap construction.  Its tests cover sibling-versus-child ordering and target
tree walking.  The trace mode performs a normal 16-row target verification at
every canonical prefix, then deliberately commits one target token.  All
three final hashes remained canonical:

- prose `914f754747d0edaa`;
- code `cf2b2c4fd9e36fe5`;
- JSON `4f813a9706abc163`.

The full trace contains 128 candidates at every one of 15 positions for all
three 256-token responses.  The important optimistic, zero-added-cost ceilings
are:

| tree budget | prose/code/JSON rounds | mean emitted/round | same-cost mean tok/s |
| ---: | --- | ---: | ---: |
| 22 | 64 / 44 / 38 | 5.518 | 89.10 |
| 48 | 60 / 41 / 33 | 6.089 | 98.33 |
| 64 | 60 / 40 / 33 | 6.141 | 99.18 |
| 96 | 60 / 39 / 33 | 6.196 | 100.07 |
| 128 | 59 / 39 / 31 | 6.387 | 103.16 |
| 192 | 56 / 37 / 31 | 6.583 | 106.31 |
| 512 | 54 / 35 / 30 | 6.863 | 110.83 |

Budgets through 64 cannot reach 100 even if wider verification is free.
Budget 96 has effectively zero cost margin.  Budget 128 can tolerate only a
`1.0316x` round-cost multiplier.

## Measured wider-target cost

A matched TP4 BF16 `llama-bench` target-only screen used the retained kernel
environment, tensor split, FA on, batch/ubatch 1024, seven repetitions, and
the exact target artifact.  It measured:

| target batch | mean forward time | standard deviation |
| ---: | ---: | ---: |
| 16 | 44.478503 ms | 0.219987 ms |
| 128 | 110.305179 ms | 0.137257 ms |

Batch 128 is `2.47997x`, not the `<=1.0316x` needed.  Using the deliberately
optimistic proxy `incumbent round time + (pp128 - pp16)` with the measured
budget-128 round counts projects `33.73 / 51.51 / 64.76 = 50.00 tok/s` mean.
Real tree bookkeeping, masks, KV compaction, and batch 129 rather than 128 can
only make that worse.  Larger budgets also require larger verifier batches and
are therefore excluded by an even wider margin.

## Pretrained DSpark tree control

The same full-rank trace was run with the already-trained public Muse DSpark
checkpoint (no local training).  Its budget-15 tree is worse: `75.24 tok/s`
same-cost ceiling, with class round counts `75 / 50 / 47`, versus DFlash's
`82.68` and `65 / 48 / 42`.  Even at budget 128 DSpark reaches only `91.13`
before wider-verifier cost.  Do not use DSpark for the conditional tree lane.

DSpark evidence:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dspark-ddtree-prefix-top128-trace-20260813.jsonl`,
  SHA-256 `ba3ea7da50b3ed52880cca7e1077991840083aa9f30e74062d5036fda694e7dc`;
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-dspark-ddtree-prefix-top128-trace-20260813-dspark-prefix-top128-verify16.log`,
  SHA-256 `67e1b9ca44f67ce0a57e68afae86e7d8acf35029062a8ced02e6952034bfc497`;
- `data/muse-dspark-ddtree-prefix-top128-coverage-20260813.json`, SHA-256
  `0eadfe101a80287d7994a86d7e5fb39073396c402f874ecfda3eead3d7c3529a`.

## Evidence

- config:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-ddtree-prefix-top128-trace.json`;
- trace result:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-ddtree-prefix-top128-trace-20260813.jsonl`,
  SHA-256 `b3ab4b21ba83d98fcbf39947d0f7b23e45287288e2c9be553f25a67635118a89`;
- server trace:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-dflash-ddtree-prefix-top128-trace-20260813-dflash-prefix-top128-verify16.log`,
  SHA-256 `53f474338ba38f71eec03f23a410d09fcaff8524efc9e4180f5618d68c3e6198`;
- structured coverage:
  `data/muse-ddtree-prefix-top128-coverage-20260813.json`, SHA-256
  `c7d5771ceb50faa02e3d8404ebdf4cf7e156b3ef0e56276898342f83c3a60d8f`;
- target batch timing:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/target-pp16-pp128-cost-20260813.json`,
  SHA-256 `3678c0e6ee4b26124c758608c5d999a7d36044057dc948657800bc908c759801`.

Production was restored without reboot and passed the full model,
cache-zero code, and vision health gate in
`data/muse-health-20260813-ddtree-cost-restore.json`.

## Updated budget-15 integration gate after kernel wins

Later exact kernel/runtime work materially changed only the conditional
budget-15 lane. The distributed top15 merge/tree/512/heap kernels plus the
allreduce last-event win now project `75.291 / 103.278 / 120.524 tok/s`, mean
`99.698`, at zero DDTree bookkeeping cost. Wider trees remain rejected by the
measured target-batch cost above.

Budget 15 keeps the incumbent 16 target rows: one anchor plus 15 unique tree
nodes. The smallest valid server form requires unified KV and temporary target
sequence IDs per leaf. The anchor belongs to all leaf IDs; each tree node
belongs to its descendant leaves. After target verification, retain the chosen
leaf, copy it back to canonical sequence 0, and inject only the selected
anchor-to-committed-path target features into canonical DFlash KV. Do not pass
the multi-sequence target batch to the current contiguous single-sequence
DFlash processing path.

Measured traces imply roughly 7.23 / 4.93 / 4.63 leaves per round for
prose/code/JSON (p95 11). Expected host heap/tree bookkeeping is tiny, but KV
metadata scans and multi-sequence masks are not free. A public-API prototype is
expected to add roughly `0.15--0.6 ms/round`; a dedicated bulk fork/select may
reduce that to `0.05--0.2 ms`. At `0.1 / 0.3 / 0.5 ms` uniform added cost, the
modeled mean becomes approximately `99.50 / 99.12 / 98.73 tok/s`.

Therefore do not begin the full server acceptance rewrite until both gates
pass:

1. canonical linear `--kv-unified` C/A/C at n_parallel=1, requiring no more
   than about `0.05 ms/round` regression;
2. a 16-row branch-layout probe that verifies selected-path logits/greedy IDs
   against separate linear paths and measures sequence-fork/mask/prune cost,
   preferably no more than `0.2--0.3 ms/round`.

Even after those gates, another exact `0.155 ms/round` plus measured tree
bookkeeping is required. Full integration is plausible only after that margin
exists; the tree alone still cannot honestly claim 100.
