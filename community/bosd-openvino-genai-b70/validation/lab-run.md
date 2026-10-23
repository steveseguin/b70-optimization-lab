# Reference-lab run, 2026-10-23

Maintainer record. The contributor's numbers are in `../reported/`; this file
holds what the reference lab ran on its own hardware and what came out.

## Prediction, written before the run

Registered before any GPU time, as lab rules require.

- OpenVINO GenAI will see both B70s without `setvars.sh` (already confirmed
  while installing: `['CPU', 'GPU.0', 'GPU.1']`, both Arc Pro B70).
- No-spec decode on Qwen2.5-7B INT4, one card: between 100 and 120 tok/s,
  within about 10% of the contributor's 113. The B70's 608 GB/s over 4.2 GB
  of weights allows about 145 tok/s, so a result near 113 is roughly 78% of
  the bandwidth peak, not "at" it.
- Spec arm with the 1.5B draft: a wash again, below no-spec on prose and above
  on code.
- Fresh llama.cpp-SYCL, same card, Q4_K_M: between 90 and 105 tok/s, so a
  10-20% gap to OpenVINO, matching the contributor's 15%.
- Greedy output text identical across repeats on each arm.

## Reference lab environment

| Field | Value |
| --- | --- |
| Host | reference lab two-card host, 2x Intel Arc Pro B70 (32 GB), 15 GiB host RAM |
| OS / kernel | Ubuntu 24.04.4 LTS / `7.0.0-38-generic` |
| GPU driver | `xe` |
| Level Zero packages | libze-dev:amd64=1.28.6-1~24.04~ppa1 libze-intel-gpu-dev=26.22.38646.7-1~24.04~ppa1 libze-intel-gpu-raytracing=1.2.4-2~24.04~ppa3 libze-intel-gpu1=26.22.38646.7-1~24.04~ppa1 libze1:amd64=1.28.6-1~24.04~ppa1  |
| OpenVINO venv | CPython 3.12.3 openvino 2026.4.1-22982-e213a147257-releases/2026/4 genai 2026.4.1.0-3408-ab01d1771e4 (uv venv, no setvars) |
| oneAPI compiler for the llama.cpp baseline | Intel(R) oneAPI DPC++/C++ Compiler 2026.1.1 (2026.1.1.20260724) |
| Models | `OpenVINO/Qwen2.5-7B-Instruct-int4-ov`, `OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov`, `bartowski/Qwen2.5-7B-Instruct-GGUF` Q4_K_M, all pulled 2026-10-23 |
| Harness | `ov-bench-lab.py` (this directory), 3 repeats per prompt, device `GPU.0` |

## Result

All runs on one B70 (`GPU.0` for OpenVINO, `level_zero:0` for llama.cpp),
2026-10-23, nothing else on the cards. Raw records sit beside this file.

### OpenVINO GenAI 2026.4.1, Qwen2.5-7B-Instruct INT4 (`ov-bench-lab.log`, `ov-bench-lab.json`)

| Arm | Prompt | Lab decode tok/s (3 reps) | Contributor | TTFT | TPOT |
| --- | --- | --- | --- | --- | --- |
| no-spec | tech | **114.7** (sd 0.1) | 114.0 | 23 ms | 8.7 ms |
| no-spec | code | **114.6** (sd 0.1) | 112.5 | 84 ms | 8.7 ms |
| + 1.5B draft, k=5 | tech | 95.1 (sd 1.5) | 98.6 | 20 ms | 10.3 ms |
| + 1.5B draft, k=5 | code | 126.0 (sd 1.0) | 128.2 | 88 ms | 8.0 ms |

### llama.cpp-SYCL, upstream `184f653` (2026-10-23), Q4_K_M, `-fa 1` (`llama-bench-fresh.log`, `llama-bench-tg-r10.json`)

| Test | Lab | Contributor (`970b51c`) |
| --- | --- | --- |
| pp512 | **3755 ± 9** | 3528 ± 28 |
| tg256, first run, 6 reps | 87.3 ± 29.5 (one cold rep drags the mean) | — |
| tg256, rerun, 10 reps | **99.5 ± 0.1** (99.2, then 99.5 nine times) | 98.6 ± 0.3 |

The build used the contributor's flags exactly (`-DGGML_SYCL=ON
-DGGML_SYCL_DNN=OFF -DGGML_SYCL_F16=ON -DGGML_SYCL_GRAPH=ON`, icx/icpx). The
commit is two days newer than the contributor's; the steady-state number is
the one to quote, as the contributor also found.

### Reading

- **Both numbers reproduce within 2%.** OpenVINO GenAI 114.7 against
  llama.cpp 99.5 is a 15% gap, the contributor's figure.
- **Bandwidth arithmetic.** 114.7 tok/s times 4.2 GB of INT4 weights is about
  480 GB/s, 79% of the B70's 608 GB/s. "Near roofline" is fair; "at roofline"
  is not, and the contributor's "~107 tok/s roofline" assumes an unstated
  ~450 GB/s achievable figure.
- **Speculative decoding with the 1.5B draft is a wash**, as reported: 17%
  slower on prose, 10% faster on code.
- **Greedy output is not repeat-stable on the first generation** (see below).
  Throughput was unaffected (sd 0.1 tok/s across the differing repeats).

### Greedy repeat probe (`determinism_probe.py`, `determinism-warm.log`, `determinism-cold.log`)

The prediction "identical text across repeats" failed, so the lab probed it.
Five greedy 256-token generations of the same prompt on the same
`LLMPipeline`, then a second pipeline instance, then the same again in a
second process without the warmup call:

| Condition | Prompt | Generation 1 | Generations 2-5 |
| --- | --- | --- | --- |
| after 32-token warmup | tech | `db1e63af` | `88f721e7` x4 |
| after 32-token warmup | code | `eb2a0ead` | `16697823` x4 |
| no warmup | tech | `533de519` | `8f203e75` x4 |
| no warmup | code | `eb2a0ead` | `eb2a0ead` x4 |

(SHA-256 prefixes of the output text; both instances and both processes gave
the same rows.)

So: the first full generation of a fresh pipeline decodes differently from
every later one, the later ones are stable, and the settled text depends on
what ran before it (the warmed and cold steady states differ). It is fully
repeatable across processes, so it is a deterministic ordering effect in the
GPU plugin, not noise. The divergences are greedy near-ties flipping ("Args:"
against "Parameters:", "real-time applications" against "high-latency
environments"), consistent with a numerics path that changes after the first
run, for instance a KV-cache or workspace allocation that settles after the
first long generation. The cause was not isolated here. For this lab's
lossless rules that means an OpenVINO GenAI greedy run is not reproducible
from the prompt alone; it needs the pipeline's prior history fixed too.

### Prediction check

| Predicted | Held? |
| --- | --- |
| both B70s visible without setvars | yes |
| no-spec 100-120 tok/s, within 10% of 113 | yes, 114.7 |
| spec arm a wash, below on prose, above on code | yes |
| llama.cpp 90-105 tok/s, 10-20% gap | yes, 99.5 and 15% |
| greedy text identical across repeats | **no**, see the probe |
