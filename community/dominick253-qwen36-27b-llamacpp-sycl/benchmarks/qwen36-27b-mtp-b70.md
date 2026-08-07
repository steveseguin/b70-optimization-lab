# Qwen3.6-27B MTP on Intel B70 (llama.cpp SYCL)

Historical benchmark data from the setup session; **not rerun** for this PR.

## Identity

- Model: Qwen3.6-27B-Q4_K_M.gguf (MTP-enabled)
- Backend: llama.cpp SYCL, dpcpp + sccache
- oneAPI: 2026.1.1
- Flash Attention: `squeezed`
- GPU offload: `-ngl 999`
- Temperature: `0.0` (greedy)
- Draft tokens: `draft_n=1` or `draft_n=2`
- MTP minimum probability: `0.0`
- Harness: `/home/dom/scripts/benchmark-qwen36-llamacpp-sycl-mtp.py`

The benchmark ran a single 128-token completion at each target context depth
and recorded wall throughput, decode throughput, prompt throughput, and MTP
acceptance. The current persisted service is similar but not identical: it uses
temperature 0.6, `--spec-draft-n-max 2`, and the systemd per-GPU deployment.

## Results: draft_n=1

| target depth | wall tok/s | decode tok/s | prompt tok/s | acceptance | drafted | accepted |
|---:|---:|---:|---:|---:|---:|---:|
| 2,048 | 17.8 | 31.4 | 654 | 85% | 68 | 58 |
| 32,768 | 3.1 | 24.7 | 927 | 75% | 72 | 54 |
| 65,536 | 1.5 | 20.9 | 838 | 76% | 72 | 55 |
| 120,000 | 0.73 | 17.6 | 718 | 85% | 68 | 58 |

## Results: draft_n=2

| target depth | wall tok/s | decode tok/s | prompt tok/s | acceptance | drafted | accepted |
|---:|---:|---:|---:|---:|---:|---:|
| 2,048 | 39.7 | 16.9 | 935 | 80% | 68 | 58 |
| 32,768 | 3.0 | 21.9 | 788 | 66% | 72 | 54 |

## Interpretation

- `draft_n=1` was the more stable deep-context tradeoff in this sweep.
- `draft_n=2` improved short-context wall throughput but reduced acceptance at
  32K and did not improve the reported decode-rate field.
- Prompt throughput remained 718–935 tok/s through 120K in the recorded sweep.
- These values are historical observations and are not a fresh validation of
  the current service process.
