# Qwen3.8 AutoRound INT4 upstream vLLM/XPU frontier audit

Date: 2026-08-18

Status: **closed audit; no direct candidate transferred**

## Compared identities

- local vLLM base: `44fc8fde09fc311d3099dab10366b672d9142ea4`;
- official vLLM `main` inspected at
  `f9f066d195ca079c7403d9d9447c6b1d740c348c`;
- local XPU-kernels base:
  `2dd55f380df753a10a88fcd9e96192561066e713`;
- official XPU-kernels `main` inspected at
  `1fd7c92004ed1f155e4e116fbffe47f837b70faa`.

The comparison was limited to changes matching the measured dense Qwen3.8
TP2 decode path: XPU, GDN, native MTP, graph/compile, oneDNN W4A16, output
head, and collectives.

## Findings

1. [XPU-kernels PR 492](https://github.com/vllm-project/vllm-xpu-kernels/pull/492)
   upgrades the vendored oneDNN revision to 3.13. The pinned local base already
   contains its merge commit `07d44bc`; rebuilding solely for this change
   would duplicate the active identity.
2. Official XPU-kernels after the pinned base adds
   `fp8_gemm_out` (`1fd7c920`) for zero-copy AsyncTP shard writes. The target
   and draft here are W4A16/INT8/INT4, not FP8, so that code is not on this
   lane's hot path.
3. vLLM `cdb8545a9` broadens fused GDN MTP head-ratio support to Qwen's 3:1
   ratio, but the implementation is the CUDA stable-kernel path guarded by
   `self.gdn_decode_kernel == "cuda"`. It does not replace the local native
   XPU GDN transaction.
4. vLLM `7b544ecb5` fuses a trailing MTP all-reduce and adds local-argmax draft
   tokens for DeepSeek V3.2's NVIDIA model. The local Qwen3.5/Qwen3.8 model and
   logits processor already implement `get_top_tokens` plus the XPU TP local
   argmax reduction; the model-specific patch does not apply.
5. [vLLM issue 51008](https://github.com/vllm-project/vllm/issues/51008)
   documents avoidable PIECEWISE/eager proposer dispatch on stock Qwen MTP.
   This fork already uses the proposer cudagraph dispatcher and its promoted
   full-graph transaction/captured-GDN work. Transplanting the stock issue's
   premise would not establish a new executed path here.
6. [XPU-kernels PR 494](https://github.com/vllm-project/vllm-xpu-kernels/pull/494)
   is an unmerged fused MoE gate/up kernel. Qwen3.8-27B is dense, so it is out
   of scope.

## Decision

Do not churn the validated runtime for these upstream revisions. The current
high-value arms remain:

- make the `97-99 tok/s` compiled fast lane reproducible by isolating Python
  traversal, max-autotune, coordinate-descent, and combo benchmarking, then
  seal the winning compile cache;
- improve native-MTP acceptance with the bounded original-weight top-K draft
  reranker only if its extra work clears a direct speed/acceptance gate; and
- retain the packed-GDN ordinary-code-shape operator oracle as the source-side
  route back to fresh-compile arithmetic identity.

Reopen this audit only when official vLLM/XPU gains a dense W4A16, Qwen GDN,
Qwen native-MTP, or XPU graph change after the identities above.
