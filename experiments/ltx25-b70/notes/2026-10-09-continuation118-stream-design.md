# Continuation 118: the timing split, fingerprint safety snapshots, a decoder-graph pool cap (built, not launched)

*2026-10-09. CPU only: no GPU, no server, nothing launched. Sources and tests:
`recovery/20261009-continuation118-stream/`. Build receipt: `data/resume-20261008/continuation118-build.json`.
Packet: `prepared-continuation-stream-118` (manifest in the receipt and in LAUNCH.md). Parent: packet 117
(manifest `5826174e…0802c9`). Inputs: the two 117 live runs (`notes/2026-10-09-continuation117-results-97.md`,
`-121.md`) and open question 2 of the 117 design note. Numbers marked "estimate" are estimates.*

## Why

117 at 97 frames runs a 4.04 s chunk every 4.82 s (1.19 s of work per second of video); at 121 frames, decoder
graph off, a 5.04 s chunk every 5.40 s (1.08 s/s). Two items did not move as designed and are not explained by
the receipts:

- `submit_to_sampler_start` is 0.51–0.52 s at both lengths (prediction 0.33–0.40; 116b 0.435) although the
  precomputed stage-A/B encodes are never waited for (`waited_s` 0.00). The receipt has one number for it.
- The period minus `submit_to_anchor_ready`, the receipt staging and the client leaves ≈ 0.28 s per chunk.

And two costs are known but not yet attacked: the six four-card safety snapshots per chunk (estimated 0.05–0.09 s
each), and the 121-frame dg1 launch, which missed the 9 GiB xpu:3 floor by 76 MB.

## What 118 is

Packet 117 plus three server-side levers, each with an off form that is packet 117's code path, none of which
changes a request graph or an output byte; names `stream118-`, packet id 118, run names with `-sm<walk|fp>-`.

| lever | launch variable | default | off form |
|---|---|---|---|
| A. timing split | (always on) | on | measurement only: marks and records, no check or arithmetic changes |
| B. fingerprint safety snapshots | `LTX_SNAPSHOT_MODE=walk\|fingerprint` | `fingerprint` | `walk` = 117's `CandidateAdapter._inspect`, timed |
| C. decoder-graph pool cap | `LTX_DECODER_GRAPH_POOL_CAP_GB` | unset | unset = 117 (both decoder methods captured) |

The snapshot mode and the pool cap are not request fields and not in the qualification id: they do not touch a
graph, a tensor or a numerical contract, and keeping them out of the plan keeps the plan the size it was (the
authority hashes the whole plan on every `healthy()` call, see below). The plan has the same 132 keys as 117 with
new identities.

## Lever A: the timing split (measurement only)

New marks (all `time.time_ns()`), every one outside any check:

- admission middleware: `admission_received` (before the body is read), `precheck_done`, `queued` (ComfyUI's
  `/prompt` handler returned: `validate_prompt` and the queue put);
- an outer timing wrapper of the guarded `PromptExecutor.execute_async`: `executor_entry` / exit (it records
  two timestamps and passes results and exceptions through; it refuses to install twice or without the guard);
- `before_request`: `request_snapshot_start` / `_done` around the unchanged `adapter.before_request`,
  `before_request_done`;
- every node's first `executing` event (`node_starts_ns`; `stream_text`, `stream_anchor`, `stream_condition_a`,
  `377` also as named marks);
- the stage nodes: `condition_{a,b}_lookup_done` (fixed inputs and the precompute lookup/take) and
  `condition_{a,b}_done`;
- each four-card snapshot (from the snapshot inspector, lever B): label, start, end, parts.

