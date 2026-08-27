# Qwen3.8 27B FP8 — two-B70 candidate package

This is the first distribution-package front door. It uses Qwen's official
FP8 model and digest-pinned vLLM XPU containers on two Intel Arc Pro B70
32 GiB cards. The selected dynamic MTP3-to-MTP1 service reaches a replicated
median of **`99.930434 tok/s`** for one fresh user and **`1,074.939939 tok/s`**
aggregate at 64 active users while passing 1,024/1,024 concurrent exact-answer
checks across two fresh servers. The target-only block-W8A16 service remains the aggregate peak at
**`1,112.570323 tok/s`** with 128 active users. A separately measured
33,024-token W8A16 service profile reaches `31.489587 tok/s` decode at an exact
32K prompt with `13.740 s` TTFT. The target-only/MTP0 64-slot HTTP profile reaches
`774.394144 tok/s` aggregate at 64 active users on the unpatched baseline.

The package also retains a separate static publisher-MTP1 profile. It reaches
**`61.699580 tok/s`** for one fresh user and **`1,091.642460 tok/s`** aggregate
at 64 users. Dynamic MTP is the faster interactive mode; target-only/MTP0
remains the highest-throughput mode. The site and guide keep those identities
separate.

The checkpoint has one publisher MTP layer. The dynamic service serially
reuses it for MTP3 only at one active request, then uses MTP1 at two or more.
The two fresh-server attempts measured 99.712488/100.148379 tok/s single and
1,066.000395/1,083.879484 tok/s aggregate; see the
[replication result](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-dynamic-mtp3-r7-replication-result.md).

> **Status: candidate, not a beginner install guide.** The exact model,
> container, configuration, commands, and evidence are present. A clean Ubuntu
> host installation of the Intel driver and Docker prerequisites has not yet
> been replayed, so this package does not install or modify host drivers.

The technical source of truth is the
[`reproduction guide`](../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md).
The machine-readable front door is [`package.json`](package.json).

## Who built what

**neural.download lab — integrated and optimized:** B70/XPU integration,
graph and quality validation, direct-I/O model verification, direct-P2P
concurrency tuning, block-W8A16 dispatch, dynamic-width GDN repair, and active
Mamba-state allocation. Against the exact same
overlay image with its environment gate omitted, W8A16 improved fresh
single-user decode from `21.872717` to `35.011369 tok/s` (+60.07%) and c128
aggregate decode from `860.460981` to `1,112.570323 tok/s` (+29.30%). See the
[W8A16 result](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-result.md)
and the earlier [baseline evidence](../../experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md).
The active state allocation separately raised the dynamic service from
`817.007910` to a replicated high-throughput lane. MTP3 then raised its
single-user median from `83.680193` to `99.930434 tok/s` while retaining
`1,074.939939 tok/s` at c64.

