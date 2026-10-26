# Parent-capture full suite: experimental gain

Median controller decode was 44.967923984 tok/s versus balanced baseline 41.398996823 tok/s: an 8.62% gain under the same suite observer. All 5,965 output IDs and final 2,065 target buffers match; all four workers exited zero. The preceding measured two-request gate also matched all 32 outputs, 2,065 target buffers and 73 draft allocations per request. This is experimental, with no new-build debug-policy qualification, independent full-cohort draft parity or GPU-concurrency claim.

[Summary](summary.json), [plan](plan.json) and [retention receipt](retention-receipt.json). Full raw evidence remains protected in `/dev/shm/sc117-parent-capture-suite-proof-20261025`; no durable raw archive is claimed.
