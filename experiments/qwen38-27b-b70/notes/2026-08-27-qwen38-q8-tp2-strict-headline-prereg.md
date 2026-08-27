# Qwen3.8 Q8 TP2 strict reasoning-off headline preregistration

## Purpose

The Q8 TP2 package has a valid historical reasoning-enabled headline, a
qualified reasoning-off exact-depth curve, and scoped concurrency evidence.
Its current launcher is reasoning-off, so the historical headline cannot be
silently transferred. This campaign measures the missing exact packaged
identity.

## Frozen profile

- `ggml-org/Qwen3.8-27B-GGUF` revision
  `0669b98607d47046c7c2b3f801011d54a08cfccf`, Q8_0 SHA-256
  `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`;
- accepted DP4A2+SG24 oneAPI 2026.1.1 runtime: `llama-server`
  `f7bc299a830cbbbbfc3e06ac46ef4f063b9d85e43995c04e07ffa9de0aa390bb`
  and `libggml-sycl.so`
  `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`;
- two B70s, tensor split 1:1, Q8_0 weights, F16 KV, no MTP/speculation,
  reasoning off, XPU Graph off, one active slot, 8,192-token capacity, and
  server-side prompt caching disabled;
- full 12-prompt/six-class suite, one request per prompt, 512-token natural
  cap, streamed token IDs, temperature zero, prompt cache disabled per request,
  and `cached_tokens=0` on every row;
- class-balanced 99-interval rate over events 1 through 100;
- two fresh server lifetimes. No prompt, KV, response, history, or warmed-prompt
  reuse and no prompt subset.

The model is verified once through direct I/O and once through ordinary reads
before each server. Runtime/model/environment hashes and raw responses are
captured in each create-only evidence directory.

## Gates

Both attempts must pass the full workload and objective canaries. Promotion
also requires `12/12` exact complete token-array agreement across the two fresh
servers and explicit comparison with the historical reasoning-enabled oracle;
different reasoning policy is expected to change text and is disclosed rather
than treated as a regression.

No rate is a package headline until all gates pass. No Q8 TP1, MTP, 32K, or
concurrency authority transfers from this short single-user TP2 result.
