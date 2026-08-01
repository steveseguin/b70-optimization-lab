# Qwen3.6 35B A3B UD-Q8_K_XL on Intel Arc B70 (llama.cpp SYCL)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | read, no execution |
| Tested in reference lab | no |
| Safe to merge as documentation | yes, after the maintainer corrections recorded here |
| Eligible for `repro/` or `results/` | no until `B70-tested` |

## Provenance

- Contributor: dominick253
- Source PR or URL: [PR #14](https://github.com/steveseguin/b70-optimization-lab/pull/14)
- Commits: `27469f01a`, `32f41bb09`, `6077da861`; maintainer corrections on
  2026-08-01 are explicitly identified in the README note and repository
  history
- Right-to-submit statement present: yes
- Third-party material and attribution: llama.cpp/GGML; Qwen3.6-35B-A3B from
  the Qwen team; GGUF conversion published by Unsloth

## Claim

The contributor reports that the `Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf` artifact
served successfully through llama.cpp/SYCL on two 32 GB Intel Arc B70 cards,
averaging 40.12 tok/s in the original MTP-on 200-token measurements and
approximately 45 tok/s in a later MTP-off control, with a configured context
ceiling of 512000 tokens.

These are contributor claims, not measurements from the reference lab.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | Intel Arc B70 (Battlemage G31, 8086:e223), 2 cards, 32 GB each |
| OS / kernel | Ubuntu 26.04 LTS / 7.0.0-28-generic |
| GPU driver (`i915` / `xe`) and version | xe; version unknown |
| compute-runtime / level-zero | unknown |
| Engine / image and exact version | llama.cpp `fb92d8f18`; IntelLLVM 2026.1.0; SYCL backend |
| Model repo and revision | `unsloth/Qwen3.6-35B-A3B-MTP-GGUF`; revision unknown |
| Quantization (weights / KV / activations) | UD-Q8_K_XL weights; implicit F16 KV because neither `-ctk` nor `-ctv` was supplied; activation precision unknown |
| Command and environment variables | Maintainer-corrected command in README; original command used MTP n-max=3, `ZE_AFFINITY_MASK=0,1`, and the listed SYCL variables |
| Prompt / output / context lengths, concurrency | reported prompts 5, 23, 57, and 96 tokens; 200-token requests and one 512-generated-token server-log row; configured `--ctx-size 512000`; 2 slots |
| Cache and speculation policy | F16 KV default; original measurements used draft-MTP n-max=3; later approximate control disabled MTP; independent-request cache behavior described as stateless |
| Metric definition, repeats, dispersion, TTFT | three 200-token streaming requests described as cold, 40.12 tok/s average and 34.96-42.74 range; first request approximately 35 tok/s and later requests approximately 42.5 tok/s; exact timing window and TTFT values unknown |
| Logs / JSON / durable links | no raw logs, payloads, responses, hashes, or structured summaries included in the PR |

## Reference Lab Environment

No runtime environment applies because no command, model load, container,
service, GPU probe, or benchmark from this contribution has been executed in
the reference lab. A candidate GGUF was pre-positioned for future validation at
Hugging Face revision `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`, size
`39099447584` bytes, and SHA-256
`6c6b816537abad90b250a0972b345466028d861ddfe316d5f0de31ca6440f781`;
recording this file identity is not execution evidence.

## What Was Actually Run Here

The maintainer performed source/documentation review only. The review checked
the two commands against their labels, compared the linked GGUF filename with
the stated quantization, reconciled the later MTP-off result recorded in the PR
discussion, recorded the pre-positioned candidate artifact identity, and
applied documentation/safety corrections. The model was not loaded. No
throughput, correctness, long-context, memory, MTP, or service behavior was
tested here.

## Findings

1. The download URL and file size support an artifact identity of
   `UD-Q8_K_XL`, not Q8_0. The title, paths, alias, and tables are corrected to
   that identity. The candidate file for future local validation is pinned by
   revision, byte size, and SHA-256 above, but has not been executed.
2. Neither submitted launch command provided `-ctk` or `-ctv`; the described
   run therefore used llama.cpp's F16 KV-cache default, not Q8_0 KV.
3. The contributor's later approximate control was about 45 tok/s with MTP off
   versus about 40 tok/s with MTP on. This contradicts the original conclusion
   that MTP was the primary throughput driver. The maintained recipe defaults
   MTP off and keeps MTP-on as an optional diagnostic.
4. An 86.5% draft acceptance rate does not by itself demonstrate end-to-end
   acceleration. Controlled same-prompt and same-runtime A/B evidence is still
   required.
5. `--ctx-size 512000` establishes a configured ceiling only. The longest
   reported measured prompt was 96 tokens; a 512-generated-token result is not
   a long-context test.
6. The contributor-reported throughput, MTP, reasoning, and GPU observations
   remain useful community evidence but are not reference-lab findings.

## Known Issues

- `README.md` (Model and Contributor Environment): the contributor's exact
  model revision and GGUF checksum are unknown. The locally pre-positioned
  candidate is pinned, but cannot yet be proven byte-identical to the file used
  for the reported benchmark.
- `README.md` (Contributor-Reported Benchmark Results): no raw logs, payloads,
  response/output hashes, generated-token timestamps, or machine-readable
  summary are present. The metric window and cold/warm state are not fully
  reproducible.
- `README.md` (Optional MTP Diagnostic): the later MTP-off result is
  approximate and lacks an attached same-prompt, same-sampling, same-runtime
  comparison. It supports the conservative default but not a promoted speed
  claim.
- `README.md` (Contributor Environment): 512000 was configured, but no
  long-context correctness, boundary, memory-pressure, or stability run was
  reported; measured prompts reached only 96 tokens.
- `README.md` (Reasoning Mode): one reported math smoke response is insufficient
  to establish general reasoning correctness or quality parity.
- `README.md` (systemd Service and Launch Script): the original root service,
  unauthenticated `0.0.0.0` listener, and broad `pkill -9` were unsafe copy
  defaults. The maintainer-corrected example uses an unprivileged account,
  loopback, and no forced kill. Deployers still must configure device/file
  permissions and any intended authentication/network boundary.

## Open Questions For The Contributor

No contributor response is required before merging this as community
documentation. To raise the evidence level, the maintainer validation should
capture or independently establish:

1. the full llama.cpp commit and Intel compute-runtime, Level Zero, compiler,
   kernel, and driver identities, plus confirmation whether the contributor's
   file matches the pinned candidate GGUF;
2. raw request/response and server logs for fixed cold prompts, with output
   hashes, exact timing definitions, repeats, and dispersion;
3. a same-prompt MTP-off versus MTP-on A/B with identical sampling and cache
   state, plus exact-token or semantic correctness comparison;
4. staged context-length gates well beyond 96 prompt tokens, including a
   near-boundary test, before describing the 512000 configuration as validated;
5. behavior under the intended two-slot concurrency rather than only
   single-request observations.

## Disposition

Keep the entry in `community/` at `community-reported`. It is safe to merge as
maintainer-corrected documentation, but it must not be promoted to `repro/`,
`results/`, or LocalMaxxing and must not be described as reference-lab evidence.
The next step is isolated B70 validation of the conservative MTP-off recipe,
followed by an optional controlled MTP A/B and progressively longer context
gates.
