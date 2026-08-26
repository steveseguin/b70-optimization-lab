# Current-f01e AutoRound TP2/MTP3 eager F16 scoped depth expansion R1

State: **preregistered draft; not launched**.

This packet runs one TP2/MTP3 eager/F16 server across exact 4K, 8K, 16K,
24K, and 32K requests. Exact 2K is deliberately excluded: the completed
TP2/MTP2 parent generated 128 tokens and positive conserved acceptance there,
but diverged from the same-topology TP2/MTP0 target at output token 90
(one-based; candidate 59178, target 16539). The parent 2K depth, verification,
candidate-ID, target-ID, and first-divergence evidence are hash-pinned so the
exclusion cannot be silently removed or reinterpreted.

The five included depths are the exact independently valid TP2/MTP2 subset.
The parent terminal and arm are pinned to the globally clean
`partial-depth-expansion` result with frozen oracles
`[4096,8192,16384,24576,32768]`, failed/quarantined `[2048]`, objective and
baseline quality, TP2 topology, rank-cache isolation, and cleanup all passing.
Its quality receipt and every parent depth and verification receipt—including
2K exclusion evidence—are pinned. The same-topology TP2/MTP0 terminal, quality,
tracked result, and six target receipts are also pinned; 2K is retained there
only to bind the exclusion evidence, not as an execution depth.

The only runtime mechanism change from those five parent oracles is native
embedded MTP depth three: `qwen3_next_mtp`, three speculative tokens, resolved
startup method `mtp`. Both speculative counters are snapshotted immediately
before and after every included exact request. All values and deltas must be
finite, cumulative counters cannot decrease, drafted and accepted deltas must
be positive, and accepted cannot exceed drafted. Startup and quality traffic
cannot satisfy a depth gate.

Each included result is valid only when exact depth, 128-token TP2/MTP0 parity,
cache zero, and acceptance all pass. Full objective and target-baseline quality
(seven exact cases, eight deterministic repeats, long-context needle, and all
16 usage rows cache-zero), TP2 worker topology, rank-isolated cache evidence,
and strict cleanup are global gates. A partial result retains each independently
valid included depth without authorizing an automatic descendant.

Identity remains the official f01e image, exact AutoRound model revision, TP2
on `ZE_AFFINITY_MASK=0,1`, memory utilization 0.60, graph explicitly off,
F16/auto KV, one sequence, fresh port `19495`, and fresh ext4 output and
rank-isolated cache roots. Context zero remains missing because the frozen
fixture has no empty active-context case.

There is no speed floor, protected-route replacement, historical replacement,
automatic site publication, or automatic descendant execution. The protected
decode values remain untouched.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-r1.sh --check
```
Execution command (not run during packet preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-20260826-r1'
```
