# Reproduce official Qwen3.8 27B FP8 TP2 on two B70s

> **Certification: `candidate-portable-repro`, not a starter guide.** The
> model, image, launch, and validation identities are pinned and the model has
> been verified on this host. The remaining gates are a tested Intel
> driver/Docker installation path, beginner recovery guidance, and a replay
> from a clean supported host. See the
> [guide catalog](../guide-catalog.json) and
> [certification standard](../../docs/reproduction-guide-certification.md).

This is a quality-gated, target-only vLLM/XPU service snapshot for two ASRock
Intel Arc Pro B70 32 GiB cards. It uses Qwen's official block-scaled FP8
weights, native FP16 KV, TP2, one graph-captured decode size, and no MTP,
DFlash, draft model, response reuse, or speculation.

## Optimized block-W8A16 profile

The lab's default-off block-W8A16 overlay is now the fastest quality-qualified
official-FP8 profile in this guide. It uses the FP8 weights unchanged while
keeping activations in FP16 for the existing XPU W8A16 GEMM primitive.

| Measured profile | Default-off | W8A16 overlay | Patch-only change |
| --- | ---: | ---: | ---: |
| one fresh user, 40 prompt + 128 output tokens | 21.872717 tok/s | **35.011369 tok/s** | **+60.07%** |
| 128 active users, aggregate decode | 860.460981 tok/s | **1,112.570323 tok/s** | **+29.30%** |

The c128 headline is the median of conditioned repeats 2-5 on one server. All
four included repeats returned 16,384 completion tokens with cache zero and
passed output isolation. The same endpoint passed 7/7 sequential exact cases,
eight identical sequential repeats, and 1,024/1,024 concurrent semantic
canaries. Greedy token identity varies with batch shape, so this is an
output-isolation-qualified shape variant, not a universal token-exact claim.

This short-context p128 profile has a 256-token service limit. It is separate
from the directly measured one-slot W8A16 2K-32K profile below; no workload is
inferred between the two services.

### Build the exact overlay

The build helper creates a dedicated checkout at vLLM commit
`ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9`, applies the
[repository patch](../../experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-block-w8a16-20260826.patch),
and overlays only the modified integration file onto the pinned upstream XPU
image:

```bash
BUILD_ROOT=/path/to/dedicated-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-w8a16-image.sh
```

The locally validated overlay image ID was
`sha256:ced02d013fe356faac513f2598b4da1f11fd8e20a9bb8fb9a443564fda460556`.
Docker rebuild identities can vary with builder metadata, so verify that the
installed `xpu.py` SHA-256 is
`7c36e4a8dab4bfc06b1d5be2d8466e8cdc94099dd5409424fecc6dd8ffc2c208`.

### Launch and validate the p128 profile

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-w8a16-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-concurrency-server.sh

OUT_DIR=/path/to/new-w8a16-attempt \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-concurrency.sh
```

The benchmark wrapper captures a fresh single-user row, one excluded c128
conditioning batch, five measured c128 batches, the sequential suite, and
1,024 concurrent semantic cases. It refuses to overwrite an existing result
directory. See the [result note](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-result.md),
[structured summary](../../experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-summary.json),
and [raw receipts](../../experiments/qwen38-27b-b70/data/qwen38-fp8-block-w8a16-tp2-p128-20260826-r1/).

## Captured result

- median decode after TTFT: **`21.708532 tok/s`**
- median wall rate: `19.624649 tok/s`
- median TTFT: `626.227 ms`
- five unique p512/g128 requests; all completed 128 tokens and reported
  `cached_tokens=0`
- decode CV: `0.0738%`
- eager control: `17.097358 tok/s`; the captured size-one graph improved it
  by about `26.97%`

This is slower than the repository's GGUF Q8_0 TP2 record (`36.772932 tok/s`)
and Q4_K_M record (`49.717503 tok/s`). Its value is a working, pinned official
FP8/vLLM baseline and a clean starting point for XPU GDN and collective work.

## Quality boundary

The final graph run passed all seven exact semantic cases, eight identical
repeat runs, and a 3,829-token needle test. Every checked output hash matched
the established Q8_0 oracle, including the Python-result canary (`14`). Prefix
caching was disabled and every quality/benchmark request reported zero cached
tokens.

Longer free-form benchmark continuations were not byte-identical between the
eager and graph modes, so this packet does **not** claim universal token-exact
equivalence for arbitrary prompts. The official FP8 target is quantized and
should not be described as lossless BF16.

## Exact identities

- model: [`Qwen/Qwen3.8-27B-FP8`](https://huggingface.co/Qwen/Qwen3.8-27B-FP8/tree/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a)
- revision: `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
- 66 Safetensors files, `30,866,866,928` bytes
- aggregate basename-sorted `sha256sum` manifest:
  `82fb8f84fa117c81c3e8639c4675709dfb667d70ddaa2fd097d35fc37d95453a`
