# Qwen3.6 Hotset Split GPU Microbench

Date: 2026-06-12

Purpose:

- Test the top-64 layer `9` routecapture6 hotset split on real XPU grouped
  W8A8 GEMM after the CPU-only floor model.
- Keep exact Quark W8A8 math: hot rows run through the top-64 table, cold rows
  run through compact exact fallback.
- Restore the accepted endpoint and verify quality/sanity afterward.

Command shape:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers[.]9[.]' \
  --route-start-indices 0,1,2,46,78 \
  --route-window-size 16 \
  --hotset-cold-mode compact \
  --gemm-stage both \
  --device xpu:0 \
  --warmup 5 \
  --iterations 20
```

Artifacts:

- `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac.json`.
- `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac.log`.
- `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac-pre-xpusmi-ps.txt`.
- `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac-poststop-xpusmi-ps.txt`.
- `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac-postrestore-xpusmi-ps.txt`.
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-hotsetbench-20260612ac.json`.
- `data/qwen36-quark-int8-tp4-post-hotsetbench-sanity-repetitive-p512o256-20260612ac.json`.

Per-window result:

| case | route start | hot coverage | cold rows | cold active | exact total us | split total us | split/exact |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0.9375 | 8 | 5 | 248.552 | 379.038 | 1.525 |
| 1 | 1 | 0.9375 | 8 | 5 | 190.146 | 378.425 | 1.990 |
| 2 | 2 | 0.9375 | 8 | 5 | 203.541 | 492.482 | 2.420 |
| 3 | 46 | 0.7500 | 32 | 22 | 235.071 | 408.249 | 1.737 |
| 4 | 78 | 0.7891 | 27 | 19 | 191.950 | 377.764 | 1.968 |

Aggregate:

- Exact grouped-GEMM mean total: `213.852 us`.
- Compact hot/cold split mean total: `407.192 us`.
- Mean split/exact ratio: `1.928x` slower.
- Exact mean by GEMM stage:
  - `gemm1`: `108.392 us`.
  - `gemm2`: `105.460 us`.
- Compact split means by cold fallback size:
  - `64+5`: `208.548 us` (`gemm1`), `208.101 us` (`gemm2`).
  - `64+19`: `186.308 us` (`gemm1`), `191.456 us` (`gemm2`).
  - `64+22`: `216.954 us` (`gemm1`), `191.295 us` (`gemm2`).

Restore and quality:

- Accepted endpoint restored to `/health` `200`.
- Provenance guard passed:
  - `natural_latency_plan`: prefix match true.
  - `repetitive_kernel_notes`: prefix match true.
  - Sentinel IDs matched: `4752`, `11436`, `198`.
- Post-restore repetitive p512/o256 sanity:
  - corrected after-first output speed: `99.1568 tok/s`.
  - e2e output speed: `96.6069 tok/s`.
  - vLLM decode time: `10.047 ms/generated token`.

Decision:

- Reject simple two-launch compact hot/cold split as a speed path.
- The split reduces table memory, but current launch and small-shape overhead
  dominates. It is slower even on high-coverage exact windows.
- Do not spend more endpoint downtime on full-cold or prompt-class two-launch
  split variants unless a kernel/policy change first reduces the hot/cold
  launch overhead.
- Next useful work should target one of:
  1. persistent/fused hotset layerlet with in-kernel cold queue,
  2. grouped-GEMM policy/kernel changes for small expert tables,
  3. tile-native hotset repack used inside one launch,
  4. or a different no-quality-loss lever such as resident-state speculation.
