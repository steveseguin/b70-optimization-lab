# One loaded owner: exact request and checkpoint lifecycle

## Question and identity

Can the checkpoint engine accept dynamic requests without reloading the model,
mixing conversation state, or changing output? This pilot uses Qwen3.8
Flash-Next Unsloth UD-IQ3_XXS as its own quantized model, one B70, target-only
greedy arithmetic `iq3-p49-split32-v1`, full BF16 KV, context4096 and the
packet181 baseline expert cache of21,552,729,600bytes. It does not include
packet196's larger cache or expert instruction diet. The exact source,
binary and command identity are in [READY-FOR-DEVICE.json](READY-FOR-DEVICE.json).

## Outcome

The single device run passed all eight requests and 1,408 output tokens through
one native process and one model load. Fresh A and B match their parent references; A's first128
tokens also match the CPU oracle. Saving A at256 and resuming128 reproduces
uninterrupted384-token generation. Appending a new turn, repeating that append
and evaluating the merged prompt fresh produce identical tokens and saved
state. B remains identical after the intervening A requests. Independent
comparison also matches all three appended outputs to the historical merged
prompt reference, and the fresh-A/appended state maps to packet181 S1/S2.

The worker exited successfully with no new GPU fault, no incident signal,
no retained child, and a clean device drain. The controller's privileged
passive ownership check passed before restoring the prior applications as
restore26. All three validated at16:42:06UTC, and both worker and controller
units finished inactive with success and exit0. Original pause bytes were
restored, queues stayed empty, and no STOP latch remained.

## What worked

The device run used the same bounded token-ID protocol and transport that
passed the tiny host lifecycle. Each new request resets mutable state;
restore then reconstructs the exact saved prefix and pending-token state.
Immutable weights and the expert cache remain in the same owner. Five
checkpoints retain the explicit experimental label and new binary identity.

Loading and pinning took210.251seconds once. The three restore operations
took0.360,0.371 and0.368seconds. Appending126 new input tokens steps those
tokens plus the saved pending token: prefill took4.015seconds, then3.395seconds
on the repeat. The fresh469-token merged prompt took14.052seconds to prefill
in the same warm owner. These are ordered component observations, not a
controlled cold-speed benchmark or a serving-throughput claim. The result's
`first_generated_token_ms` measures the first generated step, not total TTFT.

## What failed or remains uncertain

No device request failed. CPU preparation exposed an incomplete compiler
input closure and a parent-import collision; both were corrected before
device admission, with earlier receipts retained under `lineage/`.

This is a bounded sequential token-ID pilot. It does not qualify concurrent
serving, an OpenAI endpoint, natural completion, cancellation/reuse or TP2.
The generic native receipt retains `real_model_qualified=false`; the explicit
worker comparisons qualify this lifecycle only. Checkpoints remain
`experimental-warm-front` / `v1.2+p197`, with no silent adoption of packet181
or packet197 checkpoints by a future binary. There is no LocalMaxxing submission.

## Evidence and patches

- [Worker result](evidence/device-p197-lifecycle-A-a/worker.json),
  [owner shutdown receipt](evidence/device-p197-lifecycle-A-a/owner/receipt.json)
  and [load measurement](evidence/device-p197-lifecycle-A-a/owner/cold-start.json).
- [Exact native delta](native-request-front.patch), [build receipt](evidence/build-compile-only.json)
  and [CPU readiness audit](evidence/independent-device-readiness.json).
- [Independent device audit](evidence/independent-device-result.json) verifies
  all 129 binary files per checkpoint and the full request comparisons.
- [Controller](../../ops/packet197-window/README.md) and
  [closeout inventory](evidence/closeout-inventory.json).

The five raw checkpoint states total369,087,828bytes. Compact manifests,
request results and digests preserve the reviewed identities; exact small
token/control payloads are encoded in [checkpoint-controls.json](evidence/checkpoint-controls.json)
to respect the repository's binary-file exclusions. Large tensor state and
generated driver caches are not added to Git. Retention and reconstruction
limits are stated in the inventory. The complete five checkpoints are in a
371,281,920-byte external tar, SHA256
`a3e37a6c2b3ce4b554ff966d3df668a3fb472e84e6c0676fd4315064b458182d`.
Every archived file was read back and verified before removing 605 redundant
local tensor blobs. The [archive receipt](evidence/checkpoint-archive.json)
contains all member digests and fresh-directory restore instructions; the
[local prune receipt](evidence/checkpoint-local-prune.json) records the exact
scope. Local checkpoint folders are explicitly marked incomplete until their
tensor blobs are restored. No tracked file or unique evidence was removed.

## When to revisit

The next serving step is an explicit postreply save operation. The current
RUN chooses its checkpoint ID before generation, whereas ctxkeeper computes
the full-history ID after the reply. A separate successor packet will retain
the exact completed request state until SAVE or RELEASE, including after
the final allowed request. Its new binary and protocol need their own tests.
The [design](../../integration/request_front/POSTREPLY-CHECKPOINTS.md) also
records the later inspect/delete, adapter identity and storage-policy gaps.
