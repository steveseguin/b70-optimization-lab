# Packet98c: one-load kernel selection brackets

This packet copies packet97's native bundle sources and packet98's v5 wrapper.
It adds a quiescent native switch for route, recurrence, production/wide HC
gate and draft attention. Weights, layouts and allocation identities stay fixed.
The target and draft captures are rebuilt and all request state is reset before
each view. See [load/dispatch proof](LAYOUT-AUDIT.md).

Both builds, all full-shape and reset checks, native refusals and repeated
miniature comparisons pass. Native preparation is sealed; wrapper sealing and
queue planning receipts are recorded separately under `evidence/`.
Device output equality, acceptance and speed are unmeasured.
CPU miniature checks are not full-model quality evidence.
No record, model package or production default changes.

The first proposed device job is
[`proposed-p98c-smoke-B.txt`](../../ops/lane-queue/proposed-p98c-smoke-B.txt):
route production / fast / production, one loaded rank pair on lane B.
Production means packet97's route-exp32-rank4; all other choices stay fixed.
Each view runs incident64 and twelve cold 128-token oracle requests. These
screens are not the 512-token promotion suite. Cache reuse is forbidden and
every request must report cached_tokens=0.

Only after that same-binary smoke passes may the coordinator use:

- `proposed-p98c-bracket-{A,B}.txt`: the kernel-only portion of packet97 decision
  f1e5d7f47fc0fe54, route-fast + rec-both-plus, with experts fixed at wide64.
- `proposed-p98c-attention-{A,B}.txt`: packet101's draft split32 attention alone.

Each full bracket is control/candidate/control/candidate/control. Lane A remains
the record lane. Proposals are alternatives for scheduling, not authorization
to occupy both lanes. All thirteen oracle checks and per-prompt acceptance
must agree in every view. First-use smoke checks both end controls for drift;
it makes no speed verdict. Later readiness needs both candidate repeats faster
than every control and the separate full-chain quality/performance gates.

`bracket_job.py --kind smoke|bracket|attention --lane A|B --output PATH --plan`
is CPU-only. Smoke is lane B only. Device mode additionally requires the
coordinator's explicit window, fault review, memory/lane admission and guarded
systemd lifecycle. Full jobs refuse until the saved same-seal smoke passes.
Planning does not occupy a lane or edit a live queue.

Reproduce locally with `nice -n 19 taskset -c 8-15,24-31 python3 -B`, closed
stdin, in this order: `bracket_config.py`, `build_engine.py`, `full_shape.py`,
`reset_gate.py`, `protocol_gate.py`, `audit_sources.py`, the unittest suite, `seal_native.py`,
`cpu_seal.py`, `queue_plan.py`. Seals require fresh outputs. Both native
compilers are serialized through packet94's `compile_turn.py`; compilation of
the device binary does not execute a GPU program. The 8 GiB address-space
limit and 300 MB build ceiling apply throughout. This is an originating-host
lab experiment, requiring the pinned packet97 objects and inherited inputs.

The large generated rope header is ignored. `restore_rope.py` restores it from
the hash-pinned parent copy when absent. [Retention](RETENTION.md) describes
verified full-shape archives. Historical inherited chain patches and placement
examples are provenance only; use the proposed packet98c jobs above.

[Task note](../../../../notes/2026-10-18-own-runtime-packet98c.md),
[boundaries](DO-NOT-REPEAT.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
