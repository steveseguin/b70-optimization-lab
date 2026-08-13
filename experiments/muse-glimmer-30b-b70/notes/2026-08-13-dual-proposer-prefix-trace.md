# DFlash + DSpark identical-prefix complementarity trace

Date: 2026-08-13

## Decision

Close a dual-pretrained-proposer ensemble as a route to the honest
three-class `>100 tok/s` goal. This lane uses no drafter training, but even a
zero-cost oracle that selects the longer matching DFlash or DSpark branch each
round reaches only `73.562 tok/s`. A real implementation would add a second
draft pass and a wider target verification batch, so it must be slower than
that ceiling.

## Measurement design

Source commits `8ffc5db8b` and `9805f636b` add default-off
`LLAMA_SPEC_PROPOSAL_TRACE_ONE_TOKEN=1`. At every generated-token prefix the
server runs the complete pretrained proposal block, verifies a full 16-row
target batch, logs the target token, then deliberately forces zero accepted
draft tokens. This yields DFlash and DSpark proposals at the same 254 prefixes
per request while preserving the normal batch-16 target arithmetic.

The first trace revision cleared the proposal before target decode. That made
the target execute batch-1 and changed the known prose/code near-tie hashes;
it is preserved as an invalid diagnostic and not used in the conclusion. The
v2 trace keeps all 15 proposals in the target batch. Both DFlash and DSpark v2
runs reproduced the canonical output hashes:

- prose `914f754747d0edaa`;
- code `cf2b2c4fd9e36fe5`;
- JSON `4f813a9706abc163`.

`scripts/analyze-muse-dual-proposer-prefix-trace.py` parses the per-position
top-1 candidates and canonical target tokens, simulates each proposer, and
simulates an exact two-branch oracle that chooses whichever primary branch
matches the target longer. Two focused tests cover parsing, probability
truncation, and complementary branch selection.

## Results

The trace independently reproduces the retained DFlash acceptance identity
exactly: `172 / 197 / 207` accepted tokens and `84 / 59 / 49` target rounds
for prose/code/JSON. It also reproduces the measured DSpark accepted-token
counts `168 / 203 / 204`. This is a strong internal validation of the prefix
trace and simulator.

| strategy | prose rounds | code rounds | JSON rounds | zero-added-cost mean |
| --- | ---: | ---: | ---: | ---: |
| DFlash | 84 | 59 | 49 | 67.874 |
| DSpark | 88 | 53 | 52 | 68.168 |
| oracle longer of both | 75 | 52 | 48 | **73.562** |

At the incumbent per-class round costs (`62.83 / 61.61 / 61.69 ms`), the
oracle projects `54.326 / 79.907 / 86.454 tok/s`. Its accepted-token totals
are only `181 / 204 / 208`; the main gain is nine fewer prose rounds, seven
fewer code rounds, and one fewer JSON round. Prose would require an impossible
`34.13 ms` dual-proposer round merely to reach 100 by itself, versus the
current `62.83 ms` single-DFlash round.

Because `73.562` already assumes the second drafter and branch-width cost are
zero, no implementation or kernel optimization of this ensemble can bridge
the remaining gap. Do not build the server tree for this proposal pair.

## Evidence

- run identity:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-dspark-prefix-proposal-trace-v2.json`,
  SHA256 `5bbb3a27a95ca2f9250ef9d377ae8d9435a95b569905f3c8103798192e6ef7b0`;
- sweep result:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-dspark-prefix-proposal-trace-v2-20260813.jsonl`,
  SHA256 `e7a4f649afd51b1ffa13a377d940edd32228419fbd99bfa19b714940f67807ab`;
- DFlash trace SHA256
  `35fd3208c20949a9a8d9b11ff4f32d87c89a18664b066b6713dca9581b859c89`;
- DSpark trace SHA256
  `1aaf8f02cc841c84f2d5a1e7b3b3a88a2733057d4512072c2f31f5a4db87ef10`;
- parsed analysis:
  `data/muse-dual-proposer-prefix-coverage-20260813.json`, SHA256
  `432a0a8aedf2642f3282190257409a43b0542c7bd80096a7e9207ed19ddf3b91`.

Production was restored after both trace windows and passed the full
code/cache-zero/vision gate in
`data/muse-health-20260813-prefix-proposal-trace-v1-restore.json` and
`data/muse-health-20260813-prefix-proposal-trace-v2-restore.json`.
