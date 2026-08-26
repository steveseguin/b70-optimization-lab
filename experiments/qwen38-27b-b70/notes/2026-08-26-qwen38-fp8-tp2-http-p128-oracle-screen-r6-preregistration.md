# Qwen3.8 official FP8 TP2 p128 oracle and capacity screen R6

Status: **preregistered diagnostic; not launched**.

R6 changes only the qualified short-context service's maximum active sequences
from 64 to 128. It keeps the official FP8 revision, pinned vLLM XPU image, TP2,
FP16 KV, target-only/MTP0 generation, 4,096-token capacity, 256 batched-token
limit, prefix cache off, size-one graph capture, and frozen unique-prompt suite.

The run first builds a new 128-row sequential output oracle. It then measures
c1/2/4/8/16/32/64/128 on the same fresh server. All points are within the
configured 128 active slots. Every oracle and benchmark response must return
128 raw token IDs, use zero cached prompt tokens, avoid every cross-base oracle
collision, and leave a clean container/process/port state.

The qualified control is p64 c64 at `695.792088 tok/s`. R6 is promising only
if c128 reaches `730.581692 tok/s`, a 5% gain. Neither the oracle-generation
pilot nor this one-attempt diagnostic is publishable. A promising result
requires two additional fresh-server attempts against the newly frozen compact
oracle under preregistered throughput and latency stability gates. No point is
interpolated or extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-p128-oracle-screen-r6-prereg.json).
