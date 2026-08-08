# Reference-lab validation - 2026-08-08

## Scope and identity

The reference lab selected an official artifact matching the contributor's
reported filename and exact byte size and ran the packet in one process on one
Intel Arc Pro B70. The contributor supplied no model revision or hash, so its
model-byte identity remains unknown:

- model repository: `unsloth/Qwen3.6-27B-MTP-GGUF`;
- repository revision: `5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`;
- file: `Qwen3.6-27B-Q4_K_M.gguf`, 17,106,773,120 bytes;
- file SHA-256: `a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f`;
- llama.cpp commit: `15586e2d7165570fb3aa7c26e0d442e289ef69de`;
- llama-server SHA-256: `1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`;
- local build: Release, IntelLLVM/oneAPI 2026.0.0, `GGML_SYCL=ON`, `GGML_SYCL_F16=ON`;
- lab host: kernel `7.0.0-28-generic`; Intel compute-runtime `26.18.37020.6`; Level Zero loader `1.27.0`;
- runtime request: one B70, MTP2, one slot, and an explicit 150,000-token context request. The retained response proves at least 120,128 tokens of capacity; it does not independently preserve the allocated slot size.

The exact source/build worktree is backed up outside Git at
`/mnt/usb-models/models/runtime-builds/llama.cpp-15586e2d7-oneapi2026.0-sycl-worktree.tar.zst`,
SHA-256 `0ab088aac2cb2c12331fd18c4dbda4a30228a25e06bc2a8a95f770693da8d4d8`.
The binary RUNPATH includes the original `/dev/shm/llama.cpp-pr19-15586`
location, so restore it there for binary replay or rebuild from the pinned
source elsewhere.

The contributor reported oneAPI 2026.1.1 and did not preserve the original
CMake command. This is therefore an independent matching-name-and-size-model,
exact-engine-commit B70 validation, not a literal toolchain reproduction. The
retained build metadata and binary hashes establish the source/build identity;
the captured `--version` attempts did not produce a successful runtime banner.
Raw artifacts are outside Git under:

`/mnt/fast-ai/llm-optimization-artifacts/community-dominick253/qwen36-27b-llamacpp-sycl/20260808-reference-lab-a/`

Critical retained-file hashes are recorded in
[`reference-lab-artifacts.sha256`](reference-lab-artifacts.sha256). Empty logs
are included deliberately so their evidentiary limitation cannot be obscured
by a later replacement.

## Target-only control

llama-bench ran three repetitions with the model fully offloaded to `SYCL0`:

| Shape | Mean tok/s | Standard deviation |
| --- | ---: | ---: |
| pp2048 | 1,213.575 | 6.050 |
| pp32768 | 1,049.455 | 2.312 |
| tg128, depth 0 | 25.124 | 0.030 |

## MTP visible-output and depth checks

A fixed greedy 128-token request was run first with `--spec-type none` and then
with MTP2. The visible output bytes matched exactly. Generated token IDs were
not retained, and the records differ in `min_p`, so this is not a token-exact
A/B. Target-only decoded at 25.307 tok/s; MTP2 decoded at 38.112 tok/s and
accepted 81 of 92 drafted tokens.

The maintained launcher requested 150,000 tokens of context. The retained
exact token-array responses produced:

| Prompt tokens | Prompt tok/s | Decode tok/s | Accepted / drafted | Acceptance |
| ---: | ---: | ---: | ---: | ---: |
| 2,048 | 993.475 | 33.412 | 75 / 104 | 72.12% |
| 32,768 | 948.189 | 24.752 | 68 / 115 | 59.13% |
| 120,000 | 684.069 | 16.027 | 64 / 124 | 51.61% |

The 120K request completed all 128 output tokens, proving completion through at
least 120,128 tokens. The operator's final checks found no matching device
faults, stopped the endpoint, and observed the card idle afterward; the exact
scan command and post-run device output were not retained in the artifact set.

## Review of the historical table

The independent rates support the contribution's underlying claims: an
official GGUF matching the reported name and byte size runs on one B70, MTP can
improve short-context decode, and both decode rate and acceptance decline with
depth. They do not authenticate the historical cells or the contributor's
model bytes. Two submitted percentages are arithmetically wrong: 58/68 is
85.3%, not 80%, and 54/72 is 75%, not 66%. The reported draft2 2K wall rate of
39.7 tok/s is also incompatible with its listed prompt and decode rates under
ordinary wall-time accounting.

## Disposition

Raise this packet to `B70-tested`, retain the corrected historical table as
contributor-host evidence, and keep the packet in `community/`. The one
visible-output match and 120K completion/depth row are useful narrow
validation, but the two-process topology, contributor model-byte identity,
realistic cold suite, and long-context retrieval remain unverified. Do not
promote it to `results/` or `repro/`.
