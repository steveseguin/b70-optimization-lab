# Packet 85: where the two-card line spends its time

The analysis is in [MODEL.md](../experiments/own-xpu-runtime/stage2/packet85-critical-path/MODEL.md),
with [machine-readable results](../experiments/own-xpu-runtime/stage2/packet85-critical-path/model.json)
and a [CPU reproducer](../experiments/own-xpu-runtime/stage2/packet85-critical-path/model.py).
Only that new folder and this note were changed by this task. Existing packet,
screen and ops trees stayed read-only. No GPU, model payload, service, sudo,
settings change, reset or reboot was used.

The model gives **53.98 tok/s against 54.06 measured** in packet77. A hit takes
about **16.05 ms**. A miss takes **27.70 ms** because the first card must restore
state and run its corrected half. The draft can overlap that repair when it
stays on the second card. Moving it to the first card makes those costs serial;
the unchanged-cost model predicts a **2.02% loss**, not a gain.

Saving 0.1 ms in the second card's target work adds about **0.293 tok/s**.
Saving it in the corrected first half adds only **0.062 tok/s**, because that
helps misses alone. A draft saving adds about **0.230 tok/s**, because the draft
already finishes well before correction on misses. Faster speculative work on
the first card alone has no local benefit: it currently finishes about half a
millisecond early.

The accounting matches the signs and sizes of wide64, HC-wide, ordered cleanup,
packed reads and draft relocation when supplied their measured command costs.
Using lane A's savings to predict lane B gives the correct signs, with errors
of **0.85, 0.30 and 0.15 percentage points** for wide64, HC-wide and ordered.
That is stronger than replaying the same run, but it is still based on a
measured change. It does not predict an unseen kernel's cost from its source.

Depth two needs its own tile model. It adds three draft passes, tile rebuilding
and state selection/restoration. The complete-command model gives **28.58 tok/s
against 28.57 measured** over the full decode window. Its first-99 result was
28.16 tok/s, a 46.76% loss. The old device-only tile costs predict a loss too,
but understate it by **30.16 percentage points**. The report keeps that failure
visible rather than fitting it away. The sparse expert tables also understate
wide64's gain by 2.23 points.

The six priority decisions are smaller target kernels, a cheaper draft on rank1,
a different expert dequantization mechanism, miss repair, exposed host cleanup,
and checking rank balance where a 23/25 configuration remains. Packet77 and the
packet80 selection note already use 24/24; changing to it is not another gain
for that record. The report gives each lever's conditional gain, evidence,
closed prior attempts, arithmetic constraints and estimated engineering size.
Packet81's newly recorded neutral result rules out another expert load-count
campaign without a new explanation. The full instrumented host remainder is
not an available saving either.

The next engineering proposal should name the command it shortens, the hit or
miss path it helps, any new dependency, and the acceptance loss it can afford.
For example, a 0.2 ms faster draft can lose only about **1.33 percentage points
of acceptance** before the benefit disappears. Packet85 schedules no follow-on
work; it completes the requested analysis only.

Recompute or check under `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`, as shown in the report. The script enforces a 4 GiB address-space
ceiling. It verifies the packet77 event/timer hashes and records every input
hash. The raw screen run trees are local ignored evidence, so a clean clone
needs those exact retained inputs before it can reproduce the analysis.
There is no public-recipe or new speed-record claim.

Validation passed: byte-identical `--check` recomputation, all 13 command-model
sign checks, three held-out lane signs, the 1,188-interval count, separate
depth-two accounting, six lever entries and every local document link. The
measured check took 3.39 seconds and peaked at 104,768 KiB RSS, well below the
4 GiB limit. It did not write bytecode or modify the evidence.

The required opening `git pull --rebase` refused unrelated unstaged work.
`git fetch origin main` confirmed that local main already matched remote main
at that point. Those edits and concurrent commits were preserved. No stash,
branch or secondary worktree was created. `CURRENT.md` was left unchanged under
the brief's explicit two-location write boundary; no live state changed.