**vLLM XPU kernel contributors — upstream mixed-batch fix:** upstream commits
[`4054175`](https://github.com/vllm-project/vllm-xpu-kernels/commit/40541752f4f7fdef3cab471038c775e3f8d42838)
and [`1d5b4f5`](https://github.com/vllm-project/vllm-xpu-kernels/commit/1d5b4f5e5ddd8da96ea23c76d7e7421b00083fdb)
make concurrent MTP safe when speculative decode and newly arriving prefills
share a scheduler step. The old kernel aborts this workload; the integrated
fix reaches `1,091.64 tok/s` at c64. See the
[MTP1 result](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-mtp1-tp2-result.md).

## What you need

- x86-64 Ubuntu 24.04;
- two accessible Intel Arc Pro B70 render devices;
- at least 15 GiB host RAM and 20 GiB RAM plus swap;
- Docker access for the current user;
- about 31 GB for model weights plus working space for the vLLM cache.

The currently observed working host versions are recorded in the reproduction
guide. They are evidence, not yet a general compatibility promise.

## 1. Download the exact model

Choose paths appropriate for your machine; `/path/to/...` is deliberately not
a hidden lab default.

```bash
huggingface-cli download Qwen/Qwen3.8-27B-FP8 \
  --revision 017b9c7af6b5689d5dd426a76e0bc077eb5ca20a \
  --local-dir /path/to/qwen3.8-27b-fp8
```

Weights remain distributed by the model publisher. This repository stores the
immutable revision and all 66 publisher LFS identities, not a copy of the
weights.

## 2. Acquire the pinned runtime

```bash
docker pull vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
```

No project patch is required for the baseline. To build the faster
default-off W8A16 overlay from its pinned vLLM source commit:

```bash
BUILD_ROOT=/path/to/dedicated-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-w8a16-image.sh
```

The helper applies the exact
[patch](../../experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-block-w8a16-20260826.patch)
and builds the repository-local Docker overlay. The model weights are not
modified.

The concurrent MTP1 profile additionally needs the pinned upstream XPU-kernel
artifact. Build the kernel image, then place the same W8A16 overlay on top:

```bash
BUILD_ROOT=/path/to/dedicated-kernel-build \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-kernel-image.sh

BUILD_ROOT=/path/to/dedicated-w8a16-build \
BASE_IMAGE=neural-download/vllm-openai-xpu:f01e-kernel-1e90-r13 \
IMAGE=neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-w8a16-image.sh
```

The selected dynamic profile adds two repository patches after that stage:

```bash
BUILD_ROOT=/path/to/new-active-width-build \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-dynamic-mtp-active-width-kernel-image.sh

repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-w8a16-dynamic-mamba-image.sh
```

The first patch makes the GDN kernel honor the active dynamic width; the
second allocates Mamba state from the active FCFS lookahead. Both build helpers
verify exact source and patch hashes before producing their overlays.

The first helper downloads the exact successful upstream GitHub Actions wheel,
checks its SHA-256 digest, and installs it over the pinned official image. It
requires `gh` authentication. If that upstream artifact expires, stop rather
than silently substituting another wheel; clean-host source-build recovery is
still an open packaging task.

## 3. Preflight

From the repository root:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/preflight.sh
```

This reads the model twice and fails unless the publisher identities, direct
backing-store reads, and ordinary cache-path reads all agree. It also checks
the OS boundary, memory, Docker, user groups, two render devices, and exact
container image.

## 4. Launch, check, and benchmark

For the selected dynamic MTP service:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-dynamic-mtp-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-dynamic-mtp-server.sh

OUT_DIR=/path/to/new-dynamic-mtp-attempt \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-dynamic-mtp.sh
```

The benchmark requires the single-user gate, a complete output-isolated c64
batch, at least 98% of the prior replicated aggregate result, sequential baseline
agreement, and 512/512 concurrent exact-answer checks. The service is limited
to 256 total tokens and is not the long-context profile.

For the original portable target-only baseline, in the serving terminal:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh
```

The first start may spend about 88 seconds compiling. In another terminal:

```bash
curl -fsS http://127.0.0.1:18087/health

OUT=/path/to/result.json \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench.sh
```

Read the reproduction guide before comparing results: its prompt shape,
quality boundary, zero-cache requirement, and experimental TP2 graph warning
are part of the result identity.

To reproduce the optimized 128-slot short-context profile instead, use the
dedicated wrapper and its full quality battery:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-w8a16-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-concurrency-server.sh

OUT_DIR=/path/to/new-w8a16-attempt \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-concurrency.sh
```

That service is deliberately limited to 256 total tokens. Its 1,112.57 tok/s
aggregate result must not be presented as a 32K-context measurement.

For the distinct MTP1 interactive profile:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-mtp1-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh

OUT_DIR=/path/to/new-mtp1-attempt \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1.sh
```

This wrapper uses Qwen's bundled `mtp.safetensors`, one speculative token,
the upstream mixed-batch GDN fix, and `max_num_batched_tokens=512`. It records
single-user decode, an output-audited c8-c128 ladder, 7/7 sequential quality,
8/8 repeat stability, and a 512-request c64 semantic canary. Its measured peak
is c64; c128 is lower. It has no measured 32K point.

For the measured 2K through 32K operating profile, launch the distinct
one-slot service and run its exact-token sweep:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-depth-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-depth-server.sh

OUT_DIR=/path/to/depth-result \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-depth.sh
```

This profile is target-only/MTP0 with official block-FP8 weights, FP16
activations/KV, the W8A16 overlay, one service slot, 33,024-token capacity,
and 4,096-token chunked-prefill batches. Its repeated-token fixture
is shape evidence, not natural-prose latency evidence. The published prompt
rate is explicitly `prompt tokens / HTTP TTFT`; it includes scheduling and
first-token work and is not a kernel-only prefill rate.

For the distinct output-audited concurrency profile, start a new server with
64 active slots:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-concurrency-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-concurrency-server.sh

OUT_DIR=/path/to/new-attempt \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-concurrency.sh
```

The concurrency wrapper enables direct oneCCL P2P access; the single-slot and
depth launch identities remain P2P-off. The published profile uses two such
attempts on separate fresh servers. Each request uses a unique short prompt,
returns 128 raw token IDs, and must pass cache-zero and cross-task
output-isolation checks. c1-c64 are active-service measurements. At c64,
aggregate throughput is `774.394144 tok/s` with median and p95 TTFT of
`768.749 / 1,525.973 ms`. See the
[qualified result](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.md)
and [structured evidence](../../experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.json).

## 5. Stop and recover

```bash
docker stop -t 20 qwen38-fp8-tp2
# If you launched the concurrency profile instead:
docker stop -t 20 qwen38-fp8-tp2-concurrency
# If you launched MTP1 instead:
docker stop -t 20 qwen38-fp8-block-w8a16-mtp1-tp2-p128
# If you launched the selected dynamic MTP profile:
docker stop -t 30 qwen38-fp8-w8a16-dynamic-mtp-tp2
```

Do not interrupt graph initialization. If startup fails, preserve the complete
container output and the preflight output before changing settings. Do not
silently reduce precision, context, memory policy, graph mode, or GPU count;
that creates a different lane. Full beginner recovery and clean-host install
instructions remain an explicit certification gap.
