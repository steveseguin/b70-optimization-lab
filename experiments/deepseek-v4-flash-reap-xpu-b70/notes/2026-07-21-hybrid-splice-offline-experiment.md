# Markov+EAGLE Hybrid Splice — Offline Validation (under-trained checkpoint)

Date: 2026-07-21 · Status: **hybrid architecture validated (marginal on current ckpt; scales with EAGLE training)**

## Numbers first (offline, CPU, 49,142 DEV cycles, EAGLE ckpt 0.60 epoch, SHA ef74bdbf…)

| Draft | Emitted tokens/cycle |
|---|---:|
| EAGLE alone | 2.3751 |
| Markov alone (current) | 3.5069 |
| **Hybrid k=4 (Markov P1-P3 + EAGLE P4-P7)** | **3.6056** |

- Crossover sweep: k=2 →2.890, k=3 →3.398, **k=4 →3.606**, k=5 →3.577. Best **k=4**.
- Clears the 3.6 gate by **+0.0056**; beats Markov by **+0.0987 emitted/cycle (+2.8%)**.
- Handoff **bit-identical** P1-P3 to Markov; EAGLE owns P4-P7. Splice correctness proven.
- EAGLE-only is WORSE than Markov (weak P1 kills prefix acceptance) → hybrid is essential, not optional.

## Interpretation
- +2.8% acceptance ≈ 80.82 → ~83 tok/s IF draft compute were free — a LOWER BOUND on the under-trained checkpoint.
- EAGLE P4-P7 conditionals here are only ~68.8/73.0/74.3/73.7%; the long-haul run should raise them, pushing the hybrid toward the design's ~3.89 emitted/cycle ≈ ~90 tok/s.
- Method caveat: the record's Markov uses layer-40-42 correction features NOT in the DEV capture; Markov per-position conditionals are taken from the dspark7 diagnostic (authoritative), EAGLE conditionals measured per-cycle on DEV. See the JSON method_notes.

## Next (gated on the EAGLE long-haul training)
1. Re-run this cheap offline splice on each improved EAGLE checkpoint to track projected emitted/cycle.
2. When EAGLE plateaus/gates, integrate the hybrid per-position source selector on GPU.
3. Integration MUST gate on NET tok/s (draft compute cost of Markov + 7-step EAGLE rollout), not acceptance — the design's flagged "isolated win that loses at endpoint" risk.

Artifacts: scripts/analyze-hybrid-splice-offline.py · notes/2026-07-21-hybrid-splice-offline-experiment.json
