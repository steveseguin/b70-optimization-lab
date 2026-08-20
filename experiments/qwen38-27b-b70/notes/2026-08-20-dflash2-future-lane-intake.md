# DFlash 2 future-lane intake for Qwen3.8 27B

Date: 2026-08-20

Status: future research intake; **not a lab result or active AutoRound lever**

## What is actually upstream

llama.cpp PR
[`#27342`](https://github.com/ggml-org/llama.cpp/pull/27342) adds DFlash 2's
grouped dynamic depthwise convolution and candidate selector. As of this note
the PR is **open**, not merged. Its own Qwen3.8 Q4_K_M test is Apple M5 Pro,
eight GSM8K prompts, concurrency one: `10.42 tok/s` target-only versus
`18.89` Q4_K_M DFlash2, with mean accepted length `5.03`.

Useful same-thread counterevidence shows that the gain is not universal:

- a 22-sample RTX 3090 result at 32K reported MTP `57.79 tok/s` versus
  DFlash2 `62.21 tok/s` (`+7.6%`, much smaller than the intake claim);
- a B70 commenter reported nearly 3x in a private single-request scenario at
  width 5, but no absolute result/raw packet, and said concurrency 2 fell near
  baseline while concurrency 4 fell near `1 tok/s`;
- other reports show strong sensitivity to draft width, prompt domain,
  context, draft quantization, multimodal input, and device placement.

The maintainer also supplied an X post claiming roughly `77–81 tok/s` DFlash2
versus `67–71 tok/s` native MTP on one RTX 4090 at 90K–150K contexts. The
original post/raw logs were not independently retrieved, so those values stay
third-party anecdote.

## Why it does not transfer directly to the active lane

The active `101.170 tok/s` working anchor is vLLM/XPU, AutoRound W4A16,
two-B70 TP2, short cold prompts, and native MTP5. PR #27342 is llama.cpp/GGUF
with a separate DFlash2 draft checkpoint. Changing to it changes runtime,
target quantization, draft architecture, parallelism, context regime, and
benchmark identity simultaneously.

SGLang documents DFlash support, and vLLM has an open DFlash bring-up tracker,
but that does not prove this Qwen3.8 DFlash2 checkpoint works on the pinned XPU
fork. No Intel XPU TP2/multi-GPU or multimodal promotion evidence exists here.

## LocalMaxxing intake

A read-only query of the newest 100 public speed tests on 2026-08-20 found six
command snippets naming DFlash2: four identified as R9700/RTX 5090 and two with
no GPU name, ranging from about `27` to `282 tok/s`. None used B65 or B70.
Their models, contexts, targets, metrics, and software are heterogeneous, so
the range identifies interest, not a comparable record or a transferable
optimization.

## When to test

Revisit after the current margin-free oracle and TP1 determinism work, or if
the native-MTP lane reaches a genuine impasse. Start as a new one-B70
llama.cpp/GGUF lane:

1. Pin the PR/merge commit, target and draft revisions and hashes.
2. Prove text correctness and target verification before timing.
3. Use the fixed cold realistic suite and compare target-only, native MTP, and
   DFlash2 on the same single B70.
4. Sweep width narrowly (`3`, `4`, `5`) while recording acceptance, VRAM,
   context ceiling, prefill, TTFT, and full decode.
5. Only after TP1 passes, test tensor split/concurrency as separate identities;
   do not assume the CUDA single-device result predicts SYCL multi-GPU.
