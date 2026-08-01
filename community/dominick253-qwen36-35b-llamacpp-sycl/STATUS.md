# Qwen3.6 35B A3B Q8_0 on Intel Arc B70 (llama.cpp SYCL)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | unreviewed |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until `B70-tested` |

## Provenance

- Contributor: dominick253
- Source PR: community submission (PR pending)
- Commits: pending
- Right-to-submit statement present: yes
- Third-party material: llama.cpp (GGML project), Qwen3.6-35B-A3B (Qwen team, Apache 2.0)

## Claim

The contributor reports a working llama.cpp SYCL deployment of `Qwen3.6-35B-A3B`
in Q8_0 quantization on Intel Arc B70 with MTP speculative decoding (n-max=3),
serving on port 8001 with 512K context and reasoning enabled.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | Intel Arc B70 (Battlemage G31, 8086:e223), 2x cards, 32 GB each |
| OS / kernel | Ubuntu 26.04 LTS, kernel 7.0.0-28-generic |
| GPU driver (`i915` / `xe`) and version | xe (version unstated) |
| compute-runtime / level-zero | unknown |
| Engine / image and exact version | llama.cpp fb92d8f18, IntelLLVM 2026.1.0, SYCL backend |
| Model repo and revision | unsloth/Qwen3.6-35B-A3B-MTP-GGUF |
| Quantization (weights / KV / activations) | Q8_0 (weights and KV) |
| Command and environment variables | See README.md |
| Prompt / output / context lengths, concurrency | Context 512K (512000), slots 2 |
| Cache and speculation policy | draft-MTP n-max=3 |
| Metric definition, repeats, dispersion, TTFT | See benchmark results below |
| Logs / JSON / durable links | llama server journal logs available |

## Benchmark Results (measured 2026-07-27)

### Throughput

- Output throughput (200 tok, avg): **40.12 tok/s**
- Output throughput range: 34.96 – 42.74 tok/s
- Output throughput (512 tok, server log): 43.75 tok/s
- Prompt eval (short, 5 tok): 2.1 tok/s (TTFT-dominant)
- Prompt eval (medium, 23 tok): 9.3 tok/s
- Prompt eval (long, 96 tok): 36.6 tok/s
- Prompt eval (server log, 57 tok): 117.47 tok/s

First request is slower (~35 tok/s) due to graph compilation warm-up.
Subsequent requests stabilize at ~42.5 tok/s.

### MTP Speculation

- Draft acceptance rate: **86.5%** (237/274)
- Mean draft length: **1.86 tokens**
- Graphs reused: **29,892**

### Reasoning Mode

- Fully functional: structured `<think>...</think>` reasoning with proper tag delimiters
- Reasoning content served via `reasoning_content` field (not inline in `content`)
- Tested with math word problem: correctly identifies problem, breaks into steps, structured output

### GPU Status

- GPU 1: 2800 MHz, 25.4 GB / 31.9 GB VRAM, 57°C, 5 W
- GPU 2: 2800 MHz, 27.6 GB / 31.9 GB VRAM, 59°C, 25 W
- Service memory: 10.2 GB resident, 14.8 GB peak, 11.6 MB swap

## Reference Lab Environment

Not yet tested in the reference lab.

## What Was Actually Run Here

Live service benchmarked against running instance. All measurements taken
from live service on port 8001:

- Completion throughput: 3x cold requests, 200 tokens each, measured via
  streaming API
- Server-side timing: extracted from llama.cpp journal logs
- MTP stats: extracted from llama.cpp slot print_timing output
- GPU status: extracted from intel_gpu_top and system monitoring
- KV cache behavior: tested cold vs. warm completion requests

## Findings

1. **MTP speculation is highly effective** — 86.5% draft acceptance with
   n_max=3 means the MTP draft model is almost always agreeing with the
   target. This is the primary driver of throughput.
2. **Graph compilation warm-up is significant** — first request ~35 tok/s,
   stabilizes to ~42.5 tok/s. This is expected for llama.cpp SYCL but worth
   noting for production deployments.
3. **Reasoning mode works correctly** — structured thinking with proper
   tag delimiters, served via `reasoning_content` field.
4. **GPU utilization is healthy** — both cards at 2800 MHz, temps 57-59°C,
   reasonable power draw (5W/25W). VRAM usage ~25-28 GB per card.
5. **No KV cache persistence across requests** — each `/v1/completions`
   call is stateless. KV cache is per-slot/per-request within llama.cpp's
   slot-based architecture.

## Known Issues

- No KV cache persistence between independent API requests (expected behavior)
- Graph compilation warm-up on first request (~35 tok/s vs ~42.5 tok/s stabilized)

## Open Questions For The Contributor

1. GPU count and VRAM per card.
2. compute-runtime / level-zero versions.
3. Benchmark methodology: how was speed measured, how many repeats, cold or warm?
4. Any logs or JSON from the original run.

## Disposition

Entry stays in `community/` at `community-reported` level until validated on B70.
