# BF16 oneMKL verify path: first-pass performance win, not promoted

Date: 2026-08-12

## Decision

Keep the new oneMKL BF16 small-batch matrix path default-off and advance it as
a verification-width candidate. It is a large measured performance win, but
it changes the BF16 GEMM reduction implementation and therefore does not meet
the established byte-replay identity without a wider quality gate.

Drafter training remains closed by operator direction. No drafter weights or
training artifacts were changed in this experiment.

## Source and build

- source worktree: `/home/steve/src/llama.cpp-muse-100`;
- base: upstream `030ebb558` plus the cumulative Muse campaign patch;
- durable source checkpoint: `1fadb9507eb7e9356800fad6f083a1d493b4644c`;
- implementation: `GGML_SYCL_BF16_MKL=1`, default off;
- operation: preserve F32-to-BF16 activation conversion, call oneMKL
  BF16-by-BF16-to-F32 GEMM directly, bypassing the generic multi-device
  wrapper and per-call oneDNN primitive construction;
- isolated build: `build-sycl-b70-aot-bmg-g31-bf16mkl-icpx`;
- server SHA-256: `8eea728f1752424475a49db07ecef8776cb42d5347f84f208243afdb8887f50f`;
- `libggml-sycl.so.0.19.0` SHA-256:
  `867870dd96b6fb9319036d024b0ce98cced1ed20c30a47228d5a31c9e0786a25`.

The measured binary included N=1 through N=16. After the result, the source
gate was narrowed to N=2 through N=16 because N=1 regressed and defines the
incumbent byte-stable target identity. The narrowed source builds cleanly but
has not yet received a model A/B.

## Exact comparator

- four Arc Pro B70 GPUs, `ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3`;
- BF16 two-part target and stock BF16 DFlash drafter;
- tensor parallel, KV mirroring off;
- `-ngl 99 -c 32768 --parallel 1 -b 1024 -ub 1024 --threads 8 -fa on`;
- DFlash `n_max=15`, `p_min=0.15`;
- three sequential greedy requests, `cache_prompt=false`, 256 output tokens;
- only changed variable: `GGML_SYCL_BF16_MKL=0/1`.

The first attempted A/B accidentally used the sweep harness default of four
slots. It is invalid and excluded. The harness now passes `--parallel 1`.

## Result

| Arm | Prose | Code | JSON | Arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| control | 39.720 | 57.670 | 69.729 | 55.706 |
| oneMKL candidate | 45.629 | 68.590 | 80.336 | 64.852 |
| candidate/control | 1.1488x | 1.1894x | 1.1521x | **1.1642x** |

Acceptance changed slightly: prose `172/1177 -> 173/1096`, code
`197/811 -> 199/781`, and JSON `207/672 -> 207/674`.

Output SHA prefixes:

| Class | Control spec | Candidate spec | Control no-spec | Candidate no-spec |
| --- | --- | --- | --- | --- |
| prose | `914f754747d0edaa` | `a71ceb1ecf6a3e43` | `914f754747d0edaa` | `a71ceb1ecf6a3e43` |
| code | `cf2b2c4fd9e36fe5` | `cf2b2c4fd9e36fe5` | `b4a2bda611510441` | `cf2b2c4fd9e36fe5` |
| JSON | `4f813a9706abc163` | `4f813a9706abc163` | `4f813a9706abc163` | `4f813a9706abc163` |

Each speculative arm matches its own no-spec identity on all three prompts.
However, oneMKL changes two of three no-spec hashes relative to the incumbent,
so it is a different BF16 reduction ordering rather than a byte-identical
replacement. Under no speculation it also regresses the mean from about
`26.455` to `23.326 tok/s` (`0.8818x`), motivating the N>=2 scope.

Raw evidence:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/bf16-mkl-ab-parallel1-20260812.jsonl`,
  SHA-256 `a995b915d6b2c688dda85f2bffb48e5eaaee7288f475a0c17b1d207e0daa6a77`;
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/bf16-mkl-nospec-ab-parallel1-20260812.jsonl`,
  SHA-256 `f4ead6fc61a5ceb48670fa8d258e6c714115b6b6f62b4ecaf352120953201134`;
- matching server logs under
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-bf16-mkl-*`.

## Ceiling correction and next work

The honest campaign baseline is approximately `56.95 tok/s`, so the target
still needs `1.756x`. At the current mean emitted tokens per round, 100 tok/s
requires reducing a roughly 74 ms round to about 42 ms. Even deleting the
entire estimated 19 ms launch pool projects only the mid-70s.

Naively verifying two consecutive DFlash blocks in one target pass is not a
valid route: the second block needs target-layer features produced only after
the first block is verified. That proposal requires different drafter
semantics, not serving-loop batching.

The next kernel campaign is persistent per-meta-subgraph SYCL executable graph
replay under tensor parallelism. The current backend globally rejects graphs
when multiple devices are visible and retains only one executable graph per
context, although meta subgraphs have stable UIDs. A safe implementation must
cache by subgraph identity and pointer/shape signature, exclude unstable
oneDNN/MKL scratch allocations, instrument hits/invalidations, and remain
default-off until exactness and performance gates pass.

## Operations

The production fleet was stopped gracefully for the four-GPU window and
restored immediately afterward. `data/muse-health-20260812-kernel-window-restore.json`
passes models, a cache-zero 512-token code canary, and the red-image routing
canary. Production does not enable the oneMKL candidate.
