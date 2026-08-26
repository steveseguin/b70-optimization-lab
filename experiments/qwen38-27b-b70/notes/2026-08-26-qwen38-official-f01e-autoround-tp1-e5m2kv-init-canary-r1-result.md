# Official f01e AutoRound TP1 E5M2-KV init/canary R1

The current official `f01e24f6…` / `ac7509e2b` runtime explicitly rejects FP8 E5M2 KV during engine initialization:

> `NotImplementedError: FlashAttention does not support fp8_e5m2 kv-cache on this device.`

The preregistered unsupported classifier therefore fired with runner return code 42. Startup never completed, so the 128-token canary and quality battery correctly did not run. This is an unsupported runtime capability result, not a quality failure or performance measurement. All 19 model files passed coherent direct and ordinary verification before the attempted boot; cleanup passed, the campaign container is absent, and port 19470 was closed at sealing.

The public closure is limited to the exact current f01e TP1/MTP0/eager/graph-off/fp8_e5m2 serving profile. Because the engine cannot initialize that profile, its seven declared active-context selectors (x0 through 32K) are unsupported rather than missing. No graph-on, TP2/TP4, MTP1–4, other runtime, or other KV conclusion transfers. The older immutable `e9d1398d9` unsupported closure remains separate historical evidence. No throughput, headline, protected-speed, or LocalMaxxing authority exists.

Compact evidence is in `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-r1-result.json`; raw receipts remain at `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-20260826-r1`.
