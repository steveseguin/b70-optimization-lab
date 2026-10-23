# Tiny host-only streaming proof plan

Status: source/design only. No owner, HTTP request, compilation or device operation
was executed for this plan. The smallest reusable fixture can prove the native
callback, checkpoint disposition, decoder and SSE seams. It cannot qualify the
production `StreamingChatService` against the tiny native owner.

The existing executable is
`stage2/packet198-postreply-checkpoint/build/host/own-rt-iq3`, SHA256
`41cbb6c4ad3bf6626dfba24d3bbd9d95d76b512102e8b94c164e9d421b3c40ca`.
The [compile receipt](../../stage2/packet198-postreply-checkpoint/evidence/build-compile-only.json)
binds its GNU `-DOWN_RT_HOST_ONLY` entry and inherited object closure. Reuse the
read-only checks in [checkpoint_engine_host_probe.py](../checkpoint_engine_host_probe.py)
and the cleanup ordering in
[session_lifecycle_host_probe.py](../session_lifecycle_host_probe.py).
Do not rebuild or substitute the device ELF.

## Compatibility boundary

The admitted miniature has four layers, context64, vocabulary16 and EOS15.
Its tokenizer TSV deliberately contains synthetic hashes, and its three model
identity rows are synthetic zero-stat records. Mini execution reads no model
shards. The earlier host lifecycle generated `[0,0,0,0]` for input `[1,2,3]`
and `[1,1,1,1]` for input `[4,5]` with cap4.

The real `PinnedChatCodec` has vocabulary248320 and stop IDs248044/248046.
`StreamingChatService` requires this exact codec and matching native vocabulary,
tokenizer identity and stop IDs. Its chat template also emits IDs outside the
tiny vocabulary. The native mini geometry is selected by `Geometry::tiny()`;
there is no admitted vocabulary CLI override. Therefore the production service
constructor must refuse this tiny owner. Do not mutate codec attributes, replace
identity hashes, monkeypatch admission, or claim that a synthetic facade exercises
the production service.

Actual `TokenDecoder(PinnedChatCodec())` can nevertheless decode the tiny
owner's observed IDs as those same IDs in the real vocabulary. This checks only
output-byte mapping: IDs0/1 are valid real-tokenizer IDs, but the miniature did
not generate model language. For these two fixed rows, require the recorded
nonterminal outputs exactly; tiny EOS15 must not be reinterpreted as a production
stop token. Reading the pinned small GGUF header/tokenizer artifacts is allowed
for this decoder check; no model-weight reads are needed.

## Proposed one-owner experiment

Use a fresh ignored output
`stage2/packet198-postreply-checkpoint/build/engine-integration-streaming-a`.
Derive the unchanged tiny argv from `checkpoint_engine_host_probe.plan(output)`:
`--mini --pipeline-mini --context 64 --retain-steps none`, native nice19,
seconds180, max-requests8, idle30, and the fixed output-local synthetic identity,
tokenizer, checkpoint and owner paths. Require the existing fixed venv, helper
cores8-15,24-31, at most two threads, a standalone-process4GiB AS limit, and
27GB free plus64MiB write reserve. Check every source/binary/fixture pin before
creating fresh0700 directories. No download, install or model startup path.

1. Start the single admitted HOST_ONLY owner; use the real `NativeFront`, real
   `NativeCheckpointStore`, `StreamingCheckpointEngine` and guarded storage.
   Preserve the synthetic expected identity. Native metadata tools use this same
   host ELF and the existing closed tool environment.
2. Use an explicitly fixture-only facade accepted by the streaming HTTP duck
   interface. It accepts only the two fixed synthetic rows and delegates to
   `engine.run_turn`; it is not `StreamingChatService`. First use Parking with an
   8MiB save bound/budget, then a separate zero-budget policy for the second row.
   This produces exactly RUN→SAVE, RUN→RELEASE. Policy selection is harness-owned,
   never an HTTP knob.
3. On every actual native token callback, record monotonic time, front state
   `running`, controls count and pending state, then feed the real `TokenDecoder`
   and offer SSE bytes through the production nonblocking delivery path. No
   callback waits on the peer or a test barrier. Record callback order before
   `run_turn` returns and before the corresponding save/release acknowledgement.
4. One serial ephemeral127.0.0.1 server handles exactly two requests; a bounded
   local client captures all SSE frames. Check nonempty content offered from
   callbacks, incremental/full decode equality, exact usage and request IDs,
   and finish/`[DONE]` only after disposition. Distinguish offer time, client
   receive time and native completion. If the tiny process finishes before the
   client observes its first delta, report that fact; do not fabricate a latency
   or peer-before-disposition claim or rerun automatically.
5. End intake and join the handler before one `front.close()` sends QUIT. Require
   two requests/two controls, one load, native max8 unused, no pending/discard,
   owner exit0 and native `device_executed:false`. Inspect/hash the retained tiny
   SAVE state only after the handler has stopped, then close the borrowed store.

The old `SessionLifecycle.serve` requires the exact nonstream server class and
cannot accept `StreamingServer`. Use a two-call fixture harness with bounded
joins, not a relaxed production lifecycle gate or a new launch framework.
Use soft total150seconds and bounded30second native/read/join phases within the
native180second limit. On failure preserve the original exception and evidence;
halt intake, retain resources while a handler/owner is active, and permit only
one outer cooperative SIGTERM with a bounded wait. No forced kill or retry.

## Evidence and remaining qualification

Retain exact argv/environment allowlist, source/ELF/fixture hashes, synthetic
identity, callback/control timeline, raw SSE, input/native result IDs, save or
release acknowledgements, checkpoint digests and stopped/teardown receipts.
This would prove a tiny native streaming seam, not model output quality,
production chat template integration, device behavior or throughput.

The production service remains covered separately by actual-codec/synthetic-front
CPU tests. A full native service proof requires a separately reviewed native
fixture compatible with the production codec or a separately admitted device
pilot. Neither is implemented or authorized by this plan.
