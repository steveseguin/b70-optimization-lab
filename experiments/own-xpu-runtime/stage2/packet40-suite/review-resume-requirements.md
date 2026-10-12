# Independent requirements 2, 5, 6 and 7 review

This source review ran after the disk-full resume. No device binary ran.
CPU execution was limited to the five KD cleanup mock/structural gates.

Requirement 2: fixture_driver.cpp constructs all 65 context lengths 88 through
152 plus 256 at capacity 256, budget 2048 and one token. K2 runs incumbent
versus round2, p33.qsa.shape and both p30 attention variants for each workload.
The registry admits both p30 attention variants and rows4 small projections.
KERNELS-P30.md distinguishes compile-time geometry from runtime capacity and
position. The p33 capacity-256 and full-array p30 CPU gates have matching
instantiations. On-card timing and exactness remain coordinator work.

Requirement 5: WINDOW.md lists K0, fresh K1a/K1b, K2, W0p, KD, both controller
variants of the single-request modes, class profiling, WS and WSs. Extra W2n
and W2x cover n-gram and all-miss equivalence. W windows require nice 0; cleaned
environments forward LD_LIBRARY_PATH unchanged and retain CPU affinity. The
watchdog table satisfies four times the estimate plus a 17-second allowance,
and every watchdog exceeds 300 seconds. The journal watcher starts from its
own cursor, and latches require both a launched child and a new fault line.
Token-mode receipt paths do not require class-only profiling tables.

I found seal admission gaps and reported them to the parent for repair:
p33_linked_fixture_host_sha256, nongemv_fixture_host_sha256,
draft_capture_fixture_sha256 and draft_capture_input_sha256 were consumed by
window paths but absent from seal.py at review time. The old unused cpu_gate
helper has another legacy host/own-rt-iq3 schema; do not call it unchanged.
Component host rehearsal exercises the receipt and summary paths, but cannot
catch every window.main seal admission defect. Final seal admission needs a
separate no-launch check against the completed receipt.

KD cleanup previously allowed a children.json failure immediately after Popen,
or a failure-hook/receipt error, to skip cooperative shutdown. draft_window.py
now covers post-launch bookkeeping, attempts diagnostics before stop, handles
stop-write failure by closing the pipe, drains for a bounded period, and always
closes pipe descriptors. Five CPU mocks/structural checks passed. Each owner
also receives storage admission with a reserve based on retained CPU fixture
sizes; completed diagnostic logs are losslessly compressed and verified.

Requirement 6: pipeline enrichment records each generated token's forward and
reverse handover, retaining signed speculative overlap separately. It records
acceptance and hit/miss cycle summaries. Rank idle values explicitly separate
host-command lower bounds from profiled kernel-time complements. CPU output
has no device speed and no GPU idle estimate. Event profiling remains a
separate diagnostic class-timing mode.

Requirement 7: FUTURE.md has separate pages for moving the draft, double
speculation and batch prefill. The 47.2 ms halves sum, (T+m)/2 balance examples,
199/256 acceptance squared, and both-card memory arithmetic are internally
consistent. Unmeasured draft time and independent survival are assumptions,
not observations. The designs list target verification and complete rollback
requirements. No future design was implemented by this review.

Documentation fixes: KERNELS.md now names packet38, labels its lack of card
measurements, and links the inherited packet37 dense review at its real path.
