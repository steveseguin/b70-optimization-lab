# Qwen3.8 Flash-Next exact serial GDN verifier rows in the kernel extension (`bbae3c5`)

Exported: 2026-09-13

The lossless MTP1 line's two-row verification step ran the GDN (gated delta net) verifier
rows through vLLM's Python serial path (`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`): the accepted
state copied into spec column 0, row 0 through the single-row decode kernel, column 0 copied
into column 1, row 1 through the decode kernel. It is exact and it costs 8.7 ms of a 42.7 ms
verify step, and the cost is not in its kernels or its index/copy glue (A355-A358). The
kernel extension already carries an exact mode that does the same per-row decode inside the
single `gdn_attention_spec_decode` op (`VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`
with `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`), but the served build hard-gates it to four
verifier rows (the MTP3 era); commit `ad25aa9` ("Generalize exact GDN replay to MTP row
count") is in the lane's kernel tree but not in the served `_xpu_C`. This series rebuilds
`_xpu_C.abi3.so` from the lane's kernel tree head `e421889` plus two commits; every other
file of the served stage is byte-identical.

The two commits are disclosed but inert on the promoted line: `3279856` adds an env-gated
`VLLM_XPU_GDN_SPEC_ROUND_STATE` (off) and `bbae3c5` unrolls the multi-row spec kernel's
fixed-count loops. Neither is set or used by the exact mode; the kernel-level probe
(`experiments/qwen38-flash-next-fp8-b70/probes/gdn-spec-round-state-equivalence.py`) is
bit-identical for the exact mode with and without the completion barrier, and both server
certifications (A364, A365) reproduce the certified line's exact-2K (`afffd211…`) and
exact-4K (`1d833e5f…`) pins with the quality profile byte for byte.

- base: `e421889999bc1e5a5f11044d14548b9afdba644d` (tree `ca6c804765ccb40f5e74d17b665065bd57d9cde7`), the lane's
  kernel tree head recorded as `kernels_head` by every certified Flash-Next run; it is the
  certified `2f829747` series (`../vllm-xpu-kernels-certified-2f829747/`) plus the eight
  later commits preserved as `0001`-`0008` in `../vllm-xpu-kernels/`;
- head: `bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26`, tree `e87a7a7a5deba4e816f7e24dbf0b6ccf04c03b2b`;
- bundle `vllm-xpu-kernels-q38-gdn-exact-serial-bbae3c5-20260913.bundle` carries tag `q38-gdn-exact-serial-bbae3c5`;
- `series.sha256` pins both patches, the bundle and the loadable manifest of the rebuilt stage;
  `verify-series.sh --apply` re-creates the tree.

| Patch | Subject |
| --- | --- |
| `vllm-xpu-kernels-32798565-gdn-spec-round-state.patch` | gdn spec: VLLM_XPU_GDN_SPEC_ROUND_STATE rounds the carried SSM state through the cache dtype between verifier rows (exact multi-row mode, default off) |
| `vllm-xpu-kernels-bbae3c5-gdn-spec-unroll.patch` | gdn spec kernel: unroll the fixed-count loops exactly as the decode kernel does |

## The rebuilt stage

`/mnt/usb-models/qwen38-build/runtime-gdn-roundstate-bbae3c5-b70` is the served stage
`runtime-core-moe-negidguard-b70` with `_xpu_C.abi3.so` replaced by the build of this head
(`6b95dc90c25bb0f9c2503805e4184648ddcac089ec54ec65fe7eeb13ab2b097b`); the other 17 loadable files are unchanged.
Build: `experiments/qwen38-flash-next-fp8-b70/tools/q38-build-xpu-c-gdn-roundstate.sh` (CMake
Ninja, Release, MOE_KERNELS_ENABLED=OFF, GDN_KERNELS_ENABLED=ON, oneAPI 2025.3 with
`SYCL_LIBRARY` pinned, isolated copies of the oneDNN and CUTLASS sources); assembly and
manifest: `experiments/qwen38-flash-next-fp8-b70/tools/q38-assemble-gdn-roundstate-stage.sh`;
manifest: `runtime-stage-loadable.sha256` here (copy of
`experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-gdn-roundstate-v2-loadable.sha256`).
The rebuilt `_xpu_C` additionally links `libmqa_logits_kernels_xe_2.so` (present in the
stage); that is the only NEEDED difference against the served binary.

## Server selectors

`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=0`, `VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`,
`VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`, `VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER=1`,
printed into the packet's derived launch source next to the other exact-verify selectors.
