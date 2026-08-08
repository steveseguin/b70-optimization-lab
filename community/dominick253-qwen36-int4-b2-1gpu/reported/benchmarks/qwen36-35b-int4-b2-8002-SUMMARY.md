# Qwen3.6-35B-A3B INT4 benchmark — llama-benchy (2026-08-04)

**Config:** `intel/llm-scaler-vllm:0.21.0-b2` | sym_int4 | fp8_e4m3 KV | MTP (2 tokens) | 1x B70 (GPU 1) | port 8002 | eager

**Tool:** llama-benchy 0.4.1.dev1 (local repo `/home/dom/llama-benchy`)
**Method:** latency-mode generation, 1 warmup + 3 probes | pp=2048, tg=1024 | 5 runs per depth | avg latency 44.73 ms

## Results

| depth | pp | tg | pp tok/s | tg tok/s | peak tok/s | TTFR ms | est_ppt ms | e2e_TTFT ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2048 | 1024 | **5647.8** ± 399.2 | **103.3** ± 3.5 | 119.4 | 378.3 | 333.6 | 378.3 |
| 4096 | 2048 | 1024 | **6220.4** ± 188.8 | **77.8** ± 3.7 | 89.4 | 946.6 | 901.9 | 946.6 |
| 8192 | 2048 | 1024 | **5671.5** ± 303.8 | **33.3** ± 13.1 | 43.4 | 1691.0 | 1646.2 | 1691.0 |
| 16384 | 2048 | 1024 | **5573.9** ± 29.4 | **39.7** ± 2.8 | 52.8 | 3021.2 | 2976.5 | 3022.0 |
| 32768 | 2048 | 1024 | **4677.6** ± 13.2 | **24.8** ± 2.0 | 33.4 | 6814.8 | 6770.1 | 6816.7 |

## Notes

- **Prompt processing:** ~4.7–6.2k tok/s, stable across all context depths (moat of the B70's FP8/INT4 GEMM path; small drop at 32k).
- **Token generation:** 103 tok/s at depth 0; drops with depth — expected for MTP drafting + fp8 KV dequant on 32 GB single card. 8k/16k dips are noisy (high std) but real (deep-context decode is compute-bound).
- MTP acceptance during the run: ~67–76% avg draft acceptance (server metrics).
- Raw data: `bench-qwen36-35b-int4-b2-20260804-192953.json` / `.csv`
- **Benchmark status:** PENDING BENCHMARK → now has data; update `community/dominick253-qwen36-int4-b2-1gpu/STATUS.md` and PR #18 when adding to repo.
