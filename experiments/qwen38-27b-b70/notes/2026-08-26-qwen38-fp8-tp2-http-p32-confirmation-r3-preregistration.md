# Qwen3.8 official FP8 TP2 p32 HTTP confirmation R3

Status: **preregistered; not launched**.

R3 tests the promising but excluded R2 p32 observation on two wholly new fresh
servers. The excluded R2 rate does not enter the R3 aggregate.

The frozen identity is the official Qwen3.8 27B FP8 revision in the pinned
vLLM XPU image, TP2, target-only/MTP0, and FP16 KV. The server uses 32 active
sequences, a 4,096-token maximum, 256 batched tokens, prefix cache off, and
size-one PIECEWISE graph capture. The measured ladder is c1/2/4/8/16/32/64;
c1-c32 are active-slot points and c64 includes service queueing.

Both attempts must return 128 raw token IDs for every response, use zero cached
prompt tokens, avoid every cross-base compact-oracle collision, remove the
container, leave no non-wrapper model process, and close the port. At every
point, aggregate throughput relative range must be at most 10%; TTFT and
end-to-end p50/p95 relative ranges must each be at most 15%.

If all gates pass, publication uses the median of the two exact observations at
each point. Nothing is interpolated or extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-p32-confirmation-r3-prereg.json).
