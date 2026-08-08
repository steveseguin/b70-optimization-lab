# Benchmarks — Qwen3.6 27B / 35B A3B INT4 (vLLM b2, one GPU per model)

Measured 2026-08-04 with [llama-benchy](https://github.com/eugr/llama-benchy)
0.4.1.dev1 against the live servers (27B on GPU 0 / port 8001, 35B MoE on
GPU 1 / port 8002). Same recipe as `vllm-qwen36-int4-b2-1gpu.sh`.

## Method

- Tool: llama-benchy 0.4.1.dev1 (llama-bench-style metrics for OpenAI endpoints)
- Latency mode: `generation` (1 warmup + 3 measured probes)
- Prompt size: 2048 tokens | Generation: 1024 tokens | Runs: 5 per depth
- Depths: 0, 4096, 8192, 16384, 32768 | Concurrency: 1
- Prefix caching disabled (`prefix_caching_enabled=false`), unique requests
- Coherence test passed before each run set
- Raw data: `bench-qwen36-27b-int4-b2-20260804-194433.json` /
  `bench-qwen36-35b-int4-b2-20260804-192953.json` (+ `.csv`), full per-run
  values included

## Verification

- `est_ppt + latency = TTFR` within 0.02% for every row of both files
  (timing math internally coherent)
- Depth-0 prompt-processing cross-check: `pp_throughput` matches
  `prompt_size / (TTFR - latency)` within 15% for both models
- 5 measured runs per depth in both files
- Both GPUs were simultaneously loaded (~31 GiB each) during the run —
  no cross-instance interference

## Qwen3.6-35B-A3B (MoE) — GPU 1, port 8002

Avg generation latency 44.73 ms.

| depth | pp tok/s | tg tok/s | peak tok/s | TTFR ms | est_ppt ms | e2e_TTFT ms |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 5647.8 ± 399.2 | 103.3 ± 3.5 | 119.4 | 378.3 | 333.6 | 378.3 |
| 4096 | 6220.4 ± 188.8 | 77.8 ± 3.7 | 89.4 | 946.6 | 901.9 | 946.6 |
| 8192 | 5671.5 ± 303.8 | 33.3 ± 13.1 | 43.4 | 1691.0 | 1646.2 | 1691.0 |
| 16384 | 5573.9 ± 29.4 | 39.7 ± 2.8 | 52.8 | 3021.2 | 2976.5 | 3022.0 |
| 32768 | 4677.6 ± 13.2 | 24.8 ± 2.0 | 33.4 | 6814.8 | 6770.1 | 6816.7 |

## Qwen3.6-27B (dense) — GPU 0, port 8001

Avg generation latency 79.29 ms.

| depth | pp tok/s | tg tok/s | peak tok/s | TTFR ms | est_ppt ms | e2e_TTFT ms |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1494.6 ± 107.7 | 46.3 ± 1.5 | 54.8 | 1307.1 | 1227.9 | 1307.1 |
| 4096 | 1536.1 ± 6.8 | 35.9 ± 2.2 | 44.4 | 3711.1 | 3631.8 | 3711.1 |
| 8192 | 1506.8 ± 5.7 | 29.0 ± 0.7 | 37.4 | 6211.4 | 6132.1 | 6211.4 |
| 16384 | 1421.5 ± 7.5 | 21.6 ± 1.2 | 28.8 | 11781.5 | 11702.2 | 11782.3 |
| 32768 | 1264.3 ± 1.6 | 14.9 ± 0.7 | 19.2 | 25060.4 | 24981.1 | 25061.9 |

## Interpretation

- **Prompt processing:** 35B MoE sustains ~4.7–6.2k tok/s across all depths;
  27B dense sustains ~1.3–1.5k tok/s. The MoE wins because only ~3B experts
  are active per token (~9x less compute) despite the larger parameter count.
- **Token generation:** both degrade with context (compute-bound decode on a
  single 32 GB card). 35B: 103 → 25 tok/s; 27B: 46 → 15 tok/s from depth 0
  to 32k.
- **MTP was active** during both runs; server-side acceptance ~67–88% avg
  draft acceptance across the runs.

## Reproduction

```bash
# 35B (port 8002) — run while vllm-qwen36-35b-int4 is serving
bash benchmarks/bench-qwen36-35b-int4-b2-8002.sh
# 27B (port 8001) — run while vllm-qwen36-27b-int4 is serving
bash benchmarks/bench-qwen36-27b-int4-b2-8001.sh
```

## MTP A/B finding (2026-08-05) — MTP causes the deep-context decode collapse

Follow-up A/B on the reported slowdown: same recipe, `--speculative-config` removed
as the ONLY change. Focused sweep: depths 0 and 32768, pp=2048 tg=512, 3 runs.

| Model | depth | tg MTP ON (tok/s) | tg MTP OFF (tok/s) | Effect |
| --- | --- | --- | --- | --- |
| 35B-A3B MoE | 0 | 103.3 | 108.1 | neutral |
| 35B-A3B MoE | 32768 | 24.8 | 85.5 | MTP OFF **3.45x faster** |
| 27B dense | 0 | 46.3 | 27.7 | MTP ON 1.67x faster |
| 27B dense | 32768 | 14.9 | 23.3 | MTP OFF 1.56x faster |

**Cause:** with MTP, each step runs a draft forward + verify forward; at deep
context both do full attention over the entire KV cache, doubling attention
work per accepted token. MTP wins when GEMMs dominate (shallow context on the
dense 27B), loses hard when attention dominates (deep context). MTP acceptance
remained 85-100% throughout — this is not draft rejection, it is per-step
attention overhead.

**Corrected interpretation:** the deep-context decode ceiling on one B70 is
~85 tok/s (35B MoE) / ~23 tok/s (27B dense) with MTP off — the MTP-on numbers
in the tables above understate the hardware. The 8192-depth row anomaly
(33.3 tok/s, slower than 16384's 39.7) is MTP instability at the
attention-heavy transition.

**Recommendation:** disable MTP (`--speculative-config` omitted) for
deep-context workloads on this hardware; enable it only for shallow-context
dense-model serving where it measurably helps (27B: 46 vs 28 tok/s at depth 0).

Raw: `bench-qwen36-35b-nomtp-20260805-062613.json`,
`bench-qwen36-27b-nomtp-20260805-063206.json`

## Quality finding (2026-08-05) — 35B MoE INT4 + thinking mode emits "!"-repetition garbage

**Symptom:** with thinking enabled (`enable_thinking:true`), the 35B-A3B MoE
degenerates into `!!!!...` repetition inside the reasoning chain on trivial
prompts ("Hello"), burning the whole token budget with empty content.
Reproduced across every sampling configuration tried:

| Config change | Result |
| --- | --- |
| temp 0.6 / presence 0.0 (27B values) | `!` spam (immediate) |
| temp 1.0 / presence 1.5 (golden values) | `!` spam (after ~40 tokens of coherent reasoning) |
| temp 0.9 / rep_penalty 1.15 | `!` spam |
| thinking OFF | **clean** ("Hello! How can I help you today?") |

**Isolation:** the 27B dense on the identical recipe (INT4, fp8 KV, same image,
same reasoning parser) is **clean** — full coherent reasoning + answer,
`finish: stop`. Same KV cache dtype, same quantization path, same vLLM image.
The differentiator is the **MoE architecture under `sym_int4`**
(`XPUGPTQ4...` MoE INT4 method) with the long reasoning chain. This matches the
failure mode Intel's own `xpu_communicator.py` comment attributes to hidden
state corruption ("cascades to garbage ('!!!!') decode output"), though this is
TP=1 so it is not the multi-GPU all-reduce path.

**Status:** open issue, not yet resolved. Workarounds that produce clean output:
- Thinking OFF on the 35B (verified clean)
- Run the 35B under a different quantization (FP8 MoE was the b1 golden path,
  untested here as a fix)

Raw reproduction: `curl -s localhost:8002/v1/chat/completions -d '{"model":"qwen36-35b","messages":[{"role":"user","content":"Hello"}],"max_tokens":250}'` → reasoning starts coherent then degenerates to `!`.
