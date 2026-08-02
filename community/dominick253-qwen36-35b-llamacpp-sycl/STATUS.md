# Qwen3.6 35B A3B UD-Q8_K_XL on Intel Arc B70 (llama.cpp SYCL)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-tested` |
| Patch review status | maintainer-corrected and runtime-tested |
| Tested in reference lab | yes, prospective reproduction on 2026-08-01/02 |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no; exact quality/performance and near-boundary context remain unverified |

## Provenance And Claim Boundary

- Contributor: dominick253
- Source: [PR #14](https://github.com/steveseguin/b70-optimization-lab/pull/14)
- Contributor commits: `27469f01a`, `32f41bb09`, `6077da861`
- Maintainer corrections and validation are separately identifiable in Git
  history and the linked validation summary.

The contributor reported successful two-B70 serving, 40.12 tok/s average for
their original MTP-on measurements, and approximately 45 tok/s for a later
MTP-off control. The contributor did not preserve raw artifacts, an exact GGUF
revision/checksum, or complete build/runtime identity. Those numbers remain
community-reported and are not replaced by the lab measurements below.

## Reference-Lab Identity

| Field | Value |
| --- | --- |
| GPUs | 2x Intel Arc B70, logical devices 0 and 1 |
| OS kernel / driver | `7.0.0-28-generic` / xe srcversion `85B7CA089405934276CBAD3` |
| llama.cpp | `fb92d8f1873c96ec63f9c59721d58a55bf46d441` |
| Build | clean SYCL Release build, `GGML_SYCL=ON`, `GGML_SYCL_F16=ON`, IntelLLVM 2026.0.0 |
| Model | `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` revision `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d` |
| GGUF | `Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf`, 39099447584 bytes, SHA-256 `6c6b816537abad90b250a0972b345466028d861ddfe316d5f0de31ca6440f781` |
| mmproj | `mmproj-BF16.gguf`, 902822528 bytes, SHA-256 `da63cb47a76763c712393f8a017070188a304fa39f8aeea6edc629ed7b975cfa` |
| Runtime | corrected recipe, MTP off, F16 KV, `--ctx-size 512000 -np 2`, loopback port 18214 |
| Effective context | server reported 2 slots, 256000 tokens per slot, unified KV off |

This is a prospective reproduction identity. The local compiler version and
model checksum are not known to match the contributor's original environment.

## What Was Actually Run Here

- Startup, `/health`, and `/v1/models` identity checks.
- Exact plain, JSON, arithmetic/reasoning, sequential, concurrent, and
  post-long canaries; all relevant requests reported `cached_tokens=0`.
- Seven exact JSON retrieval cases through 34649 actual prompt tokens, 7/7
  passed, followed by another exact uncached response.
- The fixed 12-prompt realistic suite, SHA-256
  `0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812`,
  with thinking disabled, unique prompts, and cache prompting disabled.
- A native `/completion` MTP-off/MTP-on diagnostic on a fixed prompt, followed
  by fresh-process and same-process MTP-off controls.
- Clean shutdown and device-observer checks after every server run.

## Findings

1. The corrected conservative recipe starts and serves successfully on two
   reference-lab B70s. Semantic, concurrency, and 34649-token retrieval gates
   passed.
2. `--ctx-size 512000 -np 2` produced two 256000-token slots. It does not
   establish a 512000-token per-request context, and only 34649 prompt tokens
   were tested.
3. The fixed cold suite passed 12/12. Conventional 99-interval accounting was
   48.181817970061076 OpenAI content-delta events/s. Because returned SSE
   deltas lack token IDs, this is a stream-delta proxy rather than exact-token
   throughput.
4. MTP-on measured 45.7156408565 tok/s versus MTP-off observations of
   48.4407013911, 48.4534088298, and 48.4744558553 tok/s. MTP was therefore
   directionally and reproducibly slower in this identity, supporting the
   corrected MTP-off default.
5. The MTP-on run accepted 167 of 262 drafted tokens (63.74%, mean accepted
   length 2.90), confirming that acceptance alone does not imply acceleration.
6. Exact token streams varied between MTP-off controls, including two requests
   in one process with temperature zero and the same seed. The A/B therefore
   cannot attribute output divergence to MTP; exact-quality equivalence remains
   inconclusive.

## Remaining Limits

- No test approached the effective 256000-token slot boundary.
- The realistic-suite metric is not exact-token timing and is not eligible for
  a record claim or LocalMaxxing submission.
- The contributor's exact compiler flags, runtime package identities, model
  revision, and artifact checksum remain unknown.
- Greedy-output nondeterminism blocks an exact-token MTP quality conclusion.
- This validation does not establish general reasoning or multimodal quality.

## Disposition

Keep the corrected recipe in `community/` at `B70-tested`. It is useful as a
tested starting point and supports MTP-off as the default, but it is not yet a
promoted `repro/` or `results/` artifact. Exact-token quality/performance and a
progressive near-boundary context ladder are separate future work; no response
or branch update is required from the contributor.
