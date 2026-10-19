# Packet161: exact early head bounds

The tested bounds do not support a build. Simple norms still read almost every
head row. Partial dot products read at least 78.6–83.2% of the target weights
on the suite and 84.5–85.7% on independent text, even when given the final winning
score for free. The saved draft inputs need 80.6–82.9%. The most generous cost
replay gives 2.24% before overhead, below the requested 3%; adding a metadata
read-cost sensitivity leaves the best scheme at 1.64%. These are calculations,
not measured speed gains. The two-card record stays 58.798 tok/s.

The target study covers 200 real positions across all twelve suite prompts and
120 positions from five fixed excerpts of packet114's independent text. All
1,600 stored target top-five logits and 65 saved native draft winners match.
Draft coverage is incomplete: only those 65 incident positions were available.
A CPU-only attempt to obtain independent draft states hit its fixed memory cap
and drained cleanly; no missing fraction is claimed as measured.

The one-card chain stayed untouched. Weight reads began only after it was
inactive. No GPU, compiler, server, service change, sudo, host setting change
or live queue edit was used. The preparation probe ran an existing CPU-only
binary with a 3.7 GB address cap; the bound scan peaked below 0.84 GB RSS.
The session's long wall-time gap was the coordinator's one-card measurement
freeze. All new work is in packet161; older packets and dirty files stayed intact.

No build brief, proposals or READY marker were created. Reopening requires a
different, tighter inexpensive bound, broader exact draft inputs and current
head timing that support at least 3% after costs. The measured read fractions,
proof, limitations, failed probe and reproduction commands are retained in the
[closeout](../experiments/own-xpu-runtime/stage2/packet161-early-argmax/CLOSEOUT.md)
and [negative index](../experiments/own-xpu-runtime/stage2/packet161-early-argmax/DO-NOT-REPEAT.md).
