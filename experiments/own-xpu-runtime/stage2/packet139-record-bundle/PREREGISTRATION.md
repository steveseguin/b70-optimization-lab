# Packet139 bundle9 — review26, before device data

The only local selection is packet136 bundle8 (packet124c plus packet131b
banked rollback) plus packet137 `token_input=both`. All other choices, the
80,128-row non-benchmark draft prefix, BF16 KV and iq3-p49-split32-v1 stay fixed.
The complete 248,320-row projection table is an exact token-input transform;
it is not prompt, KV or response reuse. The target still verifies each token.

Chain readiness requires exactly these device gates:

1. Packet137 lane-B v5 one-load original/both/original/both/original bracket.
   Both candidate views must beat every control by at least 0.5%; control
   max/min drift must be at most 1%; all twelve 128-token prompts and the
   incident64 check must be exact. Per-prompt draft proposals and acceptance
   counts must match. Recompute rates from timestamps, not stored verdicts.
2. Packet139 lane-A composed smoke: all twelve prompts, 64 tokens each, every
   token checked against the unchanged oracle, followed by confirmed drain.
3. The fresh `build/device-cards01-a` chain; no second-lane timing grid.

These gates are fixed before any packet139 device run. Missing, changed,
malformed or failed evidence refuses readiness. CPU preparation is not device
quality or speed evidence. Existing bundle8 output is never overwritten.

Submission preparation pins the current record ledger at prepare time. If
bundle8 has posted a new record, that record is superseded; otherwise the
current last record remains the floor. No hard-coded record ID is used.
The retained owner-authorized 128-token scope has
`realistic_final_gate.passed=false`; it is not a strict512 claim.
