# Chunk-corruption D1/D2 v2 implementation

Date: 2026-08-23. Implements the isolated-cache re-registration in
`2026-08-23-qwen38-chunk-corruption-mechanism-reregister.md`.

## Frozen identities

- vLLM head: `44fc8fde09fc311d3099dab10366b672d9142ea4`.
- vLLM tracked diff SHA-256:
  `e1efc89e3c239b8b890c0d0e868b290e788f8477708a935f7c0fae1d3258788d`.
- Patch snapshot:
  `../patches/vllm-qwen38-gdn-d1d2-state-audit-v2-20260823.patch`, SHA-256
  `e1efc89e3c239b8b890c0d0e868b290e788f8477708a935f7c0fae1d3258788d`.
- vLLM XPU kernels remain at
  `2dd55f380df753a10a88fcd9e96192561066e713` with no tracked diff.
- D1/D2 validator SHA-256:
  `5cc48ab0b71cd88704747c199dca92b94f4ce5e1aa7db4be689a004ab3ec2409`
  (v2c, post-run stricter exact-release audit; it passes the preserved
  probe, D7, and D4 traces without new GPU work).

## What changed from v1

The v1 patch changed three files. V2 deliberately removes the entire
`qwen_gdn_linear_attn.py` delta—the performance-critical source whose guard
caused the protected AOT model to be rebuilt. Only scheduler metadata and
Mamba state-block lifecycle reporting remain patched.

D2 now enables the clean source tree's existing detailed GDN trace at rank 0,
layer 0, prefill only, filtered to benchmark request IDs. Its `pre_native`
record is the call-site evidence: it contains the exact `has_initial_state`
tensor immediately before `torch.ops._xpu_C.gdn_attention`, plus
request-indexed prompt and computed-token counts. The first infrastructure
probe established that this native lane does not enter the fallback call
site; the v2b validator therefore keys on `pre_native`.

The new validator fails closed unless each dose row has:

- D1 allocations and frees for cache groups 0, 1, and 2;
- twelve prefill metadata records (two chunks x three groups x two ranks),
  with state indices equal to the allocated slots;
- no allocation of a block still live for another request;
- exactly two D2 call-site records at computed-token counts 0 and 1024;
- D2 flags `[false]` and `[true]` in that order.

The validator was run against the invalid v1 D7 root. It accepts all seven
rows of D1 lifecycle/metadata evidence, detects zero live-slot collisions,
and fails because the D2 trace is missing. That is the intended fail-closed
behavior.

## Static gates passed

- both shell launchers pass `bash -n`;
- the validator and both patched Python sources compile from text;
- both repositories pass `git diff --check`;
- the source diff exactly matches the durable patch bytes and contains no
  GDN model-source hunk.

No GPU run is authorized until these lab-repository changes are committed and
pushed, the isolated cache copy and its input manifest exist, and the
recovered source manifest verifies unchanged.
