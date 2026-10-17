# Packet82 recurrence CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can a single recurrence launch use its waiting subgroups for independent
preparation while retaining every operation and rounding step? October 17,
CPU-only on steve-b70s, BMG-G31 offline compilation. Packet75 source bundle,
packet70 record configuration, `iq3-p49-split32-v1`, 24/24 target placement,
rank1 draft, wide64 experts, production HC/dense, draft-HC and batch miss copy.
BF16 recurrent state, FP32 intermediate arithmetic; no model/weight changes.

## Outcome

CPU preparation passed for production, rec-gates and rec-parallel. Analysis
was pushed first (`12a393fc4`), then candidates/build/byte gates (`67bc458cb`).
Three seals, four lane-A plans, six possible lane-B plans and both temporary
queue plans pass. No GPU, model payload, service, live queue, settings change,
sudo, power change, reboot or kill was used. There is no measured speedup.

Each view passes two fresh GNU and two fresh Intel runs: **200 full-state
comparisons / 320 token steps per execution**, 318,507,360 raw bytes compared.
Across all twelve runs this is 2,400 comparisons. State and output are checked
after every one of four consecutive calls, and after four-token calls, with
both in-place and separate state, both head mappings, guards, NaNs, infinities,
subnormals and gate thresholds. Digests are recorded only after raw equality.

All six full-size startup runs pass through actual post-load allocation,
configuration and command capture. Selected operation types confirm the chosen
recurrence. Rank0/rank1 logical device allocations remain 27,685,394,516 /
31,267,162,826 bytes, unchanged across views and within the original 30 GiB
limit. These are mock allocation extents, not physical memory measurements.
The undersized packed head and five invalid selection cases refuse correctly.
All 85 Python checks pass. Build storage is 212,789,205 bytes (about 203 MiB);
peak engine compiler RSS was 726,072 KiB (about 709 MiB). Compiles were serial.

## What worked

Giving decay and beta to different subgroups retains the exact production
state-update body. Separating Q and K normalization also keeps their individual
adjacent reduction trees and strict divisions. All work stays within the same
WG128/SG32 launch, 1,536 groups, 1,036 bytes SLM/group, with no new scratch or
state layout. Both candidates compile with 128 configured GRFs and no scratch
spills. Static instructions: production 2,892; rec-gates 2,910; rec-parallel
2,754. This supports screening, not a performance verdict.

## What failed or remains uncertain

The initial cross-compiler transcript assertion failed because GNU production
and Intel production differ on the 20 deliberate NaN cases. A follow-up raw
comparison proved every differing element is a NaN payload, with controls and
all other cases identical. Every candidate still matches **every byte** of its
own compiler's production, including NaN payloads; nothing was canonicalized,
tolerated or omitted from that gate. Cross-compiler baseline differences remain
in the receipt. CPU mirrors do not prove GPU codegen or exceptional behavior.

Flag spill metadata increased from production 10 stores/14 loads to 13/16
(rec-gates) and 14/18 (rec-parallel). No scratch messages are present, but flag
pressure and scheduling could erase the proposed overlap. Actual occupancy,
latency overlap, per-layer speed, GPU state identity and full-model output
remain unmeasured. Packet67's separate rec-head prepass remains closed.

The initial rebase pull refused other workers' dirty files; fetch showed no
incoming commits then. Concurrent main commits and all frozen trees were
preserved. The temporary copied RoPE payload was changed back to an inherited
symlink only after complete byte equality verification; all consumers and
content hashes stay identical. Historical copied chain helpers are not a
registered packet82 chain; use only the screen entry points in WINDOW.md.

## Evidence and patches

- [Analysis](ANALYSIS.md), [offline comparison](evidence/offline-comparison.json),
  [production assembly report](register-report-production.json),
  [candidate assembly report](register-report-candidate.json).
- [Candidate kernel](p82_recurrence.hpp), [production registration](p49d_submit.cpp),
  [CPU fixture](p82_cpu.cpp), [source provenance](parent-source-manifest.json),
  [inherited object provenance](evidence/object-identity.json).
- [Byte receipt](evidence/cpu-byte-identity.json), [initial exceptional mismatch](evidence/cross-compiler-exceptional-differences.json),
  compressed complete transcripts under `evidence/cpu-transcripts/`.
- [Full-shape receipt](evidence/full-shape.json), [Python tests](evidence/python-tests.json),
  [sealed plans](evidence/final-check.json), [temporary queue plans](evidence/queue-plans.json),
  [screen source seal](screen-jobs-seal.json), [retention](RETENTION.md).

## When to revisit

The coordinator next runs the lane-A grid, then only its exact improving winner
between fresh lane-B controls. [Proposed jobs and commands](WINDOW.md).
Device byte/output gates decide whether either candidate is adoptable; full
registered promotion gates are still required for any headline. This closes
CPU preparation only. No speed claim or candidate adoption is made.
