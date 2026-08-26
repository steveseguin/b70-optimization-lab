# Qwen3.8 official FP8 TP2 p64 active-slot capacity screen R4

Status: **preregistered diagnostic; not launched**.

R4 changes only the qualified short-context service's maximum active sequences
from 32 to 64. It keeps the official FP8 revision, pinned vLLM XPU image, TP2,
FP16 KV, target-only/MTP0 generation, 4,096-token capacity, 256 batched-token
limit, prefix cache off, size-one graph capture, frozen unique-prompt suite,
and compact output oracle.

One fresh server measures c1/2/4/8/16/32/64. All points are within the
configured 64 active slots. Every response must return 128 raw token IDs, use
zero cached prompt tokens, avoid every cross-base oracle collision, and leave
a clean container/process/port state.

The qualified control is p32 c32 at `470.181647 tok/s`. R4 is promising only
if c64 improves that value by at least 5%. This diagnostic is never published
directly; a promising result requires two additional fresh-server attempts
under preregistered throughput and latency stability gates. No point is
interpolated or extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-p64-capacity-screen-r4-prereg.json).
