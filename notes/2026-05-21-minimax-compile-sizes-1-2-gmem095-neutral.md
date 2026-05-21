# MiniMax M2.7 Compile Sizes [1,2] Probe - 2026-05-21

## Goal

Test whether specializing both one-token and two-token decode compile ranges improves the promoted MiniMax M2.7 AutoRound INT4 path. The timing diagnostics showed meaningful `(2, *)` collective buckets, so this checked whether `compile_sizes=[1,2]` helps the two-token graph case.

Candidate delta on top of `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`:

```json
{"use_inductor_graph_partition": true, "compile_sizes": [1, 2], "cudagraph_mode": "PIECEWISE"}
```

## Default-Memory Result

With default vLLM GPU memory utilization, the engine failed to start after compiling the extra `(2, 2)` range:

- Available KV cache memory: `0.09 GiB`
- Required for `max_model_len=2048`: `0.12 GiB`
- Estimated max model length after the extra graph memory: `1280`
- Result: startup failure before quality generation

This is not promotable as a default replacement.

## Retest With GPU Memory Utilization 0.95

Retest delta:

```bash
--gpu-memory-utilization 0.95
```

This restored startup headroom:

- Available KV cache memory: `2.04 GiB`
- GPU KV cache size: `34,048` tokens
- Maximum concurrency for 2048-token request: `16.62x`

## Quality Gate

With `gpu_memory_utilization=0.95`, the exact raw145 canary passed:

- Prompt: `prompts/minimax-raw145-tokenhash-canary.txt`
- Output tokens: `64`
- Expected combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Passed: `true`
- Degenerate/control/NUL checks: passed

## Throughput Probe

Warm in-process vLLM random-text probe with `gpu_memory_utilization=0.95`:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM XPU, TP4, llm-scaler WS INT4 path
- Prompt/output: 512 prompt tokens, 1536 output tokens
- Warmup/measured: 1 warmup, 4 measured repeats
- Mean decode throughput: `92.6697497580135` tok/s
- Mean total throughput: `123.55966634401798` tok/s
- Decode stdev: `0.07496449265543807` tok/s
- Per-repeat decode tok/s: `92.56084650108289`, `92.6820657885482`, `92.72760567604901`, `92.70848106637385`

For comparison, the promoted warm vLLM random-text baseline was about `92.374916` output tok/s and `123.166555` total tok/s on the same p512/n1536 shape.

## Decision

Quality-safe with `gpu_memory_utilization=0.95`, but neutral overall. The small `~0.32%` warm decode gain does not justify the extra compile specialization and the fact that the default memory posture failed startup. Do not promote and do not submit to LocalMaxxing.

## Artifacts

- Default-memory failed quality log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/compile-sizes-1-2-20260521T035016Z/minimax-compile-sizes-1-2-raw145-n64.log`
- gmem095 quality JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/compile-sizes-1-2-gmem095-20260521T035700Z/minimax-compile-sizes-1-2-gmem095-raw145-n64.json`
- gmem095 quality log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/compile-sizes-1-2-gmem095-20260521T035700Z/minimax-compile-sizes-1-2-gmem095-raw145-n64.log`
- gmem095 warm JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/compile-sizes-1-2-gmem095-warm-20260521T040000Z/minimax-compile-sizes-1-2-gmem095-warm-vllm-random-text-p512n1536.json`
- gmem095 warm log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/compile-sizes-1-2-gmem095-warm-20260521T040000Z/minimax-compile-sizes-1-2-gmem095-warm-vllm-random-text-p512n1536.log`
- Summary data: `data/minimax-m27-compile-sizes-1-2-gmem095-neutral-20260521.json`
