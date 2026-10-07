# R197: MTP depth 4 on the R187 line

Date: 2026-09-04 01:01-01:23 EDT, boot 88f0984f (clean). R156 image, `splitting_ops=[]`, `num_speculative_tokens=4`.
Prereg `data/2026-09-04-qwen38-fp8-r187-night-r195-r197-prereg.json`; result
`data/2026-09-04-qwen38-fp8-r197-whole-graph-depth4-result.json`.

| gate | result |
|---|---|
| G2 depth-4 a vs b | 12/12; 82.447 / 82.345 tok/s (center **82.396**; depth 3: 79.183) |
| G3 vs the R187 MTP0 oracle | 12/12 and 12/12 |
| G5 repeat probe | ids, logprobs, top-k identical |
| G6 ladder (first run) | c1-c16 exact; c32 30/32 (cache-c000 @96, rollback-c010 @97); c64 58/64; aggregate 78.8 / 71.6 / 218.0 / 384.7 / 530.7 / 558.6 / 619.8 tok/s |
| sequential 64-prompt oracle | no phantom; token-identical to the depth-3 oracle |
| acceptance | per position 0.893 / 0.828 / 0.562 / 0.521; mean accepted length 3.80 |

Reading: depth 4 is the fastest lossless single-user profile so far (+4% over depth 3) and the weakest at high
concurrency (c64 aggregate 620 vs depth 3's 713-720 and depth 2's 784): rejected draft work grows with depth and
with batch. The second ladder (R201) is queued; depth 5 (R200) probes the turnover.
