# Packet58yb coordination repair — closeout

<!-- campaign-closeout -->

## Question and identity

October 18 CPU-only repair of packet58y, unchanged `iq3-p49-split32-v1`,
one-card tile16/18 GB overlap diagnostic. No device or model/full-shape work.

## Outcome

The gate uses only the current continuous coordinator hold and this job's START.
The proposal targets fresh `card0-attribution-b/attrib`, planned but not queued.
Native artifacts and numerical host/device bounds are unchanged.

## What worked

104 policy tests, 19 admission replays, 10 analysis tests and three intercepted
native-entry paths pass. Real parsers, closed environment and the exact proposed
unit are checked; the actual hold gate reads scratch hold/START fixtures.
The complete nested pin audit and real temporary coordinator planning pass.

## What failed or remains uncertain

Planning exposed further inherited sibling pins and historical copy hashes.
They were moved into verified local provenance. The inherited admission replay
paths were also fixed to use local archives. Failed planning logs are retained.
No live PAUSE-B exists at preparation, so actual hold admission correctly refuses.
No device quality, speed or next-lever ranking is newly claimed.

## Evidence and patches

[CPU evidence](evidence/reseal-cpu.json), [temporary plan](evidence/queue-plans.json),
[hold gate](batch_gate.py), [nested pin gate](source_pin_gate.py),
[retained source bytes and restore instructions](RETENTION.md).
Prior seals and the original copy manifest remain under `lineage/`.

## When to revisit

The coordinator may admit the fresh diagnostic inside an existing continuous
one-card whole-host hold. It owns order, pause/drain and fault admission.
Any future dependency change must pass the nested pin gate before resealing;
launched packets cannot use this pre-device repair exception.
