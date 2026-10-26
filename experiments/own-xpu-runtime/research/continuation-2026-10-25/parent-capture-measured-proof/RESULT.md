# Parent-capture measured state gate passed

Both cold requests match all 32 output IDs, 2,065 target buffers and 73 draft allocations against accepted replay. Reset/provenance and capture-event checks passed. This is measured-policy experimental state parity, with no new-build debug-policy qualification or speed claim. Per-operation byte/survival diagnostics were disabled; full cold allocation bytes were not individually read back. Scheduler overlap counts do not establish GPU kernel concurrency.

[Summary](summary.json), [plan](plan.json) and [retention receipt](retention-receipt.json). Raw GPU proof remains protected in `/dev/shm/sc117-parent-capture-measured-proof-20261025`; no durable raw archive is claimed. The full twelve-prompt timing suite follows this gate.
