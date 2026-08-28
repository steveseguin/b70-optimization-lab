# Qwen3.8 FP8 MTP8 full batch-invariant R37b diagnostic

Date: 2026-08-28

R37 stopped before inference because pinned vLLM `ac7509e2b` rejects global
batch-invariant mode for `GDN_ATTN`. The lab's maintained vLLM history already
contains a narrow capability declaration: GDN reports support only while
`VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`. R35 independently proved
that exact serial GDN path matches the 512-token static-MTP1 oracle. R37b
backports only that fail-closed declaration onto the immutable R36 image.

Keep the complete R36b eager profile fixed and set
`VLLM_BATCH_INVARIANT=1`. Use TP2, MTP8→MTP1, empty runtime cache, 1,024-token
singleton service, packed-row FP8 serialization, packed-row RMSNorm
serialization, and native recurrent/conv GDN serialization. The server must
start, the global batch-invariant mode must be visible in the environment, and
the FP8 plus both GDN mechanism markers must fire.

Run only the unchanged `risk-register` 512-token, seed-42, temperature-zero,
top-p-one, token-ID, cache-zero sentinel. Pass requires 512/512 equality with
qualified MTP0 R15. Startup refusal, a missing mechanism marker, any cached
tokens, or any token divergence closes the treatment. This is a correctness
diagnostic only and cannot publish a speed.

## Result

The patched backend started with `VLLM_BATCH_INVARIANT=1`; the packed-FP8 and
both serial-GDN mechanisms fired. The 512-token response was cache zero but
remained non-exact at zero-based token 440 (`11447` versus target `24679`). Its
complete token array is byte-identical to R36b, so global batch invariance adds
no correction beyond that candidate. The observed rate is diagnostic and is
not promoted.

Candidate image:
`sha256:b31e78ede5a0b11d78237b6ce40103d4080b76d8239d13fed1c973826399117c`.
Performance receipt SHA-256:
`a0580025bd6f292256fd1bc48e82d7fc9832a91ad537411c9ec1c9a028bc8f7f`.
