# Persistent rolling native capability

This opt-in implementation preserves the existing quiescent, pending-provider,
target-only ring and two-card modes. GPU qualification is a separate gate.

Use `--pipeline-ring-persistent-requests` with the existing ring/live/pending
provider modes. Context must be at least 32. The process-wide
`--pipeline-ring-check-policy qualification|measured` defaults to qualification
only when the new capability is enabled. It cannot change at RESET.

Qualification requires target restore verification on every owner and recursive
restore plus provider-survival verification on the first owner. Measured mode
requires those diagnostic flags to be absent. Both policies retain the same
target/provider copies, allocation and descriptor checks, exact host restoration,
queue ordering, independent final-peer validation, and sticky-error refusal.
Measured mode omits full allocation readbacks and before/after provider survival
captures; it reports zero performed diagnostic checks and false aggregate byte
verification flags, including when there were no restores. It does not assert
unobserved byte equality.

The new native attestation is `ownrt.ring-state.persistent.v1`, mode
`persistent-rolling`. The layout remains the existing complete live ownership
layout. Old proof schemas are unchanged. Mandatory target host restore counts
mean executed bank/extent/reference checks and assignment of saved metadata;
they are not an additional full-host byte comparison. Provider host restore
counts follow the existing complete host equality checks. Every count is derived
from successful native operations already maintained by the owner.

Op 11 accepts zero payload plus the ordinary stage/final identity and next global
socket sequence. Its descriptor is read once from the original output directory
as `reset-SEQ.json`, with schema `ownrt.ring-reset-request.v1` and exactly eight
additional fields: `stage_id`, `global_sequence`, `previous_epoch`, `next_epoch`,
`previous_request_sha256`, `next_request_sha256`, `destination`, and `oracle`.
It requires a new request digest, consecutive nonwrapping epoch, unchanged oracle,
fresh confined output path, and bounded regular metadata with no duplicate keys.
Queued work, callbacks, target pending rows, provider branches or sticky failures
prevent RESET. Initial epoch-zero reset is supported.

RESET uses the existing owner-zero implementation and the actual ring's
`reset_owner`/`reset_after_owner_zero` hooks. It restores both context banks,
reuploads checked copy descriptors after zeroing, clears lookup/cache/history and
scratch state, resets canonical provider buffers and pinned staging, and clears
saved recursive private host/pinned state. It recreates the provider Sequence in
the new request context while retaining the global socket sequence. Shared maps
are zeroed; the readonly peer FD/inode stays pinned. No allocation is recreated.

Each request receives new stage metadata and trace files. `ring-reset.json`
binds both identities, the descriptor SHA, fixed policy, cold positions/extents,
reset index and identical before/after physical allocation census hashes. Provider
cold-host and Sequence hashes identify metadata only. Its explicit
`cold_state_byte_verified:false` prevents treating initialization as a full-buffer
readback proof. Reset maintenance ends before timing counters are cleared; the
next request cannot start until all owners acknowledge the same epoch.

CPU coverage is recorded in `evidence/native-persistent-ring-cpu.json`:

- `test_ring_reset_descriptor.cpp` exercises the actual strict parser and file
  admission, including duplicate/stale/oversized/FIFO/symlink/outside-path inputs.
- `test_persistent_ring_native.cpp` executes the actual Engine, Dispatcher,
  owner-zero, ring descriptor reconstruction and receipt path twice per policy
  on Host, with scratch/cache/shared-map corruption before each reset. Its empty
  plan performs no model arithmetic. The unused legacy 256 MiB operator reserve
  is replaced with a 4 KiB test reserve before the allocation census is frozen.
  `persistent_ring_host_stubs.cpp` contains 38 explicit throwing link stubs for
  excluded arithmetic/model-loader entries: reaching any one fails the test.
  Real owner, retirement, CopyEngine and SnapshotFlat implementations are linked.
- The recursive-provider Host fixture exercises actual provider-private reset
  members, all 71 canonical device buffers and two pinned buffers, new-epoch
  Sequence rejection, and exact canonical restoration with diagnostic byte
  verification disabled. Arithmetic in that fixture remains synthetic.
- Existing ring control and checked checkpoint fixtures retain suffix rollback,
  epoch/sequence refusal, zeroed-table reconstruction and immutable census tests.

The first actual Engine fixture failed its aggregate checkpoint bound because of
the empty plan's legacy scratch reserve. Its exact source and failure are retained,
along with the initial link failures and the pre-context-guard successful source.
No device build or GPU execution was used for these CPU checks.

Required next gates: two complete cold requests with full target/draft state
comparison under qualification policy; a separate bounded measured-policy parity
gate; then the matched 12-prompt cold suite on one continuously loaded process set.
Cancellation, early EOS and full-cap termination must retain their own explicitly
qualified evidence scope. No CPU result here establishes model throughput.
