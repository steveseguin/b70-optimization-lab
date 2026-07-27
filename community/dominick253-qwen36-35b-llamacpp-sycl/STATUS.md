# Qwen3.6 35B A3B Q8_0 on Intel Arc B70 (llama.cpp SYCL)

Copy this file to `community/<entry>/STATUS.md` and fill it in. Delete guidance
lines that do not apply. Mark unknown fields `unknown` rather than guessing.

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
- Source PR: community submission (PR pending)
- Commits: pending
- Right-to-submit statement present: yes
- Third-party material: llama.cpp (GGML project), Qwen3.6-35B-A3B (Qwen team, Apache 2.0)

## Claim

The contributor reports a working llama.cpp SYCL deployment of `Qwen3.6-35B-A3B`
in Q8_0 quantization on Intel Arc B70 with MTP speculative decoding (n-max=3),
serving on port 8001 with 512K context and reasoning enabled.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | Intel Arc B70 (Battlemage G31, 8086:e223), count unstated |
| OS / kernel | Ubuntu 26.04 LTS, kernel 7.0.0-28-generic |
| GPU driver (`i915` / `xe`) and version | xe (version unstated) |
| compute-runtime / level-zero | unknown |
| Engine / image and exact version | llama.cpp fb92d8f18, IntelLLVM 2026.1.0, SYCL backend |
| Model repo and revision | Qwen/Qwen3.6-35B-A3B (Unsloth Dynamic 2.0 GGUF) |
| Quantization (weights / KV / activations) | Q8_0 (weights and KV) |
| Command and environment variables | See README.md |
| Prompt / output / context lengths, concurrency | Context 512K (512000), slots 2 |
| Cache and speculation policy | draft-MTP n-max=3 |
| Metric definition, repeats, dispersion, TTFT | unknown |
| Logs / JSON / durable links | none |

## Reference Lab Environment

Not yet tested in the reference lab.

## What Was Actually Run Here

Nothing. This is a community submission awaiting validation.

## Findings

None yet.

## Known Issues

None identified during review.

## Open Questions For The Contributor

1. GPU count and VRAM per card.
2. compute-runtime / level-zero versions.
3. Benchmark methodology: how was speed measured, how many repeats, cold or warm?
4. Any logs or JSON from the original run.

## Disposition

Entry stays in `community/` at `community-reported` level until validated on B70.
