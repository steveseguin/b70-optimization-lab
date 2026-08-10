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

VDR2 advanced from the four-card diagnostic screen. The concurrent screen
itself remains nonpromotable.

## Official isolated VDR2 short result

The follow-up isolated GPU-0 packet passed:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal2-vdr2-official-isolated-gpu0-short-20260810T053540.789566819Z`

- 80/80-entry artifact-manifest SHA-256:
  `68060e762c655ff93b34f53bd162edece86accde83ad16642a0033cc15318e66`;
- detached completion-marker SHA-256:
  `c7f02356e23ba2a94dad123dcb7f005d95f9d628036049875437e16b7b3015fc`;
- exact-result SHA-256:
  `49d16dd2e12fd16901b886cce0b7f075308b0e25d4e2ce0a44f7816ca4c312e5`;
- exact-result-gate SHA-256:
  `9a63ba6468b10e488c6fcae64a4e7ba59ab85aedff99c553541bad34ff7af411`;
- run-identity SHA-256:
  `a966a84aeb569b6c45c95161efa89f12db9997d7bbc7db3cbeb5a0a37dea610a`;
- runtime-profile-check SHA-256:
  `7d2dc67eaf9d8938414dfc909f2db0f5c8f349830fa18ca10fdf1f92f4596a0c`.

The marker is `PASS`, `evidence_valid=true`, `official-isolated`, and
`performance_promotable=true`. Both 512-token rows are `PASS_ORACLE_EXACT`;
the intrinsic, exact-result, post-512 canary, cache-zero, `65/65` offload,
runtime-profile, model, and cleanup gates pass.

Against the official isolated VDR4 short `-ub 1024` packet, VDR2 measured:

| Metric | VDR4 | VDR2 | VDR2/VDR4 |
|---|---:|---:|---:|
| PP tok/s | `605.8452528247` | `606.0653917226` | `1.00036x` |
| TTFT s | `7.1908603735` | `7.1874381265` | `0.99952x` |
| D100 tok/s | `15.0812900263` | `16.5871550224` | `1.09985x` |
| D511 tok/s | `15.0835290852` | `16.5889072472` | `1.09980x` |
| legacy D512-after-TTFT tok/s | `15.1128678281` | `16.6211250758` | `1.09980x` |

Prompt processing and TTFT are neutral while all three decode views retain the
approximately 10% lead from the four-card screen. Cleanup required no forced
kill, retained no survivor or listener, returned GPU 0 `43 -> 43 MiB`, kept
all nonselected GPUs idle, reverified model/runtime identity, and found no
device or server fault.

The official short VDR2 decode win is banked, but conventional D511 remains
below the immediate decode target: `16.5889072472 < 18 tok/s`. This advanced
VDR2 to bounded middle and near-32K guards; the short packet does not need
another reproduction.

## Official isolated VDR2 cross-band result

The middle `-ub 128` packet passed:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal2-vdr2-official-isolated-gpu0-middle-20260810T054938.876737716Z`

- 80/80-entry artifact-manifest SHA-256:
  `5822c88d6055afa0656269a027468e2aac1dafddf0e6f32131a582e66a551502`;
- detached completion-marker SHA-256:
  `8c01de2846ff01b2d472892c695bf797c89104c32b2cc897bdbd5e09d9dd2f10`;
- exact-result SHA-256:
  `40c1e38db9d1281eb4410fbb2da3959479e49793a0a61a9c378440c01cd50426`;
- exact-result-gate SHA-256:
  `9a63ba6468b10e488c6fcae64a4e7ba59ab85aedff99c553541bad34ff7af411`;
- run-identity SHA-256:
  `5a4c6c659c42d3ea6bc9c5ac9f6f7d5f30b358064f41aa113e3884aad192783a`.

Against the matched official VDR4 `-ub 128` middle baseline:

| Metric | VDR4 | VDR2 | VDR2/VDR4 |
|---|---:|---:|---:|
| PP tok/s | `157.7084965732` | `157.6975586190` | `0.99993x` |
| TTFT s | `109.2343399920` | `109.2455990315` | `1.00010x` |
| D100 tok/s | `13.8696711812` | `15.1381732549` | `1.09146x` |
| D511 tok/s | `13.8194229005` | `15.0772808986` | `1.09102x` |

The near-32K `-ub 1024` packet passed:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal2-vdr2-official-isolated-gpu0-near32k-20260810T060340.578608937Z`

- 80/80-entry artifact-manifest SHA-256:
  `35df11c414f3898753d7a8498a4529a10ce7ff0a7622d7f5f642f1fcdbdef1b1`;
- detached completion-marker SHA-256:
  `c997d7b82e5c1ac0397e5b8306addb5d338825347fa7e098ea0e33a5ecaef4e3`;
- exact-result SHA-256:
  `96e5197165860191b4efa98d65ff1cea5ef5a2da849a03f9c3a72786d3953a50`;
- exact-result-gate SHA-256:
  `9a63ba6468b10e488c6fcae64a4e7ba59ab85aedff99c553541bad34ff7af411`;
- run-identity SHA-256:
  `08bee7023bfd1bc13c1ba979dfd057566e446deebb0688ed23c46c1c8b691510`.

Against the official VDR4 `-ub 1024` near-32K baseline:

| Metric | VDR4 | VDR2 | VDR2/VDR4 |
|---|---:|---:|---:|
| PP tok/s | `629.2050294524` | `628.7871123260` | `0.99934x` |
| TTFT s | `50.6597956765` | `50.6909852390` | `1.00062x` |
| D100 tok/s | `12.6475080195` | `13.6894526174` | `1.08238x` |
| D511 tok/s | `12.6432505506` | `13.6861593539` | `1.08249x` |

Both cross-band markers are `PASS`, `evidence_valid=true`,
`official-isolated`, and `performance_promotable=true`. Each has two
full-512 `PASS_ORACLE_EXACT` rows, exact intrinsic/result/post-canary gates,
cache zero, `65/65` offload, verified model/runtime identity, no forced kill or
survivor, a closed port, GPU 0 at `43 -> 43 MiB`, idle nonselected GPUs, and no
device or server fault.

VDR2 is now officially banked at short `-ub 1024`, middle `-ub 128`, and
near-32K `-ub 1024`. D100/D511 improves by `8.2%--10.0%` across those bands
while PP and TTFT remain neutral. Conventional D511 remains below the
immediate `18 tok/s` target everywhere: `16.5889072472`, `15.0772808986`, and
`13.6861593539 tok/s`. The current next gate is a balanced VDR1 screen against
the banked VDR2 profile.
