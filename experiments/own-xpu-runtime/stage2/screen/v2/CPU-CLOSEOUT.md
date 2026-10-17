# Screen v2 CPU preparation closeout — 2026-10-17

## Question and identity

Can screens use the record chains' nice0 conditions, admit a second pair,
pass packet57 timing modes and compare both orderings concurrently without
near-simultaneous teardowns? Scope: the existing packet56 TP2 screen contract,
unchanged packet49 target oracle and sealed packet56/57 controller families.

## Outcome

Implemented in this separate folder. Python sources compile in memory, all
13 focused checks pass and the full fake-transport v1/v2 request receipts are
byte-identical. The wrapper is sealed; device entry points verify its closure.
Both candidate seals pass CPU-only planning. The passive boot check found
exactly two fault records before deriving the retained review boundary.

No GPU, model payload, new native build, service, sudo, host setting change,
parent packet edit or external submission ran. Device exactness, actual A/B
memory pressure, timing-mode event completeness and runtime duration remain
coordinator checks. No performance improvement is claimed.

## Mechanisms and retained evidence

- Fixed lane cards, PCI checks, nice0 affinity and private locks/outputs.
- Lineage-specific sealed controller imports and explicit timing support.
- Both lanes admitted before launch; both suites complete before normal drain.
- Global v2 drain serialization and 60 seconds after complete drain, including
  cooperative error cleanup; no retries, hard kills or automatic recovery.
- Exact-count boot review and unchanged packet49 12×128 token checks.
- Both signed orderings, per-class comparisons and a balanced ratio report.

[Checks](cpu-tests.log), [byte fixture](byte-fixture.json),
[seal](wrapper-seal.json), [CPU plan](plan.json),
[passive review](evidence/cpu-review.json), [commands](README.md).
The fixture and compressed kernel capture are small and retained here; there
are no object files or copied model weights. The kernel capture was compressed
and verified byte-for-byte before deleting this task's regenerable raw copy.

## Limits and revisit conditions

One crossover cannot reliably rank a 1–2% gain. Repeat fresh crossovers if the
paired difference is that small. Attribution is diagnostic. A native crash
cannot obey a Python teardown schedule; any such failure invalidates the pair
and blocks subsequent work. A changed allocation envelope needs a new profile.

All edits stay under this task's folder per the brief; `CURRENT.md` is left for
the coordinator. V1 evidence and sealed packets remain unchanged. Initial
`git pull --rebase` refused because another job had dirty files; a fetch
confirmed HEAD and origin/main were identical, without touching those files.

Before committing, the other job's tracked edits had been committed. A second
`git pull --rebase` succeeded and fast-forwarded main; the wrapper seal still
verified after that update. Its owner-rule update does not change this brief's
exact-two-fault admission or CPU-only preparation scope.
