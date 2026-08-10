# VDR2 versus VDR4 short full-512 crossover screen

Date: 2026-08-10

## Result

A balanced two-wave, same-card four-B70 crossover found a repeatable short-
decode win from changing reordered-Q8 MMVQ VDR width from 4 to 2. VDR2/VDR4
same-card ratios were:

| GPU | PP ratio | TTFT ratio | D100 ratio | D511 ratio |
|---:|---:|---:|---:|---:|
| 0 | `0.99551` | `1.00473` | `1.09963` | `1.10025` |
| 1 | `1.00163` | `0.99834` | `1.09849` | `1.09846` |
| 2 | `0.99851` | `1.00139` | `1.10087` | `1.10081` |
| 3 | `1.00296` | `0.99676` | `1.10054` | `1.09931` |

Thus D100 and the conventional 511-interval token-1-to-token-512 rate improve
by about 9.85--10.09% on every card. Prompt processing and TTFT are neutral:
all same-card PP ratios are within `0.99551--1.00296`, and all TTFT ratios are
within `0.99676--1.00473`.

This is a `parallel-functional-screen`, not an official performance packet.
All eight completion markers set `performance_promotable=false`; no score or
LocalMaxxing claim is promoted from these concurrent diagnostic timings.

## Frozen implementation identity

- runtime-profile harness commit:
  `e8bd43bfd07f2d35e241bb43d1f46ea4e2ed0746`;
- compile-knob patch SHA-256:
  `9b211cd6d4b2648cd195decfbc865e0cdf7130d76d428c36d3384e883e1f05a4`;
- VDR4 runtime-manifest SHA-256:
  `d127dbaaf30e014cbae0dc59a3c0b0f61f329eabadffb74ce40e01264bee79cc`;
- VDR4 `libggml-sycl.so.0.18.1` SHA-256:
  `e545c2363689de3aced49bf2f26003f499cf19eb1bb302babffc2c17132b98e7`;
- VDR4 offline launcher runtime-bundle report SHA-256:
  `38d5b975612f49ffa8f5d9a135167955f53a1157aa7cd029fa73bfd04b21eef4`;
- VDR2 runtime-manifest SHA-256:
  `4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49`;
- VDR2 `libggml-sycl.so.0.18.1` SHA-256:
  `eff26ef9562196d454fdc54cca7680304e6ce37e9a9d92ef3b514e8c34f3d0a0`;
- VDR2 offline launcher runtime-bundle report SHA-256:
  `5287a0a0909878f8875b545b8721111cb5402f098dfa6a0dc62c43092354c8d9`.

`serve-target-only.sh --verify-runtime-bundle` passed offline for both runtime
profiles. The expanded 40-file build-evidence ledger is
`/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr-screen-build-evidence-20260810/evidence-files.sha256`,
SHA-256
`5ab9c6eb7a4271a933fd68d97a3d1b4f9b868dfdf140f3a2f603c00547c5d291`.
All 40 entries verify. This supersedes the earlier 34-file ledger.

## Corrected two-wave packet

Wave 1 used VDR4 on GPUs 0/2 and VDR2 on GPUs 1/3:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/vdr-short-crossover-wave1-20260810T051936.684356198Z`

Wave 2 flipped the treatment on every card:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/vdr-short-crossover-wave2-20260810T052417.359751349Z`

Each lane's 74-entry artifact manifest verifies:

| Wave | GPU | Runtime profile | Artifact-manifest SHA-256 | Exact-result SHA-256 | Completion-marker SHA-256 |
|---:|---:|---|---|---|---|
| 1 | 0 | `q8-vdr4-control` | `75da38538e11c06cb2853727db0c9482b736121411778b62b59e4b72f6cf00ac` | `30a95928ab81da004181e66bf72033fba33adb037a92d924eff172232fa5d6da` | `28f5d36adde04a58fe09ad7f4d40e4521838b5cf18f94aebc191c5b6c02cbb32` |
| 1 | 1 | `q8-vdr2-candidate` | `7b406c126d7033468327f562435f190d84692f5aca98cc958ab07b158dde34ae` | `a64827c78f42398bd85ac4dbc9165077b84bf39f5dded1ec371bc4fa33e5e006` | `b71d8a3c03321f76d87927e540d6da453323bd1911a0adb729b91fb8b5c6e63f` |
| 1 | 2 | `q8-vdr4-control` | `0fa60dbc17876010b4f968b09834e3533b806f61e62e36098d6d8243b5c34558` | `de245ad9f152fefbbb3cd5014cf1c4c6c84a273ccfd852ba9fab8296d99b5dec` | `91f2d866742191ddf03e11f0331851448070dd76350b603be2ad3ea181d7bfad` |
| 1 | 3 | `q8-vdr2-candidate` | `e21690a4028f8a184159588e88010fb7428de3aef2b57ad39dc8533f85510436` | `0eb43cf533aa3683d81b6f90146f8b488acdc07230adcc7cad597c4febe1c790` | `483642c51ee8c1af904182ec60d8549f1c40e0f6398ca557d18a691aec9a39ce` |
| 2 | 0 | `q8-vdr2-candidate` | `324d43f653fbb33aa8754d1dab18fd0a715957843941dc0ad7c980f87380c114` | `5f123be2b63c64e8759fc4ad3bdae32417e3369f8bca20fb1c80fb8a1b96b4e2` | `5a11b12cfc703ac2c686c380af2270944f8d5b6a0e640773d8faca6ec1b3a427` |
| 2 | 1 | `q8-vdr4-control` | `cb1779fe38fcde00c0998429ecd0d154252c43f0afae23a9d1b7de37daa6b795` | `efe742ec85330af2bdff9139cc6fd25a65d6b09afa288d5e32a4b7d60e358e0f` | `44c33b581dd25f3aff4a4c37bc7bfc15fdef673a456df4756f3c6197c3832d99` |
| 2 | 2 | `q8-vdr2-candidate` | `3ae63aac2357c55e47cd6711170b7081758fb8372b27aa68426b6905cb7029ca` | `d198b555d6ce0676675ad07c0c0747e14274a0bd7284bd7c5189dc9762797b09` | `f415f6d54b86ddcddffa4b6f0325f3ae89770bc4874e62bb441378f89271abd0` |
| 2 | 3 | `q8-vdr4-control` | `72315c573f8d0f91add7624ed7cb85d44ab4bd5bf794a078a8ac8f2c99ba51e4` | `d6aca1e3bcc3e7a81a7b4c1fddca732ec16739a00ec194d1d5c3497d1cb6c5fa` | `29d8cb6a90d8bb9210ce25713fa774541e176fa1c4316b49245bd3f4746e0d12` |

All eight lanes are `PASS` and `PASS_ORACLE_EXACT`; both full-512 rows, the
intrinsic gate, exact-result gate, post-512 canary, cache-zero check, `65/65`
offload, runtime-profile binding, and cleanup pass. No lane required a forced
kill, retained a survivor or listener, or recorded a device/server fault.

## Excluded false start

The earlier root

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/vdr-short-crossover-wave1-20260810T051851.034690276Z`

used the wrong outer comparison oracle and was interrupted during preflight.
All four children have `original_status=130`, `FAIL`, and no completion marker.
It is excluded from correctness and performance evidence; the corrected
`051936` wave above is the only Wave 1 authority.

## Decision

VDR2 advances from the four-card diagnostic screen. The next gate is one
official-isolated short full-512 VDR2 packet with promotable timing and the same
exact-output, canary, cache-zero, full-offload, runtime-identity, and clean-
teardown requirements. Do not promote the concurrent screen itself.
