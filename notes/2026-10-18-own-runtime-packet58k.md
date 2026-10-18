# Packet58k: shorter one-card screen

The new screen loads the model once for each of production / port / production.
Each arm keeps two small, fresh K1 fixture runs to choose how missing expert
weights are read, then checks every token in all twelve 128-token answers
against packet49. The port is down-tile16 + route-fast + rec-both-plus.

The planned bracket takes **33–39 minutes**, including the 90-second gaps,
instead of three full seven-window chains. Plan a 39-minute whole-host gap;
admission waits and unusually slow storage can extend it. The peak host budget
is **109.72 GB plus an 8 GiB reserve**, requiring **118.31 GB available** before
the model load. This is the unchanged timing bound, not a new measured peak.
Lane B cannot overlap. The card mask, memory fence checks, fault review,
lane-A lease and graceful drain remain. Tests cover releasing its own drain
record on a proven pre-compute refusal while retaining live or faulted owners.

Both native binaries are unchanged copies from sealed packet58j. Their build
is **39,526,592 bytes**, below 150 MB. No native compile was needed; the parent
byte and full-size startup gates are retained and hash-checked, not counted
as new runs. All **76 CPU tests** pass, including mutations at every output
token position. All **three queue plans** pass on a temporary queue copy and
create no device output. Only the proposed queue file was added under ops.

The candidate has one model launch, so this is screening evidence only. The
strict 512-token gate stays false. It cannot establish a speed verdict, a
fresh-process repeat or a record. The final decision can qualify spending time
on the unchanged full seven-window submission chain in 58j; it never launches
that chain or submits a result. 58j's record campaign still expects its own
full bracket and must not be given these shorter receipts.

The requested initial `git pull --rebase` refused the checkout's existing
unrelated edits. Fetch confirmed local main equaled origin/main at the start;
nothing was stashed. Root disk had about 19.7 GB free. The user's bounded
150 MB build request was handled with a 39.53 MB copy, preserving the packet's
8 GB storage floor; no cleanup or additional compiler scratch was needed.
No GPU, service, sudo, live queue, memory block, power, swap or page-cache
setting was touched. Frozen packet and screen trees remain unchanged.

- [Packet, commands, budget and full-chain handoff](../experiments/own-xpu-runtime/stage2/packet58k-onecard-screen/README.md)
- [Proposed lane-A jobs](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p58k-screen-A.txt)
- [CPU checks](../experiments/own-xpu-runtime/stage2/packet58k-onecard-screen/evidence/python-cpu-gates.json)
- [Temporary queue plans](../experiments/own-xpu-runtime/stage2/packet58k-onecard-screen/evidence/queue-plans.json)
- [CPU closeout](../experiments/own-xpu-runtime/stage2/packet58k-onecard-screen/CPU-PREPARATION-CLOSEOUT.md)
