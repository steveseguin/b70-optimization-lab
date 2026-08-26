# Qwen3.8 official FP8 TP2 active-slot capacity screen R1

Status: **preregistered diagnostic; not launched**.

The qualified four-slot service reaches `81.086716 tok/s` at c4, then c8-c64
queue and remain near `81.5 tok/s`. R1 changes only `--max-num-seqs` and asks
whether the same exact official-FP8 TP2/MTP0 service can convert more concurrent
requests into active batched decode.

Three fresh servers are fixed in ascending order: p8, p16, and p32. Every
server runs the same c1/2/4/8/16/32/64 ladder, unique 128-token short prompts,
128 returned raw token IDs, prefix cache off, and the frozen compact output
oracle. `--max-model-len 4096`, `--max-num-batched-tokens 256`, FP16 KV,
size-one PIECEWISE graph capture, model, image, topology, and all collective
settings remain unchanged.

This single-attempt screen cannot publish a new package number. A profile is
mechanically usable only if every response completes, every prompt-cache count
is zero, no output collides with another base task's frozen sequential oracle,
the server cleans up, and no XPU fault is observed. The diagnostic winner is
the profile with the highest aggregate rate at its own unqueued capacity point.
It must improve the qualified p4 c4 median by at least 5% to justify a separate
two-fresh-server confirmation under the existing 10% throughput and 15%
latency stability limits. No result may be interpolated or extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-capacity-screen-r1-prereg.json).
