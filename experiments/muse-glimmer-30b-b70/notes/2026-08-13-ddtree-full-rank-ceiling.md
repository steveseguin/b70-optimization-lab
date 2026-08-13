# DDTree full-rank ceiling: negative on TP4 BF16 Muse

Date: 2026-08-13

## Decision

Do not implement DDTree in the Muse server.  Even the exact full-rank proposal
coverage cannot pay for the required wider BF16 target verification on this
four-B70 stack.  Keep verifier/kernel work as the primary lane.

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
