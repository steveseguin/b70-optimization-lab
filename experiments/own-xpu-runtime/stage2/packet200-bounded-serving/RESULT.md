# Packet200: sixteen-turn bounded native serving

## Question and identity

Can one native owner serve a varied local chat session, preserve exact recorded
outputs and state behavior, and close cleanly? This uses the unchanged p198/p199
one-card baseline engine, Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, full BF16 state,
context 4096 and a 21,552,729,600-byte expert cache. The exact source/dependency
closure and plan are in [the admission manifest](READY-FOR-DEVICE.json).

## Outcome

**Passed:** one loaded owner completed 16 requests, 16 postreply SAVE operations
and 1,484 output tokens. All five full recorded-output comparisons passed, as
did the resumed/fresh token pair. All 16 actual native prompt sequences, HTTP
text, finish reasons and usage counts matched their native results. The expected
unsupported-sampling request returned 400 before a native RUN.

Both worker and client completed successfully. The native process exited zero,
teardown released its allocations, diagnostic readers reached EOF, and separate
physical drain passed. No incident signal or new kernel fault occurred. The
controller began the single conditional restore29 at 20:17:35 UTC. All three
applications passed their validations by 20:27:14 UTC and remain running.
Final read-only observations found the same two historical faults, unchanged
PAUSE bytes, empty queues and no STOP or inflight marker. Root had 27.737 GB
free; memory blocks 53–56 remained offline and 57 retained its known online state.

## What worked

The listener appeared before the conservative launch-origin idle deadline.
Model loading and pinning took 210,700.901003 ms. All requests then reused that
one loaded owner, with serial chat, edited-history fallback and bounded parking.
The final two states contain 69,121,603 and 64,715,747 actual bytes; the parking
policy reserves 256 MiB per state under its 512 MiB budget.

Independent review rehashed all 256 current native checkpoint blobs against
their manifests. Final A's 128 blobs match retained p198 S1; final B's 128 blobs
match the retained p199 B state. The worker ended normally at its 16-request
limit with no pending disposition. All 170 diagnostic bytes were captured,
with no discarded bytes or retained reader/capture thread.

## What failed or remains uncertain

There was no runtime or output mismatch. Three reviewer-side audit assumptions
were corrected and preserved in the audit lineage; they are not device failures.
In particular, the appended conversation has 342 processed cached tokens plus
one pending token, so the visible history is 343 tokens.

Parking normally deleted the earlier resumed/fresh checkpoint files. This run
therefore independently compares that pair's tokens and SAVE acknowledgements,
not their deleted tensor contents. The final A/B states remain fully verified.
Transient systemd units were collected before independent review; successful
worker/client unit status is attested by the sealed controller's qualification,
not a retained raw pre-collection status snapshot. No raw protocol transcript
was captured; receipts and operation artifacts provide the retained proof.

The eight short practical prompts have no prerecorded semantic-quality oracle.
This is a bounded serving qualification, not a broad quality evaluation, cold
speed record, long-context test, multi-user batching result or LocalMaxxing
submission. The storage reserve remains a monitored forecast, not a hard quota
on all external writers. The underlying profile still claims no general live
readiness.

## Evidence and patches

- [Independent device audit](evidence/independent-device-result.json).
- [Worker closure](evidence/planned-a/output/terminal/worker.json) and
  [pre-completion proof](evidence/planned-a/output/terminal/pre-completion.json).
- [Client result](evidence/client-a/client-result.json),
  [client admission](evidence/client-a/admission.json), and
  [native result](evidence/planned-a/output/owner/receipt.json).
- [Independent physical drain](../../ops/packet200-window/evidence/window-a/postflight-drain.json)
  and [guarded restoration admission](../../ops/packet200-window/evidence/window-a/restore-admission.json).
- [Independent restoration audit](evidence/independent-restore29-review.json) and
  [copied restoration evidence](evidence/restore29/copy-receipt.json).
- [Restoration observations](evidence/restore29-final-observations.json).
- [Post-device unit observations](evidence/device-unit-observations.json) and
  [locally retained diagnostic index](evidence/raw-diagnostics-index.json).

The 2.43 MB retained kernel capture is intentionally tracked: the independent
audit consumes it to verify the two-fault baseline and absence of new faults.
Keep it as permanent run evidence; Git restores its exact bytes if the local
copy is lost.

Raw checkpoint tensors and compiler caches remain local. The device audit
records hashes for the surviving checkpoint contents. Tracked evidence includes
manifests, small token/control files, input/output records and operation receipts.

## When to revisit

Commit the independently reviewed result and restoration evidence and watch CI.
The next serving feature is actual token-time streaming, using additive callback,
UTF-8 decoder and bounded SSE transport modules. CPU replay and socket checks
precede a separate host-only native protocol proof and any later device test.
The sealed packet200 engine and adapters remain unchanged.
