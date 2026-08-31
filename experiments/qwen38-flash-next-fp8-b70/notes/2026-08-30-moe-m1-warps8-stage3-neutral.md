# Qwen3.8 Flash-Next FP8 M1 warps-8 stage-3 result

Date: 2026-08-30
Status: lossless component neutral; stage 4 retained

The three-seed default/candidate/default screen completed exactly. Every arm
was finite, retained one hash through 100 repeats, and matched its seed's
qualified warps-8/stage-4 output bytes. Stage 3 versus its stage-4 bracket was:

- seed 20260826: 409.088 versus 406.178 us, 0.72% slower;
- seed 20260827: 404.462 versus 409.145 us, 1.14% faster;
- seed 20260830: 431.252 versus 423.275 us, 1.88% slower.

No seed clears the frozen 3% gate and median change is 0.72% slower. The third
seed also contains a slow first control start, but the candidate remains slower
than the bracket and cannot be promoted under any favorable reading. Keep the
qualified M1 map at eight warps and four stages. Do not continue to stage 5 or
stage 2 tonight; preserve this neutral so the same refinement is not repeated.

Structured result:
[`20260830-moe-m1-warps8-stage3-neutral.json`](../data/20260830-moe-m1-warps8-stage3-neutral.json).
