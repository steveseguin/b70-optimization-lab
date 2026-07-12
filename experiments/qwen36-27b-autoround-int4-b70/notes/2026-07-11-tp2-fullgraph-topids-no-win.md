# TP2 full-graph target top-ID verifier: no win

## Scope

The existing exact greedy-verifier consumer was tested for the first time on
the promoted TP2 full-target-graph transaction stack. Each TP rank still
materializes its dense local INT8-LM-head logits, but reduces to a local
`(value, token)` pair before communication rather than all-gathering the full
vocabulary. Accepted speculative tokens remain target verified.

## Swapped crossover

With the legacy extra token-ID broadcast enabled:

- window 1: `93.823` candidate vs `89.863` dense control;
- window 2: `90.642` candidate vs `93.117` dense control;
- pair-balanced mean: `92.233` vs `91.490`, nominal `+0.81%`, sign-changing
  and inside variance.

`get_top_tokens()` already all-gathers the pair and performs the same
deterministic reduction on both ranks, so the subsequent broadcast was
disabled and the crossover repeated:

- window 1: `92.759` candidate vs `91.513` control;
- window 2: `91.105` candidate vs `95.753` control;
- pair-balanced mean: `91.932` vs `93.633`, **`-1.82%`**.

Every row passed the fixed realistic fresh-response gate with
`cached_tokens=0`. Quality was intentionally skipped after the speed gate.

## Decision

Close dense-producer target top-ID plumbing as a speed lane. Avoiding the
full-vocabulary TP gather does not cover the added local max/pair reduction;
the actual remaining target is a producer-integrated LM-head top-ID operation
or a captured verifier tail that avoids dense logits rather than adding work
after dense logits exist.

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-fullgraph-topids-sync1-crossover-20260711.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-fullgraph-topids-sync0-crossover-20260711.json`;
- `experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-topids-candidate.sh`.
