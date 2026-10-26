# Balanced persistent qualification passed

Placement cuts `0,8,21,34,48` passed both cold requests: each matches all 32 output tokens, 2,065 target buffers and 73 canonical draft allocations. Per-operation byte/survival checks and request reset/provenance checks passed. All four workers exited zero. This is correctness qualification, with no speed claim; full cold allocation bytes were not individually read back.

The [summary](summary.json), [plan](plan.json), runtime identities and [retention receipt](retention-receipt.json) retain the small proof record. Full state and journals remain protected in `/dev/shm/sc117-persistent-balanced-qualified-proof-20261025` and `/dev/shm/sc117-ring-20261025/persistent-rolling-balanced-qualified-b`; this record does not claim a durable raw archive. Qualification is not an archival prerequisite for the next benchmark.
