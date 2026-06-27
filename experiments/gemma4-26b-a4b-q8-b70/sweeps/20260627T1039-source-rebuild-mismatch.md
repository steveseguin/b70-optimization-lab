# Gemma 4 26B Q8: Source Rebuild Mismatch After Q8 MMVQ Screens

Date: 2026-06-27

## Summary

The Q8 MMVQ follow-up exposed a more important reproducibility issue than the
candidate kernel itself: new builds from the current dirty
`/home/steve/src/llama.cpp-gemma-record-stack` worktree are not reproducing the
current `104.309 tok/s` record binary. The same build family, even with the new
Q8 hoist gate disabled, lands around `40-49 tok/s` on the standard fresh row0
screen.

Do not interpret the Q8 hoist or VDR=4 screens as clean kernel losses until a
clean rebuild control first matches the record lane.

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

All three runs below used the standard repeated-prompt screen shape. Per the
fresh-response rule, row0 is the only headline-eligible value; later rows are
support only. All rows reported `cached_tokens=0`.

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

Stop source-kernel screens against the current dirty rebuild until the record
binary can be reproduced from a clean worktree. The next engineering step is a
clean reconstruction:

1. Create a separate clean worktree from llama.cpp commit `c926ad098`.
2. Apply the known record-stack patch artifacts in order, including the
   `20260626T2225` current-record stack and the RMS-reuse record change.
3. Build an AOT BMG/G31 SYCL binary with the same CMake identity.
4. Run the standard record-identity screen on a single GPU.
5. Only resume Q8 MMVQ/body experiments once the clean rebuild control is back
   near the `104 tok/s` record lane.

