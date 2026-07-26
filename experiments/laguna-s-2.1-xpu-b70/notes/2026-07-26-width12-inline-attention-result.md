# Laguna width-12 inline-attention result

Date: 2026-07-26 America/Toronto

Status: **rejected — 12/13 exact and no material latency win**.

## Artifact and identity

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-inline-attn-20260726T185856Z
```

The leg used width 12, DFlash depth 11, persistent exact-attention metadata,
TP4/EP4, one active request, no warmup or retry, and all shared-elementwise,
QKNorm/RoPE, draft-graph, nested-attention-graph, and local-argmax selectors
off. The only treatment selector was
`VLLM_XPU_LAGUNA_M8_INLINE_ATTENTION_GRAPHS=1`.

Source and binary identity:

```text
vLLM     4a03b432437258575754ca6798769fe3df056771
kernels  7e680978dc3a92175ea74fd59428eed55c03e019
FA2      3390a3065de25e06dbe95a8fbc2c8456c3489a2295816782e90a4086aedc9dd4
attn lib ad0eb26f3b0680fcd54a50de821e9c881524d50ad5361b872f88cb0b333b65ca
```

All four ranks captured and replayed the preregistered topology of exactly
`98` graphs and `97` eager breaks. This proves that the 48 attention
boundaries were removed without changing the 97 collective boundaries.
Shutdown, worker cleanup, port release, and post-run idle checks passed.

## Result

```text
scored median: 90.74011046813025 tok/s
exactness:     12/13
cached tokens: 0 on all 13 rows
draft cycles:  1,604
draft tokens:  17,644
accepted:      4,757
```

`shell-safety-review` diverged at output-token index 1:

```text
teacher:   4603
candidate: 23950
```

The exactness failure is sufficient to reject the candidate.

The low median does not describe a broad throughput regression. The divergent
row moved from `100.524890` to `77.771353` tok/s and therefore changed which
row occupied the suite median. Across the other twelve rows, candidate/control
rate ratios had median `1.006067` and mean `1.007422`; individual rows were
mostly within ordinary sub-percent leg noise, with no consistent cycle-cost
reduction. The candidate and standing result also had slightly different
acceptance totals, so the ratio is not valid promotion evidence.

## Decision

Retire inline attention as a throughput route. The graph-safe paged-decode
kernel and guarded selectors remain default-off, committed research artifacts.
Do not infer that fewer Breakable graph segments reduce PCIe collective
latency: the 97 collective boundaries and operations were unchanged, and
merging the 48 attention segments produced no material endpoint benefit.

Do not rerun this configuration in search of a favorable median. Any future
attention graph work needs a new mechanism and a new preregistration.
