# Q8_0 versus Q4_K_M contributor measurements

> **Evidence: `community-reported`; not run in the reference lab.** The tables
> are preserved as reported. They do not provide a performance bound for vLLM
> dynamic FP8.

Pinned contributor write-up:
[`results/q8-vs-q4-b70.md`](https://github.com/bosd/trx50-arc-b70-benchmarks/blob/fda0d86c47ff02d8e36f813a8e0121a2152d4478/results/q8-vs-q4-b70.md).

## Reported setup

- Two Arc Pro B70 GPUs on a TRX50/Threadripper 9960X host.
- Fedora Server 44, kernel 7.0.10, `xe`, NEO 26.18.38308.1,
  oneAPI 2026.0, llama.cpp SYCL with `GGML_SYCL_F16=ON`.
- Exact llama.cpp commit and exact model revisions: unknown.
- `llama-bench` prompt length 512 and generation length 128; contributor says
  the default five repeats were used.
- Wall power from a Shelly plug; raw results for these tables are not present
  in the pinned source snapshot.

## Reported measurements

| Model | Quantization | GPUs | Size GiB | pp512 tok/s | tg128 tok/s | Wall W | tg/W |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-30B-A3B | Q4_K_M | 1 | 17.3 | 1227 | 79.2 | 292 | 0.271 |
| Qwen3-30B-A3B | Q4_K_M | 2 | 17.3 | 1179 | 77.5 | 327 | 0.237 |
| Qwen3-30B-A3B | Q8_0 | 2 | 30.2 | 890 | 41.2 | 311 | 0.132 |
| Hermes-4-14B | Q4_K_M | 1 | 8.4 | 1393 | 47.5 | 368 | 0.129 |
| Hermes-4-14B | Q4_K_M | 2 | 8.4 | 1349 | 47.5 | 422 | 0.113 |
| Hermes-4-14B | Q8_0 | 1 | 14.6 | 1464 | 29.8 | 385 | 0.077 |
| Hermes-4-14B | Q8_0 | 2 | 14.6 | 1423 | 28.9 | 381 | 0.076 |

## Maintainer review

- On the same two-GPU Qwen rows, Q8_0 generation is **0.53×** Q4_K_M
  generation and reported wall-energy efficiency is **0.56×**. The
  contributor's 0.52× and 0.49× figures instead compare the two-GPU Q8 row to
  the one-GPU Q4 row.
- On the same one-GPU Hermes rows, Q8_0 generation is **0.63×** Q4_K_M and
  reported wall-energy efficiency is **0.60×**.
- The one-versus-two GPU rows show that llama.cpp layer splitting did not
  improve generation throughput for these two fits-on-one-model tests. They do
  not establish that two GPUs can never help other models, engines, workloads,
  split modes, or concurrency levels.
- The MoE and dense rows use different models and therefore do not isolate
  architecture as the cause of their speed or efficiency difference.
- The observed prompt-processing range does not establish that prefill is
  generally quantization-insensitive.

Q8_0 GGUF under llama.cpp and dynamic FP8 under vLLM differ in engine, weight
format, kernels, fusions, scheduling, and model identity. Equal nominal bit
width does not make Q8_0 an upper bound or proxy benchmark for vLLM FP8. The
tables are useful Q8_0-versus-Q4_K_M observations for the reported llama.cpp
setups only.
