# Continuation111: consumed runtime interfaces

Source-only audit, October 7. No imports of runtime/model code, model calls,
GPU observations, endpoint calls or tests. This maps the sealed110 consumers to
the future native-only111 authority; it does not implement or admit that runtime.
The plan is banked in commit `36d2b341f`. The corrected stage guard is banked in
`3886394b6`, with independent review and37 combined safety tests passing. Its
signatures below are integration obligations; runtime assembly is still pending.

All sealed paths below are relative to
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110`.
Its manifest SHA is
`bfa78fcf6af59acc3d63318ca97c61846b3a9b80999f6f17cb4c4d3651f2ad09`.
`S/` abbreviates `source/scripts/`; `C/` abbreviates `resolution/components/`.
Line numbers describe those immutable files, not a future successor.

## Authority compatibility surface

| Consumer and source lines | Exact call or attribute | Required result / semantics |
| --- | --- | --- |
| `S/native_adapter.py:133–151` | `NativeAdapter(*, torch, nodes, model_management, session, qualification_id, run_name, plan_sha256, runtime_sha256, source_hashes, fault_check)` | `session` is normally the module `ltx_resolution_session`; adapter takes `session._authority` if present. `source_hashes` maps resolved absolute paths to SHA256, including packet source and installed Torch/model-manager dependencies. `fault_check()` must return literal `False` for admission. |
| Adapter `161–175` | `session.require_phase('native', qid, current_name)` | Dictionary with `phase='native_reference'`, exact qualification ID, plan SHA and `runtime_manifest_sha256`. It must bind the actual active request, not just return matching strings. |
| Adapter `177–185` | `authority.lock`, `healthy()`, `active`, `_metadata('observation', None)` | Reentrant lock; `healthy()` raises after permanent failure. Between-request inspection requires `active is None` and the same native metadata. Keep phase `native_reference` through all six captures and proof barriers; there is no need to advance into an optimized phase. |
| Adapter `348–357` | `authority.active['name']`; `authority.requests[name]['phase']` | `prepare()` runs inside the admitted prepare request, whose row phase must be `native-setup`. `requests` is a name-to-row mapping. `prepare()` is one-shot and clears its current name afterward. |
| `S/executor_guard.py:19–60` | `install(executor_class, authority, before_request, after_request, on_failure=None)` | Patches `execute_async` once. `authority.begin(name, prompt, prompt_id)` returns the exact row; callbacks take `(row, prompt_id)`. `authority.finish(status_messages)` runs after postchecks and before the genuine deferred success is released. Return from `finish` is ignored. |
| Executor `61–89` | `on_failure(row, prompt_id, error)`; `authority.halt(error)` | Failure cleanup only after begin succeeded. Halt must latch before durable writing; receipt failure must not unhalt. Executor records cleanup/receipt errors while preserving failed status. No retry or lifecycle operation. |
| `S/ltx_output_size_98.py` extension, authored at `C/geometry_overlay.py:38–81` | `ltx_resolution_session.require_phase(role, qid, run_name)` | Text role for the native text node. Required fields: `role`, `run_name`, `plan_sha256`, `qualification_id`, `comparison_mode='same-size-native-v1'`, `phase='native_reference'`, 64-hex runtime and server identity SHAs. Reference/candidate receipt SHAs are not required in native phase. |
| Geometry extension `115–146` | `session.auxiliary_metadata()` | Outside a numerical receipt context: dictionary with same identities, `role='auxiliary'`, `run_name=None`, native phase, `output_parity_claimed=False`; current session also includes `halted`. This labels observations only. Returning `None` falls back to historical metadata and is inappropriate after111 authority installation. |
| `S/runtime_observer.py:19–57` | `session.pipeline_snapshot(pipeline)` | Under `pipeline._LOCK`, return `{'running': int, 'stages': {name: {'queued_indices': [...], 'jobs': [...]}}}`. Each job has `index, done, error, tag, target, started, finished`. Preserve real completed-but-uncollected jobs. |
| `C/integration.py:71–78`; capture guard `155–164` | Active capture callback, under authority lock | Return `name, prompt_id, plan_sha256, graph_sha256`, deriving graph SHA from `authority.requests[active['name']]`; never accept graph/capture-node caller declarations as authority. |

Keep module-level `configure(...)`, `_authority`, `require_phase(...)`,
`auxiliary_metadata()`, `require(...)`, `canonical(...)`, `digest(...)`,
`strict_json(...)`, `read_regular(...)`, `write_exclusive(...)`,
`pipeline_snapshot(...)` and `require_quiescent(...)` if retaining the indicated
consumers. Their sealed definitions are at `S/ltx_resolution_session.py:22–102`
and `318–337`. A new small authority can preserve this surface without retaining
the optimized-phase machinery or its `advance()` implementation.

Authority state actually shared by these paths: `plan`, `requests`, `lock`,
`active`, `failed`, `completed`, `runtime_sha`, `identity_sha`, `phase`, `run_dir`.
The old metadata factory also exposes nullable `references_sha` and
`candidate_sha`; preserving both as `None` avoids unnecessary receipt-shape
changes. Its active request is `{name, prompt_id, start_ns}`. Additional trusted
per-chunk proof state belongs alongside this state, not inside mutable graphs.

**Do not transplant110 admission unchanged.** Its `begin()` at session `210–252`
orders requests only within each row phase, has a hardcoded50 capture cap, and
does not consume111 `requires_proofs`.111 needs exact global eight-row order,
unique prompt IDs, graph SHA, six capture reservations, completed prior request
**and** durable verified proof dependencies before begin. All setup rows already
exist in111 `plan.requests`; passing them again as `setup_requests` triggers the
constructor's duplicate-row refusal (`160–168`). Keep row phases `native-setup`,
`native-reference`, `native-repeat`, all mapped to authority `native_reference`.
Do not confuse the controller snapshot phase `native-reference` (hyphen) with
the authority phase `native_reference` (underscore).

## Native adapter and state schemas

`prepare()` returns a snapshot and leaves `adapter.ready=True` and
`adapter.controller` attached (`native_adapter.py:348–402`). It first discovers
actual registry owners, admits the missing resident bytes, makes its existing
full-residency load, and attaches `NativeReferenceSafety`. These are future
runtime operations; this audit performs none. `before_request(name)` and
`after_request(name)` return controller receipts, not bare snapshots (`442–469`).
Receipt schema is `{event, request_id, required_physical_free_bytes, snapshot,
admitted, allowances_are_not_peak_bounds}` (`native_safety.py:128–175`).
`native_state()` returns a fresh snapshot with `observation_only=True`, only
between requests (`native_adapter.py:433–440`). `abort_request(error)` restores
the scoped no-eviction wrapper and latches failure (`471–478`); capture its
receipts even if preparation refused before a controller existed. Do not call
`close()` during chunk proof barriers: it disables native availability.

Snapshot (`native_adapter.py:404–431`) contains:

- `plan_sha256`, `runtime_sha256`, `phase='native-reference'`, `fault=False`;
  `text_graphs_captured=True`, `window_qualified=True`, zero `sampler_routes`
  and `decoder_replicas`.
- `residence`: exact roles `sampler_primary`, `sampler_secondary`, `upsampler`,
  `text_primary`, `text_secondary`, `video_vae`, `audio_vae`; each has
  `object_id, device, dtype='torch.bfloat16', fully_resident=True,
  ownership_sha256`. Device mapping is0/1/0/2/3/3/3 respectively.
- `physical_free_bytes`: all four `xpu:N` integers; `peaks`: each card's
  `allocated,reserved,peak`; `constructor_fp32_state` separately documents
  allowed constructor buffers rather than falsely calling every buffer BF16.
- `observed_state={text_capture, window, pipeline_running}`, residence dtype
  semantics and `timestamp_ns`.

The ordinary runtime state from `runtime_observer.actual_state(fault=False)`
is a different schema: queue counts plus IDs, pipeline snapshot,
`fault, preview_pending, preview_failures, sampler_routes, lean_state,
decode_replicas, captures_frozen, loads_frozen, registered_module_paths`.
`require_quiescent` (`session:88`) requires empty prompt queues, zero workers,
empty queued indices, no unfinished/error jobs, and no preview tasks/failures;
`no_tails=True` additionally requires no retained jobs. During admission only,
the old authority permits the currently executing prompt (`queue_running<=1`)
and checks a copy with that count zero. Do not falsify the recorded snapshot.

`NativeAdapter._discover/_state` (`207–293`) **still need these registered
classes and defining module globals**, even in111: `LTXHostEmbeddingComponents`
`load`; `LTXTextEncoderGraphGate` `_apply`; `LTXGraphCaptureGate` `_apply`;
`LTXPipelineDecode` `_apply`; `LTXPipelineTextEncode` `_apply`;
`LTXPipelineSampler` `_apply`. It verifies class/function/code/global identity
and defining `NODE_CLASS_MAPPINGS`, not a separately imported mirror. Keep their
existing registrations and supporting `window`, `pipeline`, text adapter/shard,
graph capture and lean modules. The optimized nodes remain unused: routes,
freeze flags, lean installs and decode replicas must stay absent. W2/B1 and
20/28 source configuration still identify the unchanged loaded stack. Accepted
text capture remains48 layers with24/24 placement. Removing these modules is
not a safe shortcut for a native-only scheduler.

## Registration and exact native result handling

The launcher writes server identity before `integration.install(...)`, then
executes `source/main.py` (`launch/serve-encoder.py:418–431`). Installation
configures authority and the executor guard but must not discover loaded node
owners yet. `main.py:549–558` creates `PromptServer`, then loads nodes.
`C/runtime_packet.py:237` supplies the tiny custom package
`source/custom_nodes/ltx_resolution_lab/__init__.py`:
`from integration import NODE_CLASS_MAPPINGS, install_routes; install_routes()`.
This supplies the prepare node and installs routes while the server exists.
`nodes.py:2255–2277,2305–2315` executes that package and registers its mapping.
Extend this one mapping with the two111 classes, and retain once-only installation;
do not load a second integration module under an alternate name.

The native conditioner is a **V3 node**, unlike these simple lab mappings:
`nodes_lt.py:133–177`, registered through `comfy_entrypoint()` at1352 and
`nodes.py:2316–2341`. Resolve
`nodes.NODE_CLASS_MAPPINGS['LTXVImgToVideoInplace'].execute`, source-pin its
underlying classmethod/function, and call its exact keyword API
`(vae, image, latent, strength, bypass=False)`. It does not have the lab node's
defining `NODE_CLASS_MAPPINGS`; do not use the adapter's legacy `_globals`
helper for this native V3 class. Source-bound class/module/method identity is
needed instead.

At `comfy_api/latest/_io.py:2510–2541`, `NodeOutput(*args, ui=None, expand=None,
block_execution=None)` stores `args` as a tuple; `.result` is that tuple (or
`None` when empty), and indexing reads `args`. With required `bypass=False`,
native conditioning returns `NodeOutput({'samples':..., 'noise_mask':...})`.
The guard's trusted unwrap callback must require the exact loaded NodeOutput
type, one result, no expansion/block/UI, then inspect that LATENT dictionary
without replacing or mutating the native result. The bypass branch returns a
plain tuple, but it is forbidden by111 and should not motivate a permissive
fallback. `execution.py:362–410` accepts `_NodeOutputInternal` returns even from
a legacy wrapper; therefore the111 wrapper can return the original NodeOutput
unchanged. No tuple conversion is necessary.

Provider runtime wrapper: bind active request and actual plan/runtime first,
load/own the checked IMAGE from that request's accepted predecessor proof,
then call `guard.begin_request(run_name, anchor=image,
expected_anchor_sha256=...)` once for conditioned requests. Stage wrapper:
require supplied image is that owned object, strength1 and bypassFalse, then
`guard.run_stage(stage, request_id=run_name, vae=vae, latent=latent,
native_call=exact_native_execute)`. Postrequest integration must require
`guard.finish_request(run_name)` after A/B succeeded and before emitting
success. Both stage calls must occur inside the adapter's already active native
request and no-eviction scope. Chunk0 does not begin a conditioning request.
Failure cleanup must preserve the first failure and keep the anchor alive until
native use is finished; it cannot turn an incomplete A/B pair into success.

## Smallest successor source changes

| File or exact seam | Required111 delta |
| --- | --- |
| New `session.py` under existing module alias | Keep the compatibility surface above; replace fixed110 pins/counts/phases with eight-row native authority and proof registry. Preserve durable before/after/halt evidence and uncached execution requirements. |
| New `integration.py` plus the existing one-line custom loader | Runtime wiring, prepare node's exact111 name, provider/conditioner classes, trusted inspection/unwrap callbacks, per-chunk proof actions, first-native and first-conditioned barriers, failure evidence and finite final replay proof. Replace110 action schedule rather than retaining candidate/timing actions. |
| Geometry authority extension | Repin plan/QID in the sealed49-frame `ltx_output_size_98.py` extension. Retain `same-size-native-v1`, accepted49-frame arithmetic and native text authorization. The original overlay generator consumes exact99b inputs; do not feed already transformed110 bytes to it. Either reconstruct its declared source chain or source-pin one precise successor delta. Canonical and custom-node mirrors must remain equal if changed. |
| Capture helper + capture node | Use reviewed111 `capture_adapter.transform_guard` on exact110 helper, retaining alias `ltx_duration_guard`; configure six full rows only and trusted active callback. Existing capture node at `capture_node.py:59` already calls the helper before writes, so it needs no extra tensor work or changed serialization. Persist reservation checkpoints against completed rows/proofs. |
| `comfy/sd.py` | Apply separately reviewed111 encode-OOM refusal to source110; retain existing decode refusal. Bind both to the same native controller. No retry/fallback weakening. |
| New anchor/stage-guard modules | Include frozen reviewed sources and their callback/native-method inventory. Anchor context must use actual111 plan/runtime identities, not prototype context or110 identity. |
| New bounded client/proof driver and packet assembly | Register only the fixed eight graphs, wait for durable per-chunk proof, independently replay all four tensors, preserve storage/source/fault checks. Keep retained application lifecycle. Finalize actual aggregate storage/cache admission and source closure before any build/launch. |

Reuse byte-identical `native_adapter.py`, `native_safety.py`, `executor_guard.py`
and `runtime_observer.py` where possible. `setup_gates.validate_window(report,
name, identity_sha)` (`C/setup_gates.py:29–54`) has no110 plan/QID pin; its
source-bound49-frame/window40-prompt/model checks remain applicable. The full110
reference/candidate gates and schedule are not the111 proof controller.
Do not weaken window qualification to just the boat prompt. Do not count a
server execution-complete receipt as a verified capture/predecessor proof.

## Verified source inventory

The following hashes were checked against the sealed110 manifest and file bytes.
Script/component mirrors above have matching hashes. These pins are inputs to
the audit, not a substitute for a future111 manifest.

| Sealed110 path | SHA256 |
| --- | --- |
| `source/scripts/native_adapter.py` | `f39420afe2907dab4075d05419be1cd1740cfd8e12732c558fae9b2dc91666e8` |
| `source/scripts/native_safety.py` | `8a98f462417c4e5b630bbeb023666acc3829f8248361fb3b8ce0f73fa998fa0c` |
| `source/scripts/executor_guard.py` | `1a2ec2ec7a08321c0cacd9625952658df04e07b861a0091a98ebc688c3fb947d` |
| `source/scripts/ltx_resolution_session.py` | `0e8d63b3ddbf727c69e1b06f166af9b16867d1b3790067caac50718df810fed0` |
| `source/scripts/runtime_observer.py` | `475ede8de04d5cd45fc3bc0e550d6c7f4d9d00da1bd129095d6736c8fd6ff0b8` |
| `resolution/components/geometry_overlay.py` | `cdec475c12f8b5257addffda74fb4c5423af069dae186649c73aedf7c9900ae7` |
| `source/scripts/ltx_output_size_98.py` | `1699cbdff6992a950c25ce8ccb3f5bd395e9b3b34e1a18a747e25a63aca356eb` |
| `resolution/components/integration.py` | `63dd416b478a4ccb1dd2ce3bbc6eae8b58de4ebdf5466504fd33a7ae4ce78e3a` |
| `resolution/components/setup_gates.py` | `000c806bd2fa771d3260f2d06a3fc9c229dcde7c59ac99ff0ece15a55407f43a` |
| `resolution/components/runtime_packet.py` | `c4af003c493f54ed6bd514765e24c840212785f1ed89a212317bb863e6dfede9` |
| `source/scripts/ltx_duration_guard.py` | `0f1b45631d87caf61e6d7b1396f9ddfd0fbdd66e719dd9df6abc9c2622c63036` |
| `source/scripts/capture_node.py` | `ba880ce9114bd15b7b62c0719eb6620978c483f92ade8294d338a0c7d85164f2` |
| `source/custom_nodes/ltx_resolution_lab/__init__.py` | `49de5dc29f27a6dbe16232ee2d5e8207cb617e0d84c02c114a4b0ccc504072ae` |
| `source/comfy_extras/nodes_lt.py` | `09ddb30d42244d64ae72e9c64261d1a6b4c512afe0570372222c43dbebd64243` |
| `source/comfy_api/latest/_io.py` | `c2a5aded4895a1adf1acb2df6c011fdfb74e15b0d4fd331ec00ea7562d91d91d` |
| `source/execution.py` | `a628d8c81b8381147a8dafa5133340ab02e54a05694db4013833138297e7b9dc` |
| `source/nodes.py` | `e498f0dfe9146d56ddeff184ade4b402edd6e6c4eaca136ae112c8be3914bc96` |
| `source/main.py` | `d8cdcb6c4158766069722c6beae524b023ae9dfe720cbd5af8264d1497e45756` |
| `launch/serve-encoder.py` | `ea8025de915fed5d4a9961a53226c025006cb37fb731b633dd7c86550d3dc5e8` |
