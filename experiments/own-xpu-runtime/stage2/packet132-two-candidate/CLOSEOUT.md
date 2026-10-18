# Packet132: confidence-gated second candidate — closeout

<!-- campaign-closeout -->

## Question and identity

Could draft confidence select a second speculative sibling often enough to
gain at least 3% after its cost? CPU-only study on steve-b70s, October 18, 2026.
The target is Unsloth UD-IQ3_XXS, the quantized compressed version of Qwen3.8
Flash-Next, using packet49 `iq3-p49-split32-v1`. The draft is packet31's INT8
CPU semantic reference with IQ3 embedding/head and the 80,128-row prefix.
Five mechanically selected excerpts from packet114's pinned independent text
produced 120 target positions. The twelve-prompt benchmark did not supply
calibration or evaluation rows. [Plan and identity](PLAN.md).

## Outcome

Rejected under the preregistered +3% screening gate. The favorable primary
model chooses never (0.00%); the best policy with any second-candidate work is
−0.20%. Even expert-only cost gives only +2.25% pooled and +1.77% held out.
No runtime candidate, GPU measurement or quality claim was produced.
[Result](result.json) and [analysis](ANALYSIS.md).

## What worked

The independent CPU capture completed all five fixed excerpts without retries.
Second choice matches the target on 13/56 misses; always allowing both changes
candidate membership from 53.33% to 64.17%. Confidence margin <1.125 captures
nine rescues on 38 flags. Training choices were frozen before held-out rows
were examined. Eight analysis tests, source audit, exact table recomputation
and byte-preserving retention checks pass. This qualifies the diagnostic
method, not a runtime optimization.

## What failed or remains uncertain

Rescues do not pay for the modeled extra rank0 work. The best registered gate
needs an added half of at most 1.952223 ms to reach +3%, even granting 15 ms per
rescue and free state/policy work. Primary cost is 4.153946 ms; expert-only is
2.345046 ms. No faults occurred. Packet128b instrumentation failed its overhead
gate; M=2 timing and route overlap are unmeasured. CPU draft/device parity and
second-state-bank ownership are unproved. Short excerpts have a 46.67% miss
rate versus the production brief's roughly 21%, so no production acceptance
or universal impossibility claim follows.

## Evidence and patches

[All thresholds](thresholds.csv), [structured sweep](thresholds.json.gz),
[training selection](evidence/training-selection.json),
[source audit](evidence/source-audit.json),
[environment](evidence/environment.json),
[raw retained rows](evidence/capture/rows.json) and
[retention/restore manifest](evidence/capture/retention-manifest.json).
The capture, analysis and audit scripts are local to this packet. The six
archives preserve target streams and private oracle source bytes; all 81
copied artifacts and archive members were checked. Originals remain in ignored
`build/capture`; external weights and local binaries are not committed.
The [analysis](ANALYSIS.md#reproduce-the-analysis) records reproduction limits.
No production runtime patch exists for this arm.

## When to revisit

Only with a concrete new mechanism and evidence that total incremental M=2
work can fit below the 1.952223 ms favorable budget, or materially better
confidence discrimination on a new preregistered independent corpus. First
resolve CPU/device identity, exact row arithmetic and complete sibling-state
ownership. A larger threshold search over these same rows is not new evidence.
This closes this arm, not the model lane. [Negative-result row](DO-NOT-REPEAT.md).
