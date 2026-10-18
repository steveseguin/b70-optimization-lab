# Packet115 one-load expert bracket

This separate copy combines packet103 after the 103x launch repair with
packet109's one-load wrapper. It switches only `expert_kernels`; the physical
expert layout remains `exp-halfcache+down-tile16`. Every view resets target,
draft, history and capture state and retains weight allocation identities.

The proposed B job is conditional. It rereads the two-process micro gate,
selects the first registered design that passes, and requires a CPU seal for
that exact candidate. Both orders must be exact and at most 0.85 of both the
normal and LARGE production controls. Missing or changed evidence refuses
before admission or launch. A CPU `--plan` may describe a pending conditional
job, explicitly marked ineligible to launch. No device result is implied.

The initial E3 view is provisional, not a measured winner. Once both micros
finish, run `prepare_winner.py` on CPU. It rereads the measured gate, chooses
the first passing registered design, archives prior selections and receipts,
and prepares only production plus that winner. An already matching valid CPU
seal is reused. It never edits a live queue or launches a GPU job.

Preparation uses the two layouts that will run, production and the selected
candidate. `build_engine.py` reuses pinned packet103 objects and builds the new
entry, selection parser and expert dispatcher. `full_shape.py` checks both
ranks, fresh and switched captures; `reset_gate.py` and `protocol_gate.py` run
two fresh miniature CPU passes. Miniature projection to `experts=wide64`
checks reset/transport only; full-size operator byte evidence is separately
required by `cpu_seal.py --operator-evidence PATH`.

`queue_plan.py` writes only the new proposed file and plans in a temporary
queue. The complete five-view bracket uses one loaded rank pair, approximately
15 minutes, and a 60-minute watchdog. The coordinator supplies authorization,
fault review and lane/memory admission. This diagnostic bracket retains every
token check and per-prompt acceptance comparison; it cannot publish a record.

Run CPU preparation with `nice -n 19 taskset -c 8-15,24-31 python3 -B` and
stdin from `/dev/null`. Resource caps are installed only by CPU `__main__`
entry points. Device entries install the 103x guard against inherited caps.
Only packet115 owns the generated sources and evidence; prior packets and
live queues remain frozen.
