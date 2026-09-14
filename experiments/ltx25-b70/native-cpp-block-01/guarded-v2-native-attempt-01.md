# Guarded v2 native import attempt — 2026-09-14

**Guard refusal confirmed; compiled C++ qualification remains incomplete.** Root ran one diagnostic, process91112 (parent91111, tool session27411), which exited1. Its startup identity was saved and fsynced at2026-09-14T16:47:43.883733+00:00, before Torch import. The copied [startup receipt](guarded-v2-startup-01.json) matches the SHA256 bound by the [result](guarded-v2-result-01.json).

The only recorded accelerator attempt was `torch.xpu.device_count`, blocked by `AcceleratorAccessBlocked` in phase `guarded-Kitchen-Inductor-import`. The captured stack runs through `comfy.ops` → model/memory management → `comfy.quant_ops` → `comfy_kitchen` → Triton backend `_register` (`comfy_kitchen/backends/triton/__init__.py:349`) → `torch.xpu.is_available` (`torch/xpu/__init__.py:290`) → the device-count trap. The original device-count implementation was not called by that trapped entry.

Both `xpu_initialized_at_exit` and `cuda_initialized_at_exit` are false. `calls` is empty: there was no tiny-block eager execution, CPU compilation, compiled repeat, C++ boundary execution, or output comparison. This import-time availability query occurs **before** the original suspected `FxGraphCache._save_graph` → Triton target-metadata path. The attempt neither proves nor disproves that later source-backed initialization mechanism. In particular, the first blocked query is not identified as the original initialization cause.

Parent's [postflight](guarded-v2-postflight-01.json) at16:49:06UTC records the probe process absent, server84255 unchanged and idle, that server as the only render-node owner, no fault latch and no matching kernel faults. The saved [journal output](guarded-v2-journal-postflight-01.log) contains no entries. No restart, retry, device action or global FAULT write followed this controlled refusal.

## Bounded next implications

The trap is doing what its contract promised: accelerator enumeration is blocked as well as actual initialization. An unmodified full model import on this host consults accelerator availability even when the harness passes Comfy's `--cpu` flag. Getting beyond that import would require a separately reviewed, explicit CPU-only availability/import policy; none was added here. Any such diagnostic-only policy must be recorded, applied equally to the Python and C++ arms, and retain initialization/property/stream traps. It must not silently change the existing numerical or compiler qualification contract.

After that import barrier is addressed, the CPU cache-metadata path remains a separate unresolved barrier. It needs direct guarded evidence before proceeding to the four-graph tiny-block comparison. There is no automatic retry or further native work scheduled until root finishes the confirmation campaign. The current result is a successful diagnostic refusal and a **non-passing compiled-block gate**, not a native C++ speed or quality result.

The original failed harness, prior guarded versions, source deltas and evidence were not changed. Only this note and the current-status wording in `GUARDED-V2.md` were added/updated.

Pinned inputs:

```json
{
  "experiments/ltx25-b70/native-cpp-block-01/guarded-v2-result-01.json": "f260a91a12a620ad37a3d3a709790f42ccf3c0c5b4568a0dbb55a9c80899d1db",
  "experiments/ltx25-b70/native-cpp-block-01/guarded-v2-startup-01.json": "f884cd92d75b0e5fa8862fb657856b74460872375b7c20d03f85e9366f652455",
  "experiments/ltx25-b70/native-cpp-block-01/guarded-v2-preflight-01.json": "65fad5398c1004c3fe168dda236eacbb3f0c7789b131cfe0d5db0457a593fd91",
  "experiments/ltx25-b70/native-cpp-block-01/guarded-v2-postflight-01.json": "f2a12b84558c4dd11f8e2430be1bd6b16e1483d72b7c4923ab79b0213fe90e8b",
  "experiments/ltx25-b70/native-cpp-block-01/guarded-v2-journal-postflight-01.log": "19c4e28b2f54ea8f217db4e622b0a5c758efa7b77ce2dc0394b6d159568c0b2e",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/comfy_kitchen/backends/triton/__init__.py": "9dd763c1688725d8d7cb4461e1e97687e4ca9e60ab19c6d369e47b175b59b8fa",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/xpu/__init__.py": "391dd518f4fe944cf0e7dae37f4f4f63b0b54973fdc7e93d76627ffcbda3852c"
}
```
