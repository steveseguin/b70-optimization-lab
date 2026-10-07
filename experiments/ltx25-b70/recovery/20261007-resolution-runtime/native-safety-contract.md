# Native reference safety contract

This is an inactive CPU-tested overlay, not an admitted runtime or a peak-memory
guarantee. The coordinator must seal the transformed source, this module and
the adapter/session integration into a new identity before any device work.
The successful native decode arithmetic is unchanged.

`transform_sd(raw_bytes)` accepts only the exact sealed99b `comfy/sd.py`
SHA256 `2917a7982d08640ebe297ebc5cb5ad873567099c2e66688dcaff3650464dc694`.
It inserts one object-scoped callback immediately after `raise_non_oom(e)` in
`VAE.decode`'s exception handler. An attached controller raises before the
fallback flag, cache flush or tiled execution. Actual and estimator-triggered
OOMs both reach that refusal. Non-OOM errors still escape the original
classifier; unbound VAE objects retain original behavior. There is no global
default activation and no installed-package/source mutation by this module.
Once attached, these exact video/audio VAEs retain strict OOM refusal through
the end of this finite experiment, including later optimized qualification.
This is an explicit safety configuration delta, not an arithmetic change.

## Explicit lifecycle and integration

Construct exactly one `NativeReferenceSafety` for this native phase with:

- trusted `plan_sha256` and `runtime_sha256` (64 lowercase hex characters);
- exact live `objects` and their trusted `expected_residence` ownership hashes;
- injected `synchronize(card)`, `inspect(objects)` and `require_phase()` callables.

The trusted phase callback closes over the process-local session, qualification
ID and run name, e.g. `session.require_phase('native', qualification_id, run_name)`.
It must not accept an arbitrary phase chosen by submitted graph JSON. Root's
session owns the progression from native references to reference verification,
optimized preparation, candidate verification and timing. Controller snapshots
use the fixed local phase label `native-reference`; translate the session's
internal spelling inside the adapter rather than weakening the session gate.

After the accepted window probe and an explicitly admitted resident-model
preparation, wrap each exact pinned native graph execution in
`with controller.request(request_id): ...`. Do not wrap setup/optimized graphs,
do not queue overlapping native requests, and do not bypass the context manager
on execution failures. The trusted executor must also check its own success
status: some graph engines record node exceptions without raising to the caller.
If such execution fails, raise inside the context so the controller latches it.
Request names must additionally belong to the frozen plan; this module checks
nonempty uniqueness, while the session/executor verifies plan membership.

Each pre/post inspection first requires the trusted native phase, synchronizes
all four devices, then obtains a fresh snapshot. Before a request it requires
physical free bytes of 6/6/2/7 GiB on xpu:0/1/2/3 respectively. After a request
it requires 2 GiB on every card. Snapshots also require actual object IDs,
registered ownership hashes, expected devices, BF16 inference identity, full
residency, accepted encoder/window qualification, no fault, no sampler graph
routes, no decoder replicas and allocation/reservation/peak counters on all
cards. The schema is documented in the class docstring. Integer byte counts
exclude booleans, negatives and nonfinite/coerced values.

These allowances come from
`notes/2026-10-07-resolution-memory-admission.md`. They are not reservations or
a proven upper bound for the full 48-block eager sampler. Permit the first
bounded native measurement only after actual admission, then review its peaks.
Peak counters include the preexisting resident baseline unless the trusted
adapter records an explicitly scoped reset; this helper never resets them.

Any failure permanently latches the controller. Later admission, close or reuse
refuses without new inspection/device calls. A failed instance must not be
replaced to retry: the session must also halt. Failure receipts retain the
rejected snapshot when inspection returned one. `receipts` are in-memory
evidence; the caller must preserve them on success and exception. This module
makes no filesystem durability claim. On successful reference completion,
`close()` is one-way and ends reference admission while retaining its VAE OOM
callbacks until process exit; root still owns
reference exactness verification before transitioning to optimized work.

## Actual99b ownership and loader state

