# Preregistration: A359 - exact multi-row GDN verifier rows in one kernel launch

## Why

- A356: with the Python serial verifier-row path off, the M=2 verify step is 33.9 ms instead of
  42.7, but the exact-2K hash moves (`8b4f5fcb…`, not `afffd211…`). The serial path buys exactness
  for about 8 ms per verify step, essentially the whole GDN excess of the block decomposition.
- Reading the served kernel tree (`/home/steve/src/vllm-xpu-kernels` at `e421889`, the tree the
  staged `_xpu_C.abi3.so` was built from): the multi-row spec kernel
  (`gated_delta_rule_spec_kernel`, `csrc/xpu/gdn_attn/spec_decode.hpp`) and the per-row decode
  kernel run the same per-token arithmetic in the same order. The one difference for a
  two-row sequence is where the SSM state lives between the rows: the multi-row kernel carries it in
  fp32 registers, the serial path stores it to the cache slot (the lane's cache dtype is `auto`,
  i.e. BF16 for both conv and SSM state) and reloads it for the next row. The conv stage is the same
  arithmetic per token in both paths (`causal_conv1d_spec_kernel` vs the decode conv), and the
  initial-state column selection is the same (`num_accepted_tokens - 1`).

## Treatment

Kernel tree branch `q38-gdn-spec-round-state` (worktree
`/mnt/usb-models/qwen38-build/src-gdn-roundstate-e421889`, based on `e421889`): the multi-row spec
kernel gets `round_state_between_tokens`; after storing the per-token state column, for every token
that is not the last of its sequence it replaces the carried fp32 state with its StateT round trip.
Env `VLLM_XPU_GDN_SPEC_ROUND_STATE=1` (read in `gdn_attn_interface.cpp`, default off). Nothing else
changes. The rebuilt `_xpu_C.abi3.so` goes into a new stage directory
`/mnt/usb-models/qwen38-build/runtime-gdn-roundstate-<sha7>-b70` (a copy of the served
`runtime-core-moe-negidguard-b70` with only `_xpu_C.abi3.so` replaced; `libgdn_attn_kernels_xe_2.so`
and everything else byte-identical), with its own loadable manifest
`data/runtime-stage-gdn-roundstate-loadable.sha256` and the stage build head recorded in the
derived script (generator options `STAGE:`, `MANIFEST:`, `STAGE_BUILD_HEAD:`).

Build isolation: configured in `/mnt/usb-models/qwen38-build/xpu-gdn-roundstate-e421889` with the
cache values of `xpu-moe-40683a3` (MOE off, GDN on, SYCL 2025.3 pinned, Ninja, Release) and copied
dependency sources under `deps-gdn-roundstate`. A first configure mistakenly pointed FetchContent
at the main tree's `.deps` and recompiled about 130 oneDNN common objects there with identical
flags before it was stopped; `libdnnl.a` (2026-08-31) was not relinked. Recorded here so a later
oneDNN relink from the main tree is not a surprise.

## Gates (within-binary, per the fp-model rebuild rule)

- G0 no-op proof, A359a: new stage, flag off, promoted config (Python serial on, views on). Expect
  `afffd211…` at 2K on all three rows and the promoted step time (~41.8 ms). If the rebuild alone
  moves the hash, the codegen drifted (icpx defaults to fp-model=fast for this target); the
  remaining gates are then within the new binary and the 4K/quality battery decides promotion.
- G1 exactness, A359b: new stage, `VLLM_XPU_GDN_SPEC_ROUND_STATE=1`, Python serial path OFF.
  Expect the same hash as A359a on all rows (i.e. `afffd211…` if G0 held) and, with the serial
  copies gone, a verify step near A356's 33.9 ms.
- G2 depth: exact-4K on the surviving arm must reproduce the promoted `c6193cc6…` (or A359a's 4K if
  G0 drifted), then the certified two-run rule before any record claim.

## Stop rules

Build fails; the server fails health; G1 hash differs from G0's (the rounding point is not the whole
story: next candidate is the conv state publication order).

## Amendment (2026-09-12, before A360 ran): the kernel-level probe found a second difference

`probes/gdn-spec-round-state-equivalence.py` runs the serial rows (decode op, state copies between
columns) and the multi-row spec op on random data with the model's per-rank dims and compares bit
for bit. With the first treatment (`32798565`, round trip only) row 0 already differed by one
BF16 ulp whenever both the initial state and q/k were non-zero (identity conv: still differs; zero
conv: outputs equal but the stored state differs; zero initial state: row 0 equal, row 1 not). The
two kernel cores are textually identical; the decode kernel carries `#pragma unroll` on every
fixed-count loop and the lane's spec kernel carries none, which changes the compiler's FMA
contraction and summation pattern. Second treatment `bbae3c5`: the same unroll pragmas on the spec
kernel's fixed-count loops, nothing else. The probe is the gate before any server arm: PASS with the
flag on, and the flag-off run must still differ on row 1 (sensitivity). The server arms move to a
new stage built from `bbae3c5`; A360 on the first stage is superseded and not run.

## Amendment 2 (2026-09-12 06:20 UTC): unrolling did not close row 0; the C++ exact serial mode does

- Stage v2 (`runtime-gdn-roundstate-bbae3c5-b70`, `_xpu_C` from `bbae3c5` = round trip + unroll):
  the probe still differs on row 0 by one ulp with the flag on or off. The multi-row spec kernel's
  remaining difference from the decode kernel is not in the source text; it is left open (the
  probe's zero-conv case isolates it to the `g * state` decay/store step).
- The lane's own C++ exact mode (`VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1` with
  `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`) runs the plain decode kernel per verifier row inside the
  spec op with the state passing through the cache between rows. On the served stage it is
  hard-gated to four rows (MTP3 era); on stage v2 (built from `e421889`, which carries `ad25aa9`
  "Generalize exact GDN replay to MTP row count") it accepts two rows, and the probe is PASS on
  every seed and case (outputs, z, both state columns bit-identical to the serial rows), with and
  without `VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER=1`.
- Server arms (queued for the reopened window, ports 19974-19976): A361 = stage v2, flag off,
  promoted config (no-op proof for the v2 binary); A362 = stage v2, Python serial OFF, C++ exact
  mode ON with the completion barrier; A363 = same without the barrier. Gates as before:
  `afffd211…` on every 2K row; the step time is the result. A85 (2026-09-03, eager) measured this
  mode at about -15% on short rows; the promoted line is full-graph, where small launches were
  shown to be cheap (A355, A357), so the prediction is open: anywhere between A344's 42.7 and
  A356's 33.9 ms.
