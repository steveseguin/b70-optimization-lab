# Qwen3.8-27B Q4_K_M TP2 exact-cache c96 result

The exact `ffn_down,ffn_gate` cache reaches a qualified two-B70 c96 center of
**`192.341954 tok/s`**. Two fresh candidate servers measured `192.350949` and
`192.332958 tok/s` (a `0.0094%` range), each matching a separately frozen
same-shape c96 control-batch oracle **96/96** by complete token-ID digest.
Prompt caching was disabled, all 192 responses returned 128 tokens, no
cross-base collision occurred, and both servers shut down cleanly.

This is an aggregate-capacity endpoint, not a single-user or
batch-invariant-text claim. The pilot's synchronized batch matched its own
exported oracle 96/96, while only **50/96** control-batch rows matched the
isolated sequential references. The candidate therefore proves the cache
changed none of the tested same-shape c96 outputs; it does not prove that c96
greedy generation equals isolated generation. Older generic summary fields
called the pinned oracle “sequential”; the structured result above records its
actual provenance, and the runner now keeps sequential and same-shape fields
separate.

The command requested a 32,768-token context pool, but llama.cpp rounded the
runtime to **49,152 tokens** so each of 96 slots received 512 tokens. Peak used
VRAM was about **30,480 MiB on GPU 0** and **30,354 MiB on GPU 1**, leaving
only about 2.18/2.30 GiB free. Treat c96 as a near-capacity service profile.

The c96 center is `+9.52%` over the qualified c64 center of `175.623794 tok/s`.
A single nonpublishable cache-off r14 pilot measured `186.523159 tok/s`; the
candidate center was `+3.12%` above it, but that one pilot is not promoted as a
standalone control headline.

Apply the base exact-cache patch and then the comma-filter increment:

- [`llama-qwen38-q4k-f16-exact-weight-cache-candidate-20260830.patch`](../patches/llama-qwen38-q4k-f16-exact-weight-cache-candidate-20260830.patch)
- [`llama-qwen38-q4k-f16-cache-comma-filter-20260830.patch`](../patches/llama-qwen38-q4k-f16-cache-comma-filter-20260830.patch)

Launch the validation profile with `MTP_DEPTH=0`, `PARALLEL_SLOTS=96`,
`CTX_SIZE=32768`, `BATCH_SIZE=2048`, `UBATCH_SIZE=256`,
`FUSE_EXT_OVERRIDE=31`, `Q4K_F16_CACHE_FILTER=ffn_down,ffn_gate`,
`QUEUE_SETTLE_MS=1000`, and `QUEUE_SETTLE_TARGET=96`. The strict runner,
preregistration, frozen oracle, complete artifact hashes, and exact memory
samples are linked from the [structured result](../data/2026-08-30-qwen38-q4km-tp2-exact-cache-c96-r14-results.json).
