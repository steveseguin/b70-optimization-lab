# Coordinator screens

CPU preparation creates these proposed jobs only; it never changes a live queue
or launches a device. Arithmetic remains `iq3-p49-split32-v1`, with the same
packet49 oracle, wide64 experts, production HC and dense, draft-HC, batch miss
copying, rank1 draft and 24/24 placement. Memory limits and reserves are unchanged.

- Lane A: production → rec-gates → rec-parallel → production.
- Lane B: production → exact improving best-of-A → production.

B refuses unless all A screens match all 13 exact requests and its selected
winner beats both A controls. There is no B grid and no retry. Each screen
owns its ordinary shared lane lease, fault monitoring, graceful drain and
90-second inter-screen gap. Plans exercise the actual shared admission/import
path. Shared sources are pinned; none are copied and modified for these screens.

Proposals (append only through the coordinator's queue workflow):
[Lane A](../../ops/lane-queue/proposed-p82-A.txt),
[Lane B](../../ops/lane-queue/proposed-p82-B.txt).
`queue_plan.py` checks them in a temporary queue directory.

CPU plan commands from the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet82-recurrence/run_screens.py --lane A --plan </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet82-recurrence/run_screens.py --lane B --plan </dev/null
```

The proposal argv is the coordinator's device command and requires its fresh
fault-review receipt and authorized window. No device command was run here.
The CPU mirror does not prove GPU output, scheduling overlap or speed. Actual
device state/output exactness, full-model exact requests and fresh control
comparison remain mandatory before adopting a candidate. 128-token screens
remain diagnostic, never full realistic-suite promotion evidence.
