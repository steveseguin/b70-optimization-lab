# Qwen3.6 Compact-Active Layer-20 Rank-0 GPU Timing 20260612dy

Date: 2026-06-12

## Purpose

Measure the upper bound for active-expert compaction on real layer-20 decode
routes. This compares the accepted 256-expert grouped-GEMM table against a
synthetic compact table containing only the 8 active experts for each c1 route.

This is not an endpoint implementation. It answers a narrower question: if the
kernel saw only active experts, would the grouped-GEMM latency floor move enough
to justify rebuilding active-offset or route-compaction paths?

## Inputs

- Route source:
  `data/qwen36-replay-digest-hot-decode1-layer20-rank0-routes-20260612dv.jsonl`
- Layer filter: `layers[.]20[.]`
- Route rows: start indices `0:32`
- Route window size: `1`
- Compact-active experts per case: `8`
- Total routed rows per case: `8`
- Device: `xpu:0`
- Warmup: `10`
- Iterations: `80`
- Kernel module:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so`
- Model config:
  `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118/config.json`

## Reproduction

```bash
PYTHONPATH=/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib \
ONEAPI_DEVICE_SELECTOR=level_zero:0 \
ZE_AFFINITY_MASK=0 \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py \
  --route-jsonl data/qwen36-replay-digest-hot-decode1-layer20-rank0-routes-20260612dv.jsonl \
  --route-layer-regex 'layers[.]20[.]' \
  --route-start-indices 0:32 \
  --route-window-size 1 \
  --compact-active-experts \
  --gemm-stage both \
  --device xpu:0 \
  --warmup 10 \
  --iterations 80 \
  --output-json data/qwen36-replay-digest-compactactive-layer20-rank0-gpu-compactactive-20260612dy.json
```

## Results

| Mode | Experts | Stage | Cases | Mean case us | Median case us | Min case us | Max case us |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| exact | 256 | gemm1 | 32 | 91.139 | 89.666 | 88.182 | 113.340 |
| compact_active | 8 | gemm1 | 32 | 90.627 | 88.964 | 87.928 | 110.092 |
| exact | 256 | gemm2 | 32 | 90.998 | 89.183 | 88.154 | 106.972 |
| compact_active | 8 | gemm2 | 32 | 90.213 | 89.317 | 88.147 | 93.078 |

Relative to the full 256-expert exact path:

- Compact-active `gemm1` was `0.5622%` faster by mean case time.
- Compact-active `gemm2` was `0.8632%` faster by mean case time.

Estimated temporary allocation in the harness drops sharply:

- `gemm1` exact case allocation estimate: about `128.27 MiB`.
- `gemm1` compact-active case allocation estimate: about `4.03 MiB`.
- `gemm2` exact case allocation estimate: about `66.03 MiB`.
- `gemm2` compact-active case allocation estimate: about `2.09 MiB`.

## Restore And Health

The accepted endpoint was restored on `http://127.0.0.1:18080`.

- `/v1/models` returned model id `qwen36-35b-a3b-fp8`.
- Reported max context: `32768`.
- Provenance guard passed with all sentinels matching.

## Conclusion

This rejects active-expert table compaction as a major standalone latency path.
The memory reduction is real, but the latency barely moves. For c1 decode, the
current grouped-GEMM path is dominated by a fixed per-dispatch floor rather than
by the number of inactive experts in the table.

Next work should stop spending time on ordinary expert-table compaction unless
it is part of a larger one-dispatch or persistent layerlet. The promising
directions are now:

- fuse GEMM1, activation, quant2, GEMM2, and gather inside a persistent MoE
  layerlet;
- capture a whole-token static decode graph that includes MoE and collectives;
- build a one-dispatch hot/cold kernel where cold fallback does not introduce a
  second launch;
- reduce the number of per-token grouped-GEMM dispatches, not just their table
  sizes.
