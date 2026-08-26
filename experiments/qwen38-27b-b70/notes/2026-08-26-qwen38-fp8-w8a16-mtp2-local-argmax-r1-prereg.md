# Qwen3.8 FP8 W8A16 MTP2-reuse local-argmax R1 preregistration

## Question

Can exact vocab-parallel local argmax recover MTP2-reuse aggregate throughput
to at least `875 tok/s` while retaining its `83.646518 tok/s` single-user
result? The incumbent MTP2-reuse service all-gathers the complete 124,160-token
draft logits across TP2 even though greedy drafting needs only one token ID.

This is a narrow draft-head communication treatment, not a target-model
shortcut. Target verification remains the full-logits standard path. The
checkpoint still has one publisher MTP layer, serially reused for two draft
positions; this is not native two-layer MTP.

## Frozen identity and treatment

- model: `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image:
  `neural-download/vllm-openai-xpu:qwen38-fp8-w8a16-mtp-local-argmax-r1`,
  ID `sha256:02f873678be881ff198d0e0f9b22e7351e09d4d42bd6cfbc15062b21a261d4f1`;
- vLLM `ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9`, XPU kernels
  `1e90ffa672ba02f17a909da11838a4c55b199783`, block-W8A16 patch
  `5db7f1af...`, and default-off Qwen3Next MTP hook patch
  `f5f15e3e97dad905ff20bd5ba69c1cd0fb3493500182753f0627e312f5237c47`;
- TP2 on B70 devices 0 and 1, FP16 activations/KV, cache disabled, direct
  oneCCL P2P access, max length 256, 128 slots, block 64, MBT512;
- MTP2 one-layer reuse with
  `use_local_argmax_reduction=true`; no experimental local-argmax environment
  sub-variant is enabled.

The patch adds only `Qwen3NextMTP.get_top_tokens()`, delegating to the already
pinned `LogitsProcessor.get_top_tokens()` implementation. The latter masks
vocabulary padding, finds each rank's local maximum, gathers `(value,index)`
pairs, and applies deterministic rank-order tie selection. Token IDs are below
the exact-integer limit of its float32 pair representation.

## Bounded screen and gates

1. Use a new cache directory. Startup must prove both TP workers, exact image
   labels, W8A16 dispatch, `num_spec_tokens=2`, and the log message confirming
   local argmax reduction for draft token generation.
2. Before timing, pass the seven-case sequential battery and eight-run repeat
   stability with cache zero. Every normalized hash must match the retained
   same-shape MTP2-reuse MBT512 control.
3. Exclude one identical 32-token/128-output conditioner. Measure the first of
   five subsequent cache-zero rows at the same 40-prompt-token/128-output-token
   shape. The single-user retention gate is at least `82.810053 tok/s` (within
   1% of `83.646518`); a value above `84.4830` is a material improvement.
4. If quality and single-user retention pass, run one output-audited c64 batch
   with 8,192/8,192 returned token IDs, cache zero, and output isolation. The
   primary aggregate gate is `875 tok/s`.
5. Only if both retention and aggregate gates pass may a separate replication
   plus 512-request concurrent semantic canary be preregistered. No c128,
   scheduler sweep, local-argmax collective sub-variant, or automatic package
   promotion is authorized by R1.

Any startup, exact-output, cache, completion, or isolation failure quarantines
the treatment. A sub-875 c64 result closes this exact local-argmax mechanism as
insufficient for the combined objective even if single-user decode improves.
All values are direct measurements; no value may be interpolated,
extrapolated, or merged into the existing MTP0/MTP1 profiles.
