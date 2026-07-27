# Qwen3.6 35B A3B UD Q4_K_M on 2x Intel Arc Pro B70 (llama.cpp SYCL)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | unreviewed |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until `B70-tested` |

## Provenance

- Contributor: dominick253
- Source PR or URL: PR to steveseguin/b70-optimization-lab
- Commits: pending
- Right-to-submit statement present: yes
- Third-party material and attribution: Model from unsloth/Qwen3.6-35B-A3B-UD via LMStudio

## Claim

llama.cpp SYCL serves Qwen3.6-35B-A3B-UD in Q4_K_M quantization on 2x Intel
Arc Pro B70 with MTP speculative decoding, 512K context, and reasoning enabled.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2x Intel Arc Pro B70, 32GB each |
| OS / kernel | Ubuntu 26.04 LTS / 7.0.0-28-generic |
| GPU driver (`i915` / `xe`) and version | xe, GuC 70.58.0 (bmg_guc_70.bin) |
| compute-runtime / level-zero | host runtime matches kernel |
| Engine / image and exact version | llama.cpp fb92d8f18, build-intel, IntelLLVM 2026.1.0 |
| Model repo and revision | unsloth/Qwen3.6-35B-A3B-UD (via LMStudio) |
| Quantization (weights / KV / activations) | Q4_K_M (weights), Q8_0 (KV cache) |
| Command and environment variables | See README.md; ZE_AFFINITY_MASK, GGML_SYCL_ENABLE_FLASH_ATTN, etc. |
| Prompt / output / context lengths, concurrency | 512K context, 2048 batch, 512 ubatch |
| Cache and speculation policy | MTP draft-n-max 2, no KV cache reuse |
| Metric definition, repeats, dispersion, TTFT | Working; not yet speed-benchmarked |
| Logs / JSON / durable links | N/A |

## Reference Lab Environment

Pending maintainer validation on B70 reference lab.

## What Was Actually Run Here

Recipe tested on host with 2x B70, Ubuntu 26.04, xe driver. Both endpoints
(8001/GPU0, 8002/GPU1) serve successfully. Not yet speed-benchmarked or
quality-gated.

## Known Issues

None identified in review.

## Open Questions For The Contributor

- Speed benchmark results (tok/s)
- Quality gate results (exactness, canary tests)
- Whether Q8_0 KV cache is necessary or if Q4_K_M KV is sufficient

## Disposition

Awaiting maintainer validation. If reproduced in reference lab, can graduate
to `B70-tested` and move into `repro/`.
