# Packet106 — hit-only draft prefix head split

CPU preparation, 2.5-hour box; nice19, CPUs 8–15/24–31, 8 GiB address-space
limit, serial packet94 compiler turn, closed workload stdin, build at most
300 MB. No GPU, service, sudo, host-setting change, or live queue write.

Initial pull refused other jobs' uncommitted files. Fetch confirmed main and
origin/main identical. Preserve their staged and unstaged work; commit only
explicit packet106 paths and push each milestone.

Packet105's byte gates were already committed at `339d7017a`; copied that
revision, not its active working files. Read packet79/83/87t/88 boundaries:
no draft-trunk relocation, compressed draft head, changed prefix, or claimed
rollback overlap. Packet87t predicts +0.7749%; no measured model gain yet.

Design is in `stage2/packet106-draft-split/DESIGN.md` under the own-runtime
experiment. Implementation, byte gates, every-window startup and proposals
are next. Parent packets, screens and existing ops files remain frozen.
