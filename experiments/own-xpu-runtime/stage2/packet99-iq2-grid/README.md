# Packet99: exact IQ2 lookup mechanisms

CPU-qualified candidates copied from frozen packet97 sources. No GPU ran in
this task. Production remains selected; there is no new model speed result.

Gate/up uses a dependent global IQ2 grid read and inline sign bits. Down uses
IQ4_NL immediate-register decode. [Exact addressing, history and linked code](DIAGNOSIS.md).

Three IQ2 mechanisms are built: the original grid in SLM, a compact exact grid
in SLM, and that compact grid in global constant data. Each has a separate
half-cache composition form. All six IQ2 candidates have zero linked spills.
The exact IQ4 byte-pair table spills and is [closed](DOWN-CLOSEOUT.md).

Evidence:

- [GNU/Intel byte identity](evidence/cpu-byte-identity.json): eight views,
  two fresh runs per compiler; 28 cases, 118,784 raw FP32 chain comparisons and
  3,456 tree comparisons per run. Includes full expert output shapes,
  exceptional values, invalid routes and exact decoded grid/sign checks.
- [Full-size startup](evidence/full-shape.json): 16 rank/view paths through real
  allocation and capture, 32 short/misaligned refusals and five malformed
  selections. Only backend/payloads are mocked. [Memory admission](evidence/full-shape-admission.json)
  uses actual arena censuses and unchanged 30 GiB / 1.5 GB margin rules.
- [Linked assembly/vISA](register-report-offline.json): SLM d32x2 or d32 reads
  for local modes; global d32 for the compact global mode. Rejected down
  assembly is retained with its spill count.
- [Python gates](evidence/python-tests.json): 80 shared-wrapper tests and 20
  focused threshold, lane, exactness and CPU-plan checks.
- [Engine build](build-device-receipt.json), [micro build](evidence/microbench-build.json)
  and [screen seals](screen-jobs-seal.json).

The binary retains packet97's head, reply-first, HC norm, route and recurrence
dimensions. The seven sealed views isolate the new expert choice against
wide64/hc-wide/ordered/rec-parallel, with the production head. Half-cache forms
use the real 840-byte loader/kernel stride. Other combinations remain subject
to selected-composition gates; independent deltas do not certify a composite.

Use only the entry points in [WINDOW.md](WINDOW.md) for this packet. Other copied
packet97 helpers are retained source context, not newly qualified record or
submission entry points. [Preregistration](PREREGISTRATION.md),
[boundaries](DO-NOT-REPEAT.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md),
[artifact retention](RETENTION.md).
