# Packet171b: one-card foreground copies on the in-order compute queue

## Result (device, 2026-10-19 10:07–10:21 UTC): CLOSED, neutral

| View | A0 (warm-up) | B0 | A1 | B1 | A2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| tok/s | 34.548 | 34.740 | 34.563 | 34.761 | 34.602 |
| slow readback fraction | 0.4016 | 0.4029 | 0.4009 | 0.4035 | 0.4042 |
| P(slow readback after a fill token) | 0.92 | 0.95 | 0.93 | 0.96 | 0.94 |
| slow-token wait excess (ms) | 2.32 | 2.34 | 2.38 | 2.33 | 2.29 |

- The bracket was 60/60 exact, with warm drift 0.11%.
- The minimum gain was +0.40%, below the +0.5% gate, so `candidate_beats_all_controls` is false.
- Under the pre-registered rule, B is neutral and the slow mode persists, so AUDIT row 1 is closed.
- The ~2.6 ms slow readback comes from fill-traffic contention, not from foreground-copy queue ordering.
- The compact record is `evidence/v5-result.json`. The full summary is `screen/evidence/card0-171b-v5-a/resident/WSCREEN/summary.json`. Raw streams are host-local and untracked.

`READY-FOR-DEVICE.json` was picked up at 10:07 UTC. A follow-up edit then removed it, along with three native sources that were already sealed, while the bracket was starting. Those sources were restored byte-identically to the sealed digests during the run. The binary was never rebuilt. READY was restored after the run from a deterministic re-run of `finalize.py`: the same inputs, `preparation_head_commit` 737330c3, and no seal or HEAD lookup.

CPU preparation only. No GPU, service, setting or live queue was touched. This is
the kill test for row 1 of `../packet171-onecard-host-parity/AUDIT.md`, built to
`../packet171-onecard-host-parity/BUILD-BRIEF.md`.

## Parent and change

- **Parent:** a private copy of packet58as at commit
  `dabfc958b7d3322dda3eeada3689b4d6011b7cc1` (`git archive`, never the working
  tree). It is the spin line: bounded 250 µs spin, then 20 µs sleeps. The copy
  rewrites only absolute paths. The packet58asd chain tooling is carried along
  inert; the bracket uses the bracket-era seal.
- **Change:** `native/cq_copy.hpp` adds a per-view thread-local
  `p171::compute_queue_copies`. It is switched with `p58as::spin_enabled` at
  the already drained view boundary. When it is set:
  - `SyclDevice::copy()` and `prepare_copy()` issue `queue_->memcpy(dst,src,n,deps)`
    on the in-order compute queue and record the event as a compute tail, with
    no barrier;
  - `foreground_sync()` waits on the compute queue, and on the BCS foreground
    list only if that list owns work issued earlier in the view.
- **Unchanged:** maintenance fills (second BCS list), publication, kernels,
  arithmetic, selection, cache policy, spin policy and resident lookups. The
  1 ms barrier-failure recovery path stays, for copy-queue mode only. The owned
  event and the existing drains still prove the pinned-source lifetime.
- `apply_cqcopy_delta.py` is the exact source delta (counted replacements);
  `native-delta.patch` is its diff against the parent.

## Device contract (proposal only; not queued)

- Lane A, whole host, one load: K1a/K1b, then v5 A0/B0/A1/B1/A2, with 12 × 128-token requests per view.
- A = packet58as spin parent (copy-queue foreground copies). B = spin plus compute-queue foreground copies.
- A0 is an exact warm-up. There is no separate smoke.
- **Gate:** both B views beat every warm A by ≥ 0.5%, warm drift ≤ 3%, and all
  60 responses are exact vs `iq3-p49-split32-v1`.
- **Mechanism readout, kept on every outcome:** `summary.json` →
  `mechanism_readout` gives per-view readback bimodality, the slow-after-fill
  probability and the slow-token wait excess (packet171 definitions).
  - B wins and the slow mode collapses: the hypothesis is confirmed.
  - B is neutral and the slow mode persists: close row 1 and attribute the 2.6 ms to fill/PCIe contention.
- Proposal: `../../ops/lane-queue/proposed-p171b-v5-A.txt` (job `packet171b-v5-A`).

## CPU gates

| Gate | Evidence |
| --- | --- |
| Ordering test that fails on the old routing: GNU and Intel builds of the mock-queue test pass; the `P171_PARENT_ROUTING` builds fail. The device source equals parent + delta, and `fill()` is byte-identical. | `evidence/cqcopy-order.json` |
| GNU/Intel byte gates: 120 request resets and 10 view resets byte-equal to packet58aj; the old poll/spin bracket order is refused. | `evidence/cpu-exactness.json` |
| One `ops/compile_turn.py` turn | `evidence/build.json` |
| Every native flag checked against `--help` | `evidence/flags.json` |
| Real device-define CPU transport: 5 view resets, 60 request resets | `evidence/preparation.json` |
| Device-path imports under the real launch environment | `evidence/entry-imports.json` |
| Real-arm-sequence analyzer on packet58as, 58aj and 58aq evidence; the mechanism readout reproduces packet171 `measured.json` | `evidence/analyzer-real-parent.json` |
| Temporary `lanequeue plan` and `rehearse_entry --report` | `evidence/queue-plans.json`, `evidence/shared-entry-report-final.json` |
| Pin guard | `evidence/pin-guard.json` |

Limits: per-operation waits are 600 s, with no wall-clock data proofs. Device
floor 25 GB, CPU stop 27 GB. Native readers run under `ionice -c3`.

The packet58as v5 streams in `lineage/device-evidence/packet58as` are host-local
(untracked, like the parent's own run streams) byte-identical snapshots of the parent's real bracket. Their digests are listed
as `{name, parent_relpath, parent_digest}` records in
`lineage/packet58as-v5-snapshot.json`. They are not packet171b measurements.
