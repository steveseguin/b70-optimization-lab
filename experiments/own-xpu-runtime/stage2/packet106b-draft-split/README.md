# Packet106b: preserved reset repair, combined validation

New copy of frozen packet106. Packet106 already restored the private active
flag in both target and draft suffix services; packet106b preserves those
runtime bytes. The draft suffix still runs only on verified hits. Misses keep
the complete 91,392-row draft prefix. Target/draft mailboxes remain separate.
No original packet, screen, service or live queue is modified.

The scheduled views are production, head split and head+draft split. Both
compilers pass repeated draft logit/winner byte checks, the target reset
regression, controller hit/miss checks and actual combined-runtime mocks.
All six rank allocations and all 33 startup windows pass, including the real
host canary and KD host reference. One immediate receipt per completed window
is retained; matching source identities permit resume. Draft-only and BCS
are excluded from this task, not claimed as newly tested.

Coordinator sequence (all proposals are planned on temporary queues only):

1. Run packet105b's suffix-heavy micro and twelve-prompt head-only smoke.
2. `../../ops/lane-queue/proposed-p106b-smoke-B.txt` runs the combined candidate
   on all twelve cold prompts at 64 tokens. It additionally requires real draft
   suffix activity and the known target suffix winner. It refuses without the
   exact completed micro receipt.
3. `../../ops/lane-queue/proposed-p105b-B-grid.txt`: production / head-split /
   head+draft-split / production, all from this packet's binary. It refuses
   until both twelve-prompt smokes and the micro pass. The existing screen checks
   target tokens, draft proposal sequences and acceptance counts exactly.
4. `../../ops/lane-queue/proposed-p105b-A-confirm.txt`: fresh production / best
   exact improving B winner / production. Execution refuses if any B screen
   is incomplete, inexact, from another boot, overlaps, changes proposals or
   acceptance, or if no candidate beats both controls. Plan mode reports a
   placeholder; it does not qualify a winner. Records remain on A.

The extra combined smoke protects a distinct binary before the grid. Both
105b and 106b must pass their own smoke; a one-prompt or shortened gate cannot
substitute. These capped screens are diagnostic, not record submissions.
Device equality, fresh-process repeats, residency and speed remain pending.

Use `nice -n 19 taskset -c 8-15,24-31 python3 -B <script> </dev/null` from the
repo root. CPU preparation: `cpu_milestone.py build_engine.py
prepare_host_inputs.py reset_regression.py cpu_gate.py controller_gate.py
full_shape.py runtime_mock.py startup97e.py`; then `prepare_packet.py` on new
unsealed views and `queue_plan.py`. Seals pin immutable inputs; no mutable
parent selection or orchestration output enters their dependency maps.
See [retention](RETENTION.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md), and
the [shared work note](../../../../notes/2026-10-18-own-runtime-packet105b.md).
