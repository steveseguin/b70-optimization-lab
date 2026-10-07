# Historical accepted-state development study

This separate client implements the eight fixed comparisons in
[the study plan](../../../notes/2026-10-07-history-state-study-plan.md), using
protocol `historical-state-study-v1`. It starts no server and admits no extension,
holdout or speed claim. Preparation and stub runs are CPU work.

The fixed order is t01-clinic AS, QH, QS, AH, then t02-theatre AH, QS, QH, AS.
A/Q mean archive/quoted bookkeeping; S/H mean source-only/history answer access.
Every row performs fresh ingestion. Both modes persist and verify identical
snapshots of actual accepted state, including wrong archive values. History
changes the final instruction and enables `state_at`; ownership still requires
source evidence. This measures that combined instruction/tool policy.

`engine.py` starts an isolated worker using the hash-pinned frozen `history_v1`
engine. Native records retain `history-live-trial.v1` and protocol
`historical-state-development-v1`; outer records use `history-study-trial.v1`.
Source, annotations, reference-check script and decision notes are copied and
hash-bound through `input-pins.json`. Tasks must equal the frozen compiler output,
including question identities. These are short assistant-authored and annotated
development documents, with no claim of human or external validation.

Limits remain 32,768 serialized prompt bytes, 6,553 memory bytes, three ingestion
attempts, 4,096 ingestion output tokens with thinking off, 8,192 answer tokens
with medium thinking, 24 distinct successful retrievals and 32 answer calls.
Cached retrieval repetitions still use answer calls. There is no resume, cap
increase or transport retry. Bounded model failures retain evidence and continue
the matrix; infrastructure/integrity failure aborts with explicit unstarted rows.
Cancellation terminates and reaps only the wrapper's own CPU interpreter.

## Interfaces

Run from this directory. Preparation requires the actual local tokenizer and an
interpreter with `tokenizers`; missing assets block preparation, without downloads.
The owner prepares the final packet after review:

```sh
python3 runner.py --prepare-only --out /path/to/new-packet \
  --tokenizer /path/to/tokenizer.json --tokenizer-python /path/to/python3
python3 runner.py --validate-packet --packet /path/to/new-packet
python3 runner.py --stub --packet /path/to/new-packet --out /path/to/new-stub-output
python3 -m unittest test_study -v
```

`prepare()` and `validate_packet()` return `{plan, budget, tasks}`. The plan binds
all eight rows, policies, source pins and prospective continuation rule. The
`history-study-budget.v1` receipt uses actual tokenization: its CPU fixture fetches
all twelve source batches, then all nine requested earlier states for history,
then submits gold answers (13 source-only or 22 history answer calls). Every
prompt is also reserialized with a full 6,553-byte ASCII memory field; ingestion
responses with that field are tokenized too. This establishes reference fit, not
a bound on arbitrary escaped memory, model reasoning or wording. Stub results
cannot pass model quality, cold interpretation or extension admission. Portable
tests need no model assets; local-tokenizer tests explicitly skip without assets.

A separately authorized host supplies a qualified endpoint and launch identity:

```sh
python3 runner.py --execute --packet /path/to/prepared-packet \
  --out /path/to/new-results --endpoint http://127.0.0.1:18196/v1 \
  --model MODEL --identity /path/to/launch-identity.json
```

This documents the interface, not launch authorization. Output must be fresh and
separate from the packet. Source, packet, tokenizer, interpreter and runtime
identity are checked at trial boundaries.

## Evidence

`summary.json` (`history-study-summary.v1`) always lists all eight ordered rows,
with condition, mode, task/question hashes and relative outer/native paths.
`unstarted_trials` is a list; `observed_trials` counts written outer receipts.
Normal completion can include bounded failed trials. Infrastructure abort retains
partial files.

Outer records retain native artifact and auxiliary SQLite/identity hashes,
raw-derived action counts, strict reference checks, snapshot integrity, answer
category scores and phase costs. Initialization, steady ingestion and answers
include every attempted call; total elapsed includes persistence. Unknown/nonzero
cache cannot support cold interpretation. Provenance-listed copied audit helpers
reconstruct actual responses, events and snapshots. Snapshot integrity alone does
not prove quality. A post-apply snapshot-write fault can produce an audit error;
raw native evidence remains and execution aborts without retry.

The client records but does not evaluate or execute the prospective t03/t04
extension. Independent review must establish exact history rows, no category
loss, and the registered answer gain or consistent cold cost signal. Automatic
extension, speed and holdout admission remain false. Older timings without
identical snapshot work are not equivalent controls.
