# Independent prepared-launch review

Final source review completed for packet37's `main.cpp`, `rank.hpp`,
`owner_api.hpp`, `owner.cpp`, `single_device.cpp` and submission/callback path.
CPU source inspection and mocked wrapper tests only; no device execution.

## Findings resolved

1. Rank 0 captures two command vectors after both state banks exist. Allocation
   IDs, cached operation maps, command vectors and parity swap together after
   draining. Rank 1 never speculates and has one vector.
2. GNU argument auditing compares the actual selected vector against independent
   current-buffer reconstruction. It bypasses the cached operation map and
   restores each site's capture-time FP32-input cache prestate. Allocation IDs,
   pointers, argument bytes and operation bytes are compared on every audited
   executed site. This replaces the insufficient immediate-clone-only proof.
3. The single-owner backend used by ranks now supports prepared native submit
   and prepared copy. In-order dependencies remain ownership-checked without
   redundant same-queue fences.
4. Rank loops use cached skip/layer metadata and fixed snapshot-index storage.
   The prepared decision uses a cached boolean. The device accessor previously
   passed a 22-byte string literal to `require(const std::string&)`, allocating
   on every call; it now constructs the exception only on failure.
5. Per-half rank receipts include affinity/load, process faults and process/thread
   context switches. The wrapper forwards the coordinator library path exactly,
   retains inherited affinity, observes only new journal lines after its own
   cursor, and refuses to latch failures before any child launch.

## Evidence and limits

`review-prepared-gates.json` records 14 source-contract checks and six rejected
negative source mutations. The mutations remove bank IDs, map/vector swaps,
parity, operation-byte comparison or independent argument reconstruction.
Source hashes bind that review. These checks complement actual forced-miss,
argument, state-byte, output and sanitizer gates; they do not replace them.

`wrapper-contract-tests.json` records 32 CPU-only mocked wrapper tests. These
cover exact library-path forwarding, argument forwarding to both rank commands,
card-pair numbering, affinity inheritance, JSON-safe launch receipts,
pre-launch refusal without latch, old-fault exclusion, new-fault latching,
watchdogs and prerequisite identity. K1 now runs an additional sequential
fresh owner for all 36 linked p33 dense instantiations (216 checks); the wrapper
requires sealed-host byte identity, exact coverage and safe zero-live teardown.
All linked-fixture receipt/output bytes and the binary hash are prerequisite-bound. The original five controller state-machine
tests were also rerun successfully without any native binary.

GNU argument serialization uses `__builtin_clear_padding` and deliberately
refuses Clang; icpx output/state correctness is separate. Real-model CPU runs use
bounded layer streaming and per-operation preparation, while miniature resident
runs exercise both persistent captured parities. Neither establishes native
prepared callback execution; coordinator K/W windows remain required.

Owner generation advances before release and distinguishes reconstruction at
the same address. Explicit invalidation refuses pending work; closed/faulted/
quiescing owners refuse issue. Native callbacks retain values and only borrow
live owner resources. Vectors are destroyed before the Engine's device owners;
no callback is issued after shutdown. Rejection preserves packet32's sticky
error, append-only QSA, token/history restore and cache invalidation rules.

The zero-allocation claim is application prepared issue only. The source guard
checks normal issue/accessor/rank-loop paths; the mock allocation benchmark
instruments actual-family front ends. It does not claim zero allocations inside
SYCL/driver, Python coordination, token-boundary lookup work, fixture capture or
diagnostic audit/logging. No new arithmetic or NaN policy is introduced.

See `LIFETIME.md` and `ROLLBACK.md` for the complete retained contracts. No
outstanding source-level stale-parity finding remained at this review. Runtime
and device qualification status must be read from the sealed gate receipts.
