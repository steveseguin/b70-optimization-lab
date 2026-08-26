# Qwen3.8 AutoRound INT4 TP4 exact-depth + quality result

The zero-overlay b2dd9ce73d/1e90ffa672 TP4 lane passed all six authorized
nonzero exact active-context cells in one fresh four-GPU server lifetime:

| active context | decode tok/s | TTFT (s) |
|---:|---:|---:|
| 2,048 | 71.16806401683698 | 0.5474729180059512 |
| 4,096 | 70.15283483831283 | 1.1045590020003146 |
| 8,192 | 69.8695629973191 | 2.210061638004845 |
| 16,384 | 69.06861442980266 | 4.56175836300099 |
| 24,576 | 67.87242695878132 | 7.011821513995528 |
| 32,768 | 66.64506545273888 | 9.568525565002346 |

Every request returned 128 completion tokens and 100 timestamped token events
(99 inter-token intervals), preserved the submitted prompt-token hash on the
returned prompt-token IDs, and reported zero cached tokens. The repeated exact
token-depth fixture makes these Grade C context-shape measurements; the full
natural-language quality battery is the separate correctness gate.

That quality battery passed 7/7 exact canaries, 8/8 deterministic repeats with
one output hash, the 8K needle, 24/24 comparisons to the qualified matching TP4
baseline, and 16/16 cache-zero observations. FULL_AND_PIECEWISE graph evidence
passed full-decode and piecewise capture checks. All ranks 0--3 served, the
runner exited successfully, and post-run cleanup passed without leaving the
four-card server alive.

The exact model is `devan-carlin/Qwen3.8-27B-int4-AutoRound` revision
`bce40cacab0a4535b92fb3d57615c2bea9adf3d1`, treated as a quantized artifact
subset of the current Qwen3.8 27B weights. It ran vLLM
`b2dd9ce73dce2ad09007d1db5c171454118981d7` and XPU kernels
`1e90ffa672ba02f17a909da11838a4c55b199783` with no source or decision
overlay. The launch and persisted clean main commit was
`3538d51b8f4517b3ccfbee1fba8e5a0252c38c55`; the remote did not move during
the stage.

Raw evidence is retained at
`/home/steve/qwen38-current-main-runs/tp4-exact-depth-b2dd9ce73d-20260826-r1/01-exact-depths`.
The stage receipt SHA-256 is
`09445b43ca46acbb88f16da2a9fffd9ae4cc14b262f6e52cff35d990582b6160`;
benchmark and quality SHA-256 values are respectively
`b7bfed3d388649927aaaa2bf8204396f03041ad46c031e392919cb5e3592eff1`
and `3f50f98f614f5256db38868c7ee42e25652a721ba9e90e2bb1a30c3bd34ca7a9`.
The fresh compiled-cache manifest contains 4,421 entries and hashes to
`cedae61252876d72b79f1d69d0c148fd7737ad06af8ad37cb1bc45155d16ac22`.
The compact result is
[`../data/2026-08-26-qwen38-b2dd9ce73d-tp4-exact-depth-quality-r1-result.json`](../data/2026-08-26-qwen38-b2dd9ce73d-tp4-exact-depth-quality-r1-result.json).

Authority is deliberately narrow. Publish only these six TP4/MTP0/F16-KV/
FULL_AND_PIECEWISE HTTP cells with their Grade-C and quality disclosures. x0 is
missing: the exact harness correctly refused to substitute an ordinary prompt
for empty active context. The configured 32,896-token capacity is not a cell.
Neither the qualified parent's 71.77179128057259/71.82969607434323 short-suite
speeds nor quality prompts fill context cells. Nothing here authorizes another
TP, MTP, KV, graph, quantization, prefill or concurrency cell, a headline or
protected-value replacement, or a LocalMaxxing submission.
