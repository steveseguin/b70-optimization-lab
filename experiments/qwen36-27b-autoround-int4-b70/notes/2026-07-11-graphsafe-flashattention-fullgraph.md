# 2026-07-11 - Graph-safe FlashAttention enables a quality-clean full target graph

## Decision

Promote this as the new strict TP2 record and retain it as the graph-safe base
for subsequent structural work. It removes the concrete Intel SYCL
scratch-memory blocker that previously made `FULL_AND_PIECEWISE` fail during
FlashAttention capture. The cooled solo confirmation reached `93.036242
tok/s`, above the prior `91.714405 tok/s` headline, with crossover and full
quality support.

## Implementation

The focused XE2 patch replaces dynamic
`sycl_ext_oneapi_work_group_scratch_memory` launch properties in chunk prefill
with typed handler-owned local accessors. The kernel keeps subgroup 16, 256
GRFs, and unchanged math. A second default-off dispatch patch,
`VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1`, routes short one-token decode through the
same graph-safe chunk implementation because compiling the monolithic paged
decode translation unit consumed more than 110 GiB RAM.

Tracked implementation and oracles:

- `experiments/qwen27_graphsafe_flash_attention/qwen27-chunk-prefill-local-accessor.patch`;
- `experiments/qwen27_graphsafe_flash_attention/qwen27-force-chunk-decode.patch`;
- `experiments/qwen27_graphsafe_flash_attention/test_graph_replay.py`;
- `experiments/qwen27_graphsafe_flash_attention/test_chunk_decode_graph_replay.py`.

The experiment used a staged hybrid attention library. Patched head-256
`ttfff` (paged causal packed MTP3) and `tffff` (paged noncausal one-token)
objects were compiled with the deployed IntelLLVM 2025.3 toolchain. The
renamed stock attention DSO supplied only symbols unavailable from cached
objects. `/proc/<worker>/maps` confirmed both workers loaded the staged Python
extension and patched attention library.

## Kernel gates

Packed MTP3 chunk prefill passed 3,000 command-graph replays across KV lengths
128/1024/2048. The oracle uses shuffled paged block tables, poisons output
before every replay, mutates Q and `seqused_k`, and compares every result to a
float32 reference. Maximum FP16 absolute deviation was `0.00048828125`.

Forced chunk decode passed another 3,000 replays with the same protections.
It is viable only for short context:

| KV | paged decode | chunk decode |
|---:|---:|---:|
| 128 | 18.133 us | 20.589 us |
| 1024 | 29.180 us | 109.625 us |
| 2048 | 22.618 us | 214.984 us |

Therefore this is not a general production paged-decode replacement. A proper
graph-safe paged-decode launch remains the long-context follow-up.

## Endpoint result

Exact record topology plus:

```text
VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1
VLLM_XPU_DDTREE_FULL_GRAPH=1
COMPILATION_CONFIG={"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}
```

Startup completed one mixed PIECEWISE capture and one four-row FULL decode
capture. The former scratch-memory exception did not recur. Strict crossover:

| Window | Candidate | Control | Delta |
|---|---:|---:|---:|
| candidate 0,1 / control 2,3 | 90.433 | 87.439 | +3.42% |
| candidate 2,3 / control 0,1 | 91.606 | 89.413 | +2.45% |

Both crossover runs used the fixed realistic suite, each prompt once,
`cached_tokens=0` for every request, target-verified MTP3, and no history,
prefix, response, or checkpoint reuse. Candidate/control crossover means are
`91.019/88.426 tok/s` (`+2.93%`). The candidate remains inside historical
run variance. The subsequent solo GPU2,3 confirmation reached median
`93.036242`, mean `92.773145`, p10 `82.845516`, and therefore becomes the
headline with crossover support.

Quality artifact:

`data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-fp16-graphsafe-fa-full-quality128-repeat128-ctx1024-20260711T203355Z.json`.

It passed exact arithmetic/copy/JSON, repeat128, complete baseline output
parity, and the 1K needle.

## Next action

1. Publish the compact record packet and submit the validated row to
   LocalMaxxing.
2. For long context, split or otherwise make the paged-decode launch
   graph-safe; do not retain forced chunk decode beyond the short record lane.
3. Combine the full graph with the next independent acceptance or GDN fusion
   lane only after preserving this result and its exact staged checksums.
