# One-card FP8 follow-ups: longer context, depth 6, prompt chunk, two users

Four questions left open by the [published packet](../../../packages/qwen38-27b-fp8-tp1-b70/README.md), all on the
R310 image with the same recipe (host input embedding, decode-identical verifier rows, INT4 67k draft shortlist).
Answers are compared with the same no-MTP reference unless stated otherwise.

## 1. A longer context is free: 16,384 tokens

Raising memory use from 0.965 to 0.975 fits a 16,384-token context with 20,264 tokens of cache.

| Setting | Context | KV tokens | Strict | Full answers | Outputs |
| --- | ---: | ---: | ---: | ---: | --- |
| Published (0.965) | 13,824 | 16,193 | 53.61 | 45.32 | 12/12 |
| Longer (0.975) | 16,384 | 20,264 | 53.576 | 45.30 | 12/12 |
| Longer, second server | 16,384 | 20,264 | 53.454 | 45.27 | 12/12 |

Both 16,384-token servers passed the context screen (2K/4K/8K/12K inputs) with every continuation identical to the
no-MTP server, and their strict pair (53.576 / 53.454) matches the published 13,824 pair (53.452 / 53.545) within
run-to-run noise. **16,384 tokens at 0.975 memory becomes the package default; 13,824 at 0.965 stays the conservative
fallback.**

## 2. Depth 6 replicates but is not the better default

| MTP depth | Strict | Full answers | Context |
| ---: | ---: | ---: | ---: |
| 5 | 53.452 / 53.545 / 53.61 | 45.05 / 45.31 / 45.32 | 16,384 |
| 6 | 54.778 / 54.800 | 44.75 / 44.74 | 12,544 |

Depth 6 is 2.3% faster over the first 100 tokens and 1.2% slower over whole answers, and it costs 3,840 tokens of
context. Both depth-6 servers were 12/12 identical to no MTP, so it stays a documented option rather than the default.

## 3. A larger prompt chunk buys nothing and costs memory

`--max-num-batched-tokens 8192` against the qualified 4,096, no MTP, same everything else:

| Input tokens | Prefill at 4,096 chunk | Prefill at 8,192 chunk |
| ---: | ---: | ---: |
| 2,048 | 2,214 | 2,220 |
| 4,096 | 2,189 | 2,193 |
| 8,192 | 2,134 | 2,138 |
| 12,288 | 2,087 | 2,091 |

That is +0.2%, within run-to-run noise, and the larger chunk raises peak activation memory enough that depth 5 could
not start at a 13,824-token context (the engine estimated a 7,488-token maximum and refused). **Keep 4,096.**

## 4. Two users at once

A server accepting two sequences (`--seqs 2`, otherwise the recommended recipe at a 16,384-token context) was screened
with the concurrency oracle: every concurrent answer must equal the same request run alone, byte for byte, over two
passes of the small-context suite with 128-token answers.

| Pass | Answers matching their solo run | Aggregate rate |
| --- | --- | ---: |
| 1 | 2 of 2 | 52.84 tok/s |
| 2 | 1 of 2 | 74.07 tok/s |

**Two users at once is not output-identical on one card**, so the package keeps its one-request-at-a-time guidance and
claims no multi-user rate. This matches the two-card lane, where MTP identity also breaks above a certain load while
no-MTP decoding holds. Nothing here affects single-user results: the server was healthy throughout and stopped cleanly.

Receipts: [data/2026-09-16-fp8-one-card-followups](../data/2026-09-16-fp8-one-card-followups/).
