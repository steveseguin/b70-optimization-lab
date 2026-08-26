# Qwen3.8 FP8 W8A16 adaptive MTP2/MTP1 R2 repair preregistration

## Question

Does the focused XPU GDN active-width repair make vLLM's exact dynamic
`[(1,1,2), (2,128,1)]` schedule correct and stable, while retaining at least
`82.810053 tok/s` for one user and reaching at least `875 tok/s` at c64?

R1 passed its sequential and singleton gates but is quarantined because the
first multi-request step killed both workers before any aggregate result. R2
changes only the XPU GDN interpretation of active token width versus padded
state-row width. It is a repair validation, not a threshold or policy sweep.

## Frozen repair and identity

- model: `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- vLLM `ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9`, XPU-kernel source
  `1e90ffa672ba02f17a909da11838a4c55b199783`;
- base W8A16 image ID
  `sha256:61bd8edb385c03b40cdadaba068608355b144a5011722597e7ca437f37346ecd`;
- repair patch
  `vllm-xpu-kernels-qwen38-dynamic-mtp-active-width-20260826.patch`, SHA-256
  `68c486a9a10a2f7e85d7d88783a05f89919e931d2b81922f85be733bfb59f1b5`;
- repaired `_xpu_C.abi3.so` SHA-256
  `de253fa31df9acae6020b95da8d2286f5ff15d8fe3d51b59b71496cbf9311f62`;
- repaired `libgdn_attn_kernels_xe_2.so` SHA-256
  `2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355`;
- R2 image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mtp-width-r1`,
  image ID
  `sha256:9918c4477d2d3bdbd84732c5beb13619a89740f9915b1d7393fb48f1d3c8ed72`;
- TP2 on B70 devices 0 and 1, FP16 activations/KV, block-W8A16 enabled,
  prefix cache disabled, max length 256, 128 slots, block 64, MBT512, direct
  oneCCL P2P, and a size-one PIECEWISE graph;
- exact schedule `[(1,1,2), (2,128,1)]`: maximum MTP2 for one active request
  and MTP1 for two through 128 active requests. The checkpoint still contains
  one publisher MTP layer; MTP2 serially reuses it and is not native MTP2.

The repair derives active loop width from compact token/qkv buffers, retains
the padded speculative-state row stride, and rejects active widths larger than
the configured state width. Static equal-width MTP behavior is unchanged by
construction. No vLLM Python source, target verification, quantization,
scheduler policy, service capacity, graph size, or benchmark input changes.

## Ordered gates

1. Before loading the model, run the focused upstream GDN regression case with
   two active positions and a three-column padded state row. It must match the
   reference output/state, exercise a preceding accepted count of three, and
   leave the padded writeback column unchanged.
2. Use a new cache directory. Require direct model verification and exact
   image, label, patch, extension, library, topology, runtime, W8A16, service,
   and schedule identities at startup.
3. First run one output-audited c2 batch as a crash canary. It must return
   256/256 token IDs with cache zero, complete accounting, and output
   isolation. It has no performance authority. Any worker/engine exception or
   assertion closes R2 failed.
4. Pass the seven-case sequential battery and eight-run repeat stability with
   hashes identical to the static MTP2 control and cache zero.
5. Exclude one identical single-response conditioner, then measure five fresh
   cache-zero 40-prompt-token/128-output-token rows. As preregistered for R1,
   the first eligible row is authoritative and must reach `82.810053 tok/s`
   after TTFT.
6. Run and exclude one complete output-audited c64 transition batch. It must
   return 8,192/8,192 token IDs with cache zero and output isolation; it has no
   performance authority.
7. Run one second c64 batch as the declared aggregate screen. Require the same
   gates and at least `875 tok/s`. Above `1,000 tok/s` meets the preferred
   objective.
8. Only if both performance gates pass may a separately preregistered fresh-
   server c64 replication and 512-request concurrent semantic canary run. R2
   does not authorize c128, a threshold sweep, context ladder, package/site
   promotion, or LocalMaxxing submission.

Any identity, regression-test, startup, output, cache, completion, isolation,
or engine-health failure quarantines the arm. Every accepted performance value
must be directly measured; nothing may be interpolated or extrapolated.
