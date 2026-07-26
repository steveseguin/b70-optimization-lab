# Laguna width-12 graph-safe attention: attempt 3 valid but not promoted

Date: 2026-07-26 America/Toronto

Status: **valid candidate; below the standing result and below 102**.

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-attngraph3-20260726T183027Z
```

## Result

| gate | result |
| --- | ---: |
| scored median tok/s | **97.659756** |
| exact vs frozen q=1 teacher | **13/13** |
| cached tokens | **0 on 13/13** |
| outer topology, every rank | **146 graphs / 145 eager breaks** |
| drafts / accepted draft tokens | 1,607 / 4,749 |
| emitted tokens per cycle | 3.9552 |
| derived cycle time | 40.50 ms |
| cleanup | stop=0, workers=0, idle=0 |

All four ranks captured the exact width-12 attention boundary successfully.
The prior SYCL scratch-memory error is repaired. The result also preserves the
canonical token stream, the rollover row, and the long-then-next transition.

This candidate is not a record and is not promoted. It trails the standing
`100.524890 tok/s` width-12 result by 2.85% and the 102 goal by 4.25%.

## Attribution boundary

The standing width-12 result used persistent exact-attention metadata. This
candidate intentionally disabled that selector because the runtime and harness
still reject combining two unvalidated attention treatments. Therefore the
comparison does not isolate attention capture: it changes both attention
capture and metadata construction.

The next required measurement is a same-binary, metadata-off,
attention-capture-off control. Only that control can classify the capture
treatment. Combining capture with persistent metadata must remain forbidden
until its fixed-address and graph-replay contract is reviewed and tested
explicitly.

## Binary identity

```text
vllm=cd11d5f19f1f7f61dc3fe0b74d2148d6571db127
kernel=7e680978dc3a92175ea74fd59428eed55c03e019
fa2_binary_sha256=3390a3065de25e06dbe95a8fbc2c8456c3489a2295816782e90a4086aedc9dd4
attn_library_sha256=ad0eb26f3b0680fcd54a50de821e9c881524d50ad5361b872f88cb0b333b65ca
```
