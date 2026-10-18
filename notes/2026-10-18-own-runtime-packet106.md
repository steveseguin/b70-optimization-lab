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

## CPU preparation complete

Both binaries compile; the device binary was never executed. GNU and Intel
produce identical bytes in two fresh processes each: three complete 91,392-row
logit vectors plus twenty tie, signed-zero, boundary-winner and nonfinite cases
per process. Invalid rows reject publication instead of inventing a token.
The native controller mocks pass all-hit, all-miss, alternating hit/miss,
no-guess and EOS paths with unchanged target tokens and draft proposals.

The actual transfer code passes payload-backed CPU mocks for draft-only and
combined views: verified draft hidden bytes, repeated hits, unchanged target
state, distinct mailboxes, reset-active restoration, per-request transfer logs,
nonfinite rejection, stale/duplicate sequence rejection, cancellation and peer
exit. Full-size startup/allocation passes all eight view/rank combinations;
nine malformed or unsupported layouts refuse.

All four views pass all eleven windows (44 total): K0, K1a, K1b, K2, W0p, KD,
W2m, WS, WSs, WS128x and WS128. K0 retains its explicitly structural CPU JIT
shim; W0p also executes the actual host canary handshake. KD exercises the
bounded unchanged full-prefix host reference and its device argv on the CPU
mock. The prior half-cache streaming command still refuses. The gate took
75.64 seconds, with peak child RSS 1,250,952 KiB. This is CPU startup evidence,
not full-model/device equivalence.

Combined rank0 allocation is 28,298,008,724 bytes, including the separate
155,750,400-byte target suffix and 152,289,280-byte draft suffix. Combined
rank1 allocation is 31,425,985,258 bytes. Both unchanged arena/reserve gates
pass. Real driver residency remains a live device gate.

The first seal attempt correctly refused an oracle manifest symlink resolving
outside the repo. Its exact bytes were localized at the same packet path;
before/after SHA256 agree. No arithmetic or completed gate was rerun for this
path-only fix. All four seals now verify, with no mutable parent selection or
orchestration pins. Packet105 itself was never edited. Its target-transfer code is copied locally
with the documented reset/log fixes; the draft implementation is packet106 work.

Nine Python checks pass. Three proposals (eight jobs) pass the real queue
planner on a temporary queue directory:

- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p106-smoke-B.txt`:
  one incident prompt, 64 tokens, combined candidate only; normal fault review,
  admission and graceful drain. It must exercise at least one draft suffix.
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p106-B-grid.txt`:
  production / head-split / head-split+draft-split / production; refuses until
  that exact sealed smoke passes. All proposal sequences and acceptance counts
  must match controls, in addition to all thirteen exact checks.
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p106-A-confirm.txt`:
  production / best exact improving B winner / production. Refuses until the
  entire same-boot B grid completes and qualifies. Planning uses a placeholder;
  execution resolves and checks the actual winner before every job.

Final build bytes: 261,302,180, below 300,000,000. Existing read-only CPU fixture
inputs (211,592,427 bytes) are linked and individually hash-bound, not copied.
Completed test object scratch was removed after recording hashes/restoration
commands; source, binaries and receipts remain. The 4,001,021-byte generated
source/evidence archive round-trips all 233 members. See the packet's
`RETENTION.md` for the required large-artifact rationale and restoration.

Reproduction order, from the packet directory with the stated nice/affinity
and closed stdin: `build_engine.py`, `cpu_gate.py`, `controller_gate.py`,
`full_shape.py`, `runtime_mock.py`, `prepare_host_inputs.py`, `startup97e.py`,
`prepare_packet.py`, `queue_plan.py`, `retain_build.py`. Frozen seals refuse
replacement. Full commands, hashes and observations are in the evidence JSON.

[Final verification](../experiments/own-xpu-runtime/stage2/packet106-draft-split/evidence/final-verification.json),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet106-draft-split/CPU-PREPARATION-CLOSEOUT.md).
No GPU, service, sudo, live queue, power, memory, swap or page-cache setting was
changed. The +0.7749% remains a model estimate; device quality and speed await
the coordinator's smoke and matched screens.
