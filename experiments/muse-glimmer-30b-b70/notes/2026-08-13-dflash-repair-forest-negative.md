# DFlash all-position mismatch-repair forest: negative

Date: 2026-08-13

## Decision

Do not implement the sparse DFlash repair forest in the server. The best
implementable proposal-only strategy measured here reaches only
`85.209 tok/s` on the honest three-class mean while pretending that a
64-row target tree costs exactly the same as the current 16-row verification.
Real wider-batch cost can only lower it. This lane uses no drafter training.

## Structure tested

The forest always retains the complete 15-token DFlash top-1 spine. Remaining
target rows add alternative tokens at any spine depth, optionally followed by
zero, one, or two of the subsequent marginal top-1 tokens. Branches are chosen
using proposal data only, under four implementable orderings:

- earliest mismatch depth;
- alternative probability;
- alternative/top-1 probability odds;
- alternative plus stale-suffix path probability.

The sweep covers verifier-tree budgets `15, 22, 30, 32, 44, 48, 64`, one to
three alternatives per position, and suffix lengths zero to two. It uses the
existing canonical full-rank DFlash prefix trace, whose target tokens and
linear acceptance already reproduce the fixed prose/code/JSON identities.
The target is never consulted when constructing a round's tree.

## Result

The best strategy was budget 64, up to three alternatives, a one-token stale
suffix, and earliest-depth ordering:

| class | target rounds | incumbent round time | zero-added-cost tok/s |
| --- | ---: | ---: | ---: |
| prose | 67 | `62.83 ms` | `60.813` |
| code | 47 | `61.61 ms` | `88.408` |
| JSON | 39 | `61.69 ms` | `106.405` |
| arithmetic mean |  |  | **`85.209`** |

For comparison, the existing official best-first DDTree analysis is stronger:
budget 64 reaches a `99.18 tok/s` same-cost ceiling. Even that cannot reach
100 with free expansion, and measured target batch 128 costs `2.48x` batch 16.
The sparse forest therefore neither creates new ceiling headroom nor offers a
reason to revisit the server tree integration.

## Evidence

- analyzer: `scripts/analyze-muse-dflash-repair-forest.py`, SHA256
  `2588fcc7ec0a15c58b785bbc185695a9ad855519c8b27e336d805a8ef49f114f`;
- focused tests: `scripts/tests/test_analyze_muse_dflash_repair_forest.py`,
  SHA256 `da78fec6fe24aa556f31ad342b5e41c17d6d6b2e1606435702c0025650b6c8aa`;
- structured sweep: `data/muse-dflash-repair-forest-coverage-20260813.json`,
  SHA256 `62017d56b91eb2c088e557674d2d2d81864bec68a0b031fc75a61ddbfd9fcb28`;
- source trace: the immutable full-rank DFlash trace documented in
  `2026-08-13-ddtree-full-rank-ceiling.md`.

The two analyzer test files passed `5/5` together in the established
`/home/steve/.venvs/deepseek-v4-xpu` environment. This was offline analysis;
no GPU, model service, or production state changed.