- image: `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`
- vLLM: `0.27.2rc1.dev77+gac7509e2b`
- Torch: `2.13.0+xpu`

The image selected `XPUFp8BlockScaledMMKernel`. It used Qwen Triton kernels
for the Qwen3.8 GDN path; that fallback is the principal source-level
optimization opportunity.

## Exact 2K–32K service profile

A separate one-slot W8A16 service raised the configured capacity to 33,024
tokens and measured six exact prompt depths. It retained the same model,
overlay image, TP2 topology, FP16 activations/KV, target-only/MTP0 policy, and
size-one PIECEWISE decode graph; only the service capacity, active prompt
depth, one slot, and 4,096-token chunked-prefill batch identify this operating
profile. The default-off values are the earlier same-shape control.

| Exact prompt tokens | Default-off decode | W8A16 decode | W8A16 TTFT ms | W8A16 prompt proxy tok/s |
| ---: | ---: | ---: | ---: | ---: |
| 2,048 | 21.835160 | **35.201648** | 1,011.401 | 2,024.915 |
| 4,096 | 21.673278 | **34.756821** | 1,635.189 | 2,504.909 |
| 8,192 | 21.270146 | **33.592729** | 3,219.230 | 2,544.708 |
| 16,384 | 20.927452 | **32.830415** | 6,549.952 | 2,501.392 |
| 24,576 | 20.650133 | **32.046666** | 10,072.020 | 2,440.027 |
| 32,768 | 20.389854 | **31.489587** | 13,739.776 | 2,384.901 |

All six receipts passed exact prompt usage, 128 returned token IDs, cache-zero,
no-truncation, and no-context-shift gates. This is one fresh-server sample per
point using a grade-C repeated-token shape fixture; no point is interpolated or
extrapolated. The effective prompt proxy is `exact prompt tokens / measured
HTTP TTFT seconds`, including scheduling and first-token work. It is not a
server-only or kernel-only prefill rate.

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-w8a16-depth-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-depth-server.sh

