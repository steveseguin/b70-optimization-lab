# Integration boundaries

Packet36 copies packet32 (sealed anchor `2e8ec7585c`). Target arithmetic stays
`iq3-p17-detmath-v2`; target kernel sources, dispatch vocabulary and oracle
fixture contract are unchanged. `source-origin.json` and
`target-source-identity.json` bind that copy.

New source: mtp.hpp (private draft plan, authenticated loader and load-time
quantizer), mtp_kernels.cpp/.hpp (routed dense, global merge norm and compile-time
draft operations), prepare_mtp.py, capture_cpu.py, compare_draft.py,
mtp_gates.py and draft_window.py. Main adds options and a CPU/device draft fixture
entry. Rank adds command 9 and 40-byte publication at offset 131072. Pipeline
starts DRAFT immediately after rank1 confirmation while resolving rank0 work.

Do not merge main.cpp wholesale over packet35's host-path work or packet34's
replay changes. Keep their owners' directories read-only. Reapply the narrow
option/provider/command changes around the winning host path. Preserve one
rank-local owner and queue, separate writable draft bindings, immutable shared
head lifetime, target head dispatch choice, begin/commit order, rollback banks,
local drain, failure-before-teardown receipts and no-retry policy.

Replay integration must retain all draft cache rows and the confirmed token
shift. A captured launch plan needs separate draft input addresses and cache
position. Never capture guessed embeddings into persistent draft state. Recheck
that replay does not overwrite previous final streams before DRAFT reads them.

Run source-identity checks, mini target/state/cache gates, both compiler/sanitizer
checks, real eight-token v2 oracle modes and CPU agreement again after either
merge. Rebuild K0 and repeat KD with two fresh owners before any W2m speed
window; old boot/binary-bound receipts are not reusable. The full head remains
the default. Shortlist support is explicitly unqualified and rejected.

## Packet35 host-path preparation

Its [current README](../packet35-hostpath/README.md) prepares resident callbacks
after dispatch selection and uploads, binds owner generations, and keeps real
events. Extend that preparation to DraftRuntime's separate immutable plan after
its private allocations exist. Prebind the new draft linear, merge and
elementwise families as well as reused QSA operations. Mutable token, position
and cache contents must remain visible through stable addresses. A shared head
keeps its target owner's generation and lifetime; private draft scratch must
never be substituted into the target's prepared sites. Keep draft event timing
available in normal W2m and separate draft class labels in W2mc.

## Packet34 replay benchmark

Its [current README](../packet34-replay-bench/README.md) covers synthetic
resident layers 24–47 and excludes token lookups, the head, argmax and transfers.
It is an input to a later integration, not evidence that full MTP replay works
or is faster. MTP has one QSA layer, no GDN and a separate merge/final head path.
Record only after those private bindings and the measured dispatch are fixed.
Confirmed embedding/hidden uploads and the draft position boundary must remain
correct on every invocation. Compare all draft mutable bytes with direct MTP
before using any replay mode; keep two fresh owners and the target v2 gate.
A replay timing must include the full draft wall cost for the pipeline model.
