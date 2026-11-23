# Qwen3.6-35B-A3B GPTQ-Int4 — dual-B70 vLLM-XPU TP2: the `0.31.0-b1-experimental` image clears the post-init APIServer hang

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` — contributor measurement on contributor hardware; not reproduced in the reference lab |
| Patch review status | no patch; stock `intel/llm-scaler-vllm` image, only the tag changed (`1.5` → `0.31.0-b1-experimental`) |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until `B70-tested` |

## Provenance

- Contributor: bosd
- Hardware: ASRock TRX50 workstation, Threadripper 9960X, 2× Intel Arc Pro B70 (32 GB) + 1× Arc Pro B60 (24 GB, idle for this run), Fedora 44, kernel `7.3.4`, `xe` driver, compute-runtime/level-zero `26.35.39758.21`.
- Right-to-submit statement present: yes — all runs are the contributor's own on the contributor's hardware.
- Third-party material and attribution: Intel llm-scaler-vLLM image (`intel/llm-scaler-vllm:0.31.0-b1-experimental`) and vLLM / vLLM-XPU; `Qwen3.6-35B-A3B` from the Qwen team (locally GPTQ-Int4 exported). CCL environment is the community `vllm#41663` recipe.

## Claim

For dual-B70 vLLM-XPU TP2 serving of Qwen3.6-35B-A3B GPTQ-Int4, image
`0.31.0-b1-experimental` (vLLM `0.31.0+xpu.llmscaler`) serves where `1.5`
(vLLM `0.26.1`) completes engine init and then hangs the APIServer; measured
aggregate throughput scales near-linearly to concurrency 64 and peaks at
**~1268 tok/s at concurrency 96** (single-stream ~10.6 tok/s). Contributor
measurement, not a reference-lab finding.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2× Intel Arc Pro B70 (Battlemage), 32 GB each; `ZE_AFFINITY_MASK=1,2` |
| OS / kernel | Fedora 44 / `7.3.4` |
| GPU driver / level-zero | `xe`; compute-runtime / level-zero `26.35.39758.21` |
| Engine / image | `docker.io/intel/llm-scaler-vllm:0.31.0-b1-experimental` (Docker Hub 2026-10-12, 19.7 GB on disk) |
| vLLM version | `0.31.0+xpu.llmscaler` (server banner); the hanging `1.5` image reports `0.26.1.dev0+g568afb3a1` |
| Model / revision | `Qwen3.6-35B-A3B`, local GPTQ-Int4 export (`qwen3_5_moe` / GatedDeltaNet hybrid MoE, 256 experts, ~A3B active) |
| Quantization | weights GPTQ-Int4 (`XPUwNa16LinearKernel` / auto_gptq); KV auto (fp16); dtype float16 |
| Command / env | `community/bosd-qwen36-35b-a3b-tp2/vllm-qwen36-35b-a3b-tp2.sh`; CCL env = `vllm#41663` (`CCL_ENABLE_SYCL_KERNELS=0`, `CCL_ATL_TRANSPORT=ofi`, `CCL_ZE_IPC_EXCHANGE=pidfd`, …), `--tensor-parallel-size 2 --distributed-executor-backend mp --enforce-eager` |
| Prompt / output / context / concurrency | ~45-token prompt, 256 output tokens (`ignore_eos`), `--max-model-len 8192`; concurrency 1/24/48/64/96 |
| Cache / speculation | prefix caching off; no speculative decoding; `--enforce-eager` |
| Metric / repeats / TTFT | wall-clock aggregate completion-tokens/s via client ThreadPool; corroborated by `lmx speed-test matrix run` (benchVersion 0.7.7); no TTFT breakdown from the ThreadPool arm |
| Logs / durable links | `reported/bench.txt`; LocalMaxxing matrix https://www.localmaxxing.com/en/inference-benchmarks/cmwsasd8k008vqh01im51npfg |

## Reference Lab Environment

Not run. No reference-lab reproduction for this entry.

## What Was Actually Run Here

All on the contributor host. On `0.31.0-b1-experimental`: engine init ~60 s,
`Application startup complete`, `/health` → 200, `/v1/models` → `tp2-test`, then
a client ThreadPool decode sweep at concurrency 1/24/48/64/96 and an independent
`lmx speed-test matrix run` (submitted to LocalMaxxing). On `1.5`, the identical
command: engine init completes (`init engine ... took 60.60 s`) then the
APIServer prints nothing and `/health` stays `000`. Nothing was run in a
reference lab.

## Findings

Confirmed on the contributor host:

- Image, not flags. The post-init APIServer hang on `1.5` is reproducible and
  independent of port (8000 vs 8001), GPU contention (both B70s free), and
  `VLLM_ENABLE_V1_MULTIPROCESSING=0`. The only change that produces a live
  endpoint is the image tag → `0.31.0-b1-experimental`. This is a vLLM v1
  frontend / EngineCore-handshake behavior that differs between the two image
  builds, not a tunable on `1.5`.
- Aggregate throughput scales near-linearly to concurrency 64; the knee is
  ~64–96; single-stream is below a single-card Int4 decode of the same family
  (expected TP2 communication overhead).
- Host-RAM gating (not silicon): with 62 GB host RAM, two TP2 workers staging
  ~20.8 GiB shards each OOM unless the other single-card GPU services are
  stopped first.

Hypothesis (not isolated): the differing behavior is a specific vLLM-XPU v1
frontend fix between 0.26.1 and 0.31.0; the exact commit was not bisected.

## Known Issues

- `--shm-size` must not be combined with `--ipc host` (they conflict).
- Single-stream decode (~10.6 tok/s) is slower than a single B70 Int4 decode of
  the same family — TP2's value here is aggregate throughput and fitting a model
  too large to prefer on one card, not latency.
- No formal quality eval; outputs were coherent on a generic prompt only.

## Open Questions For The Contributor

1. Which vLLM-XPU commit between 0.26.1 and 0.31.0 fixes the APIServer-start
   hang (bisect not done).
2. Throughput via vLLM's own `benchmark_serving` (TTFT/ITL distribution) rather
   than a client ThreadPool.
3. Behavior at higher `--max-model-len` and with prefix caching on.

## Disposition

`community-reported`. A first live dual-B70 TP2 serving datapoint for this model
on the contributor hardware, with a concrete image-version finding that others
on B70 TP2 can test directly by swapping only the tag. Raising the evidence
level needs a reference-lab (or matching-hardware) reproduction of both the
`1.5` hang and the `0.31.0-b1-experimental` endpoint.
