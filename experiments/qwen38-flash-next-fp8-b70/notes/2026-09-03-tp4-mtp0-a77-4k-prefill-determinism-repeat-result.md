# Qwen3.8 Flash-Next FP8 A77 4K-prefill determinism repeat result

Date: 2026-09-03 03:55--04:41 EDT
Status: diagnostic positive; an independently started server reproduces
A76 at every depth; the 4K candidate authority now has two servers behind
it; nothing protected touched

A77 is the A76 server (deterministic graph identity at 4352 capacity,
overlay `2169dbfe...`) at fresh attempt paths, launched behind a dropped
page cache; offload receipt logged, load 13 minutes, no hang, no kernel GPU
fault, teardown 143 after the probe's stop file.

| depth | first-step identical (8x) | spread | 128-token repeats (3x) | hash (A77) | hash (A76) |
| ---: | --- | ---: | --- | --- | --- |
| 8 | yes | 0.0 | identical | `3b397739...` | same |
| 64 | yes | 0.0 | identical | `f8db6f86...` | same |
| 256 | yes | 0.0 | identical | `5148bf48...` | same |
| 2048 | yes | 0.0 | identical | `afffd2110812...` | same (and A70-A72) |
| 4096 | yes | 0.0 | identical | `c6193cc6c9a1553f...` | same |

Every first-step top-1 logprob matched A76 to the printed digit as well
(4096: -0.000122). The deterministic line's continuations at 2K and 4K are
now reproduced across independently started servers (2K: five servers at
two capacities; 4K: two servers), which is the reproduction standard the
A70/A71 pair set. A73 remains a policy question only.

Receipt: [`20260903-tp4-mtp0-a77-4k-logprob-determinism.json`](../data/20260903-tp4-mtp0-a77-4k-logprob-determinism.json).
