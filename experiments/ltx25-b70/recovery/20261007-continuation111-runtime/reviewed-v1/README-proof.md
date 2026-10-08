# Native continuation 111 proof reconstruction

`ProofVerifier(packet, manifest, manifest_sha, run, plan, identity_sha)` accepts
trusted sealed packet/run locations and the frozen inner plan dictionary.
`produce(name)` returns a JSON-safe receipt; integration exclusively writes it to
`run/continuation-proof-NAME.json`. `verify(name, path, sha)` hashes that fixed
receipt and independently reconstructs the entire admitted prefix. Neither
method writes files, queries a process/endpoint, imports Torch, or submits work.
Success returns strict `verified: true` plus source/plan/process identity, name,
prompt ID, execution timestamps, and hashes of every consumed evidence file.
Native receipts include complete four-tensor capture metadata and archive hash;
chunks 0/1 also include the source-bound frame-48 anchor binding. Replay receipts
compare all four tensor payload hashes and conditioning fingerprint to the same
chunk in pass 0. Conditioned chunks require their own pass's predecessor proof.

## Artifact locations and input contract

`ROOT = run.parent`. Client artifacts are **ROOT/requests/NAME/**
`prompt.json`, `submission.json`, `history.json`, `result.json`, `identity.json`,
and `events.jsonl`. Native captures are **ROOT/output/validation/NAME/**
`summary.json` and `tensors.safetensors`. Server-local lookalikes are refused.

All following receipts live directly under `run`:

- `server-identity.json`; `resolution-before-NAME.json` and
  `resolution-after-NAME.json` retain the existing source-bound active-request
  state schema. Genuine node events, prompt graphs, source identity, history,
  success timestamps, uncached execution, and strict request ordering must agree.
- `continuation-observation-NAME.json` contains common identities plus actual
  quiescent `state` and `native_snapshot` (null only for the window probe).
  Historical immutable observations allow later verification without live reads.
- `text-window-probe-NAME.json` is validated by the exact sealed110 setup validator
  copied to packet `source/scripts/setup_gates.py` and pinned in this module.
- `native-preparation.json` contains the adapter snapshot and preload admission
  receipts. `native-memory-before/after-NAME.json` retain native safety schemas.
  Preload arithmetic, complete resident ownership, per-card pre/post floors, and
  snapshot order are checked. These floors are not measured physical peak bounds.
- `pipeline-NAME.json` retains native text-window encoder evidence; four-tensor
  archives require complete expected F32 shapes, finite values, exact header and
  payload bounds, and metadata hashes matching freshly streamed tensor bytes.
- `capture-checkpoint-NAME.json` has common identities and `prewrite`, the actual
  capture guard receipt: exact ordered native prefix, prompt/graph identity,
  six-capture cap, fixed per-file charge, and complete byte accounting.
- `provider-receipt-NAME.json` has common identities, `calls: 1`, `binding`,
  `anchor_metadata`, `predecessor_name`, `predecessor_proof_sha256`, and
  `current_graph_sha256`. Binding must match freshly reconstructed predecessor
  bytes/context; anchor metadata must identify an owned contiguous CPU F32 image.
- `conditioning-receipt-NAME.json` has common identities, current-request
  `guard_receipts`, full global `controller_receipts`, `failed: null`,
  `native_call_binding` and actual `runtime_policy`. Begin/A/B/finish ordering,
  controller receipt ranges, source-bound encoder cache owner/thread and zero
  residue, before/after floors, tensor ownership, source-derived encode estimate,
  actual dtype/device policy and native method source closure must agree.

Common fields are `plan_sha256`, `runtime_manifest_sha256`,
`server_identity_sha256`, `name`, and `prompt_id`. Native method binding is
`{method: "LTXVImgToVideoInplace.execute", sources: {absolute_path: sha256}}`.
Integration supplies source/code/owner checks through the actual native bindings;
proof reconstruction also checks those source files against the sealed manifest.
No caller-supplied success boolean replaces execution, memory, source or tensor
checks. Global fault/halt files remain grounds for refusal.

## Bounds and validation limits

Metadata reads are capped at 8 MiB each, safetensors headers at 64 KiB, archives
at 146230536 bytes each. Streaming uses 1 MiB blocks. Reads reject symbolic links,
nonregular files, multiple hard links, duplicate JSON keys and file-identity
changes; all consumed files are checked again before returning. Prefix proof
reconstruction intentionally rereads prior captures for fresh evidence. The
private shape seam in parser tests permits tiny synthetic archives only; the
production plan fixes all six captures to the full 49-frame dimensions.

CPU tests cover the full eight-request prefix, strict source/plan/proof binding,
genuine uncached node events, root-path separation, memory/owner drift, exact
capture accounting, predecessor context, stage/controller/cache/policy corruption,
last-chunk waveform replay corruption, file changes and bounded parser failures.
They do not establish live conditioning memory feasibility, semantic continuity,
audio assembly quality, or runtime admission. Root still owns packet sealing,
independent review and operational gates.
