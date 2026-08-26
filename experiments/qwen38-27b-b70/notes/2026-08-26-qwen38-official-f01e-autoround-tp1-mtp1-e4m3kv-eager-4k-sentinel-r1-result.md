# Current f01e AutoRound TP1 eager/E4M3 MTP1 exact-4K sentinel R1

The preregistered one-card native-MTP1 eager/E4M3 sentinel passed. On the
pinned official `f01e24f6…` image (`ac7509e2b`, vLLM `0.27.2rc1.dev77`), the
TP1 server measured **8.378608393519674 conventional decode tok/s** at exact
4K, with **3843.1851619970985 ms TTFT**. The distinct historical 100-event
field was 8.463240801535022 tok/s and is not the candidate publication value.

The isolated exact request drafted 66 tokens and accepted 62
(`0.9393939393939394`). Every exact-depth gate passed with 4,096 prompt tokens,
128 returned token IDs, and zero cached tokens. The candidate exactly matched
the frozen same-image TP1/MTP0/eager/E4M3 target across all 128 tokens (hash
`a3d7ad63…`), with no divergence.

The full objective and baseline battery passed: 7/7 exact cases,
deterministic 8/8 repeats with one hash, the long-context needle, 24/24
baseline comparisons, and cache zero on all 16 quality requests. Eager mode,
TP1 topology, embedded native-MTP1 binding, all 19 model files, the dedicated
cache, and strict terminal cleanup also passed.

This packet records exactly one measured Grade C candidate cell pending a
separate publication decision: current `f01e/ac7509e2`, AutoRound INT4,
TP1/MTP1/eager/E4M3, exact 4K. It does not edit the family contract or website.
`x=0`, 2K, 8K, 16K, 24K, and 32K remain missing for this tuple. Every other
graph mode, TP, MTP dose, KV mode, runtime image, and artifact remains outside
its authority. No interpolation or extrapolation is used.

The raw runner correctly recorded automatic publication, descendant expansion,
descendant execution, and historical replacement as false. No headline,
historical result, protected profile, LocalMaxxing row, or existing eager/graph
profile is replaced. Protected decode values `71.45427094575045`,
`30.329809361830037`, `49.05894025767351`, and `71.9001988117144` remain
unchanged.

Compact evidence is in
`experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-r1-result.json`;
raw receipts remain at
`/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-20260826-r1`.
