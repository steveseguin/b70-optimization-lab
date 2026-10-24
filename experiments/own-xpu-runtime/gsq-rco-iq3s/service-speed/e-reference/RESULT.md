# High-precision reference: the engine is near-exact; BF16 activations flip ~2% of near-ties (2026-10-24)

## Reference

Built from the pinned llama.cpp `23b0202a` source, CPU-only, in a separate copy. The baseline tree is unchanged.
- **Exact mode.** [ggml-cpu-exact-f64.patch](ggml-cpu-exact-f64.patch) is opt-in with `GGML_CPU_EXACT_F64=1`. Every
  dense and expert (`mul_mat_id`) matrix multiply dequantizes each weight row with the format's canonical `to_float`.
  There is no activation packing (normally Q8_K) and no tiling. Each output is a double-precision sum of F32×F32
  products, rounded once to F32.
- **Precision elsewhere.** The other operators are llama.cpp's F32 ops. The KV cache is F32 (`EXACT_KV` default).
- **Tool.** [exact-logits.cpp](exact-logits.cpp) teacher-forces a fixed token sequence and records, for every scored
  position: the argmax, the top 20 tokens, and the next-token logprob.
- **Rounding diagnostic.** `GGML_CPU_EXACT_ROUND=bf16` rounds matmul outputs to BF16 and exists only for diagnosis.
- **Cost.** It ran CPU-only at nice 19 on cores 8–15/24–31 beside the live service. 599 positions took about
  5.5 minutes.

The independent reference used earlier (`reference-cpu/`, unchanged llama.cpp) is **less precise** than this one. It
packs activations to Q8_K inside quantized matmuls and used a BF16 KV cache.

## Test

The incident prompt (87 tokens) plus the 512 tokens that engine 5926 generated (longer-a native output) were
teacher-forced. At each of the 512 positions, the reference argmax is compared with the engine's token, given the same
prefix (the engine's own).

| Reference variant | Positions where reference argmax ≠ engine token |
|---|---|
| exact F32 weights, F64 sums, F32 KV ([rows](runs/incident-f32kv/rows.jsonl)) | **9 / 512**: 144, 161, 186, 236, 239, 267, 368, 502, 560 |
| same, BF16 KV ([rows](runs/incident-bf16kv/rows.jsonl)) | 10: changes 3 positions vs F32 KV (165, 216, 267) |
| same, matmul outputs rounded to BF16 ([rows](runs/incident-mmbf16/rows.jsonl)) | 9, a different set: changes 8 positions vs exact |

**The known output-70 divergence (position 156) was the old reference's error, not the engine's.** The exact reference
picks token 220, the same as the engine, with a logit gap of 0.168 over 264. The old Q8/BF16-KV reference picked 264.

The 9 remaining disagreements are all near-ties. The reference's top-two logit gap is 0.04–0.23. In the exact
reference, the engine's token is the runner-up.

Rounding any of the activations to BF16 reproduces disagreements of this size and frequency. The specific positions
change with the rounding pattern. So the engine's deviation is the expected effect of its BF16 activation storage
(residual/HC streams, projection, router and expert outputs, logits) and of its BF16 KV. It is not a semantic error.

## Status against the owner's standard

"No quality loss beyond the weight quantization" would require the engine to match the exact-dequantization reference.
It matches at 98.2% of positions on this sequence and differs only at near-ties. That is close, but not exact. Two
changes are required:
1. **F32 activations everywhere in the target** (FIDELITY.md contract P1, about +139 MB rank 0 / +72 MB rank 1).
2. **F32 KV cache.** BF16 KV alone changes 3/512 near-ties in the reference. The lab rule says the KV cache stays BF16
   by default and a deviation goes to the owner, so this needs the owner's decision.

The reference tool is now the acceptance gate for that work: zero disagreements on registered sequences, with
reference-gap reporting at every position.
