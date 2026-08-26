# Current-f01e AutoRound TP2/MTP4 eager F16 exact-8K sentinel R1

State: **preregistered; not launched**.

This packet runs one exact-8K TP2/MTP4 eager/F16 sentinel. The hard mechanism
parent is the completed current-f01e TP2/MTP3 scoped campaign, not a different
topology: its terminal, arm, full quality, 8K depth, and 8K verification
receipts are individually hash-pinned. That parent passed all five authorized
4K-32K depths, isolated positive acceptance, exact TP2/MTP0 parity, objective
and baseline quality, two-worker topology, rank-cache isolation, and cleanup.
At 8K it drafted 114 tokens, accepted 89, and returned the frozen target hash
`34e792cc...`.

The sole target is the same-image, same-topology TP2/MTP0 exact-8K receipt
`55bc2ad9...`. Its terminal and quality baseline are also pinned. No MTP1,
MTP2, MTP3, TP1, or TP4 output can substitute for that target. The candidate
must return all 128 identical IDs, and the exact-depth helper must independently
prove active depth 8192 and `cached_tokens == 0`.

The only serving change from the scoped parent is native embedded MTP depth
four: `qwen3_next_mtp` with four speculative tokens, resolving at startup to
method `mtp` and `num_spec_tokens=4`. Both speculative counters are captured
immediately before and after only the sentinel request. All values must be
finite and nondecreasing, and both deltas must be positive with accepted no
greater than drafted.

This is deliberately a sentinel rather than a depth expansion. Current-f01e
TP1/MTP4 has conflicting cross-boot evidence: its 8K parent passed, its later
8K expansion diverged from MTP0 first at token 99, and its exact-32K request
killed EngineCore on the speculative-token shape assertion. Current-f01e
TP4/MTP4 also accepted strongly and passed objective/baseline quality at 8K,
but diverged from TP4/MTP0 first at token 99 and remains structurally
quarantined. Those are topology-local findings, not proof TP2 fails; together
they make one bounded TP2 8K test the responsible next measurement.

Identity is fixed to the f01e/ac7509e2 image, exact AutoRound model revision,
TP2 on `ZE_AFFINITY_MASK=0,1`, eager graph-off execution, F16/auto KV,
memory utilization 0.60, one sequence, fresh port `19497`, and fresh ext4
output and rank-isolated cache roots. Full quality requires seven exact cases,
eight deterministic repeats, the long-context needle, every one of 16 usages
cache-zero, and all TP2/MTP0 baseline comparisons. Strict TP2 topology,
cache isolation, and process/container/port/render cleanup are fail-closed.

There is no speed floor and no automatic site publication, depth expansion,
or descendant execution even on a pass. Failures retain lower-grade evidence
only. The protected decode values `71.45427094575045`,
`30.329809361830037`, `49.05894025767351`, and `71.9001988117144` remain
unchanged.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-8k-sentinel-r1.sh --check
```

Execution command (not run during packet preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-8k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-8k-sentinel-20260826-r1'
```
