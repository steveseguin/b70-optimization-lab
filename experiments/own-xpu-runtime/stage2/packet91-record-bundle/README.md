# Packet91 record bundle 3

CPU preparation only. Device quality, acceptance, speed and the record chain
remain pending. Packet84's running tree, build and orchestration are frozen.

The control is packet84's chained selection: ordered host cleanup, wide HC,
wide64 experts, parallel recurrence, production routing/norm/dense/draft head,
draft-HC, batched rollback, rank1 draft and 24/24 target layers. Full BF16 KV,
full target head, target arithmetic and packet49 oracle remain unchanged.

Four views test control, route-fast, rec-both-plus, and both changes. Route-fast
reuses packet84's original binary by hash. The optional recurrence view reuses
packet82b's already-built binary by hash, with its own source receipt and focused
variant sources. No binary is rebuilt. The original packet84 native sources
are copied byte for byte; `build-provenance.json` identifies the actual binary
and source closure for each recurrence choice. Never infer binary provenance
from the packet91 directory name alone.

`extension-slots.json` reserves packet90's expert/HC slot. It is empty and cannot
select a winner. Future additions must extend the registered views, binary
provenance and CPU evidence, then pass their own matched composition screens.
The seal/selection/queue interfaces already accept complete named compositions.

GNU/Intel recurrence fixtures run twice each and compare complete state/output
bytes to the same-compiler reference. Existing production NaN payload differences
between compilers stay disclosed. Route proof is inherited by source and fixture
hash from packet84. This is factorized operator proof, not a model-output test.
The full-shape CPU gate executes real startup, capture, draft setup and memory
admission for all four views on both ranks, with payload/backend mocks only.

## Proposed screens

All paths below are relative to `experiments/own-xpu-runtime/`:

- `ops/lane-queue/proposed-p91-A.txt`: full A grid, five fresh lifetimes.
- `ops/lane-queue/proposed-p91-B.txt`: control / exact A winner / control.
- `ops/lane-queue/proposed-p91-B-grid.txt`: full B grid, five fresh lifetimes.

The B confirmation's plan uses a placeholder view; execution resolves the exact
completed A winner before **every** job, including controls. It refuses a partial,
inexact or non-improving A grid. Both lanes use the original shared, pinned v4
wrapper through `run_screen.py`; the live queue is never edited by preparation.

Selection requires every screen to pass 13/13 exact checks, ordered nonoverlapping
same-boot controls, and the **same complete composition** to exceed both controls
on both lanes. The A winner may be confirmed by B's three-screen confirmation or
its full grid. Historical p78/p84s measurements and p82b's independent screen
cannot qualify packet91. Short screens cannot establish a record.

## CPU sequence

Prefix commands with `nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2`,
use `python3 -B`, and redirect stdin from `/dev/null`. Run from this directory:

1. `build_engine.py` (hash reuse only), `cpu_gate.py`, `full_shape.py`.
2. Tests with `/home/steve/.venvs/deepseek-v4-xpu/bin/python -B -m pytest`.
3. `prepare_chain.py`, `prepare_packet.py`, `fast_reseal.py`, `dry_run.py --cached`.
4. `dry_run.py`, `chain_seal.py --verify`, `storage_precheck.py`, `queue_plan.py`.
5. The [CPU-only orchestrator](../../ops/packet91-orchestration/README.md).

One coordinator owns a fresh record chain after confirmed screens. No service,
GPU, submission, host setting change or frozen-tree write occurs in preparation.
Root free must stay at least 12 GB; new bytes stay below 1.5 GB. Per-gate fixture
scratch is removed after compact byte receipts are retained. No compiler runs.
