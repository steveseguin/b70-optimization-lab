# Current-f01e AutoRound TP4/MTP1 eager F16 depth expansion R1

State: **preregistered draft; not launched**.

This packet runs one TP4/MTP1 eager/F16 server across exact 2K, 4K, 8K,
16K, 24K, and 32K requests. Each depth is independently compared with the
completed same-topology TP4/MTP0 output at that depth. TP1 is never an oracle.
The passed TP4/MTP1 8K sentinel is separately pinned as the hard parent.

The only mechanism change from the TP4/MTP0 curve is native embedded MTP1:
`qwen3_next_mtp`, one speculative token, resolved startup method `mtp`. Both
speculative counters are snapshotted immediately before and after every exact
request. All values and deltas must be finite, cumulative counters cannot
decrease, drafted and accepted deltas must be positive, and accepted cannot
exceed drafted. Startup and quality traffic cannot satisfy a depth gate.

A per-depth result is valid only when exact-depth, 128-token MTP0 parity,
cache-zero, and acceptance all pass. If global runtime identity, topology,
parent 8K, full quality, cache isolation, and cleanup pass, valid depths are
classified independently even when another depth fails. All failures and raw
receipts remain retained.

Quality uses the completed TP4/MTP0 curve's quality receipt. `pass_all`,
`baseline_match_all`, seven exact cases, eight deterministic repeats, long
context, and explicit cache zero on all 16 usage records are mandatory.

Identity remains the official f01e image, exact AutoRound model revision, TP4
on `ZE_AFFINITY_MASK=0,1,2,3`, memory utilization 0.60, graph explicitly off,
F16/auto KV, one sequence, and a fresh ext4 rank-isolated cache. Startup and
requests are bounded; EXIT/INT/TERM and all-render-node cleanup are strict.

There is no speed floor, protected route replacement, historical replacement,
automatic site publication, or automatic descendant execution.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-depth-expansion-r1.sh --check
```

Execution command (not run during packet preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-depth-expansion-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-depth-expansion-20260826-r1'
```
