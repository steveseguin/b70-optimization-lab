# Packet63 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Combine packet61x's controller spin, pure-spin waits and target HC fusion with
packet59c's draft HC group on the Flash-Next IQ3 quantized compressed lane.
Use its unchanged target arithmetic, packed weights, 23/25 placement, BF16 KV
and packet49 oracle. Examine a 22/26 option only if current rank0 work exceeds
rank1 by about 0.5 ms. CPU-only preparation on steve-b70s, October 17, 2026.

## Outcome

Two selections, `control` and `draft-hc`, share one built device executable.
Build, packet56 target fixture equality, fresh draft repeats and all four v3
plans pass. The 22/26 option is skipped: rank1 is slower in all current screens
and finishes last in all 4,536 complete cycles. No device or speed claim.

## What worked

The existing strict draft selector permits the exact fourteen-switch HC group
without changing the target path or the other draft groups. Lean compilation
reuses unchanged objects as hardlinks. Each of four candidate mini runs matches
96 layer fixtures and 24 tokens against packet56; each pair agrees on 27 draft
proposals and five state files. Control also equals packet61x. Two synthetic
production-width output files agree, and eleven parser checks pass.

## What failed or remains uncertain

The proposed split fails the timing prerequisite before memory admission.
Packet57's rank0 diagnosis is stale for packet61x. Draft and target command
wall times are not exact GPU-time partitions. The HC group's old +0.5% screen
is motivation only; its gain with packet61x, device determinism, acceptance
and target-oracle parity remain unmeasured. The initial source copy omitted
inherited prototype headers; the failed CPU preparation log is retained and
the complete source snapshot built successfully. No GPU fault occurred here.

## Evidence and patches

[Packet receipt](packet.json), [CPU gates](evidence/cpu-gates.json),
[diagnosis](evidence/diagnosis.json), [compressed cycle rows](evidence/cycles.jsonl.gz),
[compile inputs](build-device-receipt.json), [source manifest](parent-source-manifest.json),
[retention](RETENTION.md), [task note](../../../../notes/2026-10-17-own-runtime-packet63.md).
Original completed-screen receipts remain in ignored v3 evidence; compact
extracted timings and source hashes are retained here. No model payload scan.

## When to revisit

The coordinator screens `draft-hc` and `control` on admitted lanes. Any record
candidate still needs the unchanged full chain. Revisit 22/26 only if a later
current-configuration measurement shows rank0 exceeding rank1 by about 0.5 ms,
then admit exact memory before building. Packet61x's existing record chain stays
under coordinator ownership throughout.
