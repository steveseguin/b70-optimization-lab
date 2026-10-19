# Conditional one-card screen build brief

**Not selected, not built, not ready or queued.** Packet164's required 0.4 ms
latency premise is unidentified. At 20% transfer even free route+router is
below 2%. The raw deletion ceiling exceeds 2%, so this brief preserves the
requested next build contract without turning that mathematical bound into
expected performance. Reopen when an exact completion mechanism has a supported
net saving of at least 0.612738 ms/token, including all added work. Read
[design](../DESIGN.md) and [negative index](../DO-NOT-REPEAT.md) first.

## Private parent and scope

Create `packet164-route-fusion/onecard/` as a private, symlink-preserving copy
of the **packet58aj** line. Snapshot source/build identities and vendor the
complete dependency closure used by the new build; do not edit or rebuild
packet58aj, any existing packet, `stage2/screen/*` or `ops/*`. Resolve stale
links into this copy, preserving their original bytes and provenance. Never
substitute a two-card wrapper, packet58ad configuration or partial kernel port.

Both controls and candidates keep all 48 layers, resident lookup copies
(29,321,610,240 bytes), HC fusion, HC-wide, wide64+halfcache, p109 other-fusion,
ordered retirement, down-tile16, overlap maintenance, pinned-host zero-copy
misses and the 21,552,729,600-byte device expert cache. Retain full BF16 KV,
context4096, target-only greedy decode and `iq3-p49-split32-v1` packet49 oracle.
Preserve the complete router/shared projection tuple and shared activation.
Only the new router→route completion boundary may vary. Neither the router
arithmetic nor a newly pruned sorting network belongs in this arm.

## CPU proof before readiness

1. GNU and Intel, final production flags, separate-TU original reference,
   two fresh host processes each: exact producer logits, route scratch,
   probabilities, IDs/descriptors and shared activation at actual 512/10/640/2560
   shapes. Include original BF16 boundaries, probability ties, NaN/±Inf,
   invalid/duplicate routes, allocation aliases, bad position, inactive/error,
   every completion-counter transition and both last/first finishing groups.
   Packet164's current epilogue-only pass is insufficient.
2. **CPU real-arm-sequence gate:** run the actual copied Engine, Device,
   resident cache, capture/prepare path and runner arm loop with bounded mock
   payloads. Execute smoke and A0/B0/A1/B1/A2, all real request resets,
   post-prefill and post-decode continuation, all captured command generations
   and cache-maintenance waits. Poison the election counters before reset.
   Require zero on the next invocation, exactly one epilogue owner, correct
   ordering of every published consumer and unchanged protected allocations.
   Negative controls must fail on omitted reset, stale capture, early publication,
   missing tuple producer, bad selected route and removed dependency. A fixture
   that calls only a new helper is not this gate.
3. Build the real native entry; run its CPU preparation mode with the **exact
   two proposed argv paths**. Prove the new option reaches the selected
   production operation. Trace/refuse model and device opens in CPU entry mode.
   No full GGUF or large real-shape reads during another timing window.
4. Rehearse the private analyzer on the **real packet58aj** smoke/v5 evidence,
   explicitly labeled replay: 12×64 and 60×128 exact rows. Keep its slow first
   request and original scope. It must reproduce the saved metrics and refuse
   truncation, nonzero cached tokens, a byte mismatch, wrong identity, missing
   views and missing continuation. No toy receipts in place of real evidence.
   It must also analyze its own newly arriving rows after the first real
   request, and every complete arm after completion.
5. Exercise the actual lanequeue entry/report interfaces and the private
   runner with the two rows below in an isolated temporary queue. Run the
   actual pin/admission/report tooling, preserving any unsupported-adapter
   refusal as an unmet gate. No live queue writes. Parser import alone is not
   a launch rehearsal; an old binary hash is not a new build receipt.

CPU commands run with `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`, peak RSS≤4 GB. No wall-clock subprocess/data-proof timeout may
expire while the worker is frozen. Native operational waits/watchdogs remain
separate: preserve explicit 300-second per-operation waits and cooperative
drain. The worker must allow the coordinator to freeze it for timing windows.

## Concrete lanequeue row contract

The adjacent [lanequeue-rows.jsonl](lanequeue-rows.jsonl) contains the real
lanequeue JSON schema and argv, derived from the two actual packet58ajb rows.
They are **future build requirements**, not executable proposals: their private
entry files do not exist yet, binary/source pins and rehearsal receipts must be
added by the build, and they must not be copied into a live queue now. Source
row hashes are in [queue-row-provenance.json](queue-row-provenance.json).
The existing parent `resident` arm name is kept; in the new private runner its
five views all use resident lookups and toggle only epilogue fusion.

| Job | Lane/card | Private arm/output | Required work |
| --- | --- | --- | --- |
| packet164-onecard-smoke-A | A /0, whole host held | `smoke`; `onecard/screen/evidence/card0-p164-screen-a/smoke` | 12×64 exact candidate outputs, own-output analyzer, actual continuation and reset checks |
| packet164-onecard-v5-A | A /0, same held session after smoke | `resident`; `onecard/screen/evidence/card0-p164-screen-a/resident` | A0/B0/A1/B1/A2,12×128 each; control and fusion in one load; all lookups resident |

Both candidate views must beat **every** control by≥2% with unchanged exact
tokens; control drift≤3%. Retain all views and every first request, no post-hoc
exclusion or best-prompt selection. The new packet must update the copied
runner's fixed output root and stage definitions; changing only a JSON path
is not a build. Smoke failure closes the attempt without launching v5. V5
failure closes the arm. A positive one-load screen only warrants fresh-process
confirmation; it is not a speed verdict, promotion or submission.

## Admission and final handoff

One card first. Coordinator waits until both two-card queues are empty, pauses
and drains them, checks CURRENT and processes, then reserves lane A/card0 and
holds the entire host. Freeze all competing CPU work for the timing portion;
no GGUF/full-shape reads, compiles or second GPU lane. Fresh fault review and
all normal admission rules apply. No launch is authorized by this brief.

Retain the parent's 98,990,252,032-byte available-host requirement including
8 GiB reserve,90,400,317,440-byte host bound, resident copies, and 4 GiB shadow
stop. Recompute all added allocations and device headroom rather than hiding
new counter/local-scratch requirements in the old ledger. K1 retains its
separate 12 GiB requirement. CPU build stops below 27 GB root free;
**device admission must leave 25 GB root free after declared writes**, checked
by lanequeue immediately before START. Inherited planned writes are 48,683,776
bytes smoke and 78,362,228 bytes v5; reprice from the new output inventory before
admission. A missing floor is refusal, never cleanup permission.

No model payload or device work in CPU preparation. Graceful stop/drain, one
attempt, no restart loop, settings change or resident service. Preserve all
failure evidence. Emit **READY last**, only after native builds, byte tests,
real-arm sequence, exact-entry probe, real-evidence analyzer, actual temporary
queue/report rehearsal, allocation accounting, pin seal and verified commit/
push. Readiness must bind the final command/source/binary/evidence hashes and
carry the coordinator's unmet prerequisites. No current READY file exists.
