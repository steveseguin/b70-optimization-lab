# Qwen3.8 AutoRound INT4 TP2 exact-depth + quality result

The zero-overlay b2dd9ce73d/1e90ffa672 TP2 lane passed all six authorized
nonzero exact active-context cells in one fresh two-GPU server lifetime:

| active context | decode tok/s | TTFT (s) |
|---:|---:|---:|
| 2,048 | 48.15370845841339 | 0.7827642589982133 |
| 4,096 | 47.92727674206827 | 1.5694107989984332 |
| 8,192 | 46.82727121519769 | 3.1865807970025344 |
| 16,384 | 45.19711668502676 | 6.610571697994601 |
| 24,576 | 43.70272435704981 | 10.265161956995144 |
| 32,768 | 42.33933781431878 | 14.104753812993295 |

Every request returned 128 completion tokens and 100 timestamped token events
(99 inter-token intervals), preserved the submitted prompt-token hash on the
returned prompt-token IDs, and reported zero cached tokens. The repeated exact
token-depth fixture makes these Grade C context-shape measurements; the full
natural-language quality battery is the separate correctness gate.

That quality battery passed 7/7 exact canaries, 8/8 deterministic repeats with
one output hash, the 8K needle, 24/24 comparisons to the matching TP2 baseline,
and 16/16 cache-zero observations. FULL_AND_PIECEWISE graph evidence passed
full-decode and piecewise capture checks. Both ranks 0 and 1 served, the runner
exited successfully, and post-run cleanup passed without leaving the two-card
server alive. The sealed packet's exact validator returned
`completed-valid-six-nonzero-exact-context-cells`, with all 16 checks true.

The exact model is `devan-carlin/Qwen3.8-27B-int4-AutoRound` revision
`bce40cacab0a4535b92fb3d57615c2bea9adf3d1`, treated as a quantized artifact
subset of the current Qwen3.8 27B weights. It ran vLLM
`b2dd9ce73dce2ad09007d1db5c171454118981d7` and XPU kernels
`1e90ffa672ba02f17a909da11838a4c55b199783` with no source or decision
overlay. The launch and persisted clean main commit was
`961619a9ad800c65fb8d341f2ab89d1c13e9afdc`; the remote did not move during
the stage.

Raw evidence is retained at
`/home/steve/qwen38-current-main-runs/tp2-exact-depth-b2dd9ce73d-20260826-r1/01-exact-depths`.
The stage receipt SHA-256 is
`584560e72acebe3213dea14ac44dc26099fcce36db31ce26417c5d19398e8db9`;
benchmark and quality SHA-256 values are respectively
`27ebe6b907d3fd9bd8a97295c22e954dafa244f243f542924b9c4aad9eee650f`
and `4f314cb9f62c05dccea627cbf1b1e96958e62764c5264a672b646980c96f32ca`.
The fresh compiled-cache manifest contains 2,277 entries and hashes to
`33464e3380b3204c56a788d990cbdf5b8b69ed89eec36b36a2a5ed6d89cc0915`.
The compact result is
[`../data/2026-08-26-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1-result.json`](../data/2026-08-26-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1-result.json).

Authority is deliberately narrow. Publish only these six TP2/MTP0/F16-KV/
FULL_AND_PIECEWISE HTTP cells with their Grade-C and quality disclosures. x0 is
missing: the exact harness correctly refused to substitute an ordinary prompt
for empty active context. The configured 32,896-token capacity is not a cell.
The TP2 identity parent remained preregistered and granted no runtime cell;
its historical comparison speeds do not fill context cells. Nothing here
authorizes another TP, MTP, KV, graph, quantization, prefill or concurrency
cell, a headline or protected-value replacement, or a LocalMaxxing submission.
