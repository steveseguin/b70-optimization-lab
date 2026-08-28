# Qwen3.8 FP8 MTP8 serial FlashAttention no-causal R38b diagnostic

Date: 2026-08-28

R38's progressive one-query FlashAttention path was non-exact at token 128.
The maintained lab source preserves one remaining historical discriminator:
once each query's visible KV length is clipped to its exact progressive
prefix, omit the redundant causal mask. R38b changes only that flag under
`VLLM_XPU_FA_SERIAL_SPEC_NO_CAUSAL=1`; R38 remains immutable.

Keep the complete R38 eager TP2, MTP8→MTP1, packed-FP8, packed-RMSNorm,
serial-GDN, empty-cache, and 1,024-token service identity fixed. Run only the
same cache-zero, seed-42, greedy `risk-register` 512-token sentinel. All R38,
R36, and R35 mechanism markers must fire.

Pass requires 512/512 equality with qualified MTP0 R15. Any divergence or
missing marker rejects this treatment. This is correctness-only and its speed
cannot be promoted.

## Result

All required mechanisms fired and the response was cache zero. It still first
diverged at zero-based token 127 (`8923` versus target `4826`). The redundant-
causal-mask hypothesis is rejected and no speed is promoted.

Candidate image:
`sha256:360f4560f6d49d7bb8446aa3296764bb36dad8dc4ec1eb041544568d1077df3b`.
Performance receipt SHA-256:
`4eb627eb2e0647a4d51eaa33c471d3407038fc9ef2b19fa4b657903bdad7b828`.
Server log SHA-256:
`9da58fa99597024943c723a7a20eaebb6c046b7eff840fa241789db218476fce`.
