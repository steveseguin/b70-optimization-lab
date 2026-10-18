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

## Resume at 06:23 UTC

The first commit already copied packet105's committed sources, and the failed
session left the draft implementation and proposal helpers uncommitted. The
resume preserved that work. Pull again refused the mixed worktree; fetch found
main equal to origin/main. Other jobs' edits and staged files stay untouched.

Implementation now includes the hit-only controller flag, separate suffix
weights/mailbox, shortened prefix capture, full miss prefix, and combined view.
Review found that request reset zeroes private suffix active controls; both
local suffix services now restore them before argmax. Transfer logs also reopen
for each request after reset. No change was made to packet105 itself.

Nine Python checks pass, including missing-smoke/B-grid refusal, fixed memory
deltas and changed-proposal rejection. The A proposal is a fresh three-run
confirmation of the best exact B winner. GNU/Intel builds and byte/controller
gates are queued through the shared compiler turn, respecting the active
whole-host hold. Every-window startup and final seals remain pending.
