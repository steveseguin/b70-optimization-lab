# Packet152 — designs ready for the rank0 split

Five exact segment designs and five launch entries are prepared in
[the plan](../experiments/own-xpu-runtime/stage2/packet152-segment-prep/PLAN.md).
The two detailed build briefs cover snapshot setup and head/handoff waits.
Every design names packet136 source lines, prior closed attempts, a conditional
saving ceiling, build size, byte risks and required proofs. The common build
contract specifies vendoring, lane-B smoke and one-load v5 proposals, real
launch/report rehearsal, first-minute analyzer data, measured write budgets
and READY written last.

Packet150 finished during this work. Only snapshot setup (**0.743 ms/cycle**)
and merge/handoff waits (**1.852 ms/cycle**) meet its size threshold.
The original analyzer replay matches all five views exactly, with exactness
passing and control drift **0.136%**. The CPU split file contains correctness
checks, not timings; no ranking or gain was inferred from it.

Snapshot setup is the first build direction. The large wait bucket is mostly
remote replies; its head import/export work is only about **0.05 ms/cycle**
combined. The transport brief stays ready but is not admitted on that number.
The separate packet153-snapshot-host task was already active; this task
neither copied nor edited it and does not request a duplicate build.

The [audit](../experiments/own-xpu-runtime/stage2/packet152-segment-prep/evidence/prior-audit.json)
covers 212 negative indexes and 3,580 Markdown notes, including other lanes.
Later closure records override stale “pending” text. Existing banks, decoder
tables, early suffix scheduling, guessed early draft and deferred reports
are not relabeled as new ideas. The report's ≥0.4 flag means a large boundary,
not proven removable work; all five designs preserve iq3-p49-split32-v1.

Work began about 00:12 UTC October 19 on steve-b70s. Pull/rebase refused
unrelated dirty files; fetch confirmed HEAD and origin/main both at
03a14f428bddce33b24a1577c5bbe9c0added92f. Shared main advanced during work.
Only the new design packet and this note belong to this task.

CPU work uses nice19, cores 8–15/24–31, Python -B and closed stdin, below 2 GB.
No GPU/model/GGUF payload, build, service, sudo, setting, live queue, ops file,
screen file or existing packet was changed. No READY marker or runtime copy
was made. Packet58ah's WS-to-chain-end reservation takes priority.
The record and CURRENT.md's operational authority remain unchanged.

Validation checks local links, source pins, five-segment coverage, both full
briefs, the shared operational contract, and the exact saved analyzer replay.
The focused commit uses git commit --only with explicit paths and is pushed
immediately. No performance improvement or new device qualification is claimed.

Final local validation passed at 00:42:59 UTC, after packet58ah was inactive.
It checked 47 local links, 23 pinned source files, all five segment entries
and the saved exact analyzer replay. Validation used 15.7 MiB peak RSS.
The packet is about 1.25 MB total; its largest file is the 893 KB audit index.
The source/budget evidence is retained without a runtime copy or build.
