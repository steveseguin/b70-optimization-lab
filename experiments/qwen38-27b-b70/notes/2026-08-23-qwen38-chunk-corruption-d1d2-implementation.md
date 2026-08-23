# Chunk-corruption D1/D2 instrumentation implementation

Date: 2026-08-23. Implements the default-off, report-only patch preregistered
in `2026-08-23-qwen38-chunk-corruption-mechanism-prereg.md`.

## Frozen implementation identity

- vLLM source head: `44fc8fde09fc311d3099dab10366b672d9142ea4`.
- vLLM tracked diff SHA-256 (`git diff --binary | sha256sum`):
  `9d5450d485578d5075d3945f1284580934aac0981da484603149ef70bf4bc55a`.
- Durable patch snapshot:
  `../patches/vllm-qwen38-gdn-d1d2-state-audit-20260823.patch`.
  SHA-256: `1d6881e12dce3c8d13a7afa7708acb6d2e5aefd0076ee265907acfeadb337a10`.
- vLLM XPU kernels remain at
  `2dd55f380df753a10a88fcd9e96192561066e713` with an empty tracked diff.
  No native extension or staged graph binary is rebuilt or replaced.

The patch is inert unless both its enable flag and output file are set. D1
records Mamba state-block allocation, skipped-block release, request free,
per-step live-request maps, and the state-index tensors produced by the GDN
metadata builder. D2 records rank 0 / GDN layer 0 only, immediately before
the chunked-prefill convolution kernel consumes `has_initial_state`; it also
records request IDs, prompt/computed-token counts, query starts, and consumed
state slots.

## Speed/progress preservation

The incumbent model, quantization, TP2 placement, PIECEWISE compilation JSON,
captured graph size, cache, staged FlashAttention binaries, oneCCL, MTP5,
sampler controls, and all performance-bearing environment variables are
unchanged. The common runner exports the new variables only when explicitly
requested, so historical and production recipes retain byte-for-byte launch
settings. These two diagnostic runs are not throughput promotions; their
device-to-host boolean/index reads may add synchronization.

## Capped runs and gates

Exactly two fresh roots are authorized, in this order, with
`CHUNKDIAG_STAMP=20260823-d1d2-a`:

1. `d7` (seven multi-chunk dose rows), then the quality battery;
2. `d4` (eight multi-chunk dose rows), then the quality battery.

The cache manifest must remain unchanged, the stock native hashes must remain
exact, and the existing compile/AOT direct-load markers must pass. D7 must
remain needle-green. D4 must reproduce the red `B70_QWEN3!!!!...` signature;
if D4 turns green, the synchronization introduced by observation makes both
doors instrumentation-inconclusive rather than dead.

Expected long-request D2 coverage is 14 records for D7 and 16 for D4: first
chunk `num_computed_tokens=0` with `has_initial_state=false`, second chunk
`num_computed_tokens=1024` with `has_initial_state=true`. Every consumed state
slot must be live for that request; cross-request reuse is valid only after a
recorded free. Malformed JSONL or missing coverage is an instrumentation
failure, not mechanism evidence.
