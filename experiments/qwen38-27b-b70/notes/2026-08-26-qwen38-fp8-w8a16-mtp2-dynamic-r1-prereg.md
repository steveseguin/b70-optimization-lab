# Qwen3.8 FP8 W8A16 adaptive MTP2/MTP0 R1 preregistration

## Question

Can vLLM's built-in dynamic speculative-decoding schedule combine the static
MTP2-reuse single-user result (`83.646518 tok/s`) with at least `875 tok/s`
at c64 in one service? This tests policy selection, not a new kernel or an
unmeasured blend of the two incumbent profiles.

## Frozen identity and schedule

- model: `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image:
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122`, image ID
  `sha256:61bd8edb385c03b40cdadaba068608355b144a5011722597e7ca437f37346ecd`;
- vLLM `ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9`, XPU kernels
  `1e90ffa672ba02f17a909da11838a4c55b199783`, block-W8A16 enabled;
- TP2 on B70 devices 0 and 1, FP16 activations/KV, cache disabled, direct
  oneCCL P2P, max length 256, 128 slots, block 64, MBT512;
- maximum MTP depth 2 through serial reuse of the checkpoint's one publisher
  MTP layer; this remains non-native MTP2;
- exact built-in dynamic schedule: `[(1,1,2), (2,128,0)]`. A scheduler step
  with one active request uses two draft tokens; two through 128 active
  requests use target-only decoding.

The schedule is read by the pinned scheduler as inclusive batch-size ranges.
The runtime's existing tests explicitly support zero speculative tokens in a
range. No local-argmax treatment or other experimental collective branch is
enabled.

## Bounded screen and gates

1. Use a new cache directory and require direct model verification, both TP
   workers, exact image/runtime identity, W8A16, maximum MTP depth 2, and the
   exact dynamic schedule in startup configuration.
2. Pass the seven-case sequential battery and eight-run repeat stability with
   hashes identical to static MTP2 reuse and cache zero. This exercises the
   batch-size-one/MTP2 arm.
3. Exclude one identical single-response conditioner, then measure the first
   of five subsequent cache-zero 40-prompt-token/128-output-token rows. Require
   at least `82.810053 tok/s` (within 1% of static MTP2).
4. Run and exclude one complete output-audited c64 transition batch. It must
   return 8,192/8,192 token IDs with cache zero and output isolation; it has no
   performance authority.
5. Run one second output-audited c64 batch as the declared screen. Require the
   same accounting/isolation gates and at least `875 tok/s`. A result above
   `1,000 tok/s` meets the preferred aggregate objective.
6. Only if both single-user retention and c64 gates pass may replicated c64
   performance and a 512-request concurrent semantic canary be separately
   preregistered. No c128, threshold sweep, context ladder, or automatic
   package/site promotion is authorized by R1.

Any identity, startup, exact-output, cache, completion, or isolation failure
quarantines the arm. No value is interpolated or extrapolated, and the dynamic
result must remain distinct from both static MTP2 and static MTP0/MTP1 until
its own replication and quality gates pass.
