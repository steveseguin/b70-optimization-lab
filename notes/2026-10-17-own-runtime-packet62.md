# October 17 — packet62 cuts work around a wrong guess

Packet62 is built and sealed for the coordinator. It used CPU only. Packet61's
running record chain and packet61x were left alone.

The fresh diagnosis changes the priority. In packet61's two completed screens,
rank1 now finishes last in almost every cycle. Snapshot preparation is about
0.81 ms by a host-envelope estimate, but sits behind rank1. Rollback itself is
about **0.74 ms** and the corrected rank0 half is about **12.51 ms**. The old
packet57 observation that rank0 finishes last 93% of the time does not describe
packet61. The controller gaps are about 12 us before rollback and 1.5 us before
correction. [Exact definitions and both-lane table](../experiments/own-xpu-runtime/stage2/packet62-miss-path/DESIGN.md),
[hashed receipts and reproduction script output](../experiments/own-xpu-runtime/stage2/packet62-miss-path/evidence/diagnosis.json).

The decision is to **screen the batched-copy selection against its control
first**. One build contains five separately sealed choices:

| Choice | What changes | Expected miss saving before measurement |
| --- | --- | --- |
| `control` | Packet61 behavior | Zero |
| `batch` | One descriptor upload and one flat copy kernel | Below the old 0.74 ms rollback envelope; a point estimate is not supported |
| `banks` | A third recurrent destination preserves the old spare | Little exposed saving expected; it mainly removes hidden capture work |
| `banks-batch` | Both | The batch benefit, plus any exposed capture saving |
| `banks-batch-overlap` | Both, with host bookkeeping overlapping copies | Same, plus a small unmeasured bookkeeping opportunity |

The third bank removes **29.60 MB of capture copies per speculative half**.
It commits or discards the speculative destination by changing the prepared
bank pair. Full scratch double buffering was not adopted: scratch and workspace
retain historical tails, and QSA retains committed rows. Those bytes cannot
quietly change. The third bank fits on rank0, where this state lives; shrinking
the backup offsets its allocation exactly. Rank1 gains no allocation.

The flat path changes **31 capture / 30 redo-restore submissions to two each**,
while preserving every admitted extent and byte. The descriptor table adds
31,232 bytes inside the existing rank0 reserve. Packet61 already skips
29.60 MB of recurrent restore traffic on confirmed redo, so bank rotation does
not save that traffic a second time. The corrected half is still required.
Removing the entire old rollback would save only about 0.16 ms per average
token under these receipts; that is an optimistic bound, not a new speed.

Host and SYCL builds passed. All five choices passed packet56's **96 target
fixtures / 24 tokens**, **70 changed-path CPU cases**, and both screen-v3
`--plan` lanes (**ten plans**). Cases include hit/miss sequences, cancelled and
terminal speculation, abandoned redo, a context-bucket crossing, request reset
and 15 deliberate corruptions that remain detectable. A separate copy fixture
runs the actual device tile routine on CPU: **975 descriptors and 11,899,255
bytes match**, including unaligned tails and untouched gaps. The retained
build uses **357.44 MB**, counting the hardlinked selection views, under the
400 MB limit. [CPU closeout and evidence](../experiments/own-xpu-runtime/stage2/packet62-miss-path/CPU-PREPARATION-CLOSEOUT.md).

The coordinator's exact v3 commands for **each choice on lanes A and B** are in
[WINDOW.md](../experiments/own-xpu-runtime/stage2/packet62-miss-path/WINDOW.md).
The selection is file- and hash-bound; there is no environment toggle or
per-choice rebuild. No GPU, service, sudo, reboot, power, memory, swap or cache
setting was used here. Device exactness and speed remain pending, and a screen
cannot replace the full packet49-oracle record chain.
