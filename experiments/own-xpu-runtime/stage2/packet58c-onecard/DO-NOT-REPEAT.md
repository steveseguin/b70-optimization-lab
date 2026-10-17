# Packet58 decisions and cautions

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
