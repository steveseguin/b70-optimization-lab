# Packet 96 conditional dual guess — closeout

<!-- campaign-closeout -->

## Question and identity

Could selecting a second rank0 guess using only draft logits improve packet84's
55.69 tok/s line by at least 1.5% under conservative costs? CPU analysis on
2026-10-18 UTC, steve-b70s. Packet31 supplies 256 old CPU development positions;
packet77/85 supplies 24/24 wide64 command/class costs, and packet84 supplies
the matching 4096-capacity census. These identities are distinct.

## Outcome

Rejected for implementation/sealing. Training chooses never in all four cost
scenarios, including favorable sharing. Held-out predicted improvement is
0.00%, below 1.5%. No new device speed or arithmetic result is claimed. Memory
can reserve all duplicated nonweights with 3.750 GB arena headroom left.

## What worked

The logit-only feature search, prompt-held-out fits, temporal checks and
one-position-delayed cost/rescue accounting are reproducible. The code recovers
packet85's equations and packet31's 198/226/245 membership counts. None of the
tested policies qualifies an optimization. The complete threshold table is kept.

## What failed or remains uncertain

Recoverable misses are too sparse among flagged positions. Margin < 1 flags
58 positions but rescues only 15. Extra expert/state work consumes the small
rank0 slack. True top-1 probabilities, production-draft transfer, actual sibling
route overlap, M2 latency, extra copy time and a whole-engine arithmetic/state
guarantee remain unmeasured. Four correlated prompts are not a benchmark suite.

## Evidence and patches

[Decision and assumptions](DECISION.md), [JSON](DECISION.json),
[thresholds](thresholds.json), [model](model.py), [plan](PLAN.md),
[dated note](notes/2026-10-18-own-runtime-packet96.md),
[negative-result entry](DO-NOT-REPEAT.md). Input hashes are in DECISION.json;
the reproducer reads retained repository evidence only. No runtime patch,
binary, seal, service or queue proposal was created. Existing evidence remains
at its original paths; no external payload is required to rerun this model.

## When to revisit

A distinct mechanism and matched production-draft samples must support a
materially cheaper complete dual half, then pass a new held-out +1.5% model
gate and exact per-row/state gates. Do not rerun threshold searches on these
same 256 development positions or reopen depth two/draft relocation. This
closes the lever, not the optimization lane.
