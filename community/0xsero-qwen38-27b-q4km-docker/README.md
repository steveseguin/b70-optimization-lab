# Qwen3.8 27B Q4_K_M Docker deployment by 0xSero

> **Community-reported external recipe.** The implementation and measurements
> were produced by [`0xSero`](https://github.com/0xSero), not by this
> reference lab. No source files are vendored because the reviewed repository
> has no explicit license. Read [STATUS.md](STATUS.md) for the evidence and
> safety review before following the external project.

## Pinned Source

- Project: [`0xSero/qwen38-b70`](https://github.com/0xSero/qwen38-b70)
- Reviewed snapshot:
  [`17323a6b8948a7b4483633e24ba796df0fdb43a9`](https://github.com/0xSero/qwen38-b70/tree/17323a6b8948a7b4483633e24ba796df0fdb43a9)
- Captured: 2026-08-18
- License at capture: none found; link only, no redistribution

The external repository packages a Dockerized OpenAI-compatible llama.cpp
server for one or two B70 cards. It downloads and verifies the pinned
Qwen3.8-27B Q4_K_M target, selects TP1 or equal TP2, and offers optional MTP
and CPU vision-projector paths.

## What 0xSero Reported

| Mode | Reported result | Evidence boundary |
| --- | ---: | --- |
| TP2 target-only, approximately 2.5K context | `51.1 tok/s` decode | Summary table; no raw benchmark artifact or repeat distribution |
| TP2 target-only, approximately 245K context | `30.8 tok/s` decode | Summary table; no raw benchmark artifact |
| TP1 target-only, approximately 10K/40K context | `33.4 tok/s` decode | Summary table; no raw benchmark artifact |
| TP2 MTP, easy counting prompt | `84.3 tok/s`, 97.2% acceptance | Workload-favorable speculative result |
| TP2 MTP, hard random prompt | `49.0 tok/s`, 37.5% acceptance | Workload-dependent speculative result |

None of these rows has been reproduced in the reference lab. They must not be
mixed with the promoted model board or submitted to LocalMaxxing.

## Patch Provenance

The source accurately identifies its two patch files as lab artifacts:

| External name | Lab provenance | Decoded SHA-256 |
| --- | --- | --- |
| `tp2-full-stack.patch` | [Complete TP2 stack](../../patches/qwen36-27b-q8-tp2-asrock-b70/README.md) against `mndodd/llama.cpp` `4302fb599` | `f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998` |
| `q4k-increment.patch` | [TP2 Q4K gate/up/SwiGLU adaptation](../../patches/qwen38-27b-q4km-tp2-asrock-b70/README.md) | `0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6` |

The external project was created after both artifacts were published here and
credits this lab. Its original contribution is the container packaging and
deployment configuration, not those kernel patches.

## Potentially Useful Ideas

- Explicitly mount `/dev/dri/by-path` read-only in addition to passing
  `/dev/dri` when Level Zero discovery inside a container requires it.
- Compare the contributor's oneAPI 2025.3-family JIT build with the lab's
  accepted oneAPI 2026.1.1 BMG-G31 AOT build under the same fixed suite.
- Test batch/ubatch `8192/8192` as a long-context prefill profile. This is not
  evidence of a decode optimization by itself.
- Preserve TP1 as a prefill-oriented option and TP2 as the higher decode/KV
  capacity option rather than assuming one topology wins every phase.

Do not copy the contributor environment wholesale into the accepted repro. Its
JIT path disables the Q4K reorder and Q4K SwiGLU fusion doors because the
contributor observed corrupted output when enabling them. The lab's AOT path
passed exact-output gates with those doors enabled and measured a `+1.701%`
endpoint improvement.

## Safe Reproduction Boundary

The external Docker build uses every detected CPU through `-j$(nproc)`. That
is not safe on this lab's 15 GiB host. Any future replay must use at most `-j2`,
run inside the documented build-memory cgroup, and avoid overlapping a compile
with a loaded model. Also pin the base image by digest, bind the API to
localhost unless remote access is intentional, checksum optional artifacts,
and disable automatic restart during validation.

The exact review findings, missing evidence, and promotion requirements are in
[STATUS.md](STATUS.md).
