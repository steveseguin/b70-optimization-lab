# Bounded continuation delivery and state — 2026-09-14

Implemented a byte-delivery reader and an inactive single-request coordinator
for the continuous-generation stage of [the plan](../PLAN.md). These consume the
[float-anchor graph](continuation-anchor-provider-01.md). They do not submit
requests, install runtime nodes, play video, or qualify a new generation result.

The same host fault persisted at the start of this turn: known PIDs96119 and
102144 remained present with SIGINT pending, PID95931 remained present, and
`FAULT.json` was present. No Torch/native-library imports, GPU requests,
application restart, reboot, reset or host-setting changes were performed.
Existing protected output files were read without modification. The previous
goal turn was progress: it committed the provider and actual reference-byte
evidence; this turn implements its next required state/delivery layer.

## Exact delivery

[continuation_delivery.py](../scripts/continuation_delivery.py) verifies all
four expected F32 tensors against the completed capture's summary. It checks
their shapes, ranges, hashes and finite sample bits using reads of at most64KiB.
It records25 frame hashes, the frame24 anchor hash and the opened file identity.
Summary determinism flags are explicitly **reported settings**, not runtime
attestation or original-reference parity. The full receipt is returned only
after all four tensors pass. [Detailed reader evidence](continuation-delivery-cpu.md).

`iter_delivery_frames` rebinds the file/header/ranges and checks each frame
against its verified hash. It yields one exact786432-byte float32 RGB frame at
a time, with no media decoding, clipping or precision conversion. Chunk0 yields
frames0..24; subsequent chunks yield1..24. The overlap never counts as new
delivery. File closure is guaranteed on cancellation; completion requires iterator
exhaustion, including the final file-identity check, rather than merely seeing
its final yielded frame. Retained application buffers depend on the future sink;
this reader never stores a complete output clip in memory.

## Coordinator behavior

[continuation_stream_state.py](../scripts/continuation_stream_state.py) binds
a stream to runtime/model identity hashes and the pinned graph builder. It owns
these explicit transitions:

`idle -> reserved -> submitted -> ready -> delivering -> awaiting_finish -> idle`

- Reservation builds the actual inactive graph, using the latest committed
  capture/anchor, the caller's exact prompt and uint64 seed. A second reservation
  is refused while a request or delivery remains outstanding.
- Completion requires a successful, completed history with the reserved prompt
  ID and exact graph hash, the same supplied runtime identity, and a successful
  four-tensor capture verification. The future transport must fetch and attest
  the history/identity; passing dictionaries here is not execution evidence.
- Delivery offers one token-bound frame at a time. The sink must acknowledge
  before advancing. Duplicate/wrong acknowledgements, missing acknowledgements,
  early close, changed files and faults halt the state and preserve pending
  evidence. No automatic retry or restart exists.
- Final commitment waits for iterator exhaustion and all25 or24 acknowledgements.
  Each record retains prompt/seed, predecessor link, graph/history hashes, server
  prompt ID, all four tensor hashes, anchor hash and summary hash. Sink acceptance
  is counted separately from physical playback; no playback claim is set.
- At most three committed captures are retained. Another request is refused at
  that limit. Only the oldest non-predecessor record can be retired, after its
  capture directory is observed absent and a deletion-receipt hash is supplied.
  This method does not delete footage. The future cleanup owner still must
  preserve replay/review evidence and handle previews; full disk retention is
  not yet integrated or qualified.

The hash chain is a provenance ledger for this stream. It includes storage and
submission identities, so it is not a path-independent replay oracle. A future
replay must compare native outputs with the recorded prompt/seed/anchor sequence
under the appropriate model/runtime recipe. Retaining three clips bounds the
available raw replay window; it cannot reproduce discarded history from hashes.

Checkpoint writes are atomic, fsynced metadata replacements, capped at512KiB.
Prompt admission accounts for JSON escaping and rejects over-budget text before
mutation, never truncating it. At most65536 JSON-encoded bytes per prompt leaves
space for three retained prompts, one pending prompt and fixed capture metadata.
Restore checks identity, counters, retained record hashes and predecessor chain.
Interrupted reservations, submissions or deliveries restore halted: an ambiguous
external effect is never silently resent. Future transport/sink integration must
persist reservations/offers before effects and acknowledgements afterward; this
module alone does not implement a distributed exactly-once display protocol.

## Verification and limits

- [15 reader tests](../data/continuation-delivery-cpu-01.json) cover exact bit
  preservation, all-output validation, finite samples, truncation/corruption,
  bounded reads, overlap exclusion, cancellation and final-iteration changes.
- [15 coordinator tests](../data/continuation-stream-state-cpu-02.json) exercise
  graph/predecessor binding, acknowledgement errors, checkpoints, retention,
  wrong histories, faults and bounded metadata across12 simulated chunks.
  They use explicitly simulated transport/capture callbacks and no GPU or sink.
  The initial14-test [receipt](../data/continuation-stream-state-cpu-01.json)
  remains with its [source archive](../data/continuation-stream-state-source-01.json.gz).
  The later check adds strengthened predecessor-chain validation; both are
  source/state evidence rather than numerical generation results.
- [Actual reference delivery](../data/continuation-delivery-references-01.json)
  verifies all four raw outputs of the existing boat, marble and bird captures
  against their tracked original hashes. Both25-frame and24-frame byte streams
  then matched independent bounded reads of the corresponding image ranges.
  Data went only to hash sinks; no new media, display or generation occurred.

Reproduction uses new receipt paths:

```bash
python3 experiments/ltx25-b70/scripts/test-continuation-stream-state.py \
  --receipt /tmp/continuation-stream-state-check.json
python3 experiments/ltx25-b70/scripts/verify-continuation-delivery-references.py \
  --receipt /tmp/continuation-delivery-reference-check.json
```

The real reader and coordinator transitions have separate tests. A full
transport/capture/sink integration test remains necessary. Native tensor creation,
runtime packet binding, model continuation, exact chain replay, seam review,
audio alignment, playback pacing, bounded cleanup and endurance remain
unqualified. The source implements backpressure rather than claiming endless
generation while those integrations are missing. No generation-speed improvement
is claimed; the faster-than24-new-frames/sec target remains unachieved.
