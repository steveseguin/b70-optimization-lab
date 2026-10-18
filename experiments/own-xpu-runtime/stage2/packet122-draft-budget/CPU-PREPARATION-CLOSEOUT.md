# Packet122 draft budget CPU preparation — closeout
<!-- campaign-closeout -->

## Question and identity
Fresh complete-draft class budget on packet118 bundle7, fixed 80,128 prefix,
contexts 128/4096, two fresh B processes,47 event classes. CPU preparation only.

## Outcome
Device binary compiles and both temporary queue plans pass. Real hidden/token
captures are hash checked. The complete plan inventory matches all 47 byte
model rows. Device times remain pending; no historical number fills a gap.

## What worked
The probe isolates the draft without loading target layers, restores every
mutable draft allocation, checks exact replay, and accounts for every event.

## What failed or remains uncertain
A copied final callback referenced an unrelated micro analyzer; review removed
it and rebound the wrapper before device use. The binary stayed unchanged.
Two-minute runtime is an estimate. Context4096 cycles real captures and is not
a natural prompt. Actual event times and repeat variability remain unknown.

## Evidence and patches
[Build](evidence/microbench-build.json), [plan](evidence/micro-queue-plan.json),
[inventory](evidence/class-inventory.json), [roofline](ROOFLINE.md),
[retention](RETENTION.md), [lever ranking](LEVER-RANKING.md).

## When to revisit
Run the two coordinator proposals, then roofline.py. It rejects missing,
changed, incomplete or unaccounted evidence. Use the fresh classes to rank
follow-up work; the separate HC candidate has its own 20% kill gate.
