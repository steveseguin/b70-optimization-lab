# Qwen3.8 actual LM-head cross-process D5 preregistration

Date: 2026-08-31

Status: **preregistered before D5 model read or operator calls**

## Question

All screened backbone/recurrent primitives are stable, yet fresh servers make
late greedy branch flips. Is the actual M=1 final-logits projection bitwise
unstable across processes?

## Frozen diagnostic

- verify the complete pinned AutoRound model through the direct-read verifier
  before loading any tensor;
- exact current image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- actual checkpoint `lm_head.weight`, expected shape `[248320,5120]` and BF16,
  converted to the server's FP16 runtime dtype;
- local B70 GPU 0, four fresh containers, one fixed M=1 FP16 hidden vector;
- 16 identical `F.linear` calls per process; hash the complete logits and
  record top-2 IDs/values for every call; compare across processes.

Any multiple logit hash or top-1 is a positive causal finding. One hash across
all 64 calls is negative evidence only. No endpoint speed/quality claim follows.
