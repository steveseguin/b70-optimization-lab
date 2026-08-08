# Qwen3.6-27B INT4 benchmark — llama-benchy (2026-08-04)

**Config:** `intel/llm-scaler-vllm:0.21.0-b2` | sym_int4 | fp8_e4m3 KV | MTP (2 tokens) | 1x B70 (GPU 0) | port 8001 | eager

**Tool:** llama-benchy 0.4.1.dev1 (local repo `/home/dom/llama-benchy`)
**Method:** latency-mode generation, 1 warmup + 3 probes | pp=2048, tg=1024 | 5 runs per depth | avg latency 79.29 ms

## Results

| depth | pp | tg | pp tok/s | tg tok/s | peak tok/s | TTFR ms | est_ppt ms | e2e_TTFT ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2048 | 1024 | **1494.6** ± 107.7 | **46.3** ± 1.5 | 54.8 | 1307.1 | 1227.9 | 1307.1 |
| 4096 | 2048 | 1024 | **1536.1** ± 6.8 | **35.9** ± 2.2 | 44.4 | 3711.1 | 3631.8 | 3711.1 |
| 8192 | 2048 | 1024 | **1506.8** ± 5.7 | **29.0** ± 0.7 | 37.4 | 6211.4 | 6132.1 | 6211.4 |
| 16384 | 2048 | 1024 | **1421.5** ± 7.5 | **21.6** ± 1.2 | 28.8 | 11781.5 | 11702.2 | 11782.3 |
| 32768 | 2048 | 1024 | **1264.3** ± 1.6 | **14.9** ± 0.7 | 19.2 | 25060.4 | 24981.1 | 25061.9 |

## Why the 27B is slower than the 35B MoE (expected, not a bug)

The 27B is a **dense** model — every token activates all ~27B parameters.
The 35B-A3B is **MoE** — only ~3B experts are active per token. So the 35B
does ~9x less compute per token despite the larger parameter count. That is why
the 35B MoE benches ~3.8x faster at prefill (5,648 vs 1,494 tok/s) and ~2.2x
faster at fresh decode (103 vs 46 tok/s) on the same INT4 recipe.

## Notes

- Prompt processing: ~1.3–1.5k tok/s, very stable (low std) across depths.
- Token generation: 46 tok/s fresh → 15 tok/s at 32k depth; dense-model decode
  degrades with context as expected on a single 32 GB card.
- Raw data: `bench-qwen36-27b-int4-b2-20260804-194433.json` / `.csv`
- Both GPUs were ~31 GiB used during the run (27B on GPU 0, 35B on GPU 1) —
  no cross-instance interference.
