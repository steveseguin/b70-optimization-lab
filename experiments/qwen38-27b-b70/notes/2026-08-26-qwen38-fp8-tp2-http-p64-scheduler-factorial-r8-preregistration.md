# Qwen3.8 official FP8 TP2 p64 scheduler factorial R8

Status: **preregistered diagnostic; not launched**.

The qualified c64 HTTP metric includes prompt admission as well as generation.
R8 tests whether its 256-token iteration budget or synchronous scheduling
leaves a simple service-level gain. Three one-server arms run in frozen order:

1. 4,096 batched tokens, synchronous scheduling;
2. 256 batched tokens, async scheduling;
3. 4,096 batched tokens, async scheduling.

Everything else stays on the official FP8 revision, pinned vLLM XPU image,
TP2, FP16 KV, target-only/MTP0, 64 active slots, 4,096-token capacity,
prefix cache off, and size-one PIECEWISE capture. Every c64 response must
contain 128 raw token IDs, report zero cached prompt tokens, avoid every
cross-base oracle collision, and clean up fully.

The qualified control is `695.792088 tok/s`; an arm is promising only at or
above `730.581692 tok/s` (5%). If multiple arms qualify, the highest exact c64
rate advances to two fresh confirmation servers. These diagnostic rates are
not publishable, and no result is interpolated or extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-p64-scheduler-factorial-r8-prereg.json).
