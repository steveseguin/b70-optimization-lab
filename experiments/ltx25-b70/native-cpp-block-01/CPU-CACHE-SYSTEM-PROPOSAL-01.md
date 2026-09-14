# CPU cache-system metadata proposal — source only

Prepared after the v7 diagnostic. No successor implementation, native import,
compilation or device action. Exact installed source excerpts and SHA256s:
[guarded-v7-cache-system-source-01.json](guarded-v7-cache-system-source-01.json).

## Recommended bounded next policy

Use the native unavailable-CUDA exception path in `CacheBase.get_system`, while
preserving all cache functions and numeric compiler OPTIONS. The pinned method
(`codecache.py:329–357`) first computes its Triton key, then wraps
`torch.cuda.current_device()` and CUDA properties in
`except (AssertionError, RuntimeError)`. That handler returns the native empty
system dictionary hash. V7's BaseException correctly escaped it and stopped
compilation. Reaching current_device establishes that this invocation already
passed the preceding Triton-key calculation; it does not prove every possible
future key helper is query-free.

A proposed process-local wrapper around the frozen `torch.cuda.current_device`
trap would raise a recorded ordinary `RuntimeError` **only** for the exact pinned
native `CacheBase.get_system.__wrapped__` code/globals, bound to the actual
codecache class/module, during the explicit CPU compilation scope with all prior
policies intact. Every other caller would delegate to the frozen sticky trap,
never to hardware. Install the wrapper after the guard and before availability
and native interface imports capture callable identities; later bind the
source-pinned cache method. Before binding, every call must remain a sticky
refusal. No existing callable alias should be rewritten after import.

The native method has no device/input argument. Thus the CPU restriction must be
supported by the already-validated fixture and compilation phase, plus the next outer
pinned `FxGraphHashDetails.__init__` cache-key frame: its signature at
codecache.py:1481–1487 retains `gm` and `example_inputs` in locals at the call.
A narrow admission can require that exact code/globals frame, a flat input
sequence containing at least one tensor, all input tensors reporting CPU device
metadata, and the pinned fixture's CPU-only graph parameters/buffers. Reject
unrecognized opaque inputs and tensor-free cache keys rather than broadening the
policy. The native constructor separately probes the default accelerator for
tensor-free inputs at 1572–1576, so those inputs are explicitly outside scope.
Do not claim the immediate caller alone proves a CPU graph. This admission design
still needs source/fake review before implementation.

Require native `CacheBase.get_system` cache initially empty and exactly one
recorded ordinary refusal for this new process. Its original functools cache
then supplies the same native fallback to both compiled arms and stages. Check
native fallback key/structure, callable/caller/module identity, exception count
and all inherited hardware traps. Do not force another miss, clear caches,
reinstall wrappers or repair partial state. Cold/warm counts should be based on
this one shared native function cache, not one expected refusal per model call.
Retain the existing four FX cache-save omission gates and two graphs per arm.

This is another explicit **CPU diagnostic metadata policy**, not unchanged GPU
cache identity or hardware configuration. Its benefit over blanket cache disable
is retaining AOT/FX cache-key construction, serialization, existing save evidence
and warm graph-reuse checks. Full byte/metadata parity and the native 15/6/2
operation counts still need qualification; there is no speed claim.

## Supported cache-disable alternative and why it is broader

The installed public compiler config supports
`TORCH_COMPILE_FORCE_DISABLE_CACHES=1` (also the older
`TORCHINDUCTOR_FORCE_DISABLE_CACHES`) at `torch/compiler/config.py:98–108`.
Inductor's `force_disable_caches` aliases that setting (`config.py:165–166`).
AOT local and remote cache selectors explicitly return False when it is set
(`autograd_cache.py:115–140`); AOT compilation skips `try_load` when neither
selector is active (`aot_autograd.py:1210–1229`). Inductor's `use_cache` also
requires the setting False (`compile_fx.py:1025–1034`).

That flag would avoid the captured AOT/FX cache-key path, but it changes a broader
compiler subsystem and would eliminate the existing expected four FX cache-save
metadata omissions. A successor using it would need to explicitly revise those
cache-specific gates to zero, while retaining exact outputs, emitted operations,
Dynamo graph/recompile limits, state identity and all device traps. Same-process
compiled-function reuse is a separate mechanism and must still be tested rather
than inferred from the cache-disable flag. There are additional native
`CacheBase.get_system` callers at codecache.py:365/368, so disabling these cache
entry paths is not proof that every system-metadata call disappears.

Separately setting `TORCHINDUCTOR_AUTOGRAD_CACHE=0` only disables local AOT cache;
FX still constructs its own key. `TORCHINDUCTOR_FX_GRAPH_CACHE=0` separately
controls the local FX cache and does not itself force remote-cache selectors
False. The single supported force-disable setting is the clear broader option
if parent chooses to trade cache-behavior coverage for a simpler CPU-only probe.
It also selects `with_fresh_cache_if_config` at compile_fx.py:820–827, creating
a fresh cache directory with delete=False; artifact paths/retention would need
explicit accounting. Numeric OPTIONS can remain unchanged in either option, but the complete compiler
configuration cannot be described as unchanged when cache flags differ.

Before implementation: parent chooses the narrow caller-bound refusal or the
broader supported setting. Preserve v7 evidence, independently review the selected
admission/count semantics, and run source/fake tests. No immediate new native
attempt is proposed; encoder integration retains priority.
