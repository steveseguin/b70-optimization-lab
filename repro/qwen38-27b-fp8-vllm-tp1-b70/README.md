# Qwen3.8 27B official FP8 on one Intel Arc Pro B70: recipe

> **Status: `candidate-portable-repro`.** The current R312d-c package was
> accepted on the configured lab host on October 4: 12/12 strict outputs equal
> to no MTP, exact sequential/context/quality checks and a clean stop.
> [Receipts](../../experiments/qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/).
> A machine without Intel drivers, Docker or the model in place is untested.
> Public container availability does not certify a clean source rebuild.

Quick start and daily use: [package guide](../../packages/qwen38-27b-fp8-tp1-b70/README.md).

## Current recipe (reviewed October 10, 2026)

Use the [package quickstart](../../packages/qwen38-27b-fp8-tp1-b70/README.md#start)
for acquisition, hash verification, launch, health and graceful stop. It runs the
27B dense model on **one** B70. Flash-Next's 46.854250 tok/s record is a different
125B-A6B model on **four** B70s; the 875 tok/s result is the 27B model on **two**
cards with many short requests, not one person's writing speed.

The current runtime is **R312d-c**, not the R310 build documented in the
historical section below. Pull its exact public image:

```bash
docker pull ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a
```

The registry name says INT4 because packages share a runtime. The model remains
`Qwen/Qwen3.8-27B-FP8`, revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, with FP16 activations and full
16-bit KV. The package's download and verify helpers use the shared
[complete model hash manifest](../qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json).
Run them before launch; a file's size alone is not verification.

| Current profile | Total context | Strict writing tok/s | Reading tok/s at 2K / 8K / 16K |
| --- | ---: | ---: | --- |
| `recommended`, target-verified MTP5 | 32,768 | 54.036484 | 2,031 / 2,023 / 1,939 |
| `max-context`, target-verified MTP5 | 40,960 | 54.02 | 2,028 / 2,018 / 1,936 |
| `no-quantization`, FP16 draft shortlist | 28,672 | 52.19 | 2,019 / 2,014 / 1,932 |

These are the [October 4 package acceptance receipts](../../experiments/qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/).
The recommended figure is the median of two strict passes on one fresh package
server, 54.047 / 54.026; the independent research-server pair is separately
retained in the package manifest. Each strict attempt sends the fixed 12 varied
prompts once, with a 512-token natural-completion cap and no prompt reuse.
Writing speed uses class-balanced medians across 99 intervals after TTFT.
Reading speed divides input tokens by server prefill time; it is not HTTP TTFT.
512-token reading speed on this exact current profile is **not measured**.

On a prepared host, run the package's start command, then this client once into
a new output directory:

```bash
OUT_DIR=/path/new-strict-attempt BASE_URL=http://127.0.0.1:18130 MODEL_NAME=qwen38-27b-fp8 \
  bash repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py status --state-dir /path/fp8-one-card-session
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py stop --state-dir /path/fp8-one-card-session
```

Use the same state directory as the quickstart. A speed-suite pass alone does
not prove losslessness: compare all token arrays with the retained no-MTP
references using the [acceptance campaign](../../experiments/qwen38-27b-b70/scripts/run-20260918-fp8-onecard-r312d-campaign.py),
which documents the sequential oracle, context, chat and logprob checks.
Its historical host paths need adapting; do not silently substitute a new
oracle or reduce its quality gates. The source and exact binary pins are in the
[package manifest](../../packages/qwen38-27b-fp8-tp1-b70/package.json).

## Platform and rebuild boundary

A new user needs Linux with Intel B70 driver support, Docker, Python 3, curl,
one free 32 GiB B70, roughly 16 GiB host RAM and 60 GiB disk. The retained
October 4 host used kernel `7.0.0-38`; the older
[platform inventory](../qwen38-27b-fp8-vllm-tp2-asrock-b70/preflight-evidence-20260821.json)
is historical and does not certify current driver installation. The container
pins user-space dependencies; it does not pin or install the host kernel.
A tested clean-OS driver/Docker installation and independent-host replay remain
open. No driver, power, swap or page-cache change is part of this recipe.

The current rebuild chain is R310 → R311 checkpoint kernels → R312c host glue
→ R312d variant **c** device attention library. Source entrypoints:

- [R310 builder](../../experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r310-gdn-barriers.sh)
  and [Dockerfile](../../experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r310-gdn-barriers).
- [R311 builder](../../experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r311-gdn-checkpoint.sh)
  and [Dockerfile](../../experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r311-gdn-checkpoint).
- [R312c builder](../../experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r312c-multiq.sh)
  and [Dockerfile](../../experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r312c-multiq).
- [R312d builder](../../experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r312d-multiq-toolchain.sh),
  [builder image](../../experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r312d-builder-b)
  and [runtime Dockerfile](../../experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r312d-multiq).

The final attention build requires DPC++ 2026.0.0, IGC 2.34.4, ocloc 26.18 and
the kernel CMake's pinned sycl-tla commit `87f6850`; another revision changed
output bits in the retained census. The builders still assume earlier build
trees and local image tags. They are source recovery evidence, not a closed
fresh-host build script. Their historical swap allowances are not current
instructions: any authorized future build must set equal memory and memory-swap
limits and use a suitable host. Use the digest-pinned public image for the
current replay. The [source publication manifest](../qwen38-27b-autoround-int4-b70/publication-manifest.json)
remains draft; this guide does not upgrade it to published source closure.

## Historical results and R310 build

The rest of this guide preserves the earlier R310/R311b measurements and build
route. Its images, context limits and numbers do not replace the current package.

## Results

One B70, official FP8 weights, FP16 activations and KV cache, one user, prompt
caching off. Writing speed is the lab's strict 12-prompt suite. Prefill is
server-side prompt reading.

| Profile | Context | Writing speed | Full answers | Prompt reading 2K / 4K / 8K / 12K | Writing after 2K / 4K / 8K / 12K input |
| --- | ---: | ---: | ---: | --- | --- |
| MTP depth 5, INT4 draft shortlist, single-checkpoint state (`recommended`, R311b, 2,048-token chunk) | 32,768 | **54.3** | | 2,031 / – / 2,019 / (16K: 1,935) | 57.3 / – / 72.9 / (16K: 62.3) |
| `max-context`: the same at 0.983 memory | 40,960 | 54.3 | | 2,024 / – / 2,011 / (16K: 1,930) | 57.1 / – / 72.9 / (16K: 62.4) |
| `no-quantization` (FP16 draft shortlist), single-checkpoint state | 28,672 | 52.4 | | 2,014 / – / 2,008 / (16K: 1,927) | 50.2 / – / 69.0 / (16K: 59.4) |
| the R310 `recommended` (September 17 morning, six state copies) | 24,576 | 53.4 | 45.3 | 2,026 / – / 2,017 / (16K: 1,934) | 56.6 / – / 72.2 / (16K: 62.0) |
| the R310 `max-context` | 30,720 | 53.5 | | 2,018 / – / 2,010 / (16K: 1,929) | 56.4 / – / 72.1 / (16K: 61.8) |
| the same at 16,384 tokens, 4,096-token chunk (September 16) | 16,384 | 53.5 | 45.3 | 2,025 / 2,041 / 2,021 / 1,986 | 56.5 / 65.0 / 72.1 / 61.5 |
| MTP depth 4, INT4 shortlist, 0.983 memory (one research server; every gate exact; not a shipped profile) | 32,768 | 51.0 | | | |
| the R310 `no-quantization` | 20,480 | 51.8 | 43.2 | 2,012 / – / 2,009 / (16K: 1,925) | 49.7 / – / 68.6 / (16K: 59.0) |
| No MTP (reference) | 20,480 | 19.4 | 19.3 | 2,214 / 2,189 / 2,134 / 2,087 | 19.3 / 19.0 / 18.8 / 18.6 |

All speeds are tokens/s.

**Quality:** outputs are identical to the no-MTP reference on:

- the 12-prompt strict suite, on fresh servers
- 128-token continuations after 512 to 12,288-token prompts, with every request
  repeated
- a chat quality suite: exact answers, JSON, repeat stability, and a 7,600-token
  needle

Repeating the same request returns the same token scores, bit for bit.

Other depths on the same setup:

| MTP depth, INT4 draft shortlist | 3 | 4 | 5 | 6 |
| --- | ---: | ---: | ---: | ---: |
| Writing speed (strict suite) | 48.46 | 50.47 | 53.50 | 54.78 |
| Full answers | 43.78 | 45.26 | 45.18 | 44.75 |
| Context measured | 13,824 | 13,824 | 13,824 | 12,544 |

The depth comparison was measured at those contexts; depth 5 was then confirmed
at 16,384 tokens on two fresh servers (53.576 / 53.454 tok/s) and, on September 17,
at 24,576 tokens with a 2,048-token prefill chunk on two more (53.43 / 53.43 tok/s;
[receipts](../../experiments/qwen38-27b-b70/data/2026-09-17-fp8-onecard-24k/)). The smaller
chunk lowers peak activation memory by 0.35 GiB (2.55 to 2.9 GiB of KV) at no measured cost.
On the afternoon of September 17 the R311b image's single-checkpoint recurrent state (one GDN
state block per request instead of six; [design and results](../../experiments/qwen38-27b-b70/notes/2026-09-17-gdn-single-checkpoint-plan.md))
raised the KV budget from 26,178 to 40,140 tokens at 0.975, and 32,768 tokens became the package
default on two more fresh servers (54.36 / 54.29 tok/s, every gate exact including the logprob
replay; [receipts](../../experiments/qwen38-27b-b70/data/2026-09-17-fp8-onecard-32k/)).
Its no-MTP reference runs at the 896-token attention block the larger page implies and is
12/12 identical to the 832-token reference.
Depth 6 writes a little faster but finishes whole answers slightly slower and fits
less context, so depth 5 stays the default. Both profiles also passed the 64-prompt
sequential oracle plus queued passes against no-MTP
([review](../../experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md)).

