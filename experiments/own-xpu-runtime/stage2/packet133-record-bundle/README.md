# Packet133: bundle8 prepared ahead of the suffix verdict

Exactly two compositions are sealed: **bundle7 control** and **bundle7 plus
suffix interleave**. The public dimension is `suffix_schedule=production|interleave`;
`interleave` maps explicitly to packet130's native `layer-interleave` value.
Native selection bytes, GNU/device binaries, dispatch, memory layout and
arithmetic match packet130 v5 exactly. The unchanged model identity is
`iq3-p49-split32-v1`, with BF16 KV and the preregistered 80,128-row draft prefix.
No device speed or full-model equality is inferred from CPU preparation.

This is a symlink-preserving copy of frozen packet124c, with the exact packet130
native delta, including rank0's hidden-import suffix service, reset and rollback
rules. All 182 parent links survive; the oracle remains
`../packet49-integrate/oracle`. Both copies of the drain fix, graceful error
teardown and the native getrlimit gate remain mandatory. KD projects the
schedule to `production` because that window captures only the draft.

The [orchestration](../../ops/packet133-orchestration/README.md) gates the fresh
`build/device-cards01-a` chain on:

- a composed candidate smoke: all twelve prompts, 64 exact tokens each;
- exact A/B/A/B/A v5 brackets on both lanes; packet130's lane-B bracket counts
  only with identical native selection, binary, dispatch and memory identity;
- each of the two candidate repeats at least 0.5% faster than **every** control,
  control drift at most 3%, and identical acceptance counts across views/lanes;
- source-bound CPU tests, both drain scans, unchanged native limits, and the
  complete eleven-window argument **and queue** gates inherited from packet124c.

The new [lane-A proposal](../../ops/lane-queue/proposed-p133-v5-A.txt) is planned
on a disposable queue, not queued. Expected bracket duration: 12–20 minutes;
watchdog: 80 minutes. The separate candidate smoke entry is also prepared.
The lane-A adapter uses packet130's sealed worker and native engine, with a
copied screen entry whose only changes locate its output in this packet and
its worker in the frozen packet130 tree. It embeds the complete environment.

Packet131 has a documented disabled slot in `extension-slots.json`. It is not
part of either sealed composition and cannot inherit this packet's results.

CPU reproduction uses `nice -n 19 taskset -c 8-15,24-31`, `python3 -B`,
`OMP_NUM_THREADS=2` and stdin `/dev/null`. Keep root free space at least 25 GB
and build bytes at most 300 MB. Native binaries are reused by hash; the local
full-size CPU fixtures compile only through the copied new ops compiler turn.
Run `reuse_build.py`, then `cpu_prepare.py cpu_gate.py prepare_chain.py
full_shape.py startup103.py`; use the orchestration sequence next. Runtime
imports do not set resource caps. The CPU fixture parent caps its own process
at 8 GiB; the native getrlimit probes run without that inherited cap.

[Work note](../../../../notes/2026-10-18-own-runtime-packet133.md).

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md): all preparation gates
pass. Packet130 B arrived during preparation: exact output, −1.605458% versus
the fastest control, so the +0.5% gate fails. Readiness is false. Lane A and the
composed smoke remain unrun; the proposal remains unqueued.
