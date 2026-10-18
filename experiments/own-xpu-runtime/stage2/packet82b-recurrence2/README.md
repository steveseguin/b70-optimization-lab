# Packet82b recurrence round 2

Copied packet84 engine sources; fixed hc-wide + ordered + wide64 + rec-parallel
control. Arithmetic remains `iq3-p49-split32-v1`. See [analysis](ANALYSIS.md).

| View | Meaning |
| --- | --- |
| production | Packet84 rec-parallel composition. |
| rec-both | Same kernel as production: rec-parallel already contains rec-gates. Null control only. |
| rec-both-plus | Same arithmetic with subgroup-local entry decisions, removing the guard-only workgroup barrier. |

CPU byte checks, full-shape startup and seals prepare later device screens;
they do not establish device correctness or speed. The [window](WINDOW.md)
lists full-grid jobs for both lanes and opposite-lane best confirmations.
Only rec-both-plus can qualify, and it must beat all three control screens.
No GPU, service or live queue is used by preparation.

Run these scripts in order with `nice -n 19 taskset -c 8-15,24-31`,
`env OMP_NUM_THREADS=2 python3 -B`, and stdin from `/dev/null`:
`build_engine.py`, `cpu_gate.py`, `full_shape.py`, `python_gate.py`,
`inspect_registers.py production`, `inspect_registers.py candidate`,
`offline_compare.py`, `seal.py`, `final_check.py`, `queue_plan.py`.
One compiler at a time; 8 GiB address-space ceiling; build under 1 GB.

Only `run_screens.py` and its sealed views register packet82b screens. Copied
historical chain and bundle helpers are source context, not registered
packet82b chains. A later coordinator owns device admission and execution.
See [CPU closeout](CPU-PREPARATION-CLOSEOUT.md) and [retention](RETENTION.md).
