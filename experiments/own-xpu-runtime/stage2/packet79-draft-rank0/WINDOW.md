# Coordinator screens

No device window ran during preparation. Use the two proposed queue files:

- [Lane A](../../ops/lane-queue/proposed-p79-A.txt): production `1`,
  `0-split23`, `0`, production `1`.
- [Lane B](../../ops/lane-queue/proposed-p79-B.txt): production `1`, the exact
  improving lane-A winner, production `1`.

Both proposals were planned in a temporary queue. The live queues were not
changed. Each screen is estimated at 3.5 minutes, with the inherited 90-second
gap between screens. No retry or restart is automatic. Both lanes use the
same pinned shared `screen/v4-lanes` lifecycle, worker, fault review, real lane
admission, environment, 13 packet49 checks and drain/postflight rules.
`bootstrap.py` installs only a copied, sealed placement policy;
`worker.py` executes the shared worker verbatim. The shared files are unchanged.

CPU plan commands, from the repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet79-draft-rank0
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/run_screens.py" --lane A --plan </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/run_screens.py" --lane B --plan </dev/null
```

The coordinator puts the proposed lines in the existing lane queue. Lane B
reads all completed A receipts and refuses missing, non-exact, changed or
non-improving results. All A screens must match packet49; the winner must beat
both A controls. A tie chooses the earlier candidate, `0-split23`.
B must also beat both of its own controls before suggesting record-chain work.

After a lane finishes, inspect exactness, acceptance, proposal sequence equality
and the class-balanced speed difference:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/report.py" --lane A </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/report.py" --lane B </dev/null
```

The sealed `selections/<placement>--hc-wide/` views are ready for subsequent
composition screens using`run_screen.py`, the same placement and fresh output
paths under the shared evidence directory. They are not included in this
placement-only queue. No standalone or full-chain qualification is claimed:
128-token screens remain diagnostic; the full 512-token record gate is pending.