Do not import an alternate `host_embedding_resident_node` merely to read its
globals. The registered custom-node mirror can own a different module state.
Obtain the actual node class from `nodes.NODE_CLASS_MAPPINGS` and inspect the
globals of its actual implementation method after validating that module's
source against the new runtime inventory.

For `LTXHostEmbeddingComponents`, `load.__globals__` contains `_components`,
`_shared`, `_identity`, `_failure`, `_mode`, `_generation` and `_pending`.
Require a completed matching generation/identity, no failure/pending owners,
the accepted `control` encoder mode and unchanged shared identities.
`_components` is `(model, clip, video, audio, upscaler)`. Exact role mapping:

| Safety role | Live object |
| --- | --- |
| `sampler_primary` | `model` |
| `sampler_secondary` | sole `model.get_additional_models_with_key('ltx_layer_shard')` |
| `upsampler` | `upscaler` (LTX branch returns `CoreModelPatcher`) |
| `text_primary` | `clip.patcher` |
| `text_secondary` | sole `clip.patcher.get_additional_models_with_key('ltx_text_layer_shard')` |
| `video_vae` | `video`, with weight owner `video.patcher` |
| `audio_vae` | `audio`, with weight owner `audio.patcher` |

**Construction is not residency.** The host loader builds wrappers and splits
ownership but does not call `load_models_gpu` for sampler, upsampler or native
VAEs. A window probe loads encoder graphs, not necessarily these other models.
The adapter must perform one separately admitted full-residency preparation
before the controller can admit a native request. Charge missing model bytes
on their target devices before loading; do not evict text graphs to make room.
Checking after eviction alone is not prevention.

For registered GPU tensors, inspect both `patcher.model.named_parameters()`
and `named_buffers()` and require actual device placement, explicit expected
dtypes, registry membership and full loaded size. The inference dtype remains
BF16; integer/bool buffers must be explicitly identified rather than silently
coerced. Ownership hashes should bind tensor names, IDs/storage ownership,
shapes, dtypes and devices, not just aggregate loaded-byte counts. They are
process-local evidence and must not be confused with checkpoint content hashes.

Use `model.verify_placement()` for the sharded sampler. For text, obtain
`stack,layers = ltx_graph_text_encoder.stack_of(clip)` and use
`ltx_text_shard.verify_placement(clip, stack)`. Its actual key is
`ltx_text_layer_shard`, not `ltx_text_shard`. The three pinned99b graphs all set
node420's encoder mode to `control`: its `clip._host_embedding.owner` is None,
and the embedding remains in the registered GPU text model. Validate
`clip._host_embedding.guard()` / inventory with `require_loaded=True`.
Do not silently substitute the historical optional `host-table` mode, whose
CPU embedding owner and memory costs differ.

The actual registered `LTXTextEncoderGraphGate._apply.__globals__['_installed']`
holds `(clip, originals, captures)`. Check the identical clip and actual
`captures.summary()`/worker signatures, not merely an installed flag; window
qualification is exposed by `ltx_text_window.qualified()` and `state()`.
The actual registered `LTXGraphCaptureGate` implementation owns `_installed`;
it must be `None` for native references. The actual registered
`LTXPipelineDecode._apply` globals own `_REPLICAS` and `_REPLICA_SETS`; every
replica dictionary must be empty before references. Check the actual node
module state, not an independently imported script alias or an environment
variable describing desired replica placement.

These getters are source-audited at sealed99b; they do not replace runtime
source identity checks or a CPU-tested integration adapter. No device APIs are
imported or called at module import, and no model/device work ran to prepare
this overlay.

## Concrete adapter and no-eviction scope

`native_adapter.NativeAdapter` receives already imported trusted `torch`,
`nodes`, `model_management`, the configured session authority/module,
qualification ID, plan/runtime hashes, source inventory and fault observer.
The runtime hash is the authority's `runtime_manifest_sha256`.
`source_hashes` maps absolute source paths to sealed hashes. Include actual
registered custom-node modules and their graph/window/shard/pipeline/lean
dependencies, `comfy/model_management.py`, and baseline Torch init:
`/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/__init__.py`,
SHA256 `bd4a10ff16357ed78f45aaf4b46ce5b771fdc0e8549402206e324d0eb792c672`.
That external pin already belongs to parent99b `manifest.runtime.files`.
The adapter's fault observer must return exactly False to admit work.

