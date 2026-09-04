# R191: MTP depth 3 on the R187 line (whole-graph compile)

Date: 2026-09-03 22:19-22:41 EDT, boot 88f0984f (clean). R156 image, `splitting_ops=[]`,
`num_speculative_tokens=3`. Prereg `data/2026-09-03-qwen38-fp8-r187-mtp2-ladder-repeat-and-mtp3-r190-r191-prereg.json`;
result `data/2026-09-03-qwen38-fp8-r191-whole-graph-depth3-result.json`.

| gate | result |
|---|---|
| G2 depth-3 a vs b | 12/12; 79.163 / 79.203 tok/s (center **79.183**; depth 2: 70.142; depth 1: 54.935) |
| G3 vs the R187 same-config MTP0 oracle | 12/12 and 12/12 |
| G5 repeat probe 224/250/300 | ids, logprobs, top-k identical |
| G6 ladder (one run) | c1-c16 exact; c32 30/32 (rollback-c010 @97, index-c017 @49); c64 60/64; aggregate 70.9 / 82.1 / 236.2 / 381.9 / 556.1 / 779.0 / 720.1 tok/s |
| sequential 64-prompt oracle | no phantom; token-identical to the depth-2 oracle (which equals MTP0) |

Reading: depth 3 is lossless on every gate this lane has, 13% faster than depth 2 at one user, and its
aggregate falls below depth 2 from c32 up (more rejected draft work per step). The identity claim waits for the
second ladder (R193, queued): exact in both runs decides the published concurrency. Publication of a depth-3
line is the user's call; wrapper `scripts/run-20260903-qwen38-fp8-mtp3-whole-graph-r187-server.sh` is ready.

## R193 (22:59-23:10): second depth-3 probe and ladder

Probe exact. Ladder: c1-c16 exact; c32 28/32 (cache-c000 @96, index-c009 @79, rollback-c010 @97, index-c017
@49); c64 61/64 (cache-c032 @35, cache-c040 @60, testing-c045 @28); aggregate 70.9 / 82.6 / 237.6 / 382.8 /
557.0 / 766.0 / 713.3 tok/s; no phantom. Both depth-3 ladders are exact through c16, so the published depth-3
identity claim is c16 (aggregate 557.0 tok/s at c16); above that the tie-class residual moves between runs as
on every other profile.
