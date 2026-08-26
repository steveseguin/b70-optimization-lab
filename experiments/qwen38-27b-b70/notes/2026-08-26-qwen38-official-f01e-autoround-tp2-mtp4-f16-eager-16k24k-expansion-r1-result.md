# TP2/MTP4 eager F16 exact 16K+24K expansion result

The preregistered current-f01e AutoRound TP2/MTP4 expansion passed at both
authorized depths.

- 16K: `18.455933818605118` conventional decode tok/s,
  `10486.21621998609` ms TTFT, and 89 accepted / 160 drafted tokens.
- 24K: `23.358856068128627` conventional decode tok/s,
  `12711.349529010477` ms TTFT, and 93 accepted / 144 drafted tokens.

Both exact requests returned 128 tokens with cache zero. Their output hashes
exactly match the frozen same-image, same-topology TP2/MTP0 targets:
`dbfad627...` at 16K and `f4dfe5a8...` at 24K. Each speculative-counter delta
was isolated, finite, positive, nondecreasing, and conserved.

The complete objective and same-topology baseline quality battery passed:
seven exact cases, eight deterministic repeats with one hash, the long-context
needle, 24 comparisons, and cache zero on all 16 requests. Both TP2 workers,
model verification, rank-cache isolation, cleanup, and terminal return code
also passed.

This is an evidence packet, not a publication decision. It selects only exact
16K and 24K raw evidence and grants zero site cells. It infers no x0, 2K, 4K,
8K, 32K, other topology, MTP depth, graph mode, or KV type. The existing 8K
token-99 quarantine and every protected result remain unchanged. There is no
automatic descendant expansion or LocalMaxxing authority.

Raw root: `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-20260826-r1`

Compact result: `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-r1-result.json`
