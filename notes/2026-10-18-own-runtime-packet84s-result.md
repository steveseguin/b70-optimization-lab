# Packet 84s result: lane-B composition screen (2026-10-18 01:20 UTC)

Lane B (cards 2+3), 128-token screens through packet 84's binary (`8b615a0c…`), shared pinned v4 wrapper. Diagnostic only: screens cannot qualify a record. Helper: `experiments/own-xpu-runtime/stage2/packet84-screens/compare.py`.

| # | View | tok/s | vs control mean | 13/13 exact | Acceptance |
|---|---|---|---|---|---|
| 0 | control (p80 pinned: hc-wide, wide64, ordered, placement 1) | 55.050 | — | yes | 0.7854 |
| 1 | candidate A: + `recurrence=rec-parallel` | 55.542 | **+0.93%** (beats both controls) | yes | 0.7854 |
| 2 | candidate B: + rec-parallel + `route=fast` | 55.768 | **+1.34%** (beats both controls) | yes | 0.7854 |
| 3 | control (rerun) | 55.011 | — | yes | 0.7854 |

- Control drift 0.07%.
- The first closing control (01:01) completed its device run, but its teardown refused. Cause: the one-card 58f window had left the shared teardown record undrained. Its evidence was kept as `p84s-B-3-control-refused-58f-undrained`, and the control was rerun at 01:15.

## Decision

- **Chain candidate A now.** The p84 orchestrator selected p80 + rec-parallel:
  - p82 winner on both lanes;
  - p81 recorded as a coordinator closure (neutral, DO-NOT-REPEAT; experts pinned to wide64);
  - p83 no-winner.

  `ready.json` is ready; the chain is `packet84-chain` on lane A.
- **Route-fast is not in this chain.** p84's selection rules only read packets 81/82/83 and cannot admit it. Its increment over candidate A is +0.41% on lane B (one screen each, not bracketed); on lane A, packet 78 measured it alone at +0.54%.
- **Carry route-fast into the next record bundle,** with the next confirmed lever, rather than delaying this chain by a re-selection and dry run.
