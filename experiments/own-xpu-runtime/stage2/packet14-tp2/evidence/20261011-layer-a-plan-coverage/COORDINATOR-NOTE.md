# Packet 14 layer gate, attempt a: host-side refusal before any device work (2026-10-11 08:05 UTC)

`window.py --stage layer` on cards 2+3 exited in 6 s with `complete tensor coverage`.
`write_plan` required every tensor in the model directory to have a launch site, but
the `--first-layer` plan names only layer 0's tensors, so the real model could never
pass this check (the mini-model tests have no tensors outside the plan). The check
runs before the engine and the device owners are constructed: no device was opened,
`model_payload_bytes_read` is 0 and the teardown list is empty. The receipt's
`device_executed: true` and the `FAULT.json` latch ("unsafe or missing owner
teardown") describe a child that never created an owner; they are not a GPU fault.
The kernel log for the window is empty.

Fix: `write_plan` takes a one-layer flag; one-layer plans must be a non-empty strict
subset, every other mode still requires full coverage. Rebuilt and re-tested before
attempt b. The latch is kept here as `FAULT.resolved.json`.
