# Qwen3.8 FP8 MTP8 serial FlashAttention R38 diagnostic

Date: 2026-08-28

R36b and R37b produce the same complete output and first diverge from the
qualified MTP0 target at zero-based token 440. The divergent token is the last
token in a two-token streamed speculative group, after one accepted token.
Packed block-FP8 serialization moved this failure from token 127 to 440;
global batch invariance was bit-for-bit neutral. The remaining high-probability
shape-sensitive target surface is the full-attention layer's multi-query
verifier call.

R38 backports the lab's existing progressive serial FlashAttention diagnostic:
for XPU decode calls with more than one query token, execute each query as a
one-query call while progressively increasing the visible KV length. The gate
is `VLLM_XPU_FA_SERIAL_SPEC_DECODE=1`; ordinary one-token target calls and
prefill remain unchanged.

Keep R36b eager TP2, MTP8→MTP1, packed-FP8, packed-RMSNorm, and serial-GDN
settings fixed. Keep `VLLM_BATCH_INVARIANT=0` because R37b closed it neutral.
Use a new empty runtime cache and the unchanged `risk-register` request: seed
42, temperature 0, top-p 1, natural 512-token cap, returned token IDs, and
zero cached tokens. The R38 FlashAttention marker, R36 packed-FP8 marker, and
both R35 GDN markers must fire.

Pass requires all 512 token IDs to equal qualified MTP0 R15. Any missing
marker, cached token, startup failure, or token divergence rejects this
treatment. A pass authorizes a separately preregistered complete strict suite;
the sentinel rate is never publishable.

## Result

All required mechanisms fired and the response was cache zero, but the first
divergence returned to zero-based token 127 (`8923` versus target `4826`).
Progressive serial FlashAttention is therefore rejected. Its diagnostic speed
is not promoted. R38b separately tests the older no-causal sub-variant.

Candidate image:
`sha256:489d8947be1faba1bf9cd6f699982d9c14bfa368065f4a6477bda5cf0c1ae018`.
Performance receipt SHA-256:
`21d61f11d451a458a3bf7b1ff373117ecb083c74a7dcad1db1734455c1a24cb0`.
Server log SHA-256:
`83171d4d996e9a982716eeb0d901807811a46afda464c5f69c3dbda37cb0a440`.
