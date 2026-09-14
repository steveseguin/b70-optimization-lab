# Private C++ boundaries in the tiny LTX block — halted CPU attempt

**Inactive; compiled-block qualification did not complete. Do not rerun during a native campaign.** The first existing Python-boundary CPU compilation initialized XPU unexpectedly. The post-call gate caught this and stopped the process. No C++ compiled call, repeat, or output-parity comparison completed. The prior 119 CPU operator checks remain separate evidence; this folder does not promote them to compiled-block qualification.

## Preserved attempt

- [test_block_cpu.py](test_block_cpu.py) is the exact failed harness; [cpu-result-01.json](cpu-result-01.json) and [cpu-run-01.log](cpu-run-01.log) preserve failure, parameters, counter timeline, and command.
- [fixture.py](fixture.py) extracts the actual tiny BF16 `BasicAVTransformerBlock` initialization and input-generation arithmetic from the pinned prior CPU fixture. The source check verifies those AST bodies are unchanged: video/audio dimension32, one head, audio26 tokens, video64/256 tokens, context8, seeds17/123. Parameter count43,654 and bytes87,308 stay fixed.
- [backend.py](backend.py) copies the FX graph and retargets only the 15 RMS,6 sigmoid,2 GELU sites to the qualified CPU-only C++ binary. Original compiler options and model parameters stay unchanged. This adapter was prepared but its compiled path was **not reached**.
- [source-check-01.json](source-check-01.json) records the successful stdlib source gate before native work.
- [cache-inventory-01.json](cache-inventory-01.json) hashes all70 external cache files (2,631,985 bytes), including opaque binary/pickle artifacts without loading them. [failed-generated-source-01.json.gz](failed-generated-source-01.json.gz) retains bounded generated Python/C++ source and graph receipts (33,807 compressed bytes); no model weights, tensors, media or binaries are embedded.

The tool execution session was8264 and exited1. **The Python PID was not recorded**, so no exact PID is asserted. A tool session identifier is not an operating-system PID. This evidence gap is recorded in [initialization-incident-01.json](initialization-incident-01.json).

## Initialization evidence and limits

The initial post-import XPU check was false. The eager CPU call returned with zero new graphs and XPU still uninitialized. The first Python-boundary compiled call returned with one new graph, no recorded graph breaks or unsupported-operation events, and unchanged original parameter identities/hashes. Its subsequent XPU initialization check returned true and halted execution.

The generated wrapper contains14 CPU allocation calls,15/6/2 original Python native boundaries, and no call expressions naming CUDA/XPU. Its graph receipt contains35 metadata device entries, all `cpu`. Accelerator allocation aliases occur in generic wrapper imports, but are not called by this emitted block. This establishes CPU fixture/generated-block intent, **not proof that the compiler/driver performed no incidental accelerator work**.

A source-backed sufficient trigger exists in the installed runtime:

1. `torch/_inductor/compile_fx.py:1201` saves a compiled graph through `FxGraphCache._save_graph`.
2. `torch/_inductor/codecache.py:2306` unconditionally calls `torch.utils._triton.triton_backend()` to derive external-library cache identity, without checking whether the compiled graph is CPU.
3. `torch/utils/_triton.py:248` calls the active driver's `get_current_target()`.
4. Intel Triton `driver.py:758–760` resolves its target through the current device. Lazy `XPUUtils` construction (`:441–455`) builds/loads `spirv_utils` and invokes `mod.init_devices(self.get_sycl_queue())`.
5. `get_sycl_queue` (`:472–474`) calls `torch.xpu.current_stream()`, whose implementation (`torch/xpu/__init__.py:659`) calls `_lazy_init`, then `_C._xpu_init` at361.

The observed cache contains `spirv_utils`, `extension_utils_impl` and `arch_utils` binaries, consistent with that target-query path. This is **source-backed attribution, not a captured first-initialization stack**. Runtime context/stream initialization is real; this record cannot rule out incidental allocation or kernel activity inside driver initialization. No global FAULT was written. Parent-owned host postflight reported no observed device fault and remains the source of host classification.

## Prepared guard, not executed

[test_block_cpu_guarded.py](test_block_cpu_guarded.py) is a separate inactive successor; [guarded-diagnostic.patch](guarded-diagnostic.patch) preserves its delta from the failed harness. It records PID/PPID and installs [accelerator_guard.py](accelerator_guard.py) immediately after Torch import, before Kitchen/Inductor imports. Python and exposed C entry points for accelerator initialization, enumeration, properties, current device and streams are replaced **inside that diagnostic process only** with traps that record a bounded stack and raise before calling any original function. The exception derives directly from `BaseException` so ordinary cache `except Exception` blocks do not silently swallow it.

The guard has only been parsed as source; **it has not been imported or executed**. It does not simulate accelerator availability, alter compiler options, change installed files, mutate the live app, or automatically retry. Its first trap may be a harmless device-count/property query preceding the initialization path; that is intentional diagnostic evidence, not an operator-correctness failure.

A future safe CPU qualification must prevent the cache-metadata Triton target query from initializing devices, with any process-local suppression recorded and applied equally to both Python and C++ arms. Such suppression is **not implemented or qualified here**. Parent must schedule any further native CPU work after the active GPU campaign; no new native action followed the incident.
