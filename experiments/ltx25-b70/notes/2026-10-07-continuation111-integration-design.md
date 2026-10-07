#111 native-only integration design

Source-only design against sealed `prepared-duration-full-110`, manifest
`bfa78fcf6af59acc3d63318ca97c61846b3a9b80999f6f17cb4c4d3651f2ad09`.
This does not authorize registration, packet construction or execution. The
[anchor/graph prototype](../recovery/20261007-continuation111-reference/README.md)
remains inactive. Root owns the separate encoding-memory/safety decision.

## Minimum setup and workload

Exactly **two existing setup graph requests** are necessary to reuse the accepted
native adapter, followed by six serial native chunk requests: eight submissions,
six full raw captures. This count assumes encoding admission is implemented
without an additional model probe. Any new probe must be explicitly counted and
budgeted before a future plan is sealed.

1. Rebind110's window-probe graph: host loader420 → graph-sharded text gate425
   → `LTXTextWindowProbe`470. Accept the existing source-bound window verdict.
   This one graph includes substantial internal text model/capture/probe work on
   both encoder workers; it is not a zero-work bookkeeping request.
2. Rebind prepare-native graph: `LTXResolutionPrepareNative`490. Call the
   existing adapter's one-shot `prepare()` and preserve the preload, full-residence,
   no-eviction and physical-memory guards.
3. Run pass0 chunks0/1/2, then pass1 chunks0/1/2, with seeds42/43/44 in both
   passes. A durable complete-proof barrier follows **every** chunk before the
   next is admitted. Chunk0 is ordinary native generation; chunks1/2 use their
   own pass's preceding capture at frame48.

These two setup graphs are already the first two rows of sealed110's
`resolution/setup-schedule.json`. `pipeline_node.py:331–383` defines the window
probe and verifies its source/runtime identities. `native_adapter.py:349–401`
requires the accepted text graph/window before full-residency preparation.
Sampler pin/capture/coverage/freeze, decoder replica probes and optimized
candidate/timing phases are unnecessary for this native-only reference.

## Reuse boundaries and actual dependencies

| Component | Minimal111 treatment |
| --- | --- |
| Native arithmetic sources | Keep110's host20/28 ownership, text encoder/window, native samplers, upsampler and decoders. Add the two native image-conditioning nodes only on subsequent chunks. |
| `native_adapter.py` | Preserve actual registry/source/owner/dtype checks, seven model roles, prepare/before/after/native-observation calls and scoped `protect_residence`. Keep native phase metadata compatible. |
| `native_safety.py` | Preserve8/8/2/9GiB admission,2GiB post-request floor, owner fingerprints and fault latch. Add separately reviewed encoding protection; no threshold relaxation. |
| `executor_guard.py` | Reuse exact graph admission and delayed success until after-request safety/completion checks. Preserve original failure evidence and halt behavior. |
| `session.py` interface | A small111 authority implements only setup/native/complete/halted order, six known graph identities, one active request, unique prompt IDs, capture cap6 and per-chunk proof bindings. Keep `require_phase`, lock/active/requests/healthy and metadata methods consumed by the adapter and geometry extension. |
| Geometry authorization | Retain49-frame/640×384 shapes and native text authorization; bind new111 plan/QID. Existing source nodes import `ltx_resolution_session`, so preserve that module alias or explicitly repoint every pinned consumer. |
| Capture writer/guard | Reuse exact full F32 shapes and prewrite semantics, but freeze six full roles only—no setup/fill allowance. Bounds are6×146,230,536=877,383,216 bytes before other costs. |
| Window gate/observer | Reuse `setup_gates.validate_window` and the actual queue/pipeline/fault inspection portions of `runtime_observer`; preserve source/server binding. |
| Reference proof | Reuse bounded safetensors parsing, finite/hash validation and request-history/event checks as primitives. Do not import110's fixed ten-fixture phase counts or whole reference receipt schema unchanged. |
| Client/coordinator | Fixed eight-request serial order, bounded waits, durable events, source/process/fault/free-space checks, no retries, and six explicit post-request proof actions. No optimized scheduler/candidate machinery. |

