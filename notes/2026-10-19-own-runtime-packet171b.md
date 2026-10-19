# Packet171b: one-card compute-queue foreground copies, READY (CPU only)

This is the kill test for packet171 AUDIT row 1, built to its `BUILD-BRIEF.md`. It is CPU preparation only: nothing was queued or launched, and no GPU, service or setting was touched.

- **Packet:** `experiments/own-xpu-runtime/stage2/packet171b-onecard-cqcopy/`
- **Proposal:** `experiments/own-xpu-runtime/ops/lane-queue/proposed-p171b-v5-A.txt`, job `packet171b-v5-A`. It is not in any live queue.
- **Parent:** packet58as at commit `dabfc958` (packet58asd), taken with `git archive`. The working tree was not used.

## Change

- `native/cq_copy.hpp` adds a per-view thread-local `p171::compute_queue_copies`. It is switched with `p58as::spin_enabled` at the drained view boundary.
- In B views, `copy()` and `prepare_copy()` issue an in-order `queue_->memcpy` and record a compute tail, with no barrier.
- `foreground_sync` waits on the BCS foreground list only if that list owns work issued in the view.
- These stay unchanged: fills (second BCS list), publication, kernels, arithmetic, selection, cache policy, spin and lookups.
- The 1 ms barrier-recovery path is kept for copy-queue mode only.
- The exact delta is `apply_cqcopy_delta.py`, with its diff in `native-delta.patch`.

## Bracket

- Arm order is A0/B0/A1/B1/A2 = spin / spin-cq / spin / spin-cq / spin.
- 12 × 128-token requests per view.
- **Gate:** both B views ≥ +0.5% over every warm A, drift ≤ 3%, and 60/60 exact vs `iq3-p49-split32-v1`.
- `summary.json` → `mechanism_readout` records readback bimodality, P(slow | after a fill token) and the slow-token wait excess on every outcome.

## CPU gates (all pass)

| Gate | Result |
| --- | --- |
| Ordering test | The mock-queue test instantiates the same templates as `SyclDevice`. GNU and Intel builds pass. The `P171_PARENT_ROUTING` builds fail on: BCS foreground copy, barrier, idle-list wait and readback order. Device source = parent + delta. `fill()` is byte-identical. |
| Byte gates | GNU and Intel: 120 request resets and 10 view resets, byte-equal to packet58aj. The oracle refusal holds. The parent poll/spin order is refused. |
| Build | One `compile_turn` |
| Flags | Every native flag is listed in `--help` |
| Preparation | Device-define CPU preparation: 60 requests, 5 views |
| Imports | Entry imports pass under the closed launch environment |
| Analyzer | Run on real packet58as, 58aj and 58aq evidence: 192 exact requests. The mechanism readout reproduces packet171 `measured.json`; for example, B0 has a slow-readback fraction of 0.4042 and P(slow after fill) = 0.9404. |
| Queue | Temporary `lanequeue plan` passes |
| Shared tool | `rehearse_entry --report` passes. It warns that it has no shared preparation adapter for an unranked one-card argv; this is documented in READY. |
| Pin guard | Passes |

## Next (superseded: see `2026-10-19-own-runtime-packet171b-result.md`, row 1 CLOSED)

The coordinator runs `packet171b-v5-A` on lane A as a whole-host job, with a fresh fault review.

- If B wins and the slow mode collapses, the hypothesis is confirmed. Port the change into the spin record line.
- If B is neutral and the slow mode persists, close row 1. Attribute the 2.6 ms readback to fill/PCIe contention.
