# Build brief: one-card foreground copies on the in-order compute queue (one-load kill test)

This is the top item from `AUDIT.md`, row 1. It is a brief only. It has no packet tree, READY file or queue row.

## Why

Bundle 8 issues every foreground copy as `queue_->memcpy` on its single in-order compute queue (`packet136-record-bundle/single_device.cpp:83-84,101`). The one-card spin line does it differently, at `packet58as` HEAD:

- foreground copies go on a dedicated BCS immediate list, with a compute-queue barrier per copy (`native/generated/single_device.cpp:108-113`);
- retirement waits on both queues (`:187-188`);
- maintenance fills use a second BCS immediate list on the same copy ordinal (`:88,169-175`).

**Measured on packet58as spin views B0/B1** (`measured.json`):
- The 8-byte error/next-token readback takes 0.20 ms on 59.5% of tokens and **2.63 ms on 40.5%**.
- A slow readback follows a fill-submission token (72.9 MB of fills) with **P = 0.94**.
- Mean excess: **0.99 ms/token** in readback, plus **0.95 ms/token** of extra wait on those tokens.
- The ceiling is about 1.0–1.9 ms/token, **+3.5–7%**.

**Assumed, and what this test decides:** the delay is the foreground copy queueing behind fills on the shared copy ordinal. A DMA backlog on that ordinal is one candidate; PCIe contention from zero-copy misses, which this change would not fix, is another.

## Change (reimplementation, not a file copy)

- Start from a private copy of packet58as **HEAD** (`git archive`, never the working tree). Its working tree is being edited for `--wait-policy`.
- Add a per-view thread-local `p171::compute_queue_copies`, switched only at an already drained view boundary, in the same pattern as `p58as::spin_enabled`.
- When it is set:
  - `copy()` and `prepare_copy()` issue `queue_->memcpy(dst,src,n,deps)` on the in-order compute queue and record the event as a foreground **compute** tail, with no barrier;
  - `foreground_sync` waits on the compute queue, and on the copy queue only if that queue owns work issued earlier in the view.
- Maintenance fills, publication, kernels, arithmetic, selection, cache policy, spin policy and resident lookups stay byte-identical.
- The pinned-source lifetime is still proven by the owned event and the existing drains.
- Keep the 1 ms barrier-failure recovery path for the copy-queue mode only.

## Gates (all required before READY)

1. **CPU ordering test that fails on the old code.** A mock backend records the queue of every foreground copy. In B mode it must find no BCS foreground copy, no barrier, and a readback ordered after the compute tail. It must also confirm that fills still reach the maintenance list.
2. GNU and Intel byte gates; one `ops/compile_turn.py` turn; flags checked against `--help`.
3. Imports on the device path under the real launch environment.
4. CPU real-arm-sequence gate. Run the analyzer on the real packet58as/58aq evidence.
5. `lanequeue plan` on a temp copy and `ops/rehearse_entry.py --report`, or a private adapter with the failed receipt kept.
6. Per-op waits of 600 s. No wall-clock data proofs. Device floor 25 GB, CPU stop 27 GB. Native readers under `ionice -c3`.
7. Pin-guard: no `pins`/`files`/`gates`/`artifacts`/`sources` maps of non-hashes. Parent digests only as `{name, parent_relpath, parent_digest}`.

## Device contract

- **Bracket:** lane A, whole host, one load. K1a/K1b, then v5 A0/B0/A1/B1/A2, with 12 × 128-token requests per view.
- **Arms:** A = packet58as spin parent (copy-queue foreground); B = spin plus compute-queue foreground copies. A0 is a warm-up kept for exactness. **There is no separate smoke:** K1a/K1b and the exact A0 open the bracket.
- **Gate:** both B views must beat every warm A by at least 0.5%, warm drift must be at most 3%, and all 60 responses must be exact vs `iq3-p49-split32-v1`.
- **Mechanism readout, kept even on a loss:** per-view readback bimodality, the slow-after-fill probability and the slow-token wait excess.
  - If B wins and the slow mode collapses, the hypothesis is confirmed.
  - If B is neutral and the slow mode persists, close this row and attribute the 2.6 ms to fill/PCIe contention.
