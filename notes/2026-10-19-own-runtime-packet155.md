# Packet155 — bundle9 preparation ahead of packet153

CPU-only preparation requested for a copy of packet136's two-card record chain.
Bundle9 adds packet153's `snapshot_host=static`, keeping bundle8's remaining
choices and `iq3-p49-split32-v1`. The record remains 58.798 tok/s
(`cmve4dtir007wrf01k57sdf23`). No device result is claimed.

The initial copy preserves links and excludes prior build/run outputs, selections
and submission outputs. The original metadata is retained under
`lineage-inputs/packet136-history`. Packet153's two completed binaries and native
sources are copied into the new tree and bound by SHA-256 in the orchestration
`inputs/packet153-native.json`; launch must not depend on mutable parent files.

At copy completion root had 30.111 GB free. The CPU stop floor is 30 GB,
CPU memory ceiling 4 GiB, and build ceiling 300 MB. Existing packets, live
queues and orchestration are untouched. No service, GPU or host setting changed.

Readiness stays false pending coordinator confirmation of packet153's v5
bracket: both static views at least 0.5% above every warm control, exactness
throughout, control drift at most 1%, and strict combined gain above 2% over
58.798 unless the coordinator establishes that the lanes are idle. Device
admission and performance/quality qualification remain separate.

The final READY-FOR-DEVICE marker is not yet written. CPU gates and submission
rehearsal are pending. Submission scope must remain 128 tokens, strict512 false.
Packet150's 0.743 ms/cycle capture_snapshot host scope is attribution only,
not a promised gain. Packet153 bracket numbers are pending, never invented.

## Disk stop — 2026-10-19, about 01:47 UTC

The first CPU fixture command refused before execution because root free space
was below 30 GB. The following `df -B1 /` read **29,812,207,616 bytes** available.
The packet tree was 103 MiB and orchestration 2 MiB. Preparation stops under the
owner's explicit disk rule; nothing was deleted or relocated to evade it.

Completed: source/link copy; SHA-256-bound local packet153 engine copies and
native sources; copies of GNU/Intel host state and real-size fixtures; static
selection with probe off; private submission helper with packet136s's corrected
repository root; draft chain destination `device-cards01-p155-a`.
The initial snapshot commit `b84d897323388576e0c6150319835b9f3a04309d` was pushed.

Unfinished: all CPU gate executions, composition/real-shape receipts, entry and
per-rank admission, report rehearsal, loader checks, pin guard, storage projection,
submission replay, complete chain seal adaptation and bracket recomputation.
The copied runtime and orchestration are scaffolding, not a runnable qualified
chain. `verify_ready.py` refuses unconditionally. Copied historical pass fields
are not new receipts. No packet153 bracket numbers were available in this work.

A preparation helper hit a local variable-shadowing error after copying inputs;
that helper line was fixed, but the full helper was not rerun. The next CPU
command hit the disk guard before any fixture execution. The frozen-path census
returned nonzero; existing trees were treated as frozen regardless. All writes
were confined to the new packet, its new orchestration, this note and the status
entry in CURRENT.md. No service, GPU, model payload, secret or live queue was used.

For the eventual verifier, packet153's summary path is
`v5/evidence/device-static-v5-B-p153b/bracket-summary.json`. Exact-gate all five
C/X/C/X/C views and incidents. Compare static indices 1 and 3 against warm
control indices 2 and 4; index 0 remains exactness-gated. Recompute rates from
99 intervals across token timestamps 1–100, require identical acceptance/proposal
traces and oracle tokens, and ignore the parent's differently scoped
`candidate_qualified` flag. Require >=0.5% against each warm control and <=1%
warm-control drift. Bind the coordinator verdict, exact evidence and command
hashes. The >=2% combined-record rule and idle-lanes exception still need their
implementation and negative tests; projections must be labeled unmeasured.

The final marker records **both** incomplete CPU preparation and pending
coordinator/bracket confirmation. It cannot become ready from a bracket pass
alone. The planned launch command is informational and has never executed.

## Chain a outcome (coordinator, 05:23 UTC): failed in W0p; not repaired (hourly review 39)

`packet155-chain-a` (lane A, cards 0+1) started 05:05:19 under the idle-lane rule.
- K0, K1a, K1b and K2 passed.
- **W0p failed:** both ranks exited 1 with `shared extent` (`build/device-cards01-p155-a/W0p/run/rank*/failure.txt`), and the queue runner stopped with no retry.
- No GPU faults (count 2). stale-sweep archived the marker and the undrained teardown; the coordinator removed its own PAUSE-A/B.

`shared extent` comes from the static snapshot path in a window that packet153's one-load bracket did not exercise (W0p, the warm prefix/prefill-side window). Packet153's +0.35% bracket stays valid evidence for its own windows; the chain never reached a timing window. Hourly review 39 recorded "no bundle-10 or p155d for sub-1% items", so this chain is **not repaired**. Bundle 9 is parked. The two-card record stays 58.798109 (`cmve4dtir007wrf01k57sdf23`).
