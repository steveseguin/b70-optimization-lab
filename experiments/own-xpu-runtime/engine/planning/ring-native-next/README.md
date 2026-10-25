# Unpromoted native two-slot ring proposal

Separate source proposal only. No active native/controller file is modified or
imports this directory. It is not an executable pipeline or a speed result.

- `stage_ring.hpp`: templated native control component with immutable Row lineage,
  two completed tentative records, oldest-only resolution, ACCEPT with no physical
  rewind, one oldest-snapshot restoration for a whole rejected suffix, explicit
  independent draft borrowing, sticky/partial-failure poisoning and cold RESET
  with monotonic socket sequence/request epoch.
- `checkpoint_ring.hpp`: proposed actual Engine-compatible checked transport.
  One target/provider partition and one device census serve two backup regions
  and four copy tables. All six private allocations precede census freezing;
  snapshots never include each other's storage. Each slot retains target bank,
  attention, history/cache metadata and shared output bytes. Independent provider
  device/pinned bytes remain excluded by explicit validated ownership.
- `engine_backend.hpp`: thin adapter to the existing `half_step`, `Candidate`
  and `publish`, not another model executor. It requires retained steps disabled,
  owns complete row output bytes, and requires an explicit checked reset callback.
- `wire.hpp`: exact little-endian 224-byte row, 128-byte resolution ACK and
  192-byte future proposal header; checks stage/request/epoch, original ticket,
  prefix and payload hashes, complete stream size, padding and cursor ownership.
  Proposal validation requires exact expected seed row, parent, final commit and
  provider serial, rather than accepting nonzero identities.
- `dispatcher.hpp`: concrete, unpromoted handlers for operations 24–26 using the
  existing native Request/Reply, half_step, Candidate and final raw-hidden handoff.
- `test_wire.cpp`: layout, hash, ownership, publication, cursor and proposal
  identity refusal tests, compiled and passed.
- `test_stage_ring.cpp`: lightweight adversarial CPU control test, compiled/run.
- `test_checked_checkpoint_ring.cpp`: heavier host-only actual copy-transport and
  adapter/dispatcher compile test. **Compiled and passed on the host backend.**
  It includes the existing full-main host fixture; no GPU was opened.

The lightweight test covers both rejection depths, capacities/parent/epoch/prefix
refusal,31/32/33 extent and bank history, an older ACCEPT while newer work is fully
executed, preservation of independent newer draft state, no rollback after sticky
or partial-submission failure, final-stage verified-input gating, and RESET without
reusing the global socket sequence.

The manager and adapter are concrete code proposals, but their integration remains
unqualified until independent review closes, a native opt-in outer dispatcher
admits these handlers, and matched GPU state proofs pass. The actual host transport
test exercises checkpoint copying; it only compiles the Engine adapter and
wire dispatcher, and does not execute model HALF kernels or native socket traffic. StageRing assumes the owning socket has separately enforced
contiguous command sequence; it enforces strictly increasing sequence across its
operations, allowing other admitted operations to consume intervening sequences.
The callback must perform actual request/provider reset before the manager rebuilds
tables; no caller should zero the owner before StageRing admits the boundary.

Still missing: full request-scoped ring attestation and counters, command 27
recursive draft execution, per-row trace retention, outer socket-loop admission,
and a Python-to-native wire bridge exercised over real sockets. Preserve current
20–23 behavior and default full snapshots. Future promotion must be opt-in and
must not reinterpret current v1 quiescence evidence as ring qualification.

Actual host validation command (CPU only; avoid concurrent GPU timing):

```sh
nice -n 19 g++ -std=c++20 -O1 -DOWN_RT_HOST_ONLY -ffunction-sections -fdata-sections \
  -I experiments/own-xpu-runtime/engine/src \
  experiments/own-xpu-runtime/engine/planning/ring-native-next/test_checked_checkpoint_ring.cpp \
  experiments/own-xpu-runtime/engine/src/stage2/packet194-expert-diet-engine/owner.cpp \
  -Wl,--gc-sections -lcrypto -pthread -o /dev/shm/ownrt-test-checked-ring-next
```

Integration requirements:

- Construct the provider and validated ownership partition before this manager.
  Do not construct the old StageCheckpoint alongside it. All ring images and
  checked descriptors are allocated together before the census is frozen.
- The outer socket loop must preserve its contiguous wire sequence checks, call
  this dispatcher only for operations 24–26, and call `reply_published(op)` after
  the complete ROW reply is written. Existing operations 20–23 stay unchanged.
- ROW input is copied into owned host storage before its SHA is checked. The
  adapter uploads those same bytes using the existing prepared-input HALF path,
  avoiding a second read from mutable shared memory. This preparation path still
  requires matched GPU state qualification; CPU compilation does not establish it.
- Final ACCEPT retains the existing 112-byte canonical true-pair Handoff. The
  controller must bind its ticket, commit, position, input, head mask, output and
  raw-hidden SHA to the accepted final row before admitting a draft operation.
- The native ACK validator checks structural cursor relationships. The controller
  must also compare expected physical/committed/pending values and require a
  successful byte-restore flag when its qualification policy requested one.
- RESET parsing remains owned by the outer checked boundary. The supplied reset
  callback must reset target and provider state before rebuilding ring descriptors;
  it must preserve wire sequence and advance request epoch exactly once.

`cpu-validation.json` and its log record the final proposal's CPU-only checks.
The earlier control-only patch and receipt remain as `proposal-control-v1.patch`
and `cpu-control-v1.json`; `proposal.patch` is the current exact source snapshot.

See `../ring-wire-next.md` for the proposed wire contract and
`../wavefront-ring-next.md` for ownership and cost assumptions. No training,
restart, GPU action or active benchmark-source mutation is part of this proposal.

The later [common-cohort rejoin](../../../research/continuation-2026-10-25/recursive-common-cohort.json)
provides a better diagnostic prior than mixing the earlier censored denominators:
depth2 uses5,953 eligible seeds with correct-prefix buckets0/1/2 of
1,420/1,220/3,313 (mean1.31799); depth3 uses5,941 seeds with buckets0/1/2/3 of
1,417/1,216/918/2,390 (mean1.72059). These describe discarded diagnostic seed
probes, not realized rolling acceptance, useful work, or throughput. A rolling
scheduler can consume different proposal ages/branches and incur contention,
checkpoint and recovery costs. Preserve per-prompt distributions and raw trace
identity when using these statistics in a design model.
