# Learnings From The 2026-05-23 Bring-Up

## High-Level Learnings

- B70s can serve MiniMax M2.7 INT4 locally through vLLM when the XPU stack is aligned.
- The hardest problems were not model weights or HTTP serving; they were version/ABI compatibility and native compilation.
- The difference between total tokens per second and output tokens per second must be explicit. This run reached `110.90 total tok/s` but only `83.17 output tok/s`.
- The served endpoint later validated a `32768` token context window and warm
  OpenAI API decode around `84.1 output tok/s` after moving display duty to
  ASPEED VGA and booting with `xe.disable_display=1`.
- Prompt/prefill was healthy at about `1.7k-1.8k prompt tok/s` for 2k-16k
  prompts, but long-prompt time to first token is still visible.
- The current host's PCIe4 x16 fabric is a credible reason it trails older
  PCIe5-class `89-93` output-token notes: current 256 MiB XCCL allreduce
  measured `13.79 GB/s`, while the older reference measured `27.88 GB/s`.
- Quality gates are mandatory. Multiple optimization paths can produce plausible-looking speed while risking determinism or content quality.

## MiniMax-Specific Learnings

- The model is a large Mixture-of-Experts architecture.
- The relevant fast path is INT4 W4A16 MoE decode, not only dense attention.
- All 62 MoE layers can report the llm-scaler XPU INT4 decode path when configured correctly.
- `Lasimeri/MiniMax-M2.7-int4-AutoRound` occupies about `113 GB` locally.
- vLLM recognizes the architecture as `MiniMaxM2ForCausalLM`.
- The model's `generation_config.json` overrides default vLLM sampling with `top_k=40` and `top_p=0.95` unless `--generation-config vllm` is used.

## Runtime/API Learnings

The vLLM server provided these useful routes:

- `/health`
- `/metrics`
- `/v1/models`
- `/v1/completions`
- `/v1/chat/completions`
- `/v1/responses`
- `/v1/messages`
- `/tokenize`
- `/detokenize`

Binding to the LAN is just:

```bash
--host 0.0.0.0 --port 8000
```

The model id in requests can be the local model path:

```text
/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround
```

## Build Learnings

- Build `vllm-xpu-kernels` from source after installing the final PyTorch XPU wheel.
- Earlier 2026-05-20 runs used a `vllm-xpu-kernels==0.1.7` wheel; this
  Ubuntu 24.04 bring-up ended on an editable source build from
  `vllm-project/vllm-xpu-kernels`.
- Build llm-scaler after PyTorch is final too.
- Use oneAPI compiler 2025.3 directly.
- Keep `MAX_JOBS` conservative for native builds.
- The biggest compile unit was `paged_decode_xe2.cpp`.
- Temporary SSD swap is a practical workaround for low-RAM systems.

## Quality Gate Learnings

Passed checks:

- raw145 n64 exact token hash
- raw145 n256 exact token hash
- semantic suite
- arithmetic repeat
- extended sixpack

The first raw145 run took longer because it compiled graphs. Later runs reused caches.

## Serving Learnings

- `vllm serve` in this checkout does not accept `--async-engine`.
- vLLM still logged `Asynchronous scheduling is enabled`.
- The server successfully listened on `0.0.0.0:8000`.
- `/v1/models` initially reported `max_model_len: 2048` during the strict
  benchmark lane; the promoted serving wrapper now reports `max_model_len:
  32768`.
- `curl /health` returned `HTTP 200`.

## Problems Solved

- Installed Intel GPU runtime and oneAPI packages on Ubuntu 24.04.
- Downloaded the 113 GB MiniMax AutoRound model without relying on Xet.
- Downgraded PyTorch XPU from a failing 2.13 nightly to `2.11.0+xpu`.
- Rebuilt `vllm-xpu-kernels` from source to resolve ABI mismatch.
- Rebuilt llm-scaler custom kernels against the same PyTorch.
- Patched strict quality scripts for current CLI compatibility.
- Removed stale `--async-engine` from the serve wrapper.
- Created an OpenAI-compatible endpoint accessible on the LAN.

## Open Questions

- Can this same stack recover the earlier 89-94 output-token lane on PCIe4, or
  is most of the gap hardware fabric?
- Is the `ocloc` internal compiler error harmless because a fallback path succeeds, or is it masking a missed optimization?
- Can Intel publish a low-memory/prebuilt `vllm-xpu-kernels` package for B70?
- Which environment flags should be upstreamed into vLLM proper?
- Can anything above `32768` be made reliable, or is `32768` the practical
  stable ceiling for this stack? `33792` did not expose `/v1/models` in the wait
  window and is not promoted.
