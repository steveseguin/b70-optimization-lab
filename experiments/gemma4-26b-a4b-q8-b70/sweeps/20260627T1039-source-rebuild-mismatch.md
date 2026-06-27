# Gemma 4 26B Q8: Source Rebuild Mismatch After Q8 MMVQ Screens

Date: 2026-06-27

## Summary

The Q8 MMVQ follow-up exposed a more important reproducibility issue than the
candidate kernel itself: new builds from the current dirty
`/home/steve/src/llama.cpp-gemma-record-stack` worktree are not reproducing the
current `104.309 tok/s` record binary. The same build family, even with the new
Q8 hoist gate disabled, lands around `40-49 tok/s` on the standard fresh row0
screen.

**Correction after clean rebuild audit:** the slow `40-49 tok/s` screens below
used `BENCH_PROMPT_MODE=long` (75 actual prompt tokens), while the record lane
uses `BENCH_PROMPT_MODE=filled-long` (588 actual prompt tokens). The acceptance
collapse was primarily a benchmark-identity mismatch, not proof that the clean
source reconstruction was missing code. A clean `c926ad098` worktree with the
promoted record patch plus RMS-reuse incremental patch reproduced the record
lane at `102.252 tok/s` fresh row0 with `64/64` canaries using `filled-long`.

Do not compare Gemma 4 26B Q8 runs across `long` and `filled-long` prompt
modes. The `long` mode is useful as a separate short-prompt stress lane, but it
is not comparable to the current LocalMaxxing/reproduce.md `p512/o512`
filled-context lane.

## Current Record Reference

- Result:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
- Fresh headline: `104.30919255569083 tok/s` after TTFT, row0 only
- Support mean: `103.93445004566178 tok/s`
- Canary: `6144/6144` rows
- LocalMaxxing: `cmqw1tgzx0366qr01g4lkv7f1`
- Record identity: `UD-Q8_K_XL` target/verifier, `Q4_0-MTP` draft,
  `UBATCH_SIZE=768`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`,
  `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`, route-cache/fused-output/fused selected
  softmax stack.

## Rebuild Screens

All three runs below used the repeated-prompt screen shape, but they used the
wrong prompt mode (`long`, 75 actual prompt tokens) for comparison to the
current record lane. Per the fresh-response rule, row0 is the only
headline-eligible value; later rows are support only. All rows reported
`cached_tokens=0`.

### Clean reconstruction control with correct filled-long identity

- Data:
  `data/gemma4-q8-gpu1-cleanrepro-rmsreuse-ub768-nmin3-pmin010-filledlong-screen-20260627T110211Z/`
- Source:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`, clean worktree at
  `c926ad098` plus:
  - `patches/gemma4-26b-a4b-q8-b70/20260626T2225-llamacpp-gemma4-current-record-stack.patch`
  - `patches/gemma4-26b-a4b-q8-b70/20260627T0704-llamacpp-gemma4-moe-reuse-attn-rms-incremental.patch`
- Binary:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- Prompt identity: `BENCH_PROMPT_MODE=filled-long`,
  `PROMPT_TOKENS=512`, actual prompt tokens `588`, output `512`
- Canary: `64/64` rows
- Fresh row0: `102.2521600027975 tok/s` after TTFT
- Support mean: `102.3745597619006 tok/s`
- Interpretation: clean reconstruction is restored. The remaining `~2 tok/s`
  gap to the stale `104.309 tok/s` record is normal screen noise / GPU index /
  run variance, not a missing major source patch.

### Q8 ncols hoist enabled

- Data:
  `data/gemma4-q8-gpu1-q8ncols-hoist-rmsreuse-ub768-nmin3-pmin010-screen-20260627T103535Z/`
