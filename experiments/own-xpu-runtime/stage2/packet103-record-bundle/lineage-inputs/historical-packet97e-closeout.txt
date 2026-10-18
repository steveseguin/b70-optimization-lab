# Packet97e: KD startup repair

<!-- campaign-closeout -->

## Question and identity

Can decision `f1e5d7f47fc0fe54` run KD's exact draft reference with E1 selected,
without loading the unused resident target or changing any arithmetic?

## Outcome

CPU preparation passes. KD binds a draft-only selection to the frozen target
selection, preserving every draft kernel and exactness check. The E1 target
guard is unchanged. The same decision is ready in fresh `device-cards01-b`.
No device chain was launched.

## What worked

The real window parsers and native startup paths pass for all 128 compositions
and eleven windows (1,408 checks). The gate takes 756.482 seconds and about
1.2 GiB RSS. Existing selection-free CPU fixtures are shared. Both original
binaries, frozen decisions, 128 screen seals and old chain evidence are intact.

## What failed or remains uncertain

The original KD streaming defaults cannot satisfy E1's prepared resident guard;
the regression test retains that refusal. Resident target startup needs about
31.6 GB and cannot serve as the bounded CPU reference. CPU mocks establish
guards, allocation shapes and kernel identity, not full model/device parity.
KD's full byte comparisons and all later device gates still must run.

## Evidence and patches

- [Work note](../../../../notes/2026-10-18-own-runtime-packet97.md)
- [All-window receipt](startup97e.json) and [raw cases](evidence/startup97e-runs.json.gz)
- [Bounded reference](kd_reference.py), [KD window](kd_window97e.py),
  [strict replay](kd_projection_replay.py), [entry adapter](chain97e.py)
- [Readiness and exact manual command](../../ops/packet97-orchestration/ready.json)
- [152 passing tests](../../ops/packet97-orchestration/tests-97e-full.log)

## When to revisit

Reopen if KD runs target layers, a draft choice changes, reference residency
changes, or the unchanged device exactness chain finds a mismatch. Re-run the
source-bound all-window CPU gate after changing any covered startup path.