Run `prepare()` inside a separately registered `native-setup` request after
the window probe. It uses the authority's actual active request name, not a
server-run label. It verifies source/global ownership and resident text, charges
missing tensor bytes per device at1.1× plus the greater of the existing loader
reserve and6/6/2/7 GiB, and calls `load_models_gpu(..., force_full_load=True)`
exactly once. It refuses dynamic patchers, clone replacement, enabled pinned
memory, changed dtypes/placement, non-control text mode, encoder ownership
changes or insufficient post-load headroom. No settings are changed.

All registered floating tensors must be BF16; explicitly inventoried integer/
bool buffers retain their types. In sealed99b `sd.py`, the native VAE calls
`first_stage_model.to(vae_dtype)` before and after non-dynamic state loading.
The video timestep buffer, audio statistics and vocoder filters/bases therefore
follow the BF16 model conversion; inspected classes do not override `_apply`
to retain FP32 buffers. FP32 velocity/RoPE/atan2 temporaries are not resident
registered buffers. If actual source-bound inventory contradicts this, refuse
and review it; never cast a legitimate buffer merely to pass admission.
Storage/tensor metadata hashes bind live ownership after preload, without
hashing or copying tensor values. Both registry membership and full loaded
sizes are checked. This separate setup completes before any native sampling.

`before_request(name)` / `after_request(name)` surround each native execution
while that exact graph request remains active in the authority. Every error
path must call `abort_request(error)`, including non-raising failed graph status.
The adapter neither submits requests nor grants unknown names. Preserve both
`adapter.receipts` and `adapter.controller.receipts` on success and failure.

During preload and each native request, `protect_residence` temporarily wraps
`model_management.free_memory`. It preserves requested memory, pin arguments
and existing `keep_loaded` entries, adds every current actual `LoadedModel`
owner, and checks synchronized physical free bytes before delegating. Requests
that would require eviction refuse before the original unload path. The
original function is restored in `finally`. This adds **no explicit cache
flush**; original Comfy GPU allocator bookkeeping remains unchanged, including
its existing zero-eviction cache-release branch. Host page-cache/swap settings
are untouched. The separate strict VAE OOM handler still refuses before any
tiled-fallback cache flush. Scoped no-eviction bookkeeping and persistent
exact-object OOM refusal are declared reference/runtime configuration deltas.

`native_state()` is between-request **observation only**: preparation must have
succeeded, the native phase must remain healthy and authority.active must be
None. It does not call numerical `require_phase`, grant execution or invent an
empty queue. Root combines this with actual prompt-queue and pipeline snapshots
and requires real quiescence for reference before/after barriers. The adapter
reports a timestamp and actual pipeline running count. An executing setup
snapshot is not interchangeable with a subsequent empty-queue barrier.

Run `python experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_native_adapter.py`.
Controls cover registered-module ownership, separate preload/request phases,
actual active names, source drift, graph/lean/replica state, preload refusal,
tensor dtypes, encoder preservation, cleanup and post-request floors. A control
extracts the actual sealed `free_memory` AST with synthetic owners to verify
caller keep entries, registry protection and refusal before original execution
when physical memory is insufficient. No actual GPU/module loading occurs.

## Offline controls

Run `python experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_native_safety.py`.
The tests extract the **actual source-pinned `VAE.decode` function AST** and run
it with synthetic tensors/devices. They exercise successful original/transformed
flow, actual and estimated OOM, unchanged unbound fallback, non-OOM errors,
source/double-patch refusal, exact thresholds, every low card, post-request
floors, identity/residence/phase faults, fresh synchronization, binding tampering,
invalid byte counts, exception latching and one-way closure. They make no model,
GPU, network or runtime-qualification claim.