PORT=18119 OUT_DIR=/path/to/new-w8a16-depth-result \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-depth.sh
```

See the [W8A16 structured evidence](../../experiments/qwen38-27b-b70/data/qwen38-fp8-block-w8a16-tp2-http-depth-20260826-r2/summary.json),
[combined result note](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-result.md), and
[default-off control](../../experiments/qwen38-27b-b70/data/qwen38-fp8-tp2-http-depth-20260826-r1-attempt1/summary.json).

## Exact output-audited concurrency profile

A separate target-only/MTP0 service profile retained the same model, image,
TP2 topology, FP16 KV, prefix-cache policy, and size-one graph while fixing
maximum model length 4,096, maximum active sequences 64, and maximum batched
tokens 256. Its concurrency wrapper enables direct oneCCL P2P access; the
single-slot and depth profiles retain their captured P2P-off identity. Two
preregistered fresh-server attempts measured each point:

| concurrent HTTP users | aggregate tok/s | per-user tok/s | TTFT p50 / p95 ms | queued |
| ---: | ---: | ---: | ---: | :---: |
| 1 | 21.557059 | 21.557059 | 95.048 / 95.048 | no |
| 2 | 41.424196 | 20.712098 | 122.743 / 170.950 | no |
| 4 | 81.299381 | 20.324845 | 211.000 / 211.286 | no |
| 8 | 157.990884 | 19.748860 | 267.133 / 267.680 | no |
| 16 | 293.363030 | 18.335189 | 262.556 / 391.232 | no |
| 32 | 504.387101 | 15.762097 | 426.066 / 728.501 | no |
| 64 | 774.394144 | 12.099908 | 768.749 / 1,525.973 | no |

All responses returned 128 complete raw token IDs and zero cached prompt
tokens; no generated digest collided with a frozen sequential oracle belonging
to another base task. The worst aggregate range was `0.525%` and the worst
latency range was `4.404%`. Greedy output may vary with batch shape, so the
gate proves completion and output isolation rather than sequential token
identity.

The service scales through c64, and every published point is within its
configured active-slot limit. Reproduce one attempt with:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-concurrency-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-concurrency-server.sh

OUT_DIR=/path/to/new-attempt \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-concurrency.sh
```

Stop it with `docker stop -t 20 qwen38-fp8-tp2-concurrency`, launch a fresh
one, and use a different `OUT_DIR` for the second attempt. The
[qualified result](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.md),
[structured aggregate](../../experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.json),
[frozen preregistration](../../experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-prereg.json),
[compact oracle](../../experiments/qwen38-27b-b70/data/qwen38-fp8-tp2-http-concurrency-oracle-pilot-20260826-r1-attempt1/oracle-digests.json),
and exact [request suite](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json)
are all in this repository. No point is interpolated or extrapolated.

## Dependency closure

| Component | Status and exact dependency |
| --- | --- |
| Host platform | **Incomplete.** Observed on Ubuntu 24.04.4, kernel `7.0.0-28-generic`, Docker `29.1.3`, `intel-opencl-icd 26.22.38646.7-1~24.04~ppa1`, and `libze1 1.28.6-1~24.04~ppa1`. This records the working host; it is not yet a tested clean-host installer. |
| Accelerator toolchain | Supplied inside the digest-pinned vLLM XPU image named below; host Level Zero compatibility is still part of the missing platform gate. |
| Runtime source/image | `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`; vLLM and Torch versions are recorded below. |
| Project patches | **None.** This baseline intentionally uses the pinned upstream image without a repository patch. |
| Model | Publisher repository and immutable revision below; all 66 weight files are pinned in [`model-direct.json`](model-direct.json). |
| Configuration | [`run-server.sh`](run-server.sh) pins the two-card topology, precision, KV policy, graph size, context, cache behavior, memory bounds, and collective settings. |
| Execution | Run [`preflight.sh`](preflight.sh), launch with [`run-server.sh`](run-server.sh), exercise with [`bench.sh`](bench.sh), and stop with the command below. The image must already be pulled. |
| Validation | The [experiment note](../../experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md) and [structured result](../../experiments/qwen38-27b-b70/data/2026-08-16-official-fp8-vllm-graph-tp2.json) preserve the fixed quality and benchmark boundaries. Clean-host replay remains open. |

The 2026-08-21 host/model preflight is preserved as
[`preflight-evidence-20260821.json`](preflight-evidence-20260821.json). It is
evidence for prerequisites and model identity only; it does not claim that the
container was relaunched or that clean-host certification passed.

## Download and verify

Download the exact Hugging Face revision into one directory. For example,
with a recent `huggingface-cli`:

```bash
huggingface-cli download Qwen/Qwen3.8-27B-FP8 \
  --revision 017b9c7af6b5689d5dd426a76e0bc077eb5ca20a \
  --local-dir /path/to/qwen3.8-27b-fp8

repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-model.sh \
  /path/to/qwen3.8-27b-fp8
```

