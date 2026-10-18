# Packet58q production variance — closeout

<!-- campaign-closeout -->

## Question and identity

Explain the October 18 production slowdown across packet58k/58n and the risk
to 58p, using saved one-B70, UD-IQ3_XXS quantized compressed model receipts.
Same native binaries, packet49 arithmetic, target-only decode, BF16 KV,
12 prompts × 128 tokens. CPU analysis only; no new model run.

## Outcome

Preparation accounts for 7.3364 of the 7.4085 added ms/token; major faults
rise from 0.1263 to 11.7365. Miss counts/bytes match at every position.
The candidate's zero-fault state is not guaranteed by tile16. No record,
promotion, runtime change or new speed verdict is made.

## What worked

Extending a copy of 58n's analyzer to all five arms isolates the slowdown
without running a model. Source inspection distinguishes file-backed sparse
lookups from the pinned expert banks shared by both layouts.

## What failed or remains uncertain

No fault-address trace, isolated GPU/zero-copy times, or cache-residency history
was captured. Archive moves and layout-dependent loading remain hypotheses
for residency differences. Tight production controls do not remove the
candidate's different lookup-fault state. A constant-zero fault series has
undefined correlation; the adapted tool now records null for that case.

## Evidence and patches

[Analysis and coordinator recommendation](ANALYSIS.md),
[input hashes and snapshots](analysis-inputs.json),
[copied-tool provenance](tool-provenance.json),
[replay validation](validation.json). No runtime patches. Existing packets
and evidence remain untouched; missing originals replay inside 58q only.

## When to revisit

Read 58p's actual preparation/fault counters after its registered windows.
Any future matched performance claim needs independent timing and the lane's
quality gates. Do not add page warming, settings changes, selective retries
or fault-time subtraction. This closes the CPU question, not the model lane.
