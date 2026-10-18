# Packet142 — class allocation order

CPU-only preparation of frozen packet136 bundle8, ahead of packet141's verdict.
`READY-FOR-DEVICE.json` is the final readiness authority. Its absence means
preparation is incomplete. No GPU result or speed improvement is claimed here.
The two-card record remains packet136's 58.798 tok/s.

## Registered choices

`class_layout=production|attention-order600|expert-gate-up-order600|hc-gate-low-order600`.
Each process has one fixed `class_layout_bank`, shared by control and candidate.
All original weights and candidate copies coexist before the first request.
A variant copies complete consumer tuples in plan order until a fixed 600 MiB
per-rank budget would be exceeded. This tests a class prefix, not every layer.
The allocator does not guarantee physical adjacency. No packing, arithmetic,
precision, reduction, accepted bundle8 choice or BF16 KV setting changes.
At each view boundary only the already-loaded bindings change; all six rollback
bank capture sets are rebuilt and all request state is reset.

| Packet141 class | Candidate | Covered weight consumers |
| --- | --- | --- |
| Attention projections | `attention-order600` | GDN qkv/z and QSA qgate/k/v/output projection consumers in plan order |
| Routed expert gate/up | `expert-gate-up-order600` | Complete gate/up pairs, with the accepted E1 halfcache and original rows |
| HC gate/low | `hc-gate-low-order600` | HC attention/feed-forward gate and low consumers only |

Packet104/104b's losing gate/up tile16 transpose is excluded. This expert arm
changes allocation placement/order only, with no transpose and no new kernel.
The existing accepted expert **down** tile16 remains unchanged.

## Coordinator decision

Do not enqueue during preparation. The coordinator may select only a class
that packet141 flags at >=1.3x cold/warm and >=0.5 ms per half. A <=1.15x class
closes this trigger; the intermediate range is inconclusive, not permission to
run every candidate. Read packet141's actual receipt, not this table, for verdicts.

Each selected class first runs lane-B 12 x 64 smoke, then its own one-load v5
C/X/C/X/C bracket: five complete 12-prompt 128-token views plus the inherited
incident64 checks. Both candidate views must exceed every control by >=0.5%,
control drift must be <=3%, and every output must match the packet49 oracle.
The bracket is a screen; strict512, fresh-load device determinism and promotion
remain separate gates. No synthetic CPU output can become a device receipt.

Only `v5/bracket_job.py` is the supported device entry. Proposals use the actual
`screen-<job>.service` unit convention, fixed embedded oneAPI library path,
closed environment, inherited-limit guard, real oracle subprocess, drain fix,
lease/admission checks and cooperative teardown. No automatic retry is added.
Smoke is budgeted 240–360 s; each bracket 720–1200 s. Both watchdogs are 4800 s
(at least four times the upper estimate). They are estimates, not measurements.
Host admission is the inherited 97 GiB plus 1200 MiB for both class banks.
The existing per-rank 30 GiB arena ceiling and device headroom rules remain.

## Evidence and restoration

- [CPU gates](v5/evidence/) include full-shape allocation/capture/reset checks,
  GNU/Intel exact-byte transcripts, entry/limit refusals, and submission rehearsal.
- [Preparation notes](../../../../notes/2026-10-18-own-runtime-packet142.md)
  retain failed harness attempts and memory-budget corrections.
- [Retention instructions](RETENTION.md) explain source, fixtures and binaries.
- [Do-not-repeat](DO-NOT-REPEAT.md) records excluded arms and scope limits.
- [Closeout](CPU-PREPARATION-CLOSEOUT.md) separates CPU preparation from device work.

All 182 original symbolic-link objects are preserved. Original and current link
texts live in `lineage-inputs/packet136-history/copy142.json` and
`lineage-inputs/current-aliases.json`. Non-allowlisted dependencies are local.
Packet49 authority is accessed through `oracle-binding.json`/`shared_oracle.py`;
model files and hash-pinned frozen parent binaries are the external allowlist.
`lineage-inputs/` contains historical receipts as provenance, never readiness.
