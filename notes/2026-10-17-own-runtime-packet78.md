# Packet78: smaller route and HC norm launches

The new packet copies packet75 sources without changing the frozen parent,
shared screen wrapper or live queue. It prepares five choices in one binary,
including the combination with packet73's HC gate. The model arithmetic and
packet49 oracle stay unchanged.

Initial `git pull --rebase` refused the unrelated live orchestration log.
`git fetch origin main` confirmed HEAD and origin/main identical; no stash,
reset or edit of that log was needed. Packet58e owned the compiler initially;
packet78 waited until its receipt appeared and no compiler remained.

The final route candidate removes three dependent launches and uses a subgroup
bitonic sort on rounded probabilities, with the original index tie rule. The
norm uses one subgroup per tile with the same FP32 tree and BF16 output. Both
compose with the copied packet73 HC gate. The initial all-pairs route was CPU
exact but replaced before any device run; its source and receipts are retained.

GNU and Intel each pass two fresh byte checks for all five views. Every run
checks 2,048 random/adversarial route cases, including ties, and 40 full-size
norm cases; the HC-wide view adds eight gate/mix cases. Both engine builds pass.
Ten full-shape mock runs exercise both ranks' actual post-load allocations,
command capture and draft setup. Captured operation types prove the selection
keys reach the intended kernels. A short allocation and five malformed
selections are rejected. All 85 Python checks pass, including the real lane
admission and closed worker imports.

Existing packet77 events put the four route stages near 3.2, 3.2, 10 and
3.3 microseconds. That explains the approximately 19.6 microsecond cost;
launches and all-pairs ranking dominate its tiny input. The new route cuts
thread comparisons from 262,144 to 23,040. Its barrier cost and actual speed
remain unmeasured. The approximately 4% in the brief is not a measured gain.

All five final seals, six lane-A screen plans, twelve possible lane-B plans,
and both temporary queue plans pass. Build size is about 564 MB; the largest
recorded compiler process used 726,340 KiB. No GPU, service, sudo, live queue
edit, or machine setting change occurred. Frozen parent and shared wrapper
hashes verify. `CURRENT.md` records the handoff.

The coordinator can ingest these proposed jobs:

- [Lane A](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p78-A.txt): production, route-fast, norm-fused, small-combined, small+hc-wide, production.
- [Lane B](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p78-B.txt): production, exact improving best of lane A, production. The runner selects the winner from sealed completed A receipts and refuses if none beats both controls.

The original pinned shared v4 wrapper owns every screen and all thirteen
packet49 exact checks. Gaps are 90 seconds, with no retries. This handoff is
CPU preparation only; device correctness, speed, and full-chain qualification
remain pending.

Evidence and reproduction: [packet78](../experiments/own-xpu-runtime/stage2/packet78-small-kernels/README.md).
