# Current f01e AutoRound TP2 PIECEWISE/F16 MTP1 exact-4K sentinel R1

The preregistered two-card native-MTP1 PIECEWISE/F16 sentinel passed. On the
pinned official `f01e24f6…` image (`ac7509e2b`, vLLM `0.27.2rc1.dev77`), the
TP2 server measured **13.743731651970505 conventional decode tok/s** at exact
4K, with **2651.291036992916 ms TTFT**. The distinct historical 100-event
field was 13.882557224212631 tok/s and is not the candidate publication value.

The isolated exact request drafted 71 tokens and accepted 56
(`0.7887323943661971`). Every exact-depth gate passed with 4,096 prompt tokens,
128 returned token IDs, and zero cached tokens. The candidate exactly matched
both pinned same-image parents—the TP2/MTP0 PIECEWISE/F16 target and the
TP2/MTP1 eager/F16 mechanism parent—across all 128 tokens (hash `3febb16e…`).

The full objective and eager-MTP1 baseline battery passed: 7/7 exact cases,
deterministic 8/8 repeats with one hash, the long-context needle, 24/24
baseline comparisons, and cache zero on all 16 quality requests. PIECEWISE
size-one capture, both TP2 worker ranks, the two isolated rank-cache
namespaces, embedded native-MTP1 binding, all 19 model files, and strict
terminal cleanup also passed.

This packet records exactly one measured Grade C candidate cell pending a
separate publication decision: current `f01e/ac7509e2`, AutoRound INT4,
TP2/MTP1/PIECEWISE/F16, exact 4K. It does not edit the family contract or
website. `x=0`, 2K, 8K, 16K, 24K, and 32K remain missing for this tuple. The
quality-only 8K needle is not an exact-8K performance cell. Every other graph
mode, TP, MTP dose, KV mode, runtime image, and artifact remains outside this
packet. No interpolation or extrapolation is used.

The raw runner correctly recorded automatic publication, descendant expansion,
descendant execution, and historical replacement as false. No headline,
historical result, protected profile, LocalMaxxing row, or existing eager/graph
profile is replaced. Protected decode values `71.45427094575045`,
`30.329809361830037`, `49.05894025767351`, and `71.9001988117144` remain
unchanged.

Compact evidence is in
`experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp1-f16-piecewise-4k-sentinel-r1-result.json`;
raw receipts remain at
`/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp1-f16-piecewise-4k-sentinel-20260826-r1`.
