# Persistent meta parallel submission: exact regression

Date: 2026-08-13

Decision: **reject**. Keeping one OpenMP team alive across all meta subgraphs
preserved canonical output but was slower in all three classes.

Source implementation: `/home/steve/src/llama.cpp-muse-100` commit
`41c93b612` (`meta: add persistent parallel submission experiment`). It is
default-off behind `GGML_META_PERSISTENT_PARALLEL_SUBMIT=1` and requires the
retained `GGML_META_PARALLEL_SUBMIT=1`.

Config:
`experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-persistent-meta-submit-full-cac.json`

Raw JSONL:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-persistent-meta-submit-full-cac-20260813.jsonl`

SHA-256:
`3f0e5101c12b3046e1c216d6f659602966ef90e8fd6a78104a2bbb1c1a839315`.

All arms emitted the canonical hashes. One first-control code request crossed a
proposal boundary (781 drafted / 199 accepted versus 811 / 197); the text hash
remained canonical. Analysis therefore uses each arm's actual verifier-round
count.

Drift-interpolated candidate deltas:

- prose: `+0.097150 ms/round`;
- code: `+0.092371 ms/round`;
- JSON: `+0.084150 ms/round`.

The persistent team removes OpenMP region creation, but every subgraph still
requires the same submit barrier, master-thread collective, and next-iteration
barrier. The extra persistent-region synchronization costs more than it saves
on this stack. Leave the flag disabled and do not use it as the missing DDTree
margin.
