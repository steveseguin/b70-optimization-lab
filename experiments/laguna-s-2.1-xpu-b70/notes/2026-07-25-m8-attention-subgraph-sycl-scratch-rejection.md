# Laguna M8 attention-subgraph candidate: SYCL scratch rejection

Date: 2026-07-25 America/Toronto

Status: **rejected fail-closed during the first graph-arm lazy capture**.

Sealed internal-NVMe root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-attention-subgraph-c8aa95538-6bd7c5875-20260725T004945Z
```

Identity: protocol commit `c8aa95538de9344a3d779481db2c491eb2aad532`,
vLLM candidate `6bd7c5875fd1522b063abbfedef64678849f66f5`, kernels
`4772f727590c51b72add79350b913d098cf67872`.

The q1 and eager controls each completed exactly one fresh 272-token,
cache-zero generation and matched the frozen expected output:

- token-ID SHA-256:
  `ee44dfe987c199b248cfe8f752f5fa8600a34291815894c5fb6502ffd5187cee`;
- text SHA-256:
  `d41518e5781b3adafb966c1b9a91e46d4d23b1a1ef40d8992ccde9a55920e55f`;
- finish reason: `length`.

The graph arm failed on every rank while capturing the first exact
FlashAttention boundary:

```text
RuntimeError: The sycl_ext_oneapi_work_group_scratch_memory feature is not yet
available for use with the SYCL Graph extension.
```

The stack terminates in `_vllm_fa2_C.varlen_fwd`. This is a direct runtime
capability rejection: the FA2 kernel uses work-group scratch memory that the
installed Intel SYCL Graph extension cannot record. It is not a token
mismatch, collective-order issue, worker leak, or candidate lifecycle error.

No graph driver, replay profile, analyzer result, timing comparison, benchmark,
or LocalMaxxing claim exists. All graph pre/post worker reports are empty and
both graph idle snapshots passed. The sealed root must not be reused.

Disposition: keep the default-off source experiment as durable negative
evidence, but do not enable full attention subgraphs. Narrow the next candidate
to metadata/host preparation around FlashAttention while leaving the
unsupported FA2 submission eager and bitwise unchanged.
