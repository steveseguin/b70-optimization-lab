# Qwen3.6 Top128 Hot-Only Layer-20 Rank-0 GPU Timing 20260612dx

Date: 2026-06-12

## Purpose

Test whether a fully hot top128 expert pack is faster than the accepted full
256-expert grouped-GEMM path for real replay-digest decode routes.

This is a no-quality-loss microbench: both paths use the same Quark W8A8 INT8
weights and the same reconstructed route counts. The only policy change is the
resident expert table size when all selected experts are covered by the top128
hotset.

## Inputs

- Route source:
  `data/qwen36-replay-digest-hot-decode1-layer20-rank0-routes-20260612dv.jsonl`
- Layer filter: `layers[.]20[.]`
- Route rows: start indices `0:16`
- Route window size: `1`
- Hotset: top128 experts for layer 20, local rank 0
- Device: `xpu:0`
- Warmup: `10`
- Iterations: `80`
- Kernel module:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so`
- Model config:
  `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118/config.json`

Route metadata from the benchmark artifact:

- Records loaded: `347`
- Records matched: `347`
- Records skipped: `0`
- Unique calls: `347`
- Active experts per tested row: `8`
- Total rows per tested case: `8`

## Reproduction

The accepted backend was stopped for a short maintenance window because it was
using nearly all four B70s. The benchmark was then run on `xpu:0`.

```bash
TOP128="224,191,185,151,237,41,239,117,99,116,110,206,186,7,53,127,72,180,171,205,220,107,175,193,121,135,148,179,71,35,141,194,216,235,115,207,56,23,159,49,3,157,247,133,36,173,47,137,18,92,246,155,38,11,143,50,4,203,164,184,52,126,195,253,160,89,221,20,80,242,22,42,198,17,172,33,61,85,244,10,165,232,102,217,225,86,238,181,98,69,223,234,150,136,249,29,68,112,120,65,0,132,178,108,233,147,74,95,104,123,174,103,46,138,81,226,83,114,240,88,44,163,78,93,139,21,94,113"

PYTHONPATH=/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib \
ONEAPI_DEVICE_SELECTOR=level_zero:0 \
ZE_AFFINITY_MASK=0 \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py \
  --route-jsonl data/qwen36-replay-digest-hot-decode1-layer20-rank0-routes-20260612dv.jsonl \
  --route-layer-regex 'layers[.]20[.]' \
  --route-start-indices 0:16 \
  --route-window-size 1 \
  --hotset-experts "$TOP128" \
  --hotset-cold-mode compact \
  --gemm-stage both \
  --device xpu:0 \
  --warmup 10 \
  --iterations 80 \
  --output-json data/qwen36-replay-digest-hotset-top128-layer20-rank0-hotonly-gpu-20260612dx.json
```

## Results

| Mode | Experts | Stage | Cases | Mean case us | Median case us | Min case us | Max case us |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| exact | 256 | gemm1 | 16 | 100.533 | 97.875 | 88.323 | 122.240 |
| exact | 256 | gemm2 | 16 | 102.365 | 91.377 | 88.485 | 125.377 |
| hotset_split_compact_cold | 128+0 | gemm1 | 16 | 101.408 | 101.670 | 88.503 | 123.102 |
| hotset_split_compact_cold | 128+0 | gemm2 | 16 | 103.594 | 103.691 | 88.427 | 119.370 |

Relative to the full 256-expert path:

- Top128 hot-only `gemm1` was `0.8703%` slower by mean case time.
- Top128 hot-only `gemm2` was `1.2005%` slower by mean case time.

## Restore And Health

The accepted endpoint was restored on `http://127.0.0.1:18080`.

- `/v1/models` returned model id `qwen36-35b-a3b-fp8`.
- Reported max context: `32768`.
- Provenance guard passed with all sentinels matching.
- Restore log reported `2,052,915` GPU KV cache tokens and `62.65x` maximum
  concurrency for 32K requests.
- Refreshed post-restore `xpu-smi ps` shows the TP workers resident on all four
  B70s with about `32756-32758 MiB` used by the primary worker on each device.

## Conclusion

This is a useful negative result. A top128 resident table has excellent
admission coverage for layer 20, but simply shrinking the grouped-GEMM expert
table from 256 to 128 does not speed up c1 decode rows in the current XPU
kernel path. The result is effectively flat to slightly worse.

Next work should keep top128 admission, but move the speed path to one of:

- persistent or one-dispatch MoE layerlets that remove per-token host/dispatch
  tax;
- a fused hot/cold kernel where top64/top128 avoid split launches;
- a static decode supergraph that captures routing, hot admission, MoE, and
  collectives together;
- a route-aware grouped-GEMM kernel that changes scheduling/layout enough to
  reduce actual work, not just table cardinality.
