# STATUS — 0xSero Qwen3.8 27B Q4_K_M llama.cpp Docker

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | source read and patch digests checked; no container or model execution |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no |

## Provenance

- Contributor: [`0xSero`](https://github.com/0xSero).
- Source: [`0xSero/qwen38-b70`](https://github.com/0xSero/qwen38-b70).
- Reviewed commit:
  [`17323a6b8948a7b4483633e24ba796df0fdb43a9`](https://github.com/0xSero/qwen38-b70/tree/17323a6b8948a7b4483633e24ba796df0fdb43a9),
  captured 2026-08-18.
- Right-to-redistribute statement: no repository license was present at the
  reviewed commit. No contributor source, patch, benchmark image, or result
  artifact is copied into this repository.
- Third-party material: `mndodd/llama.cpp` commit `4302fb599`, the lab's full
  TP2 patch and Q4K increment, Intel oneAPI, and the
  `ggml-org/Qwen3.8-27B-GGUF` model repository.

## Contributor Claim

The contributor reports a one-command Docker deployment of Qwen3.8 27B
Q4_K_M with F16 KV at up to `51.1 tok/s` target-only decode on two B70s and
`33.4 tok/s` on one B70, plus workload-dependent MTP measurements up to
`84.3 tok/s`.

These are contributor-reported measurements, not reference-lab results.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 1x or 2x Intel Arc Pro B70; 32 GiB per card |
| OS / kernel | Arch Linux, kernel `7.1.8` |
| GPU driver | `xe`; exact userspace driver packages not recorded |
| Compute runtime | Intel oneAPI 2025.3-family JIT container; exact built image digest not recorded |
| Engine | `mndodd/llama.cpp` `4302fb599` plus two lab patches |
| Model | `ggml-org/Qwen3.8-27B-GGUF` revision `0669b98607d47046c7c2b3f801011d54a08cfccf` |
| Target artifact | `Qwen3.8-27B-Q4_K_M.gguf`, SHA-256 `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34` |
| Precision | Q4_K_M target, F16 KV; optional Q4_0 MTP draft |
| Runtime shape | TP1 or equal TP2; batch/ubatch `8192/8192`; concurrency 1 |
| Context | reported through approximately 245K on TP2 and 128K on TP1 |
| Cache policy | RAM cache and context checkpoints disabled |
| Benchmark evidence | summary tables and image only; raw JSON, harness, prompt/output hashes, repeats, dispersion, cache telemetry, and interval definition absent |

## What Was Actually Run Here

No Docker build, model download, GPU workload, endpoint request, or benchmark
was run. Maintainer review cloned the pinned source, read all tracked text and
build files, inspected the patch content, and compared decoded patch SHA-256
values with the lab artifacts.

## Findings

1. `patches/tp2-full-stack.patch` is byte-for-byte identical to the lab's
   decoded full TP2 artifact, SHA-256
   `f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998`.
2. `patches/q4k-increment.patch` is byte-for-byte identical to the lab's
   decoded Q4K TP2 increment, SHA-256
   `0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6`.
   The contributor correctly credits both artifacts to this lab.
3. The useful new work is deployment packaging: automatic pinned-model
   verification, TP1/TP2 selection, long-context defaults, and the explicit
   read-only `/dev/dri/by-path` mount needed by that container environment.
4. The JIT runtime disables Q4K reorder and fused Q4K SwiGLU because the
   contributor observed corrupted output with them enabled. It therefore does
   not reproduce the lab's AOT Q4K fusion path or its quality-gated `+1.701%`
   endpoint improvement.
5. The reported `51.1 tok/s` is not directly rank-comparable with the lab's
   `49.717503 tok/s` conventional cold-suite median. The contributor did not
   retain the evidence needed to establish the same metric, prompts, cache
   state, or run distribution. The lab's historical server/helper value for
   its accepted configuration is already `50.219700 tok/s`.
6. A controlled oneAPI 2025.3 JIT versus 2026.1.1 AOT replay and an
   `8192/8192` versus `8192/2048` deep-prefill A/B are useful future leads.

## Known Issues

- No license is present at the reviewed source commit, so this packet links to
  the implementation rather than redistributing it.
- The Docker build uses `-j$(nproc)` without a memory limit. Do not run it
  unchanged on the 15 GiB reference host; use `-j2`, a build cgroup, and no
  concurrent loaded model.
- The base image is identified by a mutable tag rather than a registry digest,
  and the installed Hugging Face Python package is not version-pinned.
- The optional MTP and vision artifacts are revision-pinned but are not
  independently checksum-gated by the entrypoint.
- The service binds `0.0.0.0`, publishes port 8010 on all host interfaces,
  uses host IPC, and restarts unless stopped. Review network exposure and
  lifecycle policy before use.
- The source's broad statement that oneAPI 2026.1 cannot enumerate B70s does
  not hold for this reference host, which has run the accepted 2026.1.1 AOT
  path on both cards. It should not be used as a general downgrade rule.
- The contributor reports that GPU vision-projector offload hangs `xe`; their
  default keeps the projector on CPU. This was not reproduced here.

## Open Questions For The Contributor

- Will the repository receive a permissive license or a contribution PR with
  an explicit right-to-submit statement?
- Can the exact container image digest, compiler version output, benchmark
  harness, raw responses, prompt/output hashes, cache telemetry, and repeated
  run statistics be published?
- Was `51.1 tok/s` calculated from llama.cpp's server timing field, wall time,
  or token timestamps, and how many decode intervals were counted?

## Disposition

Keep this link-only packet as `community-reported`. Do not copy the unlicensed
Docker assets, promote the throughput claim, or submit it to LocalMaxxing. A
future reproduction should independently construct a memory-bounded container
from the lab artifacts and use the fixed cold suite with exact-output and
cache-zero gates.
