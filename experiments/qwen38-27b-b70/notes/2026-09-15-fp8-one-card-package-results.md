# One-card FP8 package: final measurements (R310)

Measurements for the [one-card FP8 package](../../../packages/qwen38-27b-fp8-tp1-b70/README.md) and
[recipe](../../../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md). Measured September 15, 2026 on the published R310 image
`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04`.

Every row uses one B70, official Qwen3.8-27B-FP8, FP16 activations and KV, one user, prompt caching off, 4,096
batched tokens, host input embedding and decode-identical verifier rows. No head-group overlay: the R310 kernel fix
replaces it.

## Strict suite (12 prompts, 512-token answers, cache zero)

| Profile | Context | Writing speed (tokens 1-100) | Full answers | Outputs vs no MTP |
| --- | ---: | ---: | ---: | --- |
| MTP depth 5, INT4 draft shortlist | 13,824 | 53.452 / 53.545 / 53.61 (three fresh servers) | 45.05 / - / 45.32 | 12/12 each |
| MTP depth 5, FP16 draft shortlist | 12,544 | 51.61 | 43.22 | 12/12 |
| No MTP | 20,480 | 19.406 / 19.40 | 19.29 / 19.28 | reference |

By MTP depth (INT4 draft shortlist, same image; every row 12/12 identical to no MTP):

| MTP depth | 0 | 3 | 4 | 5 | 6 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Writing speed (tokens 1-100) | 19.406 | 48.456 | 50.465 | 53.452 / 53.545 | 54.778 |
| Full answers | 19.29 | 43.78 | 45.26 | 45.05 / 45.31 | 44.75 |
| Context | 20,480 | 13,824 | 13,824 | 13,824 | 12,544 |

## Prompt length screen (2 repeats per content type, 128-token continuations)

| Input tokens | Prefill: depth 5 INT4 / FP16 / no MTP | Writing after the prompt: depth 5 INT4 / FP16 / no MTP | Time to first token, depth 5 INT4 |
| ---: | --- | --- | ---: |
| 2,048 | 2,025 / 2,010 / 2,214 | 56.5 / 49.7 / 19.3 | 1.02 s |
| 4,096 | 2,043 / 2,035 / 2,189 | 65.1 / 61.6 / 19.0 | 2.01 s |
| 8,192 | 2,021 / 2,016 / 2,134 | 72.3 / 68.4 / 18.8 | 4.06 s |
| 12,288 | 1,987 / 1,981 / 2,087 | 61.7 / 61.5 / 18.6 | 6.20 s |

At 512 input tokens: prefill 1,370 (depth 5) and 1,650 (no MTP) tok/s. Depth 5 reads prompts about 5-17% slower than no
MTP because the draft layer also processes the prompt. Writing speed after a prompt depends on how predictable the
continuation text is, so it is not a smooth function of length. Every continuation repeated exactly and matched no MTP.

## Quality and determinism

- Chat-mode quality suite (exact answers, JSON, repeat hash, 7,617-token needle): depth 5 INT4 and FP16 shortlist both
  match no MTP exactly.
- 21-request history replay on no MTP with logprobs: zero token and zero logprob differences.
- 200-repeat GDN stage census: 0 mismatches at 1K-8K tokens (was 7-71 of 200 before R310).

## Package end-to-end test

`packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py` was run as a user would:

1. Pull the published image by digest.
2. Start from a new state directory with the default port.
3. Wait for `Ready` after the built-in warm-up.
4. Run the strict suite.
5. Run `status`, then `stop`.

| Profile | Strict writing speed | Outputs vs no MTP | Stop |
| --- | ---: | --- | --- |
| `recommended` | 53.605 tok/s | 12/12 | clean |
| `no-quantization` | 51.705 tok/s | 12/12 | clean |

Receipts: [data/2026-09-15-fp8-one-card-package](../data/2026-09-15-fp8-one-card-package/). Background:
[determinism work](2026-09-15-fp8-one-card-gdn-prefill-nondeterminism.md), [depth and draft matrix](2026-09-15-fp8-one-card-depth-draft-matrix.md).
