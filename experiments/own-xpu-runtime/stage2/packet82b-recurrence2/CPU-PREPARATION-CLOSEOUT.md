# Packet82b recurrence round 2 — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can the packet82 gate and normalization changes compose on packet84, and can
more serial preparation be removed without changing a state or output byte?
October 18, 2026; CPU-only preparation on steve-b70s for the B70 Flash-Next
quantized compressed model lane, arithmetic `iq3-p49-split32-v1`.
The unchanged packet84 control uses rec-parallel, hc-wide, ordered cleanup,
wide64 experts, draft-HC, batch rollback, draft rank 1 and target 24/24.

## Outcome

CPU preparation passed. The composition question closed as already implemented:
rec-parallel already contains rec-gates. The requested rec-both view is its
exact kernel alias and cannot qualify as a performance winner.
rec-both-plus removes the guard-only workgroup barrier. No device correctness
or speed result exists for it yet; the next step is the coordinator's screen.

## What worked

* GNU-host and Intel-device engines built sequentially; the device engine was
  not executed. Peak compiler child RSS was 731,396 KiB.
* GNU and Intel each passed two fresh executions of all three recurrence
  views: 12 runs, 260 full-state/output/control comparisons per run, 416 token
  steps per run. Four consecutive calls and a four-token call cover in-place
  and separate state, both head mappings, inactive/error/boundary cases,
  NaNs, infinities, subnormals and gate thresholds. Each run also checks 90
  integer guard cases. All candidate bytes equal same-compiler production.
* All six full-size startup/capture paths passed with HC-wide and ordered
  cleanup enabled. Both ranks use the same post-load allocation totals across
  views: 27,685,394,516 and 31,267,162,826 bytes. Five invalid selections and an
  undersized packed-head allocation refuse before execution.
* All 87 Python checks passed: 80 unchanged wrapper/admission tests plus 7
  packet tests. They verify both grids, eligible confirmations, rejection of
  alias drift, source-body equality and fixed packet84 choices.
* Offline BMG-G31 assembly has 3→2 static barrier sites, 128 configured GRFs
  for both versions and no scratch spill messages. Static instruction count
  is 2753→2757, not a measured speed improvement.
* Three view seals, two full grids, two opposite-lane confirmation plans and
  all four proposed queue files pass CPU checks. Queue planning uses temporary
  copies. Logical build storage is 211,919,023 bytes, below 1 GB.

## What failed or remains uncertain

The separate rec-gates + rec-parallel combination is not a new mechanism.
There are 20 pre-existing cross-compiler production NaN cases; raw inspection
shows only NaN payload differences. Every same-compiler candidate comparison
is exact, including those bytes. No tolerance or canonicalization is used.

The first offline counting helper counted barrier payload setup instructions
as well as barrier sends. The corrected retained helper counts `send.gtwy`
signal-barrier instructions, matching the three/two static source sites.
Both original assembly artifacts remain retained. No runtime rebuild was
needed for this reporting correction.

The guard proof depends on the existing in-order queue and immutable device
controls during the recurrence. CPU mirrors do not execute device subgroups.
Actual barrier behavior, output/oracle parity, acceptance and speed remain
pending device checks. These shorter screens cannot establish a public
performance claim or replace full quality/determinism/promotion gates.

## Evidence and patches

* [Analysis and control proof](ANALYSIS.md), [source parents](parent-source-manifest.json)
* [Build receipt](build-device-receipt.json), [reused object identities](evidence/object-identity.json)
* [CPU byte/state identity](evidence/cpu-byte-identity.json), [full-size startup](evidence/full-shape.json)
* [Python checks](evidence/python-tests.json), [offline comparison and retained startup receipts](evidence/offline-comparison.json)
* [Screen seals](screen-jobs-seal.json), [final plans](evidence/final-check.json), [temporary queue plans](evidence/queue-plans.json)
* [New prologue](p82b_recurrence.hpp), [selection integration](p49d_submit.cpp), [retention/rebuild](RETENTION.md)
* [Packet84 integration patch](integration.patch), applied on a temporary copy
  and checked byte-for-byte against both new runtime source files.

No old packet, shared screen file, live queue, GPU job, service or host setting
was changed. Initial pull --rebase refused existing unrelated edits; fetch
confirmed HEAD and origin/main matched. Those edits were not stashed or moved.

## When to revisit

Run one full-grid proposal after normal coordinator admission; confirm the
exact improving rec-both-plus on the opposite lane between fresh controls.
Both grids are available, but duplicate grids are not required. If the new
view loses, retain the packet84 control and close this barrier-removal lever
with its receipts. Never treat an apparent rec-both alias win as an improvement.
