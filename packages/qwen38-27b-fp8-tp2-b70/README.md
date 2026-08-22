# Qwen3.8 27B FP8 — two-B70 candidate package

This is the first distribution-package front door. It uses Qwen's official
FP8 model and a digest-pinned vLLM XPU container on two Intel Arc Pro B70
32 GiB cards. The lab reproduction reached `21.708532 tok/s` decode and passed
the recorded semantic, repeat, and long-context gates.

> **Status: candidate, not a beginner install guide.** The exact model,
> container, configuration, commands, and evidence are present. A clean Ubuntu
> host installation of the Intel driver and Docker prerequisites has not yet
> been replayed, so this package does not install or modify host drivers.

The technical source of truth is the
[`reproduction guide`](../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md).
The machine-readable front door is [`package.json`](package.json).

## Who built what

**neural.download lab — integrated:** B70/XPU integration, graph and quality
validation, direct-I/O model verification, and this digest-pinned package. The
packaged route measured `21.708532 tok/s` and passed the recorded semantic,
repeat, and long-context gates. No project patch is applied; the model and
container remain the pinned upstream artifacts. See the
[lab evidence](../../experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md).

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

No project patch is required for this baseline.

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

In the serving terminal:

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

## 5. Stop and recover

```bash
docker stop -t 20 qwen38-fp8-tp2
```

Do not interrupt graph initialization. If startup fails, preserve the complete
container output and the preflight output before changing settings. Do not
silently reduce precision, context, memory policy, graph mode, or GPU count;
that creates a different lane. Full beginner recovery and clean-host install
instructions remain an explicit certification gap.
