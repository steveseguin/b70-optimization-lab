# Ornith 1.5 35B-A3B: ordered MoE reduction work-group sweep

Date: 2026-08-22 EDT

Status: **CLOSED NEUTRAL — keep implicit range scheduling**

The accepted ordered MoE reduction assigns one independent output column to
each work-item. A same-binary runtime selector compared the existing implicit
`range` launch with explicit work-groups of 64, 128, 256, and 512. Every arm
kept the exact per-column sequence of seven FP32 additions.

A fixed-seed, temperature-zero, forced 128-token CLI comparison between the
implicit arm and WG256 was byte-identical after excluding the CLI's dynamic
performance footer. Both canonical outputs hashed to
`0143ca510271d95d859b69427824e56c4c502c9a41ccadac28d5726547e31ce0`.

The `llama-bench p0/n128/d0/r5` screen measured:

| Work-group | tok/s | Delta vs implicit |
| ---: | ---: | ---: |
| implicit | **109.547340** | — |
| 64 | 108.347682 | -1.095% |
| 128 | 109.773057 | +0.206% |
| 256 | 109.699343 | +0.139% |
| 512 | 109.863426 | +0.289% |

The best apparent gain was smaller than the arm's own sample deviation and did
not justify a mirrored repeat or server suite. Keep the simpler accepted
implicit-range launch. The exact screen source is archived as
`../patches/llamacpp-ornith15-moe-add-workgroup-sweep-neutral-20260822.patch`;
raw and structured JSON are under `../data/`.
