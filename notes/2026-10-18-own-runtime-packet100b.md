# Packet100b: prepare real route capture for the DOWN microbenchmark

The CPU preparation is complete. Both compiler builds pass, both ranks pass
full-size startup and memory checks, 23 Python checks pass, and all six proposed
queue jobs pass their real plans on temporary copies. The build uses about
66 MB, below 300 MB. **No GPU, service, sudo command, host setting or live queue
was used or changed. Real routes and speed remain unmeasured.**

The new [packet100b tree](../experiments/own-xpu-runtime/stage2/packet100b-route-capture/README.md)
copies packet97's entry source and record-line selection with production head.
All target and draft kernel objects are unchanged. Each target DOWN call copies
its route bytes on-device. A token slot becomes valid only when the normal
controller accepts that half. Rejected speculative routes cannot enter the
qualified capture; redo overwrites the slot. The new allocation is excluded
from speculative backup, without changing any original model-state source.

The job runs incident-retrospective and code-review for 64 tokens each and
compares every token with the existing CPU oracle. It then reads each rank's
route buffer once per request. Four compact binaries retain all 6,144 vectors,
with rank/layer/token metadata and SHA256 hashes. DOWN does not consume mixture
weights, so those are not copied. Large full-state dumps are omitted to keep the
capture's complete output at or below 50 MB. No graph execution is introduced.

The follow-on job reuses packet100's exact native micro binary. It takes
predeclared target steps 1, 16, 32 and 64 from every layer, rank and prompt,
giving 384 route strata. No routes are selected for favorable IDs or timing.
The original full-shape, exact-byte, alternating-order and **at least 15% lower
kernel-time** requirements remain. The qualification binds the capture's hashes
as well as binary, source, sample, window and drain identities. Neither this
capture nor synthetic micro weights/activations are a model benchmark.

The two new proposals are
[capture B](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p100b-capture-B.txt)
then [micro B](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p100b-micro-B.txt).
The four existing proposed packet100 B grids/A confirmations now point to the
new gate adapter. It delegates to the frozen packet100 driver and leaves its
13-request exactness, acceptance, bracket and B-before-A rules intact. Existing
live queued copies are untouched; use the updated proposals. Records remain A.

Capture uses the shared v4 lane lease, reviewed fault handling, device masking,
supervision and graceful worker drain. The 97 GiB host-memory admission is checked
before acquiring the lease, then rechecked before load. Its new per-rank device
allocation is exactly 184,320 bytes; the original arena and free-memory limits
are unchanged. GNU and Intel each pass two synthetic copy/redo tests, including
source-byte preservation and zero added host reads inside the loop. Full-size
startup tests actual route bindings and all 1,536 capture slots on each rank.

Parent selection, ledger and compiler-command controls are snapshots owned by
packet100b. The new seal does not pin parent orchestration files or mutable
decisions. All existing packet trees and seals are untouched. Build files stay
ignored; [retention and restore instructions](../experiments/own-xpu-runtime/stage2/packet100b-route-capture/RETENTION.md)
describe the local dependencies and future device evidence.

The initial `git pull --rebase` refused the record chain's pre-existing dirty
files. A fetch showed local main equal to origin/main; no unrelated changes were
stashed. Builds ran at nice 19 on cores 8–15,24–31 with Python bytecode disabled,
stdin from `/dev/null`, and packet94's serial compiler lock. A CPU fixture link
error was corrected before both startup checks passed. No device incident arose.

[Final verification](../experiments/own-xpu-runtime/stage2/packet100b-route-capture/evidence/final-verification.json),
[CPU preparation closeout](../experiments/own-xpu-runtime/stage2/packet100b-route-capture/CPU-PREPARATION-CLOSEOUT.md).
The remaining work is the proposed coordinator-owned capture, exact-output
proof, real-route micro qualification, and only then eligible B/A screens.
