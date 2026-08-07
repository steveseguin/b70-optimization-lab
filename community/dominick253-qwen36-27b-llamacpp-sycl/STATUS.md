# Qwen3.6-27B MTP Q4_K_M llama.cpp SYCL service

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | read and executed here (inspection only) |
| Tested in reference lab | no — service inspected on contributor VM |
| Safe to merge as documentation | yes, with explicit benchmark boundary |
| Eligible for `repro/` or `results/` | no |

## Provenance

- Contributor: `dominick253`
- Source: new contribution
- Base commit: upstream `main` at contribution time
- Right-to-submit statement: yes
- Third-party material: llama.cpp and llama-benchy are referenced, not vendored

## Claim

The contributor's VM runs two independent Qwen3.6-27B MTP Q4_K_M llama.cpp
SYCL servers, one per Intel Arc Pro B70, on ports 8001 and 8002.

## Contributor environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2x Intel Arc Pro B70 / 32 GiB each |
| OS / kernel | Ubuntu 24.04.4 LTS / `6.17.0-1009-intel` |
| GPU driver | `xe` |
| Compute runtime | Intel oneAPI environment, Level Zero selector |
| Engine / exact version | llama.cpp commit `15586e2d7`; `build-sycl` |
| Model | `Qwen3.6-27B-MTP-GGUF/Qwen3.6-27B-Q4_K_M.gguf`; 17,106,773,120 bytes; revision/checksum unknown |
| Quantization | Q4_K_M weights; F16 target and draft KV |
| Command | documented in `README.md`; installed launcher inspected at `/usr/local/bin/launch-llama-qwen36-27b-mtp.sh` |
| Context / concurrency | 150000; `--parallel 1`; one endpoint per GPU |
| Cache/speculation | F16 KV; draft-MTP, n-max 2, p-min 0.0; graph disabled |
| Metrics | no matching llama.cpp 27B benchmark packet supplied |
| Logs / JSON | none added; historical llama-benchy artifacts are a different vLLM recipe |

## Reference lab environment

No reference-lab execution was performed. The remote contributor VM was
inspected over SSH at `dom@192.168.122.109` on 2026-08-07. Both endpoints
reported healthy, and `/proc` command lines matched the documented per-GPU
architecture. No service was stopped, restarted, or modified.

## What was actually run here

- Inspected both systemd units and the shared launcher.
- Inspected the two live llama-server command lines and health endpoints.
- Confirmed the model path and file size.
- Confirmed llama.cpp source commit, OS/kernel, and GPU driver identity.
- Searched the prior session history and `/home/dom/llama-benchy` artifacts.
- Did **not** rerun llama-benchy or any other benchmark.

## Findings

1. The live recipe is one independent process per physical GPU, not tensor
   parallelism: selector 0 → port 8001 and selector 1 → port 8002.
2. The exact live launcher uses generic SYCL JIT, Flash Attention, F16 KV, 150K
   context, batch/ubatch 2048, and draft-MTP with two speculative tokens.
3. Existing `/home/dom/llama-benchy/results/` data is for the separate Intel
   vLLM `0.21.0-b2` INT4 service. It must not be presented as llama.cpp data.
4. The prior llama.cpp benchmark found in session history is for a 35B Q8/UD-Q8
   lane, not the live 27B Q4_K_M service. It is not included as 27B evidence.
5. Therefore this packet intentionally contains a recipe and provenance, but no
   performance table.

## Known issues

- Model revision and SHA-256 are not recorded.
- No matching llama.cpp 27B llama-benchy JSON, CSV, or log is available.
- The recipe currently binds `0.0.0.0`; network exposure should be reviewed.
- Reference-lab reproduction and quality gates remain outstanding.

## Open questions

- Capture the exact model revision and SHA-256.
- Run llama-benchy against both matching llama.cpp endpoints with raw JSON/CSV,
  prompt/output/context sizes, repeats, cold/cache policy, TTFT, and quality
  gates recorded.
- Record the exact oneAPI/compiler versions and kernel fault/restart checks.

## Disposition

Keep in `community/` as a `community-reported` recipe. This is suitable for
review because it accurately separates the inspected live configuration from
unmatched historical benchmark data. It should not move to `repro/` or
`results/` until a matching benchmark and quality evidence are preserved.
