# Generated sparse-state development screen

Protocol: `sparse-state-development-v1`. This is a prospective generated study,
separate from the authored semantic packet and all frozen r4/semantic results.
Preparation and tests are CPU-only. No server launch or GPU command exists here.
Live execution remains subject to the parent's preregistration, review and
supervised host lifecycle; this directory does not authorize a model run.

Seed 83 and report-style text are fixed. The two tasks have 8 and 128 counters,
initialized by explicit postings in chunks of at most 16. Each then receives
16 batches containing three balance changes. Both methods see identical source
bytes within a size. The two sizes are different streams, not replications.
The last counter is reserved from every subsequent update and appears in the
questions; seven queried counters are updated. There are eight current, eight
integer historical and eight historical ownership-join questions.

The key is **programmatically generated**, not independently annotated. A separate
controlled-grammar reader parses source postings and replays them; the check also
parses emitted ownership/review statements and requested question names/times.
Compiled tasks retain this generated provenance. No independent annotation file
or adjudication receipt is fabricated.

## Pinned reuse and process isolation

[`pinned-engine.json`](pinned-engine.json) pins all five runtime Python files in
[`semantic_v1`](../semantic_v1/). `engine.py` verifies that inventory and imports
the frozen compiler directly. For execution it starts in a fresh Python process
before importing the low-level trial engine, avoiding absolute-import collisions.
No frozen semantic source is edited. The inner result schema
`semantic-live-trial.v1` and inner protocol `semantic-development-live-v1` identify
implementation compatibility only; they do not classify sparse tasks as authored
semantic documents. Outer task provenance, plans, results and summaries identify
the generated sparse study explicitly.

The order is fixed: 8/archive, 8/quoted, 128/quoted, 128/archive. Both methods retain
the full state in their input. Limits are unchanged: 32,768 serialized prompt
bytes, 6,553 memory bytes, three ingestion attempts, 4,096 thinking-off ingestion
tokens, 8,192 medium-thinking answer tokens, 24 retrievals and 32 answer calls.

## Preparation and validation

Use a new packet directory, separate from a future results directory:

```sh
python3 experiments/qwen38-27b-b70/scripts/context/sparse_v1/runner.py \
  --prepare-only --out /path/to/new-prepared-packet
python3 experiments/qwen38-27b-b70/scripts/context/sparse_v1/runner.py \
  --validate-packet --packet /path/to/new-prepared-packet
```

The default local tokenizer is
`/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json`; the tokenizer interpreter
is `/mnt/fast-ai/venvs/clm/bin/python3`. Override with `--tokenizer` and
`--tokenizer-python` during preparation. No downloads are allowed. Missing local
dependencies block preparation, rather than becoming a reason to try the model.

Preparation writes source documents, private compiled tasks, `plan.json` and
`budget-receipt.json`. The receipt runs explicit oracle wiring trials with the
pinned engine and counts reference reply tokens with the local tokenizer. JSON
formatting is included. It checks actual reference prompt serialization and a
6,553-byte plain-ASCII-memory variant. These checks demonstrate feasible reference
emissions, not that arbitrary model output, reasoning or escaped memory will fit.
Runtime caps still apply and failures are retained. This is not model evidence.

`validate_packet(packet)` returns `{'plan': ..., 'budget': ..., 'tasks': ...}` for
host preparation. It regenerates the exact fixed tasks, checks policies, files,
source pins and tokenizer identity, and reruns the CPU budget calculation against
the stored receipt. Call it in an isolated process when other bare task modules
may already be imported. The wrapper also validates around each trial; these CPU
validation periods are outside the native trial wall-time measurement.

## Wiring and prospective execution

CPU wiring uses a separate new result directory:

```sh
python3 experiments/qwen38-27b-b70/scripts/context/sparse_v1/runner.py \
  --packet /path/to/new-prepared-packet --out /path/to/new-stub-results --stub
```

A reviewed host supervisor can instead pass `--execute --endpoint LOCAL_URL
--model MODEL --identity LAUNCH_JSON` with a new `--out` directory. The wrapper
holds the shared model lock; it neither starts nor stops a server. It owns its
CPU tokenizer/HTTP worker children. On cancellation it terminates and reaps its
own child; a bounded CPU-only kill is a last resort if that child ignores TERM.
There is no automatic retry, resume, cap increase or GPU-process kill.

Each trial produces an outer `sparse-state-trial.v1` result and an untouched
inner engine result under `native/`. Accepted raw archive states and quoted
counter/operation/amount sequences are checked independently at every batch.
Quoted source-span variation is allowed; net-zero extra events or changed order
cannot hide behind correct final arithmetic. All final answers must be exact.
Refused attempts remain evidence and consume costs; a corrected bounded refusal
does not itself disqualify otherwise exact accepted output. Stub checks can pass
`reference_checks_passed`, but never the model `quality_passed` flag.

Costs are split into initialization, steady ingestion and answering, plus totals.
Per-phase seconds are **client call seconds**, not fabricated complete phase wall
times. Total native wall time and unallocated non-call overhead are reported
separately. Every logged retry is included; missing token/cache counters remain
unknown. Cache hits or unknown counters prevent a cold-cost interpretation.
Both speed promotion and holdout-admission flags always remain false. A single
server and a generated screen do not establish a performance conclusion.

Run the CPU suite:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s experiments/qwen38-27b-b70/scripts/context/sparse_v1 -p 'test_*.py'
```
