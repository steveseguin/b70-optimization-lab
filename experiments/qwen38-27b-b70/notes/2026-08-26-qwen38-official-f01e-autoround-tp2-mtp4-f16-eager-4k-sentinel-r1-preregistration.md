# Current-f01e AutoRound TP2/MTP4 eager F16 exact-4K sentinel R1

State: **preregistered; not launched**.

This packet runs one exact-4K TP2/MTP4 eager/F16 sentinel. Its hard mechanism
parent is the completed current-f01e TP2/MTP3 scoped campaign. The parent's
terminal, arm, full quality, exact-4K depth, and exact-4K verification receipts
are individually hash-pinned. The parent passed all five authorized 4K-32K
depths, isolated positive acceptance, exact TP2/MTP0 parity, objective and
baseline quality, two-worker topology, rank-cache isolation, and cleanup. At
4K it drafted 123 tokens, accepted 86, and returned the frozen target hash
`3febb16e...`.

The sole target is the same-image, same-topology TP2/MTP0 exact-4K receipt
`6e32b0a0...`. Its terminal and quality baseline are also pinned. No MTP1,
MTP2, MTP3, TP1, or TP4 output can substitute for that target. The candidate
must return all 128 identical IDs, and the exact-depth helper must independently
prove active depth 4096 and `cached_tokens == 0`.

The only serving change from the scoped MTP3 parent is native embedded MTP depth
four: `qwen3_next_mtp` with four speculative tokens, resolving at startup to
method `mtp` and `num_spec_tokens=4`. Both speculative counters are
captured immediately before and after only the sentinel request. All values
must be finite and nondecreasing, and both deltas must be positive with
accepted no greater than drafted.

This is deliberately not a depth expansion. The same TP2/MTP4 profile already
has a hash-pinned exact-8K structural quarantine: it drafted 124 tokens,
accepted 97, passed exact/cache-zero, objective and baseline quality, topology,
model, rank-cache, and cleanup gates, but diverged from TP2/MTP0 at generated
token 99 (candidate 411, target 579). That 8K cell remains speedless and
quarantined regardless of this run. TP1/MTP4 and TP4/MTP4 also show
topology-local parity and 32K runtime risk. A 4K pass authorizes no 16K, 24K,
or 32K execution, inference, or publication.

Identity is fixed to the f01e/ac7509e2 image, exact AutoRound model revision,
TP2 on `ZE_AFFINITY_MASK=0,1`, eager graph-off execution, F16/auto KV,
memory utilization 0.60, one sequence, fresh port `19518`, and fresh ext4
output and rank-isolated cache roots. Full quality still requires seven exact
cases, eight deterministic repeats, the 8K long-context needle, every one of
16 usages cache-zero, and all same-topology TP2/MTP0 baseline comparisons.
Strict TP2 topology, direct model verification, cache isolation, and
process/container/port/render cleanup are fail-closed.

Execution additionally requires a clean local `main` equal to cached and live
`origin/main`. There is no speed floor and no automatic site publication,
depth expansion, descendant expansion, or descendant execution even on a pass.
Failures retain lower-grade evidence only. Protected decode values
`71.45427094575045`, `30.329809361830037`, `49.05894025767351`, and
`71.9001988117144` remain unchanged.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1.sh --check
```

Execution command (not run during packet preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-20260826-r1'
```