## What makes it work

| Piece | Why | File |
| --- | --- | --- |
| Input embedding in host memory | Frees 2.37 GiB so the model, draft and cache fit on 32 GiB; exact lookup | [b70_cpu_embed.py](../../packages/qwen38-27b-fp8-tp1-b70/overlays/b70_cpu_embed.py) |
| oneDNN fixed-K W8A16 for one-card shapes | Results no longer depend on how many draft tokens are checked at once | [patch r309](../../experiments/qwen38-27b-b70/patches/onednn-qwen38-w8a16-fixed-k-tp1-shapes-r309-20260915.patch) |
| GDN output kernel memory fences | Removes a race that changed prefill results between identical requests | [patch r310](../../experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-fwd-o-global-barriers-r310-20260915.patch) |
| Draft checks computed like normal decode | Long prompts give the same answer with and without MTP | [b70_fa_verify_rows.py](../../packages/qwen38-27b-fp8-tp1-b70/overlays/b70_fa_verify_rows.py) |
| Optional FP16 draft shortlist | No INT4 copy anywhere | [b70_draft_fp16_shortlist.py](../../packages/qwen38-27b-fp8-tp1-b70/overlays/b70_draft_fp16_shortlist.py) |

## Build the runtime image yourself

The prebuilt image is `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04` (image ID
`sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04`).
To build it from public sources instead:

