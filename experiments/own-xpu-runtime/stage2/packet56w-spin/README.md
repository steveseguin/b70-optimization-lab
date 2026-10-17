# Packet56w: bounded host spin

Packet 56 with one 250 µs host spin budget before sleeping in each mailbox or
device-event wait, plus packet57 attribution's rank-0 queue profiling property.
This is a diagnostic screen candidate. Device exactness and
speed are pending; no GPU is used during preparation.

Preparation passed: device build, **1,123 controller cases**, **five mailbox
fault checks**, and **765 identical bytes** in the parent/candidate fixture.
The screen seal and CPU-only screen plan passed. About 30 MB of regenerable
objects were deleted; the retained build is about 38 MB. See
[controller receipt](evidence/controller.json), [fault receipt](evidence/mailbox-faults.json),
[byte receipt](fixture/receipt.json), [seal](screen-seal.json) and
[screen plan](evidence/screen-plan.json).

`host_spin.hpp` uses x86 PAUSE (AArch64 YIELD; thread yield fallback), checks
completion/publication every iteration, and checks the monotonic clock and
existing guard every 32 iterations. It caps the spin at the existing deadline.
The mailbox retains acquire/release publication, cancellation, peer-abort and
total-timeout checks, then falls back to its original 100 µs futex waits. The
device backend retains completion/error checks and final `wait_and_throw`,
then falls back to its original 1 ms sleeps. Long waits do not restart the
250 µs spin budget after each sleep. Scheduler preemption can extend elapsed
wall time; the loop does not promise a real-time scheduling deadline.

The shared mailbox helper covers request, reply, accept/rollback and draft
publication waits on both ranks. The event helper covers target, miss-redo and
transfer drains. The existing draft progress callback already actively polls
with `yield`; it stays unchanged, including draft publication progress. Socket
polls are command/control transport, not an additional native hit/miss wait.

No target/draft kernel, ordering, arithmetic, prefix, dispatch, selection,
memory plan, BF16 KV or packet49 oracle changes. The copied source manifest
and [source delta](evidence/source-delta.json) identify the parent and changes.
Only documented entry points here apply; copied source comments retain history.

## Packet57 timing audit

The [retained diff](evidence/packet57-wait-audit.diff) compares packet56 and
packet57's native controller, device backend, engine, rank, draft, owner and
host backend. The mailbox and device wait implementations are identical.
Both token and attribution modes use `profile_events=false`. In token mode,
only rank 1 receives `--draft-mtp`, so MTP already enables queue profiling on
rank 1. Attribution additionally enables the queue profiling property on
rank 0. Packet56w adopts that rank-0 property, which can affect driver event
completion behavior while preserving the same in-order queue, submissions,
dependencies and arithmetic. This is a combined spin/queue-property candidate;
its A/B screen cannot isolate the contribution of each change.

Attribution also adds event registration,
event timing reads and output after existing completion/drain checks. It does
not add/remove a `wait`, event dependency, poll, sleep or draft progress hook.
These extra host operations can perturb overlap, but they are not a distinct
wait policy to copy. No event collection, timing reads or extra synchronization
is adopted. The other sleep worth testing is the existing 1 ms event wait, which
now receives the same bounded spin as the mailbox.

The brief's packet57 speed/sleep observations motivate this experiment; they
are not packet56w measurements or proof that spinning will reproduce the gain.

## Lean CPU preparation

From the repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet56w-spin
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/build_spin.py"
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/cpu_gate.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/screen/seal.py \
  --profile tp2 --lineage "$P" --build-receipt "$P/build-device-receipt.json" \
  --fixture "$P/fixture/receipt.json" --binary "$P/build/device/own-rt-iq3" \
  --dispatch "$P/dispatch-speed6.json" --output "$P/screen-seal.json"
```

Build only the compatible device engine and small host controller binaries,
serially. The device executable is never run by the build or CPU gate. The
existing controller gate compares all ternary hit/miss/no-guess patterns of
length 0–6, random long requests and EOS/overlap cases with its Python model.
The existing mailbox fault test covers timeout, abort, stop, repeated requests
and queued-command abort. One fixed parent/candidate fixture retains raw JSON
and canonical exact bytes for tokens, state, fixtures, guesses and counts.
Timing fields are excluded from byte equality. This is a small synthetic
controller check, not real-model qualification.

The screen seal binds compiler inputs, commands, binary, CPU gates, fixture
bytes, dispatch, selection and memory plan. Never overwrite it after a screen.
The unchanged RoPE bytes are a read-only link to packet56; the draft manifest
is copied unchanged. Both runtime inputs are bound by the build receipt.
See [coordinator command](WINDOW.md) and [task note](../../../../notes/2026-10-17-own-runtime-packet56w.md).