NativeAdapter's `_discover` still resolves registered graph-capture, pipeline
sampler and pipeline decoder nodes, plus `ltx_pipeline`, window, text shard,
graph helper, lean helper, model management and Torch. Its `_state` checks those
optimized states are **absent**. Keep those existing source modules installed
and source-bound as observer dependencies; omitting their execution does not
permit removing their registrations. The numeric W2 environment remains part
of this inherited observer contract; this reference does not run a W2 sampler.

## Active-request anchor binding without mutable graphs

Seal all six concrete graph topologies in the future plan. Replace the prototype's
external IMAGE edge with one new provider node whose only graph selector is the
fixed current `run_name`; do not allow arbitrary file paths or caller-supplied
anchor hashes. Both conditioning nodes consume that provider's one IMAGE result.
All seeds, prompt, node settings and current graph hashes are known before
execution. Anchor bytes and hashes become known at runtime and belong in the
authoritative predecessor-proof table, not in a newly mutated prompt graph.

At provider execution, under the existing authority lock, require the active
name/prompt ID, expected pass/chunk, pinned current graph, and the immediately
preceding accepted proof. Derive capture path and expected whole-file/anchor
hash from that table. Validate model/runtime/plan/prompt/seed/predecessor-graph
bindings, then use the prototype loader to reread the predecessor and return
owned F32 CPU storage. Recheck the active/proof identities before returning.
The provider must refuse chunks0, wrong-pass links, faults, missing/changed
predecessors and repeated unauthorized consumption. Disable cross-request
provider caching; ordinary reuse of its result by the two consumers inside one
admitted request is intended. Do not reuse pass0 anchor files for pass1.

The prototype currently needs no standalone anchor payload file: immutable
capture plus small binding receipt suffices. If payload artifacts are later
added, prewrite-bound each2,949,120-byte frame plus metadata and include all four
predecessor anchors in storage admission. Retain all six full captures and
bindings through replay/seam review. File identity checks do not replace
coordinator ownership of predecessor lifetime.

## Per-chunk proof and finite replay receipt

For each request, preserve the adapter's before/after memory receipts and
source/owner/fault checks. After server completion and actual quiescence, verify
registered graph/prompt/event identity, uncached required-node execution, exact
four-tensor header/shape/dtype/finiteness/hash, capture prewrite receipt and fresh
memory evidence. Bind the complete capture SHA to a durable per-chunk receipt.
For predecessor chunks0/1, derive and bind frame48 from that same capture.
Require exact provider consumption evidence for subsequent chunks, including
the newly added conditioning nodes executing before their respective samplers.

The first chunk's ordinary-native shape/memory barrier remains necessary. The
first **conditioned** chunk also needs explicit encoding admission and a
post-condition proof before further conditioned requests; the ordinary first
chunk does not exercise VAE encoding. Every later request rechecks accepted
receipt/file hashes so a missing or mutated predecessor cannot pass from a
cached decision.

Each pass1 chunk must match all four full tensor hashes/shapes of its corresponding
pass0 chunk; this includes raw audio unchanged. Final evidence links all six
per-chunk proofs, four predecessor links, two setup verdicts, six memory pairs,
source/model/runtime/plan IDs, final quiescence and fault state. Mark exact
deterministic replay separately from seam/motion/identity quality and unresolved
audio alignment. Count145 new video frames per chain; replay is repeat evidence.
Record latency and buffering including anchor verification and native conditioning.
No throughput, coherence, endurance or continuous-AV claim follows automatically.

## Mandatory encoding safety delta

Sealed110 `native_safety.transform_sd` guards only `VAE.decode`'s OOM-to-tiled
fallback. `source/comfy/sd.py:1418–1451` has a separate `VAE.encode` path and
silent tiled fallback.111 must add an equally source-pinned encode refusal and
fresh admission for the native320×192 and640×384 conditioning encodes, retaining
all existing memory floors. Root is preparing that separately. Decoder headroom
and110's text-to-video qualification do not bound this new workspace. Repoint
any existing exact `comfy.sd` startup consumer hashes when that source changes.

This is a bounded integration design, not a second general campaign framework.