`timing_s.submit_split` tiles submit -> sampler A into `precheck`, `comfy_validate_queue`, `queue_to_executor`,
`authority_begin` (the authority re-classifies the graph and observes the runtime), `before_request_checks`,
`request_before_snapshot`, `before_request_tail`, `executor_to_first_node`, `first_node_to_condition_a` (text
window/reuse copy and hashes, anchor file read and check, `begin_request`), `condition_a_lookup`,
`condition_a_tail` (with the stage-A before snapshot, the replayed encode and the after snapshot inside it),
`dispatch_to_sampler_a`, and `other`; tiles plus `other` equal `submit_to_sampler_start` exactly (tests). The
receipt also carries `authority_checks` (calls and seconds of the authority's `healthy()`, its plan-digest share,
and the status route's calls and seconds during the request) and `turnaround`: the predecessor's receipt ->
this submit, split into `receipt_staged_to_commit` (after_request tail, executor, `finish` with its observer),
`commit_write` (exclusive write + fsync), `commit_to_first_served` (first HTTP 200 of the predecessor's receipt
route: the client's poll), `served_to_admission` (client verify, graph build, state write, POST),
`admission_parse`, `other`. The client adds `client_turnaround_s` and `client_post_s` to its manifest lines.

Two suspects the split is built to confirm or clear (CPU measurements on this host, uncontended):

1. The authority's `healthy()` checks the plan identity by canonical-JSON SHA-256 of the whole in-memory plan:
   **4.3 ms per call** (738 kB canonical). It runs twice per `require_phase`, i.e. four times per four-card
   snapshot (the controller's `require_phase` and the inspect's `_state` each call it), plus in every
   `active_row` and authority operation. A frame chunk makes several tens of calls; `authority_checks.healthy_s`
   measures it per request. This is NOT changed in 118 (it is the plan-identity invariant; a frozen plan would
   be the equally strong alternative and is an owner decision).
2. The client polls the status route every 0.05 s while a chunk runs; the route builds a sizable JSON on the
   event-loop thread (GIL beside the prompt thread). `authority_checks.status_route_{calls,s}` measures it.

## Lever B: four-card safety snapshots from residence fingerprints

**What a snapshot does (117, sealed `CandidateSafety._snapshot` over `CandidateAdapter._inspect`).**
`require_phase` (authority phase and active request, adapter not failed, fault observer); synchronise
xpu:0..3; `_state` (the phase again, node bindings, layout, host identity, the 48-route inventory, W1 B1, text
capture, window, the text encoder inventory and placement); the sampler `verify_placement` (walks every tensor of
both sampler owners); `_rows` for all seven roles (one dict per parameter and buffer, about 6,800) serialised to
canonical JSON and hashed per role; `_free` (four syncs and readings) and the allocator counters; then the
controller's checks (identities, phase, fault, routes, residence/ownership = the admitted SHA-256, VAE binding,
floors 8/8/2/9 GiB before and 2 GiB after, counter validity).

**What changes in fingerprint mode, and why it is the same check.** A row of the walk is a pure function of
(kind, name, `id(tensor)`, `untyped_storage().data_ptr()`, shape, dtype, device) plus static facts (the
integer-buffer flag follows from the dtype; the FP32 constructor exception follows from role/kind/name and is
re-checked, with its source pin, on every snapshot). At the placement event, right after the full-residency
preparation that computed the controller's admitted fingerprints, `ResidenceLedger.capture()` walks once more,
requires the walk's SHA-256 to equal the admitted one for every role, and binds it to the tuple of those facts
(checked row by row against the walk's rows, and `parameters()`/`buffers()` against the walk's order). A later
snapshot enumerates the same tensors the same way (`named_parameters()`, `named_buffers()`, same order and
de-duplication) and reads the same facts; equal tuples imply byte-identical rows, so the walk's SHA-256 is the
bound one. If any fact differs, the fingerprint mode does not decide: it runs the walk (`_rows` + fingerprint)
and returns the walk's result, so the controller refuses exactly as in walk mode. The sampler placement check uses
the same tuples (both sampler owners' tensors on their load devices, the shard registration, no patches) and calls
the sealed `verify_placement()` on any deviation. Everything else is the unchanged code: `require_phase`,
`_state`, the four synchronisations, `_free`, the counters, and every controller check. `CandidateSafety` itself is
untouched (its source stays pinned by `conditioning_guard`); only its injected `inspect` callable is the
inspector. In walk mode that callable is 117's `_inspect` with a timer around it.

**What the fingerprint cannot see that the walk can.** Nothing, because the residual gap of a pure event
fingerprint was kept as a walk: a tensor's storage pointer, shape, dtype and device can change without any
Python-visible placement event (the C-level `Tensor.data` setter, `set_`, `resize_`,
`torch.utils.swap_tensors`, a direct `_parameters`/`_buffers` write), so every snapshot still reads those facts
of every tensor (partial fingerprinting). Dropped are only the per-row dict building, the JSON serialisation and
hashing of about 6,800 rows, and the second walk of the sampler tensors. Both modes are equally blind to what
neither reads (tensor values; a freed tensor whose id and storage address are reused for an identical tensor).

**The runtime proof.** In setup and qualification every snapshot runs both modes (the walk's snapshot is the one
the controller admits) and compares them verdict for verdict (the identity, phase, fault, route and residence
fields; both refusing is agreement, one refusing is a disagreement). In streaming the walk runs beside the
fingerprint on every 20th chunk (`stream_seq % 20 == 0`) and, from the first snapshot of a chunk whose reading is
within 0.5 GiB of a card's pre-request floor, on every later snapshot of that chunk. A disagreement writes
`snapshot-118-refused.json` and raises inside the snapshot, which latches the server; the launcher then refuses
fingerprint mode until an owner archives the latch. The decode thread's xpu:3-only snapshot of the precomputed
encodes (P7) uses the same ledger and policy (and a disagreement there writes only the snapshot latch, not the
precompute latch).

**Cost (CPU, this host, uncontended).** Residence + sampler placement for 6,832 tensors (the checkpoints' counts:
transformer 4,349 split 20/28, Gemma 686, upsampler 72, video VAE 396, audio VAE 1,329): walk 22.4 ms, fingerprint
7.7 ms per snapshot. The rest of a snapshot stays: two `require_phase` (four plan digests, 17 ms), the remaining
`_state` checks (≈ 5 ms estimate), the syncs (whatever GPU work is queued) and the readings. Estimate per snapshot
≈ 50 ms walk -> ≈ 35 ms fingerprint, i.e. **−0.06 to −0.20 s per chunk** (six snapshots, GIL contention from the
decode thread, the preview writer and the status polls inflating the Python part 1–2×), central −0.10 s. This is
below the 0.25–0.4 s the 117 note hoped for: the serialisation is the only part that can go without weakening a
check. The receipts measure it directly: on dual chunks `parts_s` has `dual_walk` and `dual_fingerprint` of the
same snapshot.

## Lever C: the decoder-graph pool cap at 121 frames

**Why 121 dg1 was refused.** Graph chunk 0 had 15.83 GB free on xpu:3 before its decode; the two captures, the
uncached eager reference decode and the cone left 9.59 GB at the next precompute snapshot (floor 9.66 GB). At 97
frames the 116b captures grew reserved memory by 2.66 GB (`forward_pre_diffusion`, including its warm-up on a
fresh side stream) and 1.51 GB (`forward_diff_step`, likewise); ×1.25 at 121 ≈ 3.3 + 1.9 GB.

**The cap.** `LTX_DECODER_GRAPH_POOL_CAP_GB=<GB>` (decimal GB, 0.25–16): methods are captured in first-call order
(always `forward_pre_diffusion` first: the cone's first call); a method whose first call comes when the measured
reserved growth of the captures already made is at or above the cap becomes a capped signature: the ORIGINAL method
runs eagerly inside the graph-decode scope, with the same bounded caches, for the life of the server. The
signature bound and the freeze apply to capped signatures exactly as to captured ones. With `1.0` at 121 frames:
`forward_pre_diffusion` is captured (stages 1–4 replay, used by the cone on the chain and by the display decode),
`forward_diff_step` is capped (stage 5 eager in the display decode; the cone's stage 5 was eager anyway).
Unset = 117 behaviour (a cap above the growth also captures both).

**Exact by construction.** The eager method with the caches is what every capture is proven against (the capture's
eager reference runs with the caches active), and the qualification's graph chain still decodes every chunk twice
(uncached eager, then graph/capped) and requires byte-identical images; the cone still compares its anchor with
the display decode's last frame on every chunk. CPU: graph-mode decodes with a capped `forward_diff_step` equal the
uncached eager decode byte for byte (fp32, bf16) on the sealed decoder, and the cone over the capped shadow equals
the full last frame.

**Memory (estimate; the floors are the stop rule).** The capped stage 5 runs in the default stream's cached
blocks, which the qualification's uncached eager decodes already reserved; the cap removes the `forward_diff_step`
capture's pool and its side-stream warm-up (≈ 1.9 GB at 121). Expected xpu:3 free at the precompute snapshots
**11.0–11.8 GB** (1.3–2.1 GB above the 9.66 GB floor; ≥ 0.5 GB margin required). The release of eager-transient
blocks after the cone was not done: `torch.xpu.empty_cache()` acts on all four cards' allocators while the samplers
run on xpu:0/1 and may capture graphs, and is not a per-device call; that is neither simple nor provably harmless.

**Speed (estimate).** The cone's stages 1–4 replay instead of running eagerly: −0.05 to −0.12 s on the chain at
121 frames against 117 dg0 (0.955 s cone). The display decode stays eager in stage 5 (≈ 2.5 s, off the chain; 117
dg0 fitted 2.68 s).

## Exactness and the gate

- A (timing): records only; tests show the marks wrap unchanged calls.
- B (snapshots): CPU-proved with the REAL sealed `NativeAdapter._rows`, `native_adapter.fingerprint`,
  `CandidateAdapter._inspect` and `CandidateSafety` over a fake residence world: every single mutation the walk can
  see (storage moved, shape, dtype, device, tensor replaced, added, removed, renamed, reordered, buffer, load device,
  dynamic mode, loaded registry, loaded size, the FP32 exception's dtype and source pin) and 300 random mutation
  sequences give the walk's SHA-256 or the walk's exception, role by role; value changes are invisible to both;
  the six snapshots of a request give identical controller receipts and synchronise the same cards in both modes;
  a moved tensor halts both modes with the same reason. End to end (the real runtime on CPU fakes): the dual
  policy, a disagreement (latch + halt), a near-floor dual, walk mode, and the gate's snapshot rows.
- C (pool cap): byte gates unchanged; the gate requires the graph chain's chunk 0 to capture exactly the methods
  its record lists, captured and capped disjoint and covering both methods, and no capped method without a cap.
- The 117 gates (three-chain byte identity, the decoder graph's dual decode, the cone check, the precompute dual
  check, the 113/114 reference at 49/97) are unchanged.

## Predictions (medians of 100 stream chunks after the first 10; frame anchor, cone/1/1, text reuse, two-way20-28)

| launch | period | work / s of video | falsified if |
|---|---|---|---|
| 97, dg1, sm fp | **4.65–4.78 s** (central 4.72; 117: 4.82) | 1.15–1.18 | period > 4.82 or < 4.55 |
| 97, dg1, sm walk (control) | 4.74–4.90 (= 117 4.82 ± noise) | 1.17–1.21 | outside 4.70–4.95 |
| 121, dg0, sm fp | **5.25–5.37 s** (central 5.31; 117: 5.40) | 1.04–1.07 | > 5.40 |
| 121, dg1, cap 1.0, sm fp | **5.15–5.32 s** (central 5.25) | 1.02–1.06 | > 5.37, or xpu:3 < 10.16 GB at any snapshot |

Per-snapshot (receipt `snapshots[].seconds`): walk 0.04–0.10 s, fingerprint 0.03–0.07 s; on dual chunks
`dual_fingerprint / dual_walk` 0.5–0.8 (falsified above 0.9). Timing split at 97 (estimates; the point is to
measure): `request_before_snapshot` + the two stage-A snapshots 0.12–0.25 s, `authority_begin` +
`precheck` 0.04–0.12 s, `other` < 0.05 s (if larger, a step is unmarked); turnaround `commit_to_first_served`
0.02–0.08 s (0.05 s client poll), `served_to_admission` 0.02–0.10 s.

## What CPU cannot verify

- The fingerprint's speed on the live server and its agreement with the walk on the real seven roles (the dual
  qualification snapshots and every 20th chunk decide; a disagreement latches before admitting anything).
- That no device-side mechanism moves a parameter without changing the facts the fingerprint reads (the same
  blind spot as the walk; the dual walks re-check).
- The pool sizes and floors at 121 frames with the cap (estimates above; the 9 GiB floor stops the run), the speed
  of the capped stage 5 in the display decode, and the stage-1–4 replay gain on the cone.
- The cost of the timing marks themselves (≈ 20 extra timestamps and a few small dicts per chunk; expected < 1 ms).

## Build

Packet `prepared-continuation-stream-118`, manifest `cb68515a1e770697ad0ac2d0c2abd9709780043e9d1579cba81706bb53f482f6`,
121,138,538 bytes, zero `__pycache__`, source closure verified against 117 … 111. CPU suites: 118 289/289 (249 adapted
from 117, 33 new unit tests, 7 new end-to-end cases); client suites as in the build receipt (118: 15/15). The
`--check-only` rehearsal (LAUNCH.md §1.7) is for the coordinator with a fresh health receipt; it was not run here.
The first launch is 97 frames, dg1, cone/1/1, fingerprint.
