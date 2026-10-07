# Native reference receipt gate: CPU component, integration pending

`reference_gate.py` validates the six native requests in reviewed plan
`307ff7547b8275c75d7f642673174cac11a45e0d7bc0041958a834544faa8745`, whose
qualified 99b parent is
`f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`.
The contract and server must both use the existing model-verification receipt
SHA `273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f`;
an internally consistent replacement model still refuses.
It does not submit requests, build a runtime, install a numerical hook, invent
state observations, or qualify the optimized candidate. There is no real
640×384 reference receipt yet. Synthetic tests are explicitly fixture evidence.

The launcher/coordinator calls:

```python
verify_references(root, plan_path, runtime_contract_path,
                  runtime_contract_sha256, output_path)
verify_receipt(receipt_path, independently_expected_receipt_sha256)
```

Paths are absolute `Path` objects. The first call writes one exclusive, fsynced
receipt only after all checks pass; its directory must already exist. The second
checks the receipt digest, rereads its retained evidence and reconstructs the
whole validation proof without writing. Neither a changed receipt with its own
new hash nor `status="reference_verified"` substitutes for successful native
executions. Both return `plan_sha256`, `runtime_manifest_sha256`,
`server_identity_sha256`, and `qualification_id` for the session authority.
The authority must compare these with its own sealed launch identity.

## Existing artifact schemas consumed

For each of the six exact planned names, the gate reads:

- `root/requests/<name>/{prompt,submission,history,result,identity}.json` and
  `events.jsonl`, as recorded by `scripts/profile-clip.py`. The submitted graph
  must equal the pinned native graph, including text, both noise seeds, geometry,
  window mode and fresh clip index. Histories must bind the same graph and unique
  successful prompt ID. Execution start/success timestamps must be ordered,
  nonoverlapping and inside the observed native phase. Events must agree with
  history timestamps and contain actual execution of nodes 364, 344, 348, 368,
  374, 358 and 414 in the required dependency order. Any cached node is refused.
- The exact server identity snapshot and
  `server_run/pipeline-<name>.json`, using the existing pipeline report schema.
  This binds server/model identity, geometry, current clip index, text hash,
  accepted window64 and conditioning fingerprint. No pending or ahead encode
  jobs and no speculation miss are allowed. Fingerprint equality is a sampled
  conditioning consistency check, **not** a full conditioning tensor proof.
- `root/output/validation/<name>/{summary.json,tensors.safetensors}`. The current
  capture format stores F32 for all four outputs. A small standard-library
  safetensors reader checks strict JSON/header bounds, exact four-tensor set,
  packed nonoverlapping offsets, fixed shapes, dtype, every value's finiteness
  and fresh raw-byte SHA-256 against the summary. It imports no Torch and does
  not touch devices. Other dtypes refuse. All four outputs and conditioning
  fingerprints must match between each native fixture and its separate repeat.

The expected shapes are images `[25,384,640,3]`, video latent
`[1,128,4,12,20]`, audio latent `[1,8,26,16]`, waveform `[1,2,48480]`; sample
rate is 48000. Determinism must be enabled and warn-only disabled. A changed
candidate graph, reordered/missing/duplicate execution, altered source/runtime,
bad shape/hash/nonfinite tensor, cached execution, or failed repeat prevents
receipt creation. All evidence files are reread again immediately before writing.
Root `FAULT.json` and the actual server `resolution-halt.json` failure latch
refuse validation, including a halt appearing during the final evidence recheck.
Symlinks, nonregular files, hard-linked evidence, oversized inputs and duplicate
JSON keys refuse. No reference tensor may be retired before later verification.

## New required runtime contract, not existing measurement evidence

The trusted integration must produce a
`ltx.native-reference-runtime-contract.v1` JSON object with:

- `plan_sha256`, `parent_manifest_sha256`, `server_run`,
  `server_identity_sha256`, `successor_manifest_sha256`,
  `model_verification_sha256`, and `request_names` in the exact six-plan order.
- Nonempty `runtime_evidence`: absolute-file-path to SHA-256 bindings for the
  reviewed successor's source closure, observation implementation, pre-native
  residency/memory admission and installed OOM-refusal evidence. The gate
  rehashes these files; the sealed launcher owns their semantic admission.
- `before_native` and `after_native`, each `{path, sha256}`, identifying actual
  observations made by the trusted runtime adapter while admissions are closed.

Each observation uses proposed schema `ltx.native-reference-state.v1` with
`phase="native_reference"`, matching `server_identity_sha256` and
`qualification_id`, an integer Unix `timestamp_ms`, integer zeros for
`sampler_routes`, `lean_sampler_installs`, `decode_replicas`, and
`oom_fallback_attempts`, and empty arrays for `queue_running`, `queue_pending`,
`pending_encode`, `pending_sample`, `pending_decode`, and `pending_save`.
`native_residency_admitted`, `no_owner_eviction`, and
`oom_to_tiled_refusal_installed` must be true. Their timestamps bracket all six
native executions. Runtime must also enforce these invariants during the phase;
two observations alone cannot prove no transient installation or eviction.
The contract digest is supplied from the trusted coordinator, never from a graph
input or inferred from a client's assertion of success.

These observations and runtime contract **do not exist merely because this CPU
component exists**. The forthcoming adapter must populate them from real state;
unavailable fields mean refusal. Upstream `comfy/sd.py` can enter tiled decoding
after either estimated or actual OOM. The required refusal must halt before
tiling/cache-clearing, not relabel a tiled result afterward. Native memory at
640×384 remains unmeasured; the gate does not itself admit GPU memory.

## Phase boundary and limitations

This component certifies only `native_reference → reference_verified`.
`session.py` owns `require_phase(role, qualification_id, run_name)` and compares
receipt identities before advancing to `optimized_preparation`. A separate
real candidate parity verifier must gate `candidate_verified → timing`; this
module cannot authorize either transition. The six references must precede
sampler graph capture and replica/lean installation. Completed native evidence
cannot retroactively authorize an earlier optimized execution.

Receipts are local trusted research records, not signatures against a malicious
host administrator. The gate checks retained bytes and execution records;
source closure and trustworthy observation hooks remain launcher obligations.
Evidence is not a reservation: concurrent file mutation after the final recheck
is excluded by the coordinator's frozen-evidence barrier. A pass covers three
same-size native sampler/decode fixtures with the accepted graph-sharded/window
encoder, not an all-eager path, other prompts, sustained reliability, visual
quality or throughput.

CPU controls:

```bash
python3 -B experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_reference_gate.py
```

Tests use the pinned real request graphs and actual JSON schemas, synthetic
identities/events and tiny real safetensors bytes. Expected tensor dimensions
are temporarily reduced and the model-verification constant uses a synthetic
fixture digest in the test process; no model output is represented as
measured evidence. The helper itself remains fixed to full-size F32 captures.
