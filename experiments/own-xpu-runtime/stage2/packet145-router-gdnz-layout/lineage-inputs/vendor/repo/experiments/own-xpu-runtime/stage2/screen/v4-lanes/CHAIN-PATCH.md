# Future chain window drain patch

This is an **unapplied template for a new packet**. Packet70 and every existing
packet remain unchanged. The patch uses packet-relative paths, so apply it
only inside a newly created future packet copied from the pinned reference.
`chain-reference.json` pins the source revision and both input SHA-256 hashes.
`make_chain_patch.py` reconstructs the patch from Git without reading or writing
live packet source. The CPU tests apply it only in temporary scratch space.

## Where the stale record comes from

In the reference packet70 `window_adapter.py`, `run_window()` calls
`bind_receipt()` only when `main()` returns zero. `bind_receipt()` calls
`WindowAdmission.complete()`, which calls `DrainPermit.complete()` in
`drain_gate.py`. That last call changes the shared
`screen/v3/teardown-state.json` to `drained: true` and records
`completed_monotonic`. Until then, its whole-window record is false and the
shared teardown flock stays held.

In `window.py`, K2's `run_fixtures()` waits for both sequential owners, then
`main()` calls `summarize()` and `pin_production_dispatch()`. A CPU exception
there returns a failed window before `bind_receipt()`. Device owners have
exited, but the shared record remains false. This is the reported October 17
K2 failure, not a new device measurement.

## What the template changes

`Watch.finish_devices()` checks that owners have exited, runs the existing
postflight, then calls the new `WindowAdmission.devices_drained()`. That method
requires observed owner isolation and exit, retains READY checks for model
windows, checks remaining clients, and marks the shared record drained under
its existing flock. It then releases that flock and its lane/whole-host lease.
The next teardown still observes the unchanged 60-second spacing.

The K fixture runner calls this boundary after its final successful owner
wait, before its final CPU receipt validator or hash work. This covers K0,
K1a/K1b and the K2 summary/dispatch failure. Calling the boundary again at the
normal end is harmless. Launching another device owner afterwards is refused.
CPU exceptions after this boundary cannot latch a device failure.

Final success is separate. `complete()` and `bind_receipt()` still require the
original successful window and matching launched owners, then bind its receipt
hash. A failed report remains `passed: false`, cannot satisfy prerequisites,
and cannot advance the queue. Drain completion alone never qualifies a result.

This is the K-fixture/K2 integration template. KD and model-window runners can
perform CPU work *inside* their helpers. A future packet adopting this boundary
for those paths must call `finish_devices()` immediately after its **last**
transport/owner exits, before helper-level aggregation. Do not call it after an
intermediate owner in a canary or sequential suite: the template explicitly
forbids later launches. The fallback at the end of `main()` preserves those
other paths' existing ordering; it is not evidence of early release for them.

## How to use it in a future packet

1. Copy the pinned chain sources into a new packet. Check the source hashes in
   `chain-reference.json`; port explicitly if the future sources differ.
2. In that new packet only, run `patch --dry-run -p1` with
   `chain-window-drain.patch` as input, then apply it there. Never target packet70.
3. For other owner-runner families, place the same boundary at the terminal
   owner exit as described above. Keep signal/fault supervision during postflight.
4. Run the packet's CPU tests plus the injected report-failure, live-owner and
   failed-postflight cases. Reseal all affected chain/window sources and regenerate
   its plans before the coordinator launches anything.

`test_chain_patch.py` checks exact patch application and compilation; a planted
K2 report failure after drain; successful receipt binding without a second lease
release; and refusal to mark live owners or a failed postflight drained. All
leases, process tables and records used by those tests are temporary CPU fixtures.
