# Packet97 CPU orchestration

Run `orchestrate.py` with the helper CPU prefix from the packet README. It reads
each source packet in a separate process, checking A-grid and B-grid through
that packet's own comparison. It requires 13/13 exact checks, unchanged
per-prompt acceptance, current-boot nonoverlapping same-lane brackets and a win
against both controls on both lanes. Packet93 also rechecks its micro gate.

`--snapshot-only` writes `screens-current.json` and false `ready.json` without
changing the bundle selection. `--pin head=production` (and equivalent defaults
for other dimensions) can only revert. `--closed 93=reason` can close pending
head evidence only when `--pin head=production` is also present. Failed evidence
is never closable. Closing 91 requires both route and recurrence baseline pins;
closing 90 or 95 requires the expert dimension pinned to wide64.

Once every source is resolved, the helper writes the actual confirmed selection
and `../lane-queue/proposed-p97-A.txt` / `proposed-p97-B.txt`, then plans them on a
temporary queue. Template files exist beforehand but refuse execution. Each lane
runs control / candidate / control, with a selection hash in every output path.
The live queue is never touched. The coordinator schedules these jobs.

A later invocation reads both complete composition brackets, applies the 1.5%
or two-confirmed-new-lever rule, selects already sealed bytes, and performs the
full CPU chain rehearsal. Only then can `ready.json` become true. The printed
coordinator command calls `verify_ready.py` before any device work. Reverted
combinations require their own composition screen; no source-winner shortcut.

Both `verify_receipt(window, data=...)` and the packed-head placement disclosure
are present before any packet97 seal. The temp-ops-path regression is covered
by pytest through `/home/steve/.venvs/deepseek-v4-xpu/bin/python`.