First pull the exact runtime image if it is not already present:

```bash
docker pull vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
```

Run the non-mutating preflight before serving:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/preflight.sh
```

The preflight checks the observed OS boundary, Docker access, groups, two DRM
render devices, memory, pinned image, and model. Model verification reads all
30.9 GB twice: once with `O_DIRECT` (or `dd iflag=direct`) and once through the
ordinary page-cache path. Every publisher LFS SHA-256, byte size, and the two
read paths must agree. It fails closed if cache bypass is unavailable. The
older [`verify-model.sh`](verify-model.sh) aggregate check remains for
diagnostics, but the launcher now requires direct verification.

## Start and benchmark

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh
```

The first start compiles 51 artifacts and took about 88 seconds locally. A
warm cache starts much faster, but reloading it briefly exceeded an 8 GiB host
cgroup; the launcher therefore uses the validated 9 GiB RAM / 12 GiB
RAM-plus-swap bounds. Do not remove the bounds on a 16 GB host.

After `/health` succeeds, benchmark from another terminal:

```bash
OUT=/path/to/result.json \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench.sh
```

To reproduce the distinct exact-depth profile, use:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-depth-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-depth-server.sh

OUT_DIR=/path/to/depth-result \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-depth.sh
```

The wrapper fixes the measured 33,024-token/one-slot/4,096-prefill profile.
Changing those values creates another operating profile and must not be
compared as though it were the same measurement.

The launcher binds the endpoint to loopback, maps both `/dev/dri` devices, and
uses `ZE_AFFINITY_MASK=0,1`. Verify device enumeration before copying that
selector to a different host. Stop with `docker stop -t 20 qwen38-fp8-tp2`;
never interrupt the engine while graph initialization is still in progress.

## Deliberate settings

- `--tensor-parallel-size 2`
- `--dtype float16 --quantization fp8 --kv-cache-dtype auto`
- context 4,096; block size 64; max sequences 4; max batched tokens 256
- prefix caching disabled; text-only model path
- PIECEWISE graph capture limited to request size 1
- oneCCL direct send/receive, TCP loopback OFI, pidfd IPC, simple collective
  thresholds pinned high
- `CCL_TOPO_P2P_ACCESS=0` for the single-slot/depth identities; the concurrency
  wrapper selects `1`, which raised qualified c64 aggregate throughput 11.30%
- `FULL_DECODE_ONLY` was quality-clean but `1.618%` slower; retain PIECEWISE

The 2026-08-16 nightly (`8efa13b70`, XPU kernels `0.1.13.2`) was also
quality-clean at `21.723631 tok/s`, only `+0.070%` versus this pinned image.
That is noise-level, so the reproduction digest remains unchanged.
Enabling XPU's supported Q/K RMSNorm+RoPE compiler fusion was also neutral:
two medians bracketed the control at `+0.150%` and `-0.083%` while preserving
the oracle. It is intentionally absent from the launcher.
Native BF16 activation/KV arithmetic was oracle-clean but decode-neutral at
`21.708409 tok/s` (`-0.0006%`) with slower TTFT, so the captured FP16 setting
remains the reproducible performance identity.
Reducing maximum sequences to one was also neutral (`21.717535 tok/s`,
`+0.041%`), and omitting the RNG seed from otherwise identical temperature-zero
requests was slightly slower (`21.659428 tok/s`, `-0.268%` against its loaded
seeded control). Keep the default capacity of 4 and explicit benchmark seeds.

vLLM warns that XPU Graph is officially supported only for single-GPU use.
This TP2 graph result is therefore experimental and stays fail-closed behind
the exact local quality gate. See the
[full experiment note](../../experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md)
and [structured result](../../experiments/qwen38-27b-b70/data/2026-08-16-official-fp8-vllm-graph-tp2.json).
