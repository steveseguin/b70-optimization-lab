# Coordinator handoff

CPU preparation only. Check `evidence/final-check.json` and all seals before
execution. Device exactness and speed remain pending. Production is packet84's
explicit hc-wide/wide64/ordered/rec-parallel composition, copied through packet90.
Do not substitute the mutable packet84 default.

Choose one grid family and one direction. All files are under
`experiments/own-xpu-runtime/ops/lane-queue/`:

| Grid family | Source grid | Winner-only confirmation |
| --- | --- | --- |
| Full, A first | `proposed-p95-all-A-grid-A-grid.txt` | `proposed-p95-all-A-grid-B-confirm.txt` |
| Full, B first | `proposed-p95-all-B-grid-B-grid.txt` | `proposed-p95-all-B-grid-A-confirm.txt` |
| E3 only, A first | `proposed-p95-exp-grid-prefetch-A-grid-A-grid.txt` | `proposed-p95-exp-grid-prefetch-A-grid-B-confirm.txt` |
| E3 only, B first | `proposed-p95-exp-grid-prefetch-B-grid-B-grid.txt` | `proposed-p95-exp-grid-prefetch-B-grid-A-confirm.txt` |

E2 is closed by the [memory proof](E2-CLOSEOUT.md); no E2/E5 executable or grid
is advertised. Full and E3-only grids both have production / E3 / production,
with disjoint output namespaces. The packet86 verdict may choose which direction
and family is appropriate; it cannot waive E3's own exactness/acceptance checks.
Do not run both families to select a lucky result, combine their controls, or
reuse outputs. Never run these proposed files as part of CPU preparation.

`run_screens.py --lane A --direction A-grid --grid all --plan` plans a source
grid; `--lane B` plans its confirmation. `--direction B-grid` reverses lanes.
`--grid exp-grid-prefetch` names the single-candidate bracket. Runtime admission
requires the normal reviewed coordinator window; the shared pinned v4 wrapper
owns health, lane leasing, the 64-token incident oracle, all twelve cold timed
requests, drain and release. Fixed 90-second gaps, zero retries.

Confirmation reads only its direction/grid's completed source runs. Every run
must be exact, per-prompt target/draft acceptance must match, and E3 must beat
both controls. Confirmation repeats the same checks against both new controls.
`compare.py --direction A-grid --grid all` (or the chosen pair) refuses any
missing/mismatched evidence. These are 128-token screens, not publication gates.
No automatic chain or promotion follows.
