# Current f01e AutoRound TP1 PIECEWISE/F16 MTP1 exact-4K sentinel R1

The preregistered one-card native-MTP1 PIECEWISE sentinel passed. On the pinned
official `f01e24f6…` image (`ac7509e2b`, vLLM `0.27.2rc1.dev77`), one TP1
server with F16 KV measured **8.685875123241662 conventional decode tok/s** at
exact 4K, with **2962.142157004564 ms TTFT**. The distinct historical
100-event field was 8.773611235597638 tok/s and is not the published value.

The isolated exact request drafted 71 tokens and accepted 56
(`0.7887323943661971`). Every exact-depth gate passed with 4,096 prompt tokens,
128 returned token IDs, and zero cached tokens. The candidate exactly matched
both frozen same-image clean parents—TP1/MTP0 eager/F16 and
TP1/MTP0 PIECEWISE/F16—across all 128 tokens (hash `3febb16e…`).

The full objective and PIECEWISE-MTP0 baseline battery passed: 7/7 exact cases,
deterministic 8/8 repeats with one hash, the long-context needle, 24/24
baseline comparisons, and cache zero on all 16 quality requests. PIECEWISE
size-one capture, TP1 topology, the embedded native-MTP1 binding, all 19 model
files, the fresh isolated cache, and terminal cleanup also passed.

Human adjudication publishes exactly one additive Grade C cell:
current `f01e/ac7509e2`, AutoRound INT4, TP1/MTP1/PIECEWISE/F16, exact 4K.
`x=0`, 2K, 8K, 16K, 24K, and 32K remain missing for this tuple. Every other
graph mode, TP, MTP dose, KV mode, runtime image, and artifact remains outside
this result. No interpolation or extrapolation is used.

The graph corruption caveat remains mandatory. In the same current-f01e MTP0
parent campaign, PIECEWISE 8K produced the `dd31856f…` alternate and diverged
from eager at generated token 99 (411 versus 579). This 4K pass does not clear
8K, long context, or graph-plus-MTP descendants.

The raw runner correctly recorded automatic publication and descendant
expansion as false. This note and compact result are the explicit human
one-cell adjudication; they do not rewrite the immutable raw receipt. Protected
values `71.45427094575045`, `30.329809361830037`, `49.05894025767351`, and
`71.9001988117144` remain unchanged. No headline, historical result,
LocalMaxxing row, or existing eager/graph profile is replaced.

Compact evidence is in
`experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-f16-piecewise-4k-sentinel-r1-result.json`;
raw receipts remain at
`/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp1-f16-piecewise-4k-sentinel-20260826-r1`.
