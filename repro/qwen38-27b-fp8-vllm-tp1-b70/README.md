# Qwen3.8 27B official FP8 on one Intel Arc Pro B70: recipe

> **Status: `candidate-portable-repro`.** Built, launched and measured on the lab
> host from the files below. A clean install on another host is still pending.

Quick start and daily use: [package guide](../../packages/qwen38-27b-fp8-tp1-b70/README.md).

## Results

One B70, official FP8 weights, FP16 activations and KV cache, one user, prompt
caching off. Writing speed is the lab's strict 12-prompt suite. Prefill is
server-side prompt reading.

| Profile | Context | Writing speed | Full answers | Prompt reading 2K / 4K / 8K / 12K | Writing after 2K / 4K / 8K / 12K input |
| --- | ---: | ---: | ---: | --- | --- |
| MTP depth 5, INT4 draft shortlist (`recommended`) | 13,824 | **53.5** | 45.2 | 2,025 / 2,043 / 2,021 / 1,987 | 56.5 / 65.1 / 72.3 / 61.7 |
| MTP depth 5, FP16 draft shortlist (`no-quantization`) | 12,544 | 51.6 | 43.2 | 2,010 / 2,035 / 2,016 / 1,981 | 49.7 / 61.6 / 68.4 / 61.5 |
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
| Context | 13,824 | 13,824 | 13,824 | 12,544 |

Depth 6 writes a little faster but finishes whole answers slightly slower and
fits less context, so depth 5 is the default.

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
  --lengths 2048,4096,8192,12288 --max-model-len 13824 --max-tokens 128 --repeats 2
```

## Evidence

- [One-card determinism and long-context identity](../../experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-gdn-prefill-nondeterminism.md)
- [Depth and draft-head matrix](../../experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-depth-draft-matrix.md)
- [Final measurements](../../experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-package-results.md)
