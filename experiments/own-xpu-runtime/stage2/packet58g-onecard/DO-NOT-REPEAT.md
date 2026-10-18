# Packet58g decisions and cautions

- 2026-10-18 / 58g: never pass one-card expert pointer tables to a direct packed
  weight submitter. Layer-2 IQ3_S is deliberately unfused; its p28 path needs
  explicit indirection. Cache setup alone is not a post-load gate. Run actual
  initialize/prepare_plan/prepare_commands with full production extents and
  distinct allocator address ranges. [Cause](evidence/fullshape-root-cause.json),
  [closeout](CPU-PREPARATION-CLOSEOUT.md).
- A proven no-compute refusal with completed drain and clean postflight releases
  its own lease; failure and drain are independent. Never release unknown/live
  owners or suppress a kernel fault to clear coordination.

# Packet58 decisions and cautions

- 2026-10-17 / 58f: a SYCL selector does not prove one-card DRM discovery.
  Filter the exact BDF before enumeration and retain strict FD monitoring.
  Never acquire a shared teardown record before prelaunch checks, or retain
  a clean completed K1 drain solely because CPU report validation failed.
  See [cause](evidence/mask-root-cause.json) and [closeout](CPU-PREPARATION-CLOSEOUT.md).

- 2026-10-17 / 58e: a supervisor peak before cache setup is not a complete
  after-load shadow measurement. Keep full census backing for cache, KV,
  weights and workspace; require the native after_load sample and live
  allocation census. Shared-host WS128x is exactness only. Keep the 8 GiB
  live stop, lane-A lease and whole-host WS128 hold-B protocol. See the
  [CPU closeout](CPU-PREPARATION-CLOSEOUT.md).

- Do not reopen CPU-computed expert misses: packet55 measured about 6 GB/s.
- Do not use warmed, small repeated host slabs to infer PCIe zero-copy speed.
  K1 uses distinct timed host regions and records their extent.
- Do not mutate the table or evict a slot while a position can read it.
- A partially failed fill cannot roll back to its previous table: victim bytes
  may already have changed. Drain safely or retain the owner for supervision.
- A copy event must remain tracked even if the compute dependency barrier fails.
- The route replay supports testing global LRU; its hit rates are not one-card
  plain-decode measurements. Actual cache logs are required.
- Between-position fill/publication waits currently add latency. There is no
  measured overlap claim and no per-layer host sync in the zero-copy path.
- MTP is not admitted. Target-only is the first milestone; extra draft memory
  needs a new host-shadow budget and its own exactness/speed windows.
- No 2-GPU threshold or external scope exception transfers to this 1-GPU lineage.

- 2026-10-17 / 58b: do not import `ze_command_queue_handle_t` into the
  installed UR Level Zero v2 adapter. Packet58 K1a returns unsupported (44)
  before fixture allocation. Use an in-order immediate command list on the
  same copy-only ordinal; do not diagnose this as a 48.6 GB host pin failure.
  See [CPU repair closeout](CPU-PREPARATION-CLOSEOUT.md). Device gate pending.

- 2026-10-17 / 58c: do not equate all GPUActive growth with device shadow when
  census-declared host USM is resident. Credit only completed exact bank sizes;
  retain combined host-budget and true-shadow checks. Do not claim an aligned
  time series from 58b's untimed progress and endpoint-only snapshots. See
  [CPU accounting closeout](CPU-PREPARATION-CLOSEOUT.md).

- 2026-10-17 / 58d: the complete weight load does not prove cache setup passes.
  Both cache-table-staging and cache-route-readback requested process lifetime
  under the transfer-only pinned-slab category. Keep the guard strict; use the
  real full post-load CPU setup gate before sealing or planning. See
  [allocation audit](ALLOCATION-AUDIT.md) and [closeout](CPU-PREPARATION-CLOSEOUT.md).