- Binary:
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31-q8hoist/bin/llama-server`
- Env: `LLAMA_SYCL_MMVQ_Q8_NCOLS_HOIST=1`
- Canary: `64/64` rows
- Fresh row0: `43.152077041798634 tok/s` after TTFT
- Support mean: `41.72099352444299 tok/s`
- Server evidence: long-prompt draft acceptance collapsed to
  `353/1099` then `342/1168` generated draft tokens, mean accepted length
  `3.25` then `3.04`.

### Q8 hoist binary, feature gate off

- Data:
  `data/gemma4-q8-gpu1-q8hoistbinary-gateoff-rmsreuse-ub768-nmin3-pmin010-screen-20260627T103731Z/`
- Binary:
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31-q8hoist/bin/llama-server`
- Env: no `LLAMA_SYCL_MMVQ_Q8_NCOLS_HOIST`
- Canary: `32/32` rows
- Fresh row0: `40.15528197170138 tok/s` after TTFT
- Support row1: `49.06479300468235 tok/s`
- Support mean: `44.610037488191864 tok/s`
- Interpretation: this is the decisive control. The rebuilt binary is already
  far below record with the new hoist path disabled, so the enabled hoist result
  cannot be compared to the stale record binary.

### Q8 MMVQ VDR=4 corrected identity

- Data:
  `data/gemma4-q8-gpu1-vdr4-rmsreuse-ub768-nmin3-pmin010-recordid-screen-20260627T102132Z/`
- Binary:
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31-vdr4/bin/llama-server`
- Build override: `-DVDR_Q8_0_Q8_1_MMVQ=4`
- Canary: `64/64` rows
- Fresh row0: `44.21455725216031 tok/s` after TTFT
- Support mean: `44.00347536660475 tok/s`
- Prior note:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1021-q8-mmvq-vdr4-negative.md`
- Interpretation update: still do not pursue global VDR widening, but treat
  the exact magnitude as non-comparable until clean rebuild is restored.

## Build Flag Check

Relevant CMake cache keys matched between the old record build directory and
the new q8hoist build:

- `CMAKE_BUILD_TYPE=Release`
- `CMAKE_CXX_FLAGS=`
- `CMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG`
- `GGML_SYCL=ON`
- `GGML_SYCL_F16=ON`
- `GGML_SYCL_DEVICE_ARCH=bmg-g31`
- `GGML_SYCL_TARGET=INTEL`
- `GGML_SYCL_GRAPH=ON`
- `GGML_NATIVE=ON`
- `GGML_CCACHE=ON`
- `GGML_OPENMP=ON`
- `GGML_BLAS=OFF`

The VDR build differs only by `CMAKE_CXX_FLAGS=-DVDR_Q8_0_Q8_1_MMVQ=4`.

## Preserved Patch Artifact

The full current dirty source diff was preserved because it includes the Q8
hoist candidate plus all uncommitted local source state that may explain the
rebuild mismatch:

- Patch:
  `patches/gemma4-26b-a4b-q8-b70/20260627T1039-current-dirty-source-rebuild-mismatch.patch`
- Size: `501K`
- SHA256:
  `095f470c731fdd836e7d34c1513f6471fb08cf389b4231dfee038275b55bd05e`
- Source tree at capture:
  `/home/steve/src/llama.cpp-gemma-record-stack`, detached at `c926ad098`
- Dirty diff stat at capture: `27 files changed, 9151 insertions(+), 519 deletions(-)`

This patch is an audit artifact, not a promoted patch. Do not apply it as a
clean recipe.

## Decision

Use `/home/steve/src/llama.cpp-gemma-record-repro-c926` as the clean source
baseline for new Gemma 4 26B source experiments. Preserve the dirty
`/home/steve/src/llama.cpp-gemma-record-stack` worktree as an audit artifact
and do not use its old `long`-mode q8hoist/VDR screens as record-lane evidence.

Before any new source patch is interpreted as a win/loss against the current
record, run the `filled-long` record-identity screen first. A `long`-mode screen
can still be useful, but it is a different short-prompt/low-acceptance lane.
