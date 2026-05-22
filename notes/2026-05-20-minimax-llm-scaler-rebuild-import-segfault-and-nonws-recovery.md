# MiniMax llm-scaler rebuild import segfault and non-WS recovery

Date: 2026-05-20

## Summary

The attempted llm-scaler source-level follow-up after the 89 tok/s MiniMax
result is not promotable. Rebuilding the `moe_int4_ops` extension now produces
a shared object that segfaults during import, before vLLM starts. Restoring the
last known importable binary recovers a quality-clean fallback path, but that
binary does not expose the WS MiniMax entry point used by the promoted 89 tok/s
stack, so it falls back to the non-WS MiniMax logits path and is slower.

Do not submit this recovery result to LocalMaxxing as an improvement. It is a
useful recovery and regression note only.

## Failed source experiment

- Source tree: `/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm`
- Candidate area: `csrc/moe_batch/moe_int4.sycl`
- Initial idea: add/adjust a single-token full-shared down-kernel tile knob for
  the MiniMax full-forward custom op.
- Rebuild result: build completed, but importing
  `custom_esimd_kernels_vllm.moe_int4_ops` segfaulted in `libsycl.so.8`.
- GDB finding: crash occurred in `__strcmp_evex()` from
  `sycl::_V1::detail::ProgramManager::addImage(...)` during
  `__sycl_register_lib()` / `sycl.descriptor_reg()` while dlopening the rebuilt
  extension.
- Tried recovery build knobs:
  - `SYCL_CACHE_PERSISTENT=0`
  - `UR_L0_USE_IMMEDIATE_COMMANDLISTS=0`
  - `SYCL_DEVICE_FILTER=level_zero:gpu`
  - `LLM_SCALER_SYCL_CODE_SPLIT=-fsycl-device-code-split=off`
  - disabling unused candidate-repair blocks
  - disabling the WS MiniMax entry point
- Result: rebuilt binaries still segfaulted at import. This points to a SYCL
  device-image registration/toolchain issue in the rebuilt extension, not a
  vLLM runtime path issue.

Patch artifact for the diagnostic/recovery source state:

- `patches/minimax-llm-scaler-import-segfault-recovery-20260520.patch`
- `patches/minimax-llm-scaler-import-segfault-recovery-20260520.patch.gz.b64`
  is the GitHub-friendly compressed copy. Decode with:
  `base64 -d patches/minimax-llm-scaler-import-segfault-recovery-20260520.patch.gz.b64 | gzip -dc > /tmp/minimax-llm-scaler-import-segfault-recovery-20260520.patch`

Broken rebuilt binary retained for inspection:

- `/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python/custom_esimd_kernels_vllm/moe_int4_ops.cpython-312-x86_64-linux-gnu.so.segfault-after-htile-20260520T110918Z`

## Recovery runtime

Restored active binary from:

- `/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python/custom_esimd_kernels_vllm/moe_int4_ops.cpython-312-x86_64-linux-gnu.so.backup-20260512T064555Z`

Import check after restore:

- `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax=True`
- `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws=False`
- `moe_forward_tiny_cutlass_nmajor_int4_full_fp16_shared_from_logits=True`

Because the restored binary lacks
`moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws`, the promoted WS env fails
early. The fallback recovery env explicitly disables the WS logits path and
uses the non-WS MiniMax logits path:

```bash
export VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=0
export VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS=1
export VLLM_XPU_USE_LLM_SCALER_MOE_WS=1
export VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/minimax-nonws-restored-binary-recovery-20260520
```

Failed promoted-WS recovery attempt:

- `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/restored-backup-quality-20260520T111244Z`

Quality-clean non-WS recovery attempt:

- `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/nonws-recovery-quality-20260520T112453Z`
- Summary JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/nonws-recovery-quality-20260520T112453Z/minimax-minimax-nonws-restored-binary-recovery-strict-tp4-ctx2048-mbt512-bs256-20260520T112453Z-summary.json`

## Quality result

Status: quality passed.

- raw145 n64 exact hash:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact hash:
  `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic-suite n64 r2: passed, deterministic
- arithmetic-repeat n64 r8: passed, deterministic
- arithmetic repeat hash:
  `261779104d5abf1642713bfc560ca8d2d6c0f16edbcc929c8b0819b5a760dd7c`

## Throughput result

This is a recovery baseline only, not a promoted speed result.

- Mean output tok/s: `75.767918`
- Mean total tok/s: `101.023891`
- Output tok/s repeats:
  - `75.336001`
  - `75.970397`
  - `76.032656`
  - `75.732619`
- Total tok/s repeats:
  - `100.448001`
  - `101.293862`
  - `101.376875`
  - `100.976826`

Promoted comparison:

- Promoted WS path: `89.314195` output tok/s, `119.085594` total tok/s.
- Non-WS restored fallback: `75.767918` output tok/s, `101.023891` total tok/s.
- Delta: about `-15.17%` output throughput versus promoted.

## Next action

The immediate priority is to recover a rebuildable llm-scaler extension that
imports cleanly and still exposes the WS MiniMax entry point. Until that is
fixed, deeper source-level experiments are risky because a clean source rebuild
cannot reproduce the promoted binary state.

Concrete next steps:

1. Diff the importable `20260512T064555Z` binary provenance against current
   source assumptions and build flags.
2. Build a minimal `moe_int4_ops` subset that imports cleanly, then add back
   kernels in groups to isolate the SYCL device-image registration trigger.
3. Once the WS entry point is rebuilt and importable, rerun the promoted strict
   quality and four-repeat throughput gate before trying new performance
   candidates.
4. Continue lower-level fusion work only after the source build is again
   reproducible.
