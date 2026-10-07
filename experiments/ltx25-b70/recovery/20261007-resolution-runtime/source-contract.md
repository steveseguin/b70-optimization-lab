# Geometry/source overlay contract (CPU preparation only)

Status: implemented source transformer and CPU controls, **not materialized or
GPU-qualified**. No installed source or sealed packet was edited. Ownership of
this component is limited to `geometry_overlay.py`, `test_geometry_overlay.py`
and this contract. Session authority, native safety, reference verifier, runtime
builder and live integration are separate components.

Parent manifest: `f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`.
Pinned semantic plan SHA:
`307ff7547b8275c75d7f642673174cac11a45e0d7bc0041958a834544faa8745`.
Workload qualification ID:
`29ef0d7afecc1254cb50477649b24a36d78648c177b7de3c553b02771ada5dc1`.
The ID identifies a workload, **not a passed comparison**.

## Pure source API and exact closure

`geometry_overlay.transform(path, raw_bytes) -> new_bytes` accepts only the
seven `SOURCE_HASHES` entries and their exact immutable99b SHA256 values.
`transform_sources({path: raw_bytes, ...}) -> {path: new_bytes, ...}` requires
all seven inputs and checks canonical/custom-node output equality:

- `source/scripts/ltx_output_size_98.py`
- `source/scripts/pipeline_node.py` and `source/custom_nodes/ltx_pipeline_lab/__init__.py`
- `source/scripts/pipeline_sampler_node.py` and `source/custom_nodes/ltx_pipeline_sampler_lab/__init__.py`
- `source/scripts/pipeline_decode_node.py` and `source/custom_nodes/ltx_pipeline_decode_lab/__init__.py`

Unexpected hashes, incomplete inventory, unknown paths and reapplication refuse.
The geometry module retains its original source then adds the explicit mode.
Each node's numerical function body is unchanged; only its optional inputs,
function arguments and receipt decorator change. Added arguments are consumed
before sampler `**chain`, never passed as numerical model arguments.

Builder obligations: preserve original bytes as provenance, write a new packet,
bind all seven new hashes and both module mirrors, update extension/startup and
source-transition contracts, include the fixed plan, and bind the exact
`ltx_resolution_session.py` source. This transformer does not copy files,
construct a manifest, approve a live model configuration or attest the complete
runtime on its own.

## Node and session interface

The three nodes gain optional inputs:

- `comparison_mode`: default `historical`; new value `same-size-native-v1`.
- `qualification_id`: default empty; new mode requires the exact ID above.

The existing `output_size` and `speed_only` inputs remain. New mode requires
640×384, `speed_only is False`,23/25 `two-way`, W1, B1, shared pools, one decoder
replica configured for xpu:2. These environment identity checks do not assert
that the replica has already been installed; reference phase must have none.

Before numerical work, the transformed receipt decorator calls:

```python
ltx_resolution_session.require_phase(role, qualification_id, run_name)
```

Roles here are exactly `text`, `sampler`, `decode`. The session is configured
once by the sealed launcher after final server identity. It must bind the
currently admitted exact request graph/name and evidence-driven phase; graph
inputs cannot provide their own phase JSON. The returned dictionary must carry
matching `role`, `run_name`, `comparison_mode`, `qualification_id`, `plan_sha256`,
plus SHA256 `runtime_manifest_sha256` and `server_identity_sha256`.

Allowed numerical phases:

| Role | Allowed phases |
| --- | --- |
| text | native_reference, optimized_preparation, timing |
| sampler/decode | optimized_preparation, timing |

Every post-native numerical phase also requires `reference_receipt_sha256`.
Timing additionally requires `candidate_receipt_sha256`. No numerical node is
admitted at the `reference_verified` or `candidate_verified` barriers. The
session owns evidence validation, request registration, phase transitions and
quiescence. The geometry layer checks the returned contract; it does not replace
those checks or certify a client-supplied digest. The native safety component
may separately use the session's `native` role.

Authorization is local to the node call through a ContextVar and is reset even
when numerical code raises. Exceptions propagate unchanged. Nested inherited
or historical authorization refuses. A worker context without the numerical
authorization cannot call the formerly refused non-speed larger-size path.

## Metadata and unchanged historical behavior

Authorized numerical receipts say
`same-size-native-reference:external-four-tensor-gate-required`, contain the
bound `phase_authorization` and set `output_parity_claimed=False`. Neither a
successful node nor phase metadata claims that all output tensors match.
The separate native/candidate verifiers provide that result.

Background completion/save and maintenance receipts lack a request ContextVar.
They read `ltx_resolution_session.auxiliary_metadata()`, which returns None
before configuration or the current fixed session identities/phase afterward,
with role `auxiliary`, run_name None and output_parity_claimed False. These
receipts are labeled `same-size-native-reference:auxiliary-no-output-parity` and
carry `session_observation`, **not** numerical `phase_authorization`. Observing
session metadata does not allow numerical execution or advance phases.

Without a configured session, the historical metadata behavior is unchanged.
Historical default256×256 references still name w93c/B2/B4 as before; historical
larger-size arms still require speed-only, and `require_reference_size()` still
refuses stored-reference use outside256×256. The old reference-loader branch
is not repurposed. Larger same-size references are verified by the new external
reference gate; internal seeded-latent decoder probes remain consistency probes,
not independent full-clip references.

## CPU evidence and remaining integration

Run:

```bash
python3 -B experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_geometry_overlay.py
```

**13 controls pass**, including old geometry/speed/oracle refusals, exact source
and mirror closure, unchanged numerical bodies, current session.Authority
integration, no active request refusal, phase restrictions, wrong workload/plan/
request/runtime refusal, absent reference/candidate receipts, W2/B2/alternate
layout refusal, exception propagation, context isolation, and auxiliary metadata
that cannot grant admission. Actual parent source and transformed geometry are
executed on CPU; numerical node bodies are AST-compared, not imported. No Torch,
model or GPU is imported by these controls.

Still required: complete successor source/manifest/launcher validation, trusted
session begin/finish integration around actual graph execution, session setup
request registration, native safety residency/OOM guards, real independent
reference verification, candidate verification and phase barriers, memory/storage
admission including queued tails, and the reviewed bounded live driver. The
native VAE guard must reject both proactive-estimate and allocation OOM before
soft-empty-cache or tiled fallback. This geometry component neither installs
that guard nor claims such fallback is prevented yet.
