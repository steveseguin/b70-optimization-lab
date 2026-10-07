# Sparse transport107 helper — CPU prototype

This helper adds timing metadata only. It imports no Torch/driver library and
does not read/copy tensors, synchronize, query events, wait, change streams,
signal a process or write files. The separately reviewed overlay supplies
existing streams and an Event factory. No live run is authorized by these files.

`prepare(identity)` binds plan, runtime manifest, server identity and qualification
metadata before workers exist; it adds/verifies the helper file SHA256.
`configure(workers, event_factory, identity=None)` later binds exactly registered
workers0/1 (`ident`, `name`). Reconfiguration with a different identity fails.
Production uses actual current thread identity; tests inject a CPU identity source.

`begin_job(clip_index, worker_index, phase)` claims at most one actual job per
worker from candidate clips99907104–99907109. Selection follows execution on
registered workers, not clip parity. The `current()` object provides hooks;
`recording` is true only during the second observed forward in stagea/b
(`forward_ordinal: 2` in evidence). Stage and block-entry hooks run before block0
argument routing. Other hooks must be gated on `recording` by the overlay to
avoid unnecessary metadata/stream lookup on disabled jobs.

Only exact `('img',0/1)` moves at block23 (xpu:0→1) and `('out',0/1)` moves after
block47 (xpu:1→0) are instrumented. D2H/H2D each have an event pair. CPU clocks
bracket the existing source-event wait and existing destination allocation;
neither operation is added, removed or reordered. Argument/custom-object moves,
fingerprints, upsampling, first/later forwards and other jobs are excluded.

Each nonempty fill call gets one pair and aggregates actual tensor count/bytes.
The overlay must count `_graph_fill_target` bytes for expanded buffers. Partition
pairs run from immediately before replay0/23 to immediately after replay22/47;
these spans include intervening host submission gaps/fills. CPU replay submission
times are summed within each partition. This does not measure isolated kernel
busy time or align device clocks.

Two forwards require at most8 moves,96 fills and4 partitions:108 operation
records and232 timing-event records (112 on xpu:0,120 on xpu:1) per worker.
The fixed allocation is128 operation records and128 events **per device per
worker**, at most256 records/512 events across the two workers. Events are
constructed before the selected chain, but backend initialization may still be
lazy on first record. Both pools remain alive in the manager, including on failure.

`finish_after_existing_drains(True)` is legal only after the caller confirms all
original drains succeeded. Only this method reads elapsed event times; every
backend error propagates unchanged. CPU hooks reserve entire pairs before the
first record. Invalid scope/order/capacity latches a global diagnostic failure,
disables subsequent hooks/claims, and preserves model execution. An event record
already in flight on another thread cannot be recalled. `clear()` records an
unfinished job as failed without event readout, then removes thread context; it
must run in the original exception-preserving wrapper's `finally`.

Disabled jobs also call finish and produce explicit zero-event receipts.
`snapshot()`/`census()` contains a bounded64-job execution audit, including
uncollected tails, finalized phase event counts, active-job count and at most two
selected receipts. `close_candidate()` never waits: it closes future selection and
invalidates an active-job barrier. The parent validates quiescence, compares job
audit with original sampler fingerprints, and persists separate candidate/timed
snapshots. A timed snapshot requires zero timed events; diagnostic validity never
weakens model quality gates.

Candidate timing covers only these instrumented samples. Instrumentation,
pipeline transients and candidate client policy differ from the later uninstrumented
timed block. No steady-state transport fraction, utilization, expected speedup,
production FPS ceiling or reason to reopen graph chaining follows automatically.

CPU verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python experiments/ltx25-b70/recovery/20261007-sparse-transport107-runtime/test_trace.py
```
