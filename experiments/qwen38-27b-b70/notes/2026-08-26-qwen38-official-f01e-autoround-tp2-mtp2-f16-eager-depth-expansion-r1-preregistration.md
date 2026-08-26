# Current-f01e AutoRound TP2/MTP2 eager F16 depth expansion R1

State: **preregistered draft; not launched**.

This packet runs one TP2/MTP2 eager/F16 server across exact 2K, 4K, 8K,
16K, 24K, and 32K requests. Each depth is independently compared with the
completed same-topology TP2/MTP0 output at that depth. TP1 and TP4 are never
target oracles. The sole execution parent is the completed TP2/MTP1 campaign:
its terminal, arm, quality, all six exact-depth receipts, and all six acceptance
verification receipts are hash-pinned. It passed 6/6 exact depths, 6/6 positive
conserved MTP acceptance gates, 6/6 TP2/MTP0 parity gates, objective and baseline
quality, TP2 topology, rank-cache isolation, and cleanup. No fabricated sentinel
or cross-topology parent is accepted. TP2/MTP0 remains the target and quality
oracle because it is the same-topology target-only behavior.

The only mechanism change from the completed TP2/MTP1 parent is native embedded
MTP depth two: `qwen3_next_mtp`, two speculative tokens, resolved startup method
`mtp`. Both
speculative counters are snapshotted immediately before and after every exact
request. All values and deltas must be finite, cumulative counters cannot
decrease, drafted and accepted deltas must be positive, and accepted cannot
exceed drafted. Startup and quality traffic cannot satisfy a depth gate.

A per-depth result is valid only when exact-depth, 128-token MTP0 parity,
cache-zero, and acceptance all pass. If global runtime identity, topology,
full quality, cache isolation, and cleanup pass, valid depths are
classified independently even when another depth fails. All failures and raw
receipts remain retained.

Quality uses the completed TP2/MTP0 curve's quality receipt. `pass_all`,
`baseline_match_all`, seven exact cases, eight deterministic repeats, long
context, and explicit cache zero on all 16 usage records are mandatory.

Identity remains the official f01e image, exact AutoRound model revision, TP2
on `ZE_AFFINITY_MASK=0,1`, memory utilization 0.60, graph explicitly off,
F16/auto KV, one sequence, fresh port `19494`, and fresh ext4 output and
rank-isolated cache roots. Startup and
requests are bounded; EXIT/INT/TERM and all-render-node cleanup are strict.

There is no speed floor, protected route replacement, historical replacement,
automatic site publication, or automatic descendant execution.
Context zero remains explicitly missing because the frozen fixture has no
empty active-context case.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp2-f16-eager-depth-expansion-r1.sh --check
```

Execution command (not run during packet preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp2-f16-eager-depth-expansion-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp2-mtp2-f16-eager-depth-expansion-20260826-r1'
```
