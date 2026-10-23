# Postreply checkpoint save: exact device lifecycle

## Question and identity

Can the warm owner keep the completed reply's state until a separate SAVE or
RELEASE operation, including at its request limit? This enables a caller to
choose a checkpoint ID after seeing the generated tokens. The model remains
Qwen3.8 Flash-Next Unsloth UD-IQ3_XXS as a separate quantized model, one B70,
target-only greedy `iq3-p49-split32-v1`, full BF16 KV, context4096 and the
21,552,729,600-byte baseline expert cache. Exact binary/source/command pins
are in [READY-FOR-DEVICE.json](READY-FOR-DEVICE.json).

## Outcome

The one device run passed all eight requests and 1,408 output tokens, five
postreply saves, three releases, and final shutdown. Every output matches
packet197 and the corresponding packet181 reference; A's first128 tokens
also match the CPU oracle. All five saved binary states match packet197
exactly. The final release precedes the eight-control stop event, with no
unsaved state discarded.

There was one native process, one model load, card0 ownership only, no new
kernel fault, no incident signal and no retained child. The worker and
privileged passive ownership checks passed before restoration of the three
prior applications as restore27 began at17:03:22UTC. All three applications
validated by17:12:54UTC. Worker and controller exited successfully; original
lane pauses are intact, queues empty and STOP latches absent.

## What worked

The new protocol retains original input, exact processed history, pending
token and parent lineage outside the request-local scope. SAVE accepts only
the matching completed request and exact full visible token history. The
existing checkpoint writer, locks, hashing, fsync and manifest-last visibility
are unchanged. A new RUN requires SAVE or RELEASE of the prior reply.

Six-save/two-release host testing covered SAVE after the final allowed
request. The real-model pilot covered five saves/three releases and RELEASE
after the final request. Both stop paths passed; native host tests also
refused wrong history, stale requests, duplicate operations, premature RUN
and overwriting an existing checkpoint, with safe shutdown.

Model load/pin took215.639seconds once. Restore components were0.344,0.345
and0.341seconds; appended-input prefill took3.979 and3.373seconds, versus
14.082seconds for the full merged prompt in the same warm owner. These are
ordered component observations, not cold or end-to-end speed claims.

## What failed or remains uncertain

No device request or control failed. The experimental checkpoint label is
`experimental-postreply-front`, contract `v1.2+p198`; exact binary identity
remains mandatory. No old checkpoint is silently adopted or relabeled.

The generic native receipt still says `real_model_qualified=false`; the
explicit worker and independent comparisons establish this bounded
lifecycle only. No OpenAI endpoint, concurrent serving, natural-completion
policy, cancellation/reuse or TP2 integration is qualified here.

Request timing ends before the separate SAVE, whereas packet197's immediate
save was inside its request wall. Those wall values cannot be compared as a
speedup. Manifest `save_seconds` measures payload work before final manifest
publication/fsync, not complete SAVE acknowledgement latency. No LocalMaxxing
submission is made for session reuse or this protocol change.

## Evidence and patches

- [Worker](evidence/device-p198-lifecycle-A-a/worker.json),
  [control events](evidence/device-p198-lifecycle-A-a/postreply-controls.json)
  and [owner shutdown receipt](evidence/device-p198-lifecycle-A-a/owner/receipt.json).
- [Independent device audit](evidence/independent-device-result.json),
  [native patch](native-postreply.patch), [build](evidence/build-compile-only.json)
  and [actual host tests](evidence/host-probe.json).
- [Controller](../../ops/packet198-window/README.md) preserves admission,
  shutdown and restoration receipts.

The five states contain369,087,828 binary bytes. Large tensor blobs stay out
of Git; compact manifests, original control/token payloads, request/control
results and digest evidence preserve their identities. Archive/reproduction
details are in the [binary-only archive reuse map](evidence/checkpoint-archive-reuse.json).
All645 binary files matched the verified packet197 external archive; their
p198 manifests and fields remain distinct. After actual native metadata
fixtures were captured,605 redundant local tensor files (368,974,848 bytes)
were removed, with [prune receipt](evidence/checkpoint-local-prune.json).
Restore only mapped binary members into a fresh copy with the p198 metadata;
local checkpoint directories are now incomplete until reconstructed.

## When to revisit

Connect the tested owner to the parking policy through a serialized adapter.
The next work supplies metadata snapshots under the native shared lock,
explicit admission of this experimental contract, safe deletion, exact
pending-token/hash conversion and peak disk accounting before SAVE. CPU
adapter tests and actual native-tool fixtures must precede live request
wiring. The existing rendering/template parity evidence remains separate
from these token-ID lifecycle results.
