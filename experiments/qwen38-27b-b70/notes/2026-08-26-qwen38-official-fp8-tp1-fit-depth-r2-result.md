# Official Qwen3.8 FP8 TP1 fit/depth R2 result

R2 passed its first arm. The exact official `Qwen/Qwen3.8-27B-FP8`
revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` fits one 32 GiB B70 in
the pinned `f01e24f...` vLLM XPU image at an 8,448-token service capacity
when the frozen eager, 0.96-memory-budget profile is used.

The one successful service lifetime produced three Grade C, cache-zero,
exact-depth cells:

| Exact active context | Decode tok/s | HTTP TTFT | Output |
| ---: | ---: | ---: | --- |
| 2,048 | `10.752574826796211` | `2,289.161 ms` | 128 token IDs |
| 4,096 | `10.760381473147484` | `4,591.801 ms` | 128 token IDs |
| 8,192 | `10.741772379915982` | `9,333.342 ms` | 128 token IDs |

Each request passed every exact prompt-count, completion-count, cache-zero,
no-truncation, no-context-shift, and 99-interval timing gate. These are
repeated-token shape measurements, not a natural-prose or full semantic
quality battery. No zero-context point was fabricated, and 16K/24K/32K stay
missing rather than inferred from the configured capacity.

This route is deliberately additive. It is TP1, MTP0, graph-off/eager,
FP16/auto KV, and one slot. It has no authority to replace a faster or
protected result, no graph-on/MTP/TP2/TP4 authority, and no LocalMaxxing
submission authority. In particular, the protected `71.45427094575045`,
`30.329809361830037`, `49.05894025767351`, and `71.9001988117144` values are
unchanged.

The prelaunch verifier read all 66 weight files (`30,866,866,928` bytes) once
through strict `O_DIRECT` with no fallback and once through a complete ordinary
read; every hash and path agreed. The terminal receipt is
`completed-valid-bounded-fit-depth`. Afterward the campaign container was
absent and port 19456 was closed.

Evidence:

- [structured compact result](../data/2026-08-26-qwen38-official-fp8-tp1-fit-depth-r2-result.json)
- [frozen R2 preregistration](../data/2026-08-26-qwen38-official-fp8-tp1-fit-depth-r2-prereg.json)
- raw root: `/mnt/fast-ai/bench-results/qwen38-official-fp8-tp1-fit-depth-20260826-r2`