1. Pull the base runtime:
   `docker pull ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`.
2. Build the kernels (about 15 minutes, host oneAPI 2026.1):
   `BUILD_ROOT=/path/new-dir bash experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r310-gdn-barriers.sh`.
3. Copy `_xpu_C.abi3.so` and `libgdn_attn_kernels_xe_2.so` from
   `$BUILD_ROOT/compile/install/vllm_xpu_kernels/` next to
   [Dockerfile.r310-gdn-barriers](../../experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r310-gdn-barriers).
   Then run `docker build --build-arg BASE=<base image> .` there.

## Launch and measure

```bash
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py start --model-dir /path/qwen3.8-27b-fp8 --state-dir /path/session
OUT_DIR=/path/strict BASE_URL=http://127.0.0.1:18130 MODEL_NAME=qwen38-27b-fp8 \
  bash repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
python3 experiments/qwen38-27b-b70/scripts/bench-prefill-followup.py --base-url http://127.0.0.1:18130 \
  --model qwen38-27b-fp8 --out /path/context --corpus experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/corpus.json \
  --lengths 2048,8192,16384 --max-model-len 24576 --max-tokens 128 --repeats 2
```

## Evidence

- [One-card determinism and long-context identity](../../experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-gdn-prefill-nondeterminism.md)
- [Depth and draft-head matrix](../../experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-depth-draft-matrix.md)
- [Final measurements](../../experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-package-results.md)
