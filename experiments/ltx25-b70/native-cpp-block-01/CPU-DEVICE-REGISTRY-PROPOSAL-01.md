# Proposed CPU fixture registry — source audit only

Prepared 2026-09-14. No implementation, native imports, compiler execution,
registry changes, endpoint or device actions. Parent owns v6 outcome/postflight.
Source pins and numbered excerpts:
[cpu-device-registry-proposal-01.json](cpu-device-registry-proposal-01.json).

V6 (PID 108612, execution session 71145) completed one eager CPU call, then
refused the first Python compile. Its explicit native Triton config=True and
native has_triton=False checks passed. The new path was independent of that
capability check: `TorchInGraphFunctionVariable._get_handlers` constructs stream
handlers by enumerating `get_registered_device_interfaces()` at
`variables/torch.py:1716–1721`, which lazily initializes the registry and calls
CUDA device_count. The unchanged trap halted. V6 recorded zero compiled results,
zero C++ calls, zero cache-metadata omissions, and both GPU backends uninitialized.
This establishes another CPU compiler discovery path, not a numerical result.

## Minimal proposed policy

Use the exact registry shape native `init_device_reg` would produce if each of
its CUDA, XPU and MTIA enumeration loops had zero iterations. This comparison is
about the resulting Python mapping only; it does not claim this host has zero
devices, simulate device_count, or preserve original GPU compiler semantics.

| Registry key, in native order | Existing native class |
| --- | --- |
| `cuda` | `CudaInterface` |
| `xpu` | `XpuInterface` |
| `mtia` | `MtiaInterface` |
| `cpu` | `CpuInterface` |
| `mps` | `MpsInterface` |
| `tpu` | `TpuInterface` |

`device_interface.py:663–681` registers those unindexed interfaces regardless of
availability, interleaving ordinal registrations only for returned device
counts. The proposed policy would use unchanged
`register_interface_for_device(name, native_class)` six times on the original,
pristine registry dict, validate the exact ordered map, then mark the existing
`_device_initialized` flag True. It would never invoke native init_device_reg or
any device-count function. Do not replace the interface classes, accessor
functions, registry dict object, handler code, or registered stream callables.
No ordinal names, including `cpu:0`, are part of this native zero-loop mapping.

Require a fresh disposable CPU process, the v3 availability False policy, v4
cache metadata refusal, v5 exact Comfy import refusal, v6 native Triton detection
disable setting, unchanged numeric OPTIONS and all frozen hardware traps. Import
the pinned native device_interface module only after these traps are installed;
install the registry policy before any compiler handler cache is populated.
Both Python and C++ compile/repeat arms use the same single registry lifetime.

**Reject `_device_initialized=True`, nonempty or replaced registry dict, foreign
classes, or existing cached handler construction at admission.** Do not clear or
repair a partial registry. Native init registers `cuda` before querying its count
(lines 665–666), so a process already stopped by the v6 trap has partial state
and cannot be reused for this proposal. No automatic retry or registry rebuild.

## Why keep the unindexed accelerator interfaces

The generic handler constructor is cached (`variables/torch.py:954–956`). Its
stream decorator gathers `device_interface.stream` callable objects and removes
duplicates using dict.fromkeys (1716–1721). It does not invoke the stream
functions while building those handlers. Keeping all six native classes retains
the same callable set/order as the native zero-enumeration case; a CPU-only dict
would remove ordinary generic handler recognition even for a CPU fixture.

`builder.py:4135–4164` likewise collects current_stream and Event identities for
output classification. Keeping the native classes also preserves that registry
metadata. CUDA/XPU interface classes capture current_device, device_count,
current_stream, properties and raw-stream aliases when their module is imported
(device_interface.py:252–264,395–398,443–455). The existing guard and import wrapper
must therefore precede that import, and relevant aliases must match the already
installed trap/wrapper identities. This avoids quietly retaining original query
functions through static aliases.

Keeping native interfaces does not itself make all their methods safe to call.
Worker property methods can still enumerate devices; direct calls must retain
existing refusal behavior. `async_compile.py:114–117` separately walks interfaces
and calls availability/property methods in pre-fork setup. CUDA/XPU availability
remains False and compile_threads remains 1, but those facts do not prove every
possible accelerator path is intercepted. No MPS/MTIA/TPU behavior is changed by
this proposal. A direct unsupported path is another diagnostic failure, not a
reason for silent policy expansion.

## Identity and qualification requirements before implementation/admission

Record source hashes, ordered pre/post registry entries with exact native class
identities, registry dict identity, prior/final initialized flag, interface module
identity, and unchanged accessor/registration function identities. At every
fixture call boundary and finalization require the same six entries in the same
order, no ordinals, no extra registrations or changed classes, and True
initialized flag. Check relevant captured CUDA/XPU aliases against the frozen
traps/wrappers. Reject metadata mutation with the existing sticky failure path;
never rebuild the registry to make a check pass.

A focused stdlib suite should AST-extract the exact registration/init/accessor
functions with fake torch/interfaces and demonstrate:

- Proposed ordered mapping equals the native initializer with three fake zero
  counts; the proposed construction itself calls none of those fake counters.
- Stream/current_stream/Event callable collection matches the same zero-loop
  mapping, including native duplicate-removal behavior; no callable is invoked.
- Original dict identity and accessors remain; empty/partial/preinitialized and
  late mutation cases are handled strictly, with no silent repair.
- Previously installed query/property/stream traps remain effective through the
  native interface aliases; CPU interfaces are the original objects.

Native qualification would still be the unchanged tiny BF16 actual block,
64/256-token stages, eager/Python/C++/repeat exact video+audio bytes and metadata,
parameter identity, 15/6/2 operation counts, two graphs per arm, no warm recompile,
exact import/cache omission counts and all device/fault gates. The proposed
registry is an additional recorded **CPU-only compiler policy difference**;
passing it would not prove an unchanged GPU compiler configuration or speed gain.
Parent review is required before implementing this proposed registry policy.
