# Current Workspace State

**October 23, 20:28 EDT — the tiny Engine passes the populated expert-cache proof.**
All 48 requests match across direct execution, cached serial execution and cached paired execution,
including saved state, continuation and prompt boundaries. Both cached modes produce the same routes,
hits, replacements and payloads. The deliberate partial failure stops intake and closes safely without
publishing a result. Independent review verifies the arithmetic, cache policy and complete retained evidence;
all 11 artifact tests pass. This is CPU correctness evidence with simulated completion, not a speed result
or production quantized-model qualification. Next is closing the production prefill integration gaps while
the native test target remains occupied. Daily applications are unchanged. The previous cache-proof commit
cbbdca31d has all three CI workflows green.
[Engine cache proof and limits](experiments/own-xpu-runtime/stage2/packet211-host-engine-cache/README.md) ·
[Independent review](experiments/own-xpu-runtime/stage2/packet211-host-engine-cache/evidence/independent-cpu-review.json).

**October 23, 19:55 EDT — two-row cache ownership passes the real CPU storage proof.**
Three matched-policy intervals produce identical output bytes and retained routes across serial and
layer-major schedules, with 24 cache hits and 552 host misses. All 25 fixture checks and 11 independent
artifact checks pass; ten owners close safely, including intentional partial-update failures. The first
attempt caught a pinned-allocation lifetime mismatch before comparisons and is preserved. This remains
synthetic byte-consumer evidence with simulated completion, not production expert arithmetic or speed.
Next is the actual tiny Engine's expert-consumer and route-retention integration. The native qualification
target remains occupied; applications are unchanged. The guarded-preparation commit 13b620b6e has all three
CI workflows green. [Cache proof and limits](experiments/own-xpu-runtime/stage2/packet210-host-cache-chunk/README.md).

**October 23, 19:45 EDT — guarded native entry compiles; the proposed idle-card test is not admitted.**
The vision application's unchanged process holds a device descriptor on the proposed BDF27 target;
all four cards currently have holders. No qualification manifest was issued and no device process was
launched. The three daily applications retain their restore30 process identities. The guarded native
entry preserves the earlier kernel image and passes 25 Python failure-path tests plus an independent
rerun. Native behavior remains untested and operational execution stays disabled. Next is a synthetic
CPU proof of captured pointer-table consumers, retained prompt-row routes and expert-cache replacement.
[Passive evidence and decision](experiments/own-xpu-runtime/stage2/packet209-native-pair-qualification/evidence/root-admission-disposition.json).

**October 23, 19:22 EDT — native paired projection compiles; GPU execution remains untested.**
The SYCL kernel and synthetic comparison fixture compile and link with the selected runtime owner and
arithmetic objects. Independent offline inspection confirms both Q6 kernel entries, the retained comparison
function and registered device image. The executable has no enabled execution command; it has not been
invoked or used to enumerate a device. Source equivalence and compilation establish no speed or native
exactness result. Next is a separately guarded single synthetic qualification on an admitted idle card,
preserving the daily applications. No launch or device window is queued. The paired-Engine commit
c1165ba2a has all three CI workflows green.
[Native build and remaining gates](experiments/own-xpu-runtime/stage2/packet208-sycl-paired-projections/README.md).

**October 23, 19:13 EDT — paired GDN projections match the serial Engine on CPU.**
The new captured operator issues 400 paired projections in place of 800 originals across the fixed tiny
fixture. All 16 replies, 13 complete saved states and 108 intermediate boundaries match the serial Engine
and previous reference. The same allocation/capture interface also passes full-size synthetic Q6 qkv/z
comparisons against independent arithmetic. Independent artifact review confirms the bytes and bindings.
An initial harness read the final allocation inventory too early; that attempt is preserved, and the corrected
run passed with the same binary. This is CPU correctness evidence, not device or speed qualification.
Next is the native paired-kernel implementation and its compile-only preparation. Daily applications retain
their restore30 PIDs, root has 28.30 GB free, and no device window is queued. The previous Engine proof's
final commit 49dcc27b9 has all three CI workflows green.
[Paired projections and limits](experiments/own-xpu-runtime/stage2/packet207-host-paired-projections/README.md) ·
[Independent artifact review](experiments/own-xpu-runtime/stage2/packet207-host-paired-projections/evidence/independent-artifact-audit.json).

**October 23, 18:58 EDT — paired prompt scheduling passes the actual tiny CPU Engine.**
Sixteen serial and sixteen paired requests match in output and all 13 saved states, including every one of
the 20 state buffers and token history. All 108 intermediate boundaries match; six older checkpoint references
also agree. Ten invalid-mode requests were refused before loading, and one intentional partial failure halted
without a checkpoint and exited safely. Independent artifact review confirms the result; this remains synthetic
CPU evidence with simulated backend events, no model/device qualification or speed claim. Next is integrating
shared weight reads for paired GDN projections while preserving causal state updates. Daily applications retain
their restore30 PIDs, root has 28.36 GB free, and no device window is queued. The previous capture-proof commit
d7a85f627 has all three CI workflows green.
[Engine proof and limits](experiments/own-xpu-runtime/stage2/packet206-host-engine-chunk/README.md) ·
[Independent artifact review](experiments/own-xpu-runtime/stage2/packet206-host-engine-chunk/evidence/independent-artifact-audit.json).

**October 23, 18:41 EDT — host capture and publication proof passes independent review.**
The existing runtime owner, arena, prepared operations and copy code pass 33 probe checks and 14 authority
tests with synthetic data. Independent replay matches all results and four shutdown receipts. Tests cover
fixed captured bindings, live payloads, shared-buffer reuse, stale allocations and partial-publication failure.
CPU operations and copies are real; the existing host backend's event/queue completion remains simulated.
Next is an opt-in chunk path in the actual Engine's tiny CPU fixture, preserving the serial default and
excluding model/device execution. Daily applications remain restored; no new device window is queued.
The previous binding-contract commit 330f7b08f has all three CI workflows green.
[Host proof and limits](experiments/own-xpu-runtime/stage2/packet205-host-row-capture/README.md) ·
[Independent review](experiments/own-xpu-runtime/stage2/packet205-host-row-capture/evidence/independent-cpu-review.json).

**October 23, 18:27 EDT — two-row ownership metadata passes independent review.**
The contract passes 31 binding checks, 17 authority tests and four cache groups. It covers shared persistent
state, row-specific inputs, causal history/attention boundaries and a completion descriptor for canonical state.
These are CPU metadata checks; actual native captures, event provenance and publication still need proof.
The next additive fixture exercises the real HOST_ONLY arena and prepared-submission APIs with synthetic data.
All three daily applications were read back as running with their restore30 PIDs. No device window is queued.
The prior output-path commit 69b94647f has all three CI workflows green.
[Binding contract](experiments/own-xpu-runtime/stage2/packet204-prefill-row-bindings/README.md) ·
[Independent review](experiments/own-xpu-runtime/stage2/packet204-prefill-row-bindings/evidence/independent-cpu-review.json).

**October 23, 18:17 EDT — paired gating, output projection and residual updates pass CPU review.**
Five synthetic cases pass 45 byte comparisons and 12 authority tests; an independent rerun matches.
The checks detect ignored gate/control inputs and a missing BF16 rounding step. This extends the earlier
CPU proof but still uses synthetic upstream controls and does not qualify full-model or device execution.
Next is the actual engine's two-row buffer/state ownership contract, including causal attention and cache
maintenance. All three daily applications remain restored; no new device work is queued. The earlier
CPU baseline 4efea254c has all three CI workflows green.
[Result and scope](experiments/own-xpu-runtime/stage2/packet203-prefill-gdn-branch/README.md) ·
[Independent review](experiments/own-xpu-runtime/stage2/packet203-prefill-gdn-branch/evidence/independent-cpu-review.json).

**October 23, 18:09 EDT — the first paired-prefill CPU proof passes independent review.**
Five synthetic cases pass all 50 intermediate byte comparisons, and all 20 planner/authority tests pass.
An independent rerun reproduces the results. The proof covers paired Q6 projections and causal convolution/GDN
with full BF16 state; it does not establish a complete layer or device speedup. The next additive patch completes
gated normalization, output projection and residual-stream updates. All three daily applications remain restored;
no new device window is queued. The streaming closeout ff03da93e has all three CI workflows green.
[CPU result and limits](experiments/own-xpu-runtime/stage2/packet202-prefill-chunk-prep/IMPLEMENTATION.md) ·
[Independent review](experiments/own-xpu-runtime/stage2/packet202-prefill-chunk-prep/evidence/independent-cpu-review.json).

**October 23, 17:49 EDT — streaming and restoration are verified; prefill is the next speed lever.**
All sixteen replies and1,484 output tokens match prior evidence. Seven streams delivered text before finishing; all256 final
checkpoint blobs match reference state. Restore30 validated all three daily applications, with unchanged fault history,
original pause bytes, empty queues and28.45GB root free. The attach-only chat CLI is committed asd725a8a8c after17 CPU checks
and independent review. Native timing attributes70% of the longer fresh-chat request to prompt processing; source and exactness
work is starting on a bounded prefill/chunk path. No new device window is queued.
[Verified streaming result](experiments/own-xpu-runtime/stage2/packet201-streaming-serving/RESULT.md) ·
[Prefill evidence](experiments/own-xpu-runtime/integration/streaming_v1/P201-PREFILL-OBSERVATIONS.md).

**October 23, 17:41 EDT — real-model streaming passed; daily application restoration is underway.**
All16 replies and1484 output tokens match the prior run. Seven streamed replies delivered text before their finish frames;
nine ordinary replies also matched. Independent review verified all256 final checkpoint blobs, clean owner exit and physical
drain. Restore30 began at21:36:41 UTC; the first text endpoint is ready, with the remaining applications still loading.
The next practical piece is an attach-only chat CLI, now passing17 CPU checks and completing independent review.
[Admission and test scope](experiments/own-xpu-runtime/stage2/packet201-streaming-serving/ADMISSION.md).

**October 23, 17:23 EDT — storage recovery verified; mixed streaming qualification is sealed.**
A verified external archive preserved8,766 closed compiler-cache files before their local copies were removed. Independent
archive hash, recovery-map and file-absence checks passed; the daily applications kept the same PIDs. Root has about28.74GB
free, roughly933MB beyond the floor plus the complete test forecast. The fresh streaming plan and384-file source configuration
are sealed. Independent admission verification, committed CI and fresh live checks precede one sixteen-turn test and guarded
restore30. [Admission and scope](experiments/own-xpu-runtime/stage2/packet201-streaming-serving/ADMISSION.md).

**October 23, 17:16 EDT — streaming window preparation passes 110 CPU checks across its three parts.**
The worker's31 checks, client's25 checks and controller/restoration's54 checks all have independent reviews. The guarded
window requires all16 outputs to match, seven complete streamed replies, successful client and owner exits and physical
drain before one restoration as restore30. No actual device plan or launch configuration has been created yet. The verified
external compiler-cache archive is complete; separate guarded removal is in progress to recover disk headroom. All three
restore29 applications remain running. [Controller scope](experiments/own-xpu-runtime/ops/packet201-window/DRIVER.md).

**October 23, 17:13 EDT — mixed streaming client passes independent review and 25 CPU checks.**
The next sixteen-turn test will use seven streamed and nine ordinary replies. Every result must match the prior native
run's complete output, consumed prompt, text and usage; original token oracles and resumed/fresh checks remain. Review fixed
partial-response closure and deadline enforcement during trickled input. The worker preparation commit84810a6d5 has green CI.
All three restore29 applications remain running. A separate privileged filesystem helper is completing review before it
archives and verifies closed compiler caches; no deletion or new device window has occurred.
[Client checks and limits](experiments/own-xpu-runtime/stage2/packet201-streaming-serving/CLIENT.md).

**October 23, 17:05 EDT — streaming session ready; real-model client preparation continues.**
The tiny native proof and guarded session composition are committed as dcf817d70, with all three CI workflows green.
The new streaming worker passes 31 CPU checks and independent review; it retains the successful pilot's launch, ownership
and shutdown safeguards. The next test will compare a mix of ordinary and streamed replies against all sixteen recorded
outputs. All three restore29 applications remain running. Archiving closed compiler caches stopped before mutation because
some files are root-owned and unreadable by the normal user; a separate, narrowly scoped privileged filesystem helper is
being prepared. No permissions or settings changed, and no new device window has started.
[Worker preparation](experiments/own-xpu-runtime/stage2/packet201-streaming-serving/README.md) ·
[Archive refusal](experiments/own-xpu-runtime/integration/CLOSED-RESTORE-CACHES-REFUSAL.md).

**October 23, 16:48 EDT — tiny CPU-native streaming passed; guarded lifecycle passes 27 CPU checks.**
One synthetic native process served two streamed requests, saved then released state and quit cleanly. Both clients received
text before disposition; all eight tokens and 21 checkpoint binary hashes verified. This is a CPU-native protocol proof, not
model/GPU qualification. The separate streaming lifecycle preserves guarded admission and graceful closure in its 27 checks.
The earlier 64-check component commit9e36c7267 has green CI. All three restore29 applications remain running. Next is the
borrowed-owner session composition and storage planning for a later device test.
[Proof and scope](experiments/own-xpu-runtime/integration/streaming_v1/HOST-RESULT.md).

**October 23, 16:35 EDT — streaming replies pass 64 CPU and socket checks.**
The additive service sends stable text while tokens arrive and waits for successful SAVE/RELEASE before its final stream marker.
Recorded replies match ordinary responses; slow or disconnected readers cannot cancel state disposition. Independent component
and composed-stack reviews pass. This is Python-stack evidence with an intercepted native front, not live-model streaming.
The sixteen-turn native pilot and restore29 are committed as75bdeb7a3 with all three CI workflows green. All three applications
remain running. A tiny host-only protocol proof is being prepared without changing the sealed baseline or queuing GPU work.
[Streaming result](experiments/own-xpu-runtime/integration/streaming_v1/CPU-CLOSEOUT.md).

**October 23, 16:28 EDT — sixteen-turn native serving passed and all three applications are restored.**
One owner completed 16 requests and 16 saves, producing 1,484 tokens. Five recorded outputs and the resumed/fresh token pair
were exact; all 256 retained checkpoint blobs verified. Restore29 validated all three applications by 20:27:14 UTC. Final
observations show unchanged fault history, preserved pause bytes and empty queues; root has 27.737 GB free. Result and restore
audits are being committed. Additive CPU work now connects streaming replies to the tested codec and state-disposition path;
no further GPU window is queued. [Result](experiments/own-xpu-runtime/stage2/packet200-bounded-serving/RESULT.md).

**October 23, 16:18 EDT — the sixteen-turn pilot passed; application restoration is underway.**
One loaded native owner completed all16 requests and16 state dispositions, producing1,484 output tokens. Five recorded-output
comparisons and the resumed/fresh pair passed. Both units exited successfully, diagnostics drained and independent physical
drain passed; restore29 began at20:17:35 UTC. Independent evidence review is underway; restored availability is not yet claimed.
The next serving feature is streaming replies, with additive CPU-only callback/decoder/transport work separate from this seal.
[Admission and identity](experiments/own-xpu-runtime/stage2/packet200-bounded-serving/ADMISSION.md).

**October 23, 16:11 EDT — the sixteen-turn serving window has started.**
The admission commit0f26bbfc5 has all three CI workflows green. Fresh live admission passed; the controller began one
graceful stop of the three idle restore28 applications at20:10:58 UTC. One native owner will serve the fixed sixteen-turn
client after passive drain. Restoration as restore29 remains conditional on exact results, successful client/worker exit
and independent physical drain. No new availability or serving-success claim is made while the window is active.
[Admission](experiments/own-xpu-runtime/stage2/packet200-bounded-serving/ADMISSION.md).

**October 23, 16:05 EDT — the sixteen-turn serving pilot is sealed for live checks.**
The reviewed configuration binds291 source/evidence files and the unchanged CPU plan. The execution preparation commit has
green CI. A verified external archive preserved all262 closed p199 checkpoint files; removing only242 matching untracked tensor
copies recovered147MB. Root now has about28.03GB free, above the27GB floor plus the full769MiB forecast. The three restore28
applications remain running. Independent admission verification and fresh live checks precede one controlled test window;
restore29 follows only a successful sixteen-turn client/worker qualification and physical drain.
[Admission](experiments/own-xpu-runtime/stage2/packet200-bounded-serving/ADMISSION.md).

**October 23, 15:50 EDT — execution and16-turn qualification adapters pass57 CPU checks.**
The first bounded serving window now has reviewed execution, client and restoration adapters. Restoration requires both
worker and client to exit successfully, all16 turns to pass, five retained token oracles, one resumed/fresh comparison and
independent physical drain. Exact consumed prompts and HTTP/native response mapping are checked. All operations remain
CPU mocks; no new model owner or device window has started. The preceding coordinator commit has green CI. Storage work is
preparing a verified archive of closed p199 checkpoints to improve the margin above the27GB floor before live admission.
[Preparation](experiments/own-xpu-runtime/stage2/packet200-bounded-serving/DEVICE-PREP.md).

**October 23, 15:28 EDT — bounded interactive coordinator passes37 CPU checks.**
The worker's26 checks and independent review cover one-owner launch interception, real pipe draining, first-error retention
and durable completion before reservation release. Eleven outer-window checks require matching pre-completion/final receipts,
successful unit exit and separate physical drain. The private staging parent is empty; no operational manifest or device
window exists. The idle-provenance commit has green CI, and all three restore28 applications remain running. Additive execution
adapters are now being prepared around the frozen worker and contract.
[CPU result](experiments/own-xpu-runtime/stage2/packet200-bounded-serving/CPU-CLOSEOUT.md).

**October 23, 15:16 EDT — fresh-owner idle provenance passes16 CPU checks and independent review.**
The optional clock proof now binds a fresh private output to the observed owner, exact command/environment and actual loaded
clock-symbol providers. Review fixed production environment compatibility and runtime ELF symbol-table coverage. Tests use
real pinned library metadata with synthetic process observations; no native owner was launched for this work. The preceding
helper commit has green CI. Packet200's bounded interactive worker and window contract are undergoing CPU shutdown review;
no operational entry point or new GPU window is enabled. All three restore28 applications remain in place.
[Provenance proof](experiments/own-xpu-runtime/integration/OWNER-IDLE-PROVENANCE.md).

**October 23, 14:52 EDT — idle timing and bounded diagnostic helpers pass 20 CPU checks.**
The timing helper safely recovers most model-loading time from initial idle accounting, conditional on proving the fresh
owner and mapped clock library; absolute deadlines stay unchanged. The pipe collector preserves bounded evidence and keeps
draining after capture failure, while uncertain endpoints and blocked workers remain explicitly retained. Both independent
reviews passed. The serving-component commit has green CI. All three restore28 applications remain running; no model or GPU
work was launched for these helpers. Coordinator integration remains the next step.
[Timing proof](experiments/own-xpu-runtime/integration/INITIAL-IDLE-ORIGIN.md) ·
[Diagnostic handling](experiments/own-xpu-runtime/integration/NATIVE-DIAGNOSTICS.md).

**October 23, 14:39 EDT — reusable bounded serving components pass 37 CPU checks.**
The profile pins the tested baseline engine and its dependencies, and the session assembly guards both native and metadata
operations. Final review fixed open-file identity checks and receipt reads during active requests. A bounded writer preserves
evidence at its limits. The proposed 16-request profile remains CPU-only: its 768 MiB forecast still includes unbounded external
driver and diagnostic writers, so no live readiness is claimed. Both completed chat/lifecycle commits have green CI, all three
restore28 applications remain running, and no new GPU window is queued. Coordinator and diagnostic work is the next step.
[Components](experiments/own-xpu-runtime/integration/BOUNDED-SERVING.md).

**October 23, 14:25 EDT — bounded sessions now close cleanly through the real CPU-native protocol.**
The new attachable lifecycle passes 16 socket tests and independent review. Its separate tiny host-only proof completed two
HTTP turns, saved both states and sent one clean QUIT before the native request limit, with no incident signal. The model
chat pilot and restore28 receipts are committed and pushed; CI is being watched. All three daily applications remain restored.
Next is a reusable experimental serving profile with fixed limits and reviewed admission; CPU preparation continues without
queuing another GPU window. The existing benchmark package and sealed device sources remain intact.

**October 23, 14:18 EDT — real chat passed and all three applications are restored.**
The six-turn pilot completed 896 output tokens through one loaded owner, with exact resumed/fresh tokens and saved state,
correct edited-history fallback, bounded parking and clean shutdown. Independent device audit passed; restore28 validated
all three applications by 18:17:48 UTC. Both experiment units exited successfully, with no new fault. The next bounded
session lifecycle passes 16 CPU tests and independent review. A tiny host-only native proof is prepared; final review is
fixing a diagnostic race before its one execution. No further GPU window is queued.
[Chat result](experiments/own-xpu-runtime/stage2/packet199-chat-parking/RESULT.md).

**October 23, 14:09 EDT — real chat passed six turns; application restoration is underway.**
One loaded owner completed896 output tokens through actual HTTP, with five saves and one final release. Resumed chat exactly
matched fresh tokens and saved state; changed history selected fresh processing. Independent audit rehashed both surviving
checkpoints and verified captured evidence for policy-deleted states. No new fault or retained owner occurred. Passive drain
passed and restore28 began at18:08:16 UTC; availability is not yet claimed. Next CPU work builds a reusable bounded session
lifecycle around the tested pieces, with no changes to the sealed native engine.
[Result](experiments/own-xpu-runtime/stage2/packet199-chat-parking/RESULT.md).

**October 23, 14:02 EDT — the six-turn native HTTP chat pilot is running.**
Preparation is committed and all three CI workflows are green. Live admission passed with unchanged fault history,
paused empty queues and full storage headroom. The coordinator began graceful application shutdown at18:02:35 UTC;
one native owner will serve all six turns after passive drain. Restoration as restore28 remains conditional on exact
results and clean teardown. No power, memory, driver or host-restart action is part of this window.
[Pilot](experiments/own-xpu-runtime/stage2/packet199-chat-parking/README.md).

**October 23, 13:58 EDT — real HTTP chat pilot is CPU-ready; live admission is next.**
The six-turn pilot passes 28 worker, readiness and controller checks plus independent review. Its unchanged native engine,
215 source files and 35 interpreter/dependency files are pinned, and a fresh interpreter verifies the same launch plan.
It will compare resumed chat against fresh tokens and saved state, check edited history and enforce bounded parking.
Root has enough room for the full forecast without lowering the 27 GB floor. No new device window has started;
all three restore27 applications remain running. One clean pilot and drain will precede their single restore28 reload.
[Pilot](experiments/own-xpu-runtime/stage2/packet199-chat-parking/README.md).

**October 23, 13:44 EDT — live chat test has local storage headroom; final CPU review is underway.**
A verified external archive preserves all876 files from four closed two-card checkpoint trees. Removing only796 matching untracked
tensor copies recovered530.6MB; metadata and small controls remain, with explicit reconstruction receipts. Root now has28.20GB free,
leaving about528MB above the27GB floor after the full640MiB test forecast. The six-turn chat worker and window controller pass their
CPU mocks. Independent source and launch review precedes sealing and any live admission. No new device window has started, and the
restore27 applications remain running. [Archive](experiments/own-xpu-runtime/integration/P184-CHECKPOINT-ARCHIVE.md).

**October 23, 13:35 EDT — local text chat interface passes its CPU and socket tests.**
All38 chat checks pass, including the exact pinned codec and two retained device replies replayed through the actual HTTP interface.
The native parking integration is committed and pushed; all four CI workflows are green.
The next test will use one native owner for real chat turns, exact append/fresh comparison and edited-prefix fallback. Storage
admission is being checked: the full local forecast leaves too little margin above the27GB root floor, and the external filesystem
must prove the required checkpoint permissions and locking before use.
No new device window has started; all three restore27 applications remain running.
[Interface evidence](notes/2026-10-23-local-chat-interface-closeout.md).

**October 23, 13:26 EDT — checkpoint parking now works through the actual native CPU owner.**
The thin adapter completed eight requests and eight dispositions through the real native protocol, store, bridge and parking policy.
Restored append matched fresh tokens and state; changed input prefills, no-save and same-ID paths release cleanly, and the owner exited
with no retained process. The first tiny-host fixture failed because it lacked required identity rows; its exact source and safe teardown
are retained, and a separate corrected fixture passed. This proves tiny CPU integration, not another device qualification. The real-model
postreply result is pushed with green CI, and restore27 applications remain running. Next: pinned text chat rendering and a local HTTP
interface, with CPU socket/replay checks before any real-model serving window.
[Integration](experiments/own-xpu-runtime/integration/CHECKPOINT-ENGINE.md).

**October 23, 13:13 EDT — postreply checkpoint pilot passed; all three applications restored as restore27.**
One loaded process completed eight requests, 1,408 exact output tokens, five postreply saves and three releases. All saved binary
states match the earlier qualified lifecycle. There was no new fault, incident signal or retained owner. Both worker and controller
exited successfully; restoration finished at17:12:54 UTC with all three applications validated. Both lane pauses retain their original
bytes, queues are empty and STOP latches are absent. The next work connects the native owner to checkpoint parking: policy, metadata
store and adapter tests pass, with actual CPU-only native integration proof next. This is exact session reuse, not a cold speed claim.
[Result](experiments/own-xpu-runtime/stage2/packet198-postreply-checkpoint/RESULT.md).

**October 23, 12:44 EDT — warm request interface passed on device; all three applications restored as restore26.**
Eight requests and 1,408 output tokens matched their references in one loaded process. Resuming and appending to a saved conversation
preserved exact output and state, including comparison to the earlier qualified engine. The worker and controller exited successfully,
with no new fault or retained device owner. Restore26 completed at16:42:06 UTC; all three applications validated. Both lane pauses retain
their original bytes, queues are empty and STOP latches are absent. Loading took210 seconds once; restore took0.36–0.37 seconds, kept
separate from cold speed records. The next separate packet adds postreply SAVE/RELEASE so ctxkeeper can choose a checkpoint ID after
generation. Its Python transport passes nine CPU tests and independent review; all three native targets compile and the actual
host-only lifecycle passes eight requests/eight controls, six saves, five invalid-operation refusals and pending-QUIT handling.
The separately sealed real-model runner is undergoing final admission; no postreply device request has run yet.
[Result](experiments/own-xpu-runtime/stage2/packet197-warm-request-front/RESULT.md) ·
[next interface](experiments/own-xpu-runtime/integration/request_front/POSTREPLY-CHECKPOINTS.md).

**October 23, 12:23 EDT — warm request interface passes its CPU lifecycle; one-card record approved at 37.595605 tok/s.**
The diet qualification passed all seven stages, with all12 ×128 output tokens exact and no new GPU fault.
The independent audit recomputed +2.713% over36.602512. Local and server dry runs passed; the single submission returned
HTTP201 APPROVED (`cmvl5k4p9004nng01z5xtanw5`), and the matching local record threshold is updated. This retains the
established128-token scope, not a512-token promotion claim. Clean teardown and privileged passive ownership checks passed.
Restore25 completed at16:00:51UTC with all three applications validated; both lane pauses retain their original bytes and STOP latches are absent. The warm request interface has CPU-tested
metadata/transport and a native source overlay with unchanged checkpoint arithmetic. Its protocol, host and device targets compiled,
and the actual host-only engine passed eight requests in one process with exact continuation and saved state. The real-model device
window is being prepared and independently reviewed; no device serving result is claimed. [Record](experiments/own-xpu-runtime/stage2/packet196-onecard-diet-chain/RESULT.md) ·
[next work](notes/2026-10-23-warm-request-front.md).

**October 23, 11:20 EDT — one-card diet qualification is running; first two gates passed.**
The service-state parser fix passed its regression tests and the qualification packet was resealed. The first admission refusal
was manually reviewed and archived: it launched no benchmark and all cards had drained. The resumed coordinator skipped endpoint
stops entirely, passed fresh admission and launched the original registered device command once at 15:18 UTC. Both K1 gates passed;
KD, W2m and the three suite windows follow. The prior applications stay stopped during the test and restore25 remains conditional
on clean completion. [Coordinator evidence](experiments/own-xpu-runtime/ops/packet196-window/evidence/window-b/preflight.json).

**October 23, 11:13 EDT — one-card qualification stopped before launch on a service-state parser bug; cards idle.**
The next substantive task is a warm one-card request interface with exact checkpoint continuation. Existing device evidence shows
0.46 s restore versus 36.75 s cold prefix work, but the engine still takes a fixed request list and cannot serve ctxkeeper.
The new bridge is being checked against real checkpoint manifests; reuse remains separate from cold record measurements.
The prior restore24 applications drained gracefully and privileged passive ownership inspection found every card empty.
The launcher rejected systemd's exit-code-4 `inactive` response for unloaded transient endpoint units. No benchmark process,
chain output or fault review was created. The coordinator halted, preserving STOP-A and both lane pauses; no restoration
was attempted. Fixing this admission parser and testing explicit continuation from the already drained state comes next,
without cycling the applications again. No power, memory or driver settings change.
[Window](experiments/own-xpu-runtime/ops/packet196-window/README.md).

**October 23, 10:26 EDT — one-card diet record qualification packet is CPU-ready; no second device window launched.**
Packet196 preserves the max23 record configuration and reuses the exact screen engine with the diet flag. Its final readiness check passes:
801 sealed packet inputs, 227 exact engine source/build-input/proof files, 12 separately verified orchestration sources, 33 gates, zero mutable cross-packet
pins in the packet closure. CPU tests, script-entry checks, seven-window replays, submission rehearsal and launcher refusal checks pass.
The +2.657% screen remains the latest measurement; the one-card record is still36.602512 tok/s pending qualification. All three restore24
endpoints are running and validated; both lane pauses remain armed. [Qualification note](notes/2026-10-23-packet196-onecard-diet-chain.md).

**October 23, 09:56 EDT — one-card diet engine screen wins +2.657%; all 60 responses exact.**
Control/diet/control/diet/control: 36.579 / 37.573 / 36.599 / 37.583 / 36.601 tok/s. Warm drift0.00333%, unchanged fills/bytes,
no kill rule. Both screen and chain thresholds passed; this is not a submitted record. The registered row completed13:56 UTC,
clean teardown and complete passive owner check passed; all three endpoints restored as restore24 and validated at14:05 UTC. Both lane pauses are armed. CPU preparation of a separate
qualification packet is next; no second device window launched. [Result](experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/RESULT.md).

**October 23, 09:41 EDT — one-card diet engine CPU preparation completed; device screen pending.**
The resumed packet preserves all 47 production device images and adds the qualified diet kernel. Exactly 47 halfcache gate/up sites switch;
layer 2 keeps its other-layout kernel. Cache capacity and the production-size memory census are unchanged. All required CPU gates pass:
583 cache checks, 72 historical requests rechecked exact, real parser/argument paths, and shared smoke/bracket report rehearsal. The Python
comparison retains one unchanged inherited missing-fixture failure, explicitly recorded. Stale capacity metadata and copied test fixtures were
fixed before readiness. Endpoints still serve as restore23; no device work has run. Next: one controlled card-0 screen after idle/admission checks,
then exactness and speed assessment. New window driver halts on failure and restores endpoints only after successful clean drain; no retries.
[Packet](experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/README.md) · [note](notes/2026-10-23-packet58-onecard-diet-engine.md).
**October 23, 11:21 EDT — North-star review: preserve real task progress next; campaign 59's control reproduced campaign 55.**
The memo-off control finished 420/423 in 93m01s with all 152 NOTES versions identical to campaign 55.
Its server stopped cleanly; the memo-on stage began its trial at 11:19 and remains running. No result
or default change yet. The next question is a recorded pi failure: correct completed work was deleted
after notes treated the assistant's mistaken recollection as fact. Campaign 60 prepares two recorded
cuts and a clearly labeled user-cancellation control, comparing existing thinking off/on. Its queued
wrapper waits for campaign 59's full completion and shutdown, then runs CPU checks and an independent
read-only review before one short model diagnostic. No task tools execute and completion is not a
quality verdict. Registration: `experiments/qwen38-27b-b70/notes/2026-10-23-campaign60-note-evidence.md`.
Only small source/log work while campaign 59 runs; pending commits stay local until servers are down.

**October 23, 09:44 EDT — Campaign 59 is running; the timestamp control reproduces the first NOTES exactly.**
Started unit `ctx-campaign59` at 09:39 EDT; c59a (memo off) began its seed-2 trial at 09:42 after a fresh
server load. Its opening listing, all 16 archive text records through the first cut, and first NOTES text
match campaign 55 exactly. c59b (memo on) follows automatically on its own fresh server after clean
completion/shutdown checks. Expected finish roughly 12:45 EDT; full results remain pending. The runner
saves both unchanged audits, comparisons and time budgets under `context-longrun-20261016/campaign59-control/`.
All prior audit/setup commits were pushed before launch; this live-state/early-check commit stays local
until servers are down. No other work on this host while the campaign runs. Public figures and memo
default remain unchanged. Early receipt: `experiments/qwen38-27b-b70/data/2026-10-23-campaign59-preflight/early-control.json`.

**October 23, 09:38 EDT — Campaign 59 is registered and prepared: isolate the counting memo from seed 2's directory timestamp.**
Two fresh-server seed-2 runs, upstream counts then memo, use a separate fixture that sets only the sandbox
root directory mtime to campaign 55's observed timestamp before the first model call. No tool output is
filtered. Five fixture tests and two CPU fake-server Harbor jobs pass; memo off/on writes identical requests,
trajectory, usage, grader output and snapshots. The runner records audits after each shutdown and compares
all NOTES/archive text and answers at the end. Memo default remains off; public wall figures unchanged.
Launch target `ctx-campaign59`; no server running at this entry. Registration:
`experiments/qwen38-27b-b70/notes/2026-10-23-campaign59-matched-memo.md`; results will be under
`/mnt/fast-ai/bench-results/context-longrun-20261016/campaign59-control/`.

**October 23, 09:32 EDT — Campaign 58 is audited; memo withdrawn from the default pending a controlled seed-2 comparison.**
On the two-card host, seed 0 reproduced all 153 NOTES and 423/423 with zero wrong STATE lines in 81 min 15 s
(was 92 min 40 s). Seed 2 scored 418/423 with 16 audit flags and failed; its opening directory listing exposed
a different timestamp before its first NOTES call, so the comparison did not hold model input fixed.
Both seeds kept every forgery target and applied all audits. The remaining between-step work is 233/277 s,
above the 150 s prediction. `COUNT_MEMO=0` is restored as default and public wall figures stay unchanged.
Both servers stopped at campaign end (05:46 EDT), cards empty. Preparing a fixed-metadata off/on comparison;
no new GPU work yet. Evidence: `experiments/qwen38-27b-b70/notes/2026-10-23-campaign58-closeout.md`.


**October 23, 03:50 EDT — the one-card expert instruction diet qualifies on device (packet58-onecard-diet-micro, lane B card 2, 07:41 UTC).**
The diet re-derived for the one-card halfcache gate/up kernel (`p58ag_diet::GateUp`: hoisted exceptional test from the halfcache entry, sign
after the scale multiply from the 16-bit code pair, hoisted effective scales; 12.0 vs 15.7 instructions per weight) runs at 0.78× production
cold (57.2 vs 73.2 µs) and 0.75× warm (36.9 vs 48.9) in both orders, byte-identical on every claimed stratum on device, controls within 0.1 %
of a fresh production pass; 12–16 µs saved per layer where 11.4 µs is +2 % on one card. The engine integration (packet58-onecard-diet-engine:
`expert_gateup=production|diet` on the max23 line, card-0 screen K1a/K1b + one load max23/max23+diet/max23/max23+diet/max23) is being prepared
CPU-only. Endpoints restored as `*-20261023-restore23`. Packet `stage2/packet58-onecard-diet-micro/` (note `notes/2026-10-23-packet58-onecard-diet-micro.md`).

**October 23, 02:53 EDT — 17 % of a 2M hostile seed's wall is the harness re-counting the whole history four times a step; exact memo built and checked; campaign 58 (campaign 55 again with it) registered and launching.**
Campaign 57's time budget: model 3,715 s, tool runs 132 s, proxy/client around calls 146 s, and 807 s between steps in the client (898 s in
campaign 55), growing from 0.2 s a step to 1.2 s as the history reaches 2M tokens: `clm_harness` counts the full retained history with tiktoken
at the top-of-step snapshot, the sent_tokens annotation, the sent snapshot and the calibration (0.25-0.36 s each at the end). `clm_baselines.py`
now installs an exact per-message memo (`COUNT_MEMO=1` default): a message is re-encoded unless its text pieces are the same string objects.
Checks: equal to the upstream count on 69 cases over the real 2,642-message history (simulated run 14.6 s against ~1,250 s), and one fake-server
job with the memo off/on writes byte-identical request bodies, trajectory, usage, grader output and all 28 snapshots
(`data/2026-10-23-count-memo/`). Campaign 58 = K32V on 1.3.0, both seeds, unit `ctx-campaign58`, predictions in
`notes/2026-10-23-harness-count-memo.md` (seed 0 NOTES identical to campaign 55, 423/423; wall 76-82 and 77-84 min against 92.7/93.2).

**October 23, 03:35 EDT — NEW TWO-CARD RECORD: 63.611824 tok/s class-balanced (packet195 diet chain, LocalMaxxing `cmvkniuvp003gng017f0s68rn`, APPROVED, +2.03 % over 62.345282).**
The record bundle (packet190's k3x line with packet193's bit-identical instruction diet of the IQ2_S expert gate/up kernel; packet194's engine
`b8482321…` bound byte for byte) ran its 11-window chain on cards 0+1 (unit `packet195-chain-a`, 06:43–07:31 UTC): K0, K1a, K1b, K2, W0p, KD,
W2m, WS, WSs, WS128x, WS128 all passed, no faults. WS128: 63.611824 tok/s class-balanced (all-prompt median the same, p10 61.44), 12/12 exact,
hit/miss cycle 13.25/24.99 ms, acceptance 0.787. Submitted 07:34 UTC after a local dry run and a server dry run (HTTP 200 valid): HTTP 201,
APPROVED; `scripts/packet49_record_threshold.json` updated; receipt `data/localmaxxing-responses/2026-10-23-packet195-record-bundle-diet-ws128.txt`.
Endpoints were idle (last requests 06:20 UTC), stopped after the launcher's dry run, and are back as `*-20261023-restore22`; PAUSE-A re-armed,
PAUSE-B untouched. The one-card diet-micro prep held its compiles during the chain. Packet `stage2/packet195-record-bundle-diet/` (chain receipts
under `evidence/device-cards01-p195-a/`, bundle under `submission/prepared-a/`), `ops/packet195-orchestration/`, note
`notes/2026-10-23-packet195-record-bundle-diet.md`. Two-card line this session: 58.80 → 60.66 (V3) → 62.35 (k3x) → 63.61 (expert diet).

**October 23, 02:45 EDT — one-card diet port STOPPED at step 1 (packet58-onecard-diet): the one-card gate/up kernel is a different kernel.**
The one-card record line runs `p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,Cached>` (820 B rows, 16-bit halves decoded through the 65,536-entry
halfcache table, indirect expert-cache slots, 20 bindings), not the two-card `p90exp` kernel (840 B rows, FP32 halves, direct pointers) that
packet193's diet header diets; `p90exp::validate` refuses the one-card stride. The "byte-identical dispatch tables" of one-card synthesis 1 were
the packet26 small-kernel classes, not the expert gate/up class. Per the stop rule the packet reports with stride/binding proofs (compiler
`static_assert` receipts) and proposes no row. Next: a packet193-shaped micro that applies the same three exact transformations to
`p58ag_exp::wide_chains` (keeping the table decode and slot resolution) with device byte identity at ≤ 0.85×, then the engine screen.
Packet `stage2/packet58-onecard-diet/` (note `notes/2026-10-23-packet58-onecard-diet.md`).

**October 23, 02:38 EDT — Campaign 57 (notes thinking off on the 2M hostile stream): both seeds FAIL the audit; thinking stays on; lever closed.**
Seed 0 412/423 with 29 wrong STATE lines (three memory-forgery targets lost), seed 2 419/423 with 20 wrong lines, against campaign 55's 423/0 and
420/2 with thinking on. The saving was 605 and 572 s of notes time a seed (a 35 % cut of notes time, 10-13 % of the wall: 80.6 and 83.7 min against
92.7 and 93.2), not the registered 15-22 %: the in-place notes reply is the CHANGES list with its working (~535 tokens, every digit a token), so
thinking was half of a notes call's writing, not nine tenths. The wrong lines are running sums that drift and persist for 5-10 versions (wepe21 72 off, a removed counter kept at −45,
rumi62 at twice its value); the 1.3.0 checks catch omissions and format, not sums; in-place re-asks doubled (71/72 against 20/25). Audits
`data/2026-10-22-context-campaign57/c57-seed{0,2}-audit.json`, receipts beside them; result section in the hostile note. The registered next look (a notes-only
`low` effort) is closed on the template alone: at `low` the Qwen template writes the effort line into the system message when thinking is on, so a
notes call would miss the whole prefix cache (~18K tokens a call); no run. Cards empty (RESTORE=0), no server up.

**October 23, 02:15 EDT — packet194: the exact expert instruction diet wins +1.96 % in the two-card record engine (lane B, 05:56–06:11 UTC).**
One load k3x/k3x+diet/k3x/k3x+diet/k3x = 62.168/**63.474**/62.155/**63.413**/62.193 tok/s; every view 13/13 exact, draft proposals and acceptance
identical, drift 0.06 %; gate/up saving 10.8 (rank 0) and 11.8 (rank 1) µs per layer from the host scopes; hit cycle 13.54 → 13.28 ms, miss
25.58 → 25.01. The chain bar (+2 %, 63.592) is missed by 0.04 points; the lanes are idle, so the record bundle (packet195 = packet190 with the
`k3x-diet` selection and packet194's engine `b8482321…`) is being derived CPU-only, and the same kernel is being ported to the one-card record
line (packet58-onecard-diet screen, where 11.4 µs/layer is worth +2 %). A first launch was refused by the lane runner until packet193's failed
done-file was reviewed and archived (`ops/lane-queue/reviewed/`). Endpoints restored as `*-20261023-restore21`. Packet
`stage2/packet194-expert-diet-engine/` (note `notes/2026-10-23-packet194-expert-diet-engine.md`).

**October 23, 00:45 EDT — packet193 instruction diet: the exact gate/up diet runs at 0.78× cold / 0.77× warm (lane B, card 2, 04:27 UTC); first lever in the +2 % family.**
On device every claimed stratum was byte-identical for all three candidates. exp-diet (hoisted `exceptional` test, sign applied after the scale multiply,
hoisted effective scales; 11.8 vs 15.3 dynamic instructions per weight) 57.92 vs 73.85 µs cold and 36.0 vs 46.8 warm (−15.9 / −10.8 µs per layer-
equivalent); exp-act-epilogue 0.82/0.85 with no gain over exp-diet plus the separate activation launch (dropped); down-diet 0.96 (closed). The wrapper
stopped the row on the production kernel's NaN-payload order vs the CPU fixture on the NaN-only diagnostic stratum (ruled diagnostic, not an
exactness failure); the dead-owner lane marker was archived and removed. Projection: +1.5 to +2.1 % two-card, about +2 % one-card. Next:
packet194 integrates exp-diet into the k3x record engine (`expert_gateup=production|diet`, engine-level exactness proofs) with a lane-B one-load
bracket; prepared CPU-only. Endpoints restored as `*-20261023-restore19`. Packet `stage2/packet193-expert-diet/` (note `notes/2026-10-23-packet193-expert-diet.md`).

**October 22, 23:35 EDT — Session-swap parity step 3 (engine history → next turn's prefix) 50/60 exact, misses = one trimmed tail token; parking policy built and CPU-tested.**
`integration/continuation_parity.py` on the five one-card device runs with recorded generated ids (packets 178-181, 12 prompts each, 512-token
greedy): decoded reply re-rendered as a stored assistant turn and re-tokenized reproduces 29,905/29,915 generated ids in place; the 10 misses are
two prompts × 5 runs each losing exactly the last id, a `\n`/`\n\n` at the cut-off that the template's `|trim` removes (a fixed-length artefact; of
campaign 55's 2,580 re-sent assistant messages, 0 end or start with whitespace). Parity closed on this host from the pinned header. Piece 3 of the
adapter, `tools/ctxkeeper/parking.py` (stdlib, 13 tests): checkpoint id = sha of the token prefix, restore only when inspect's identity/label pass
and the saved history is an exact prefix of the new rendering, else prefill with a named reason and the stale checkpoint deleted; one checkpoint per
session (prompt + generated ids), LRU eviction under a byte budget, in_use never deleted. Not wired into the request path (needs the four-card host's
request front). Receipt `integration/receipts/continuation-parity-20261023.json`; CHECKPOINT-INTEGRATION.md steps 3 and piece 3. Cards empty.

**October 22, 23:40 EDT — packet192 expert issue-floor micro (lane B, card 2, 03:33 UTC, 34 s): both record expert kernels are instruction-issue bound.**
gate/up `p90exp` cold 73.75 / L2-warm 46.35 / no-load 44.69 µs; down `p100` 45.94 / 33.75 / 33.33: no-load within 1–4 % of warm, so load latency is
not the limiter and register-free prefetch is out; the cold strata add a real DRAM term (+27 and +12 µs). Layer-equivalent cold 119.7 µs vs the 37.4 µs
copy floor. Only an exact instruction diet can move the class; packet193 (`exp-diet`, `down-diet`, `exp-act-epilogue`, byte-identical on all 384 real
routes on both host twins before any timing, bars ≤ 0.85× production cold and warm in both orders) is being prepared CPU-only. Endpoints restored
as `*-20261023-restore18`. Packet `stage2/packet192-expert-issue-floor/` (note `notes/2026-10-23-packet192-expert-issue-floor.md`).

**October 22, 23:29 EDT — Session-swap parity step 2 DONE (messages → text, 12/12) from the pinned GGUF header itself; the HF template copy was the wrong one.**
Shard 1 of the runtime's model is 10.9 MB of header, so it was fetched at the pinned revision (file 268f81fd…, header 7c1460a9…, both equal to the
admission receipt) and `tokenizer.chat_template` read out of it (9,993 chars, sha 12827f24… = the sealed prompt manifest's pin), saved as
`experiments/own-xpu-runtime/integration/chat_template-7c1460a9.jinja`. The `tokenizer_config.json` copy on this host (8,952 chars) differs: the
header's template merges leading system/developer messages into one block, renders developer as system, maps effort high → xhigh, and renders a
history assistant turn with an empty think block before its text. `integration/template_parity.py` renders the 12 raw suite prompts the way the
sealed files were made: 12/12 byte-identical from the saved copy and from the shard header (`--gguf`); four ctxkeeper message shapes recorded as
adapter fixtures. Step 1 re-run with the header's own vocabulary (`render_parity.py --gguf`): 12/12, HF stand-in no longer in the evidence.
Receipts `integration/receipts/{template-parity,render-parity-gguf}-20261023.json`; CHECKPOINT-INTEGRATION.md updated. Parity closed; next is the
parking policy in ctxkeeper behind an engine interface, CPU-tested until the four-card host's request front exists. Cards empty.

**October 22, 22:45 EDT — PRs #77 and #75 merged; the OpenVINO GenAI community entry is now `B70-verified` (reference-lab rerun on card 0, 02:30–03:10 UTC).**
bosd's documentation-only entry `community/bosd-openvino-genai-b70/` (OpenVINO GenAI 2026.4.1, Qwen2.5-7B INT4, one B70) reproduced within 2 %:
no-spec 114.7/114.6 tok/s (contributor 114.0/112.5), 1.5B-draft spec 95.1/126.0 (98.6/128.2), fresh llama.cpp-SYCL `184f653` tg256 99.5 ± 0.1 and
pp512 3755 (contributor 98.6/3528), so the 15 % engine gap and the "rebuild llama.cpp first" caution both hold; 114.7 tok/s is 79 % of the 608 GB/s
roofline, not "at" it. New lab finding: OpenVINO GenAI greedy output is not repeat-stable on the first generation of a fresh pipeline (later
generations stable, settled text depends on whether a warmup ran, byte-identical across two instances and two processes, so a deterministic
ordering effect, cause not isolated). Prediction registered before the run; four of five held, the "identical text" one failed and was probed.
Records in `community/bosd-openvino-genai-b70/validation/` (`lab-run.md`, raw logs, probe). #75 (Dependabot, hermes-agent pyjwt 2.15.0 and
urllib3 2.8.0) pins verified against PyPI hashes. OpenVINO venv at the lab's `builds/ov-genai-repro`, models under the HF cache, llama.cpp build at
`builds/llama-fresh-20261023` on the fast disk. Cards empty afterwards.

**October 22, 23:25 EDT — expert GEMV kernel-floor study: NO-GO on a +2 % kernel packet; one issue-floor micro remains informative.**
From the record kernels' source (`p90exp::Kernel<IQ2_S,2560,WG64,wide>` gate/up + `p100::Kernel<2>` down; the routed experts are IQ2_S gate/up and
IQ4_NL down, not IQ3_XXS): bytes per layer per token 20.06 MB → copy floor 37.4 µs; measured gate/up 60–62 + down ~35 + act 5 (class ~105): excess
~64 µs/layer. Packet162b's L2-resident run of the production gate/up kernel still took 48.3 µs (2.4× its copy floor) and packet86's no-decode variant
33.8 µs: the kernel is instruction-issue bound (~16 dynamic instructions per weight; the exact three-op identity plus decode gives an ALU floor of ~27 µs,
above the 20 µs copy floor). Every bytes-side mechanism is closed by a DO-NOT-REPEAT row or memory-infeasible (pre-expanded streams +3.77 GB/rank vs
630 MB headroom); the open instruction-level items (SLM gate↔up epilogue 4–5 µs, register-free LSC prefetch ≤ 12, instruction diet 0–12 + 0–7) sum to
4–36 µs at 100 % transfer against the 15.1 µs (+2 %) bar, with the class's transfer record at 0–47 %. Next: a 5-minute lane-B micro on card 2
(cold / L2-warm / no-load issue-floor decomposition of the two record kernels on packet100b's 384 real routes) decides whether the instruction diet
is worth a ≤ 0.85× micro packet; prepared CPU-only as packet192. Study archived in packet190 `analysis/expert-kernel-study-20261023.md`.

**October 22, 22:40 EDT — NEW ONE-CARD RECORD: 36.602512 tok/s class-balanced (packet58-onecard-cache23 chain, LocalMaxxing `cmvkcqznb002lng01fsrhjn7t`, APPROVED, +1.88 % over 35.926720).**
The chain (packet182c's seven windows on card 0 with `cache_cap max23` = 23.05 GB admitted device expert cache and the plan re-partitioned from 182c's
lifetime receipts; engine `083e3853…` bound byte for byte) ran 01:55–02:29 UTC (unit `packet58-onecard-cache23-a`): K1a, K1b, KD, W2m, WS, WS128x,
WS128 all passed and exact. WS128: 36.602512 class-balanced (all-prompt median 37.43, p10 34.75), 12/12 exact, timing-claim eligible, TTFT 1.79 s.
Submitted 02:36 UTC after a local dry run and a server dry run (HTTP 200 valid): HTTP 201, APPROVED; `scripts/packet58_onecard_record_threshold.json`
updated; receipt `data/localmaxxing-responses/2026-10-23-packet58-onecard-cache23-chain-a-onecard-ws128.txt`. Chained under the idle-lanes rule (screen
+1.72 %, below the +2 % chain bar). Endpoints restored as `*-20261023-restore17`; PAUSE-A re-armed, PAUSE-B untouched. Packet
`stage2/packet58-onecard-cache23-chain/` (chain receipts under `evidence/card0-cache23-a/`, bundle under `submission/prepared-a/`),
`ops/packet58c23chain-orchestration/`, note `notes/2026-10-23-packet58-onecard-cache23-chain.md`. Both records are now from this session:
one card 35.93 → 36.60, two cards 58.80 → 60.66 → 62.35.

**October 22, 21:15 EDT — one-card 23 GB expert-cache screen WINS +1.72 % (packet58-onecard-cache23, card 0, 00:57–01:10 UTC).**
One load max/max23/max/max23/max = 35.892/**36.546**/35.929/**36.569**/35.925 tok/s with K1a/K1b passed; every view 12/12 exact, drift 0.01 %;
fills per token 15.45 → 13.46 (−12.9 %), fill MB 30.6 → 26.7; no kill rule fired; DRM stayed under the unchanged 30.5 GB guard with the plan
re-partitioned from packet182c's lifetime receipts (driver allowance 671 MB, transient 785 MB). Chain bar (36.645) missed by 0.2 %, but the lanes
are idle, so the one-card record chain is being derived from packet182c with the max23 selection (`packet58-onecard-cache23-chain`, CPU-only);
its WS128 must beat 35.926720. Endpoints restored as `*-20261023-restore16`; PAUSE-A re-armed, PAUSE-B untouched. Packet
`stage2/packet58-onecard-cache23/` (note `notes/2026-10-22-packet58-onecard-cache23.md`).

**October 22, 20:50 EDT — packet191 per-class attribution on the record line (lane B, 00:32–00:47 UTC): exact, class table withheld.**
Sites-off views 62.198/62.166/62.184 reproduce the record line (−0.08 % vs packet189, −0.26 % vs the chain; drift 0.05 %); sites-on 58.266/58.238
(recorder cost 0.937, ~32 µs per layer per half). The completeness kill rule fired: device kernel sums (11.44 ms per half) vs the host `layer_body`
scope sum (16.40 ms) differ by 30 % because host layer scopes overlap while the host runs ahead, so the analyzer withheld the table (the rule's
reference, not the device, is at fault). Raw per-layer class costs on both ranks (µs): dense 154, experts 105, route+small 76, HC 68, recurrence 30,
QSA attention 17–20, norms 16; only route+small reads above packet110 (+22) and that class absorbs the recording cost, so no class shows a measured
excess; `open_mechanisms_remaining` is empty. Closed as a measurement at this overhead. Next on the cards: the one-card cache23 screen (lane A,
card 0) once the endpoints are restored. Packet `stage2/packet191-k3x-class-attribution/` (note `notes/2026-10-22-packet191-k3x-class-attribution.md`).

**October 22, 20:05 EDT — one-card lever synthesis 1: nothing open reaches +2 %; the line is bound by 48 serial layer bodies.**
Premise corrections: the one-card record (35.927, packet182c) runs NO draft (decode_mode plain; one-card MTP closed three times: 58h/58aa/170),
and its layer body is 0.48 ms, at parity with two cards (0.47–0.50); the dispatch tables of 182c and the k3x record are byte-identical. Per-token
model on the 1,188 record intervals (reproduces 35.926720 exactly): 27.75 ms = 48 bodies 23.3 + head 1.40 + expert-cache miss reads 1.0–1.5 +
fill traffic 0.51 + boundary gap 0.54; the 2.06 ms LRU plan is hidden under the wait. Prices: cache +1.5 GB (23.05 GB) +0.58–0.84 % (the only
open lever above the +0.5 % screen bar; the +2 % bar would need a 32 % byte cut, impossible on 32 GB; all-resident ceiling +6–7.5 % needs 48.6 GB);
prefetch/demand copy closed (packet125/138/58am); host path +0.4–1.3 % inside drift; kernel classes at their floors. Structural ceiling 40.5 tok/s
(48 bodies + head) without M=2 (closed at 9.21 ms/half row) or a new per-layer kernel floor; the Strata target is not reachable on this line.
Next: `packet58-onecard-cache23` capacity screen on card 0 (~14 min; satisfies packet58x's revisit condition with the 182c lifetime receipts),
prepared CPU-only. Synthesis archived in `stage2/packet182c-chain/analysis/onecard-synthesis-1-20261022.md`.

**October 22, 19:35 EDT — lever synthesis 4 (after the 62.345 record): the two-card line is at a structural ceiling for single mechanisms.**
Critical-path model on the record intervals (reproduces 62.345282 to 1e-9): hit = max(draft 1.531, boundary 1.483) + max(A 11.927, B 11.902) + 0.038 =
13.51 ms; both ranks are 99.3 % busy per hit, so the hit cycle is half the total work; single-side ceilings are +0.2 % each. Misses are 48 serial
layer bodies (25.51 ms). No open lever reaches +2 % (1.02 × 62.345 = 63.59) and none reaches +0.5 % alone: every kernel class is at its measured
ledger floor, every draft item is closed (packet158 family), +1 acceptance point is worth +0.75 % with no lossless lever open, width-2 drafts lose.
The one family that can still reach +2 % is per-layer kernel cost on both ranks (+1.32 % per 0.01 ms per GDN layer; +2 % needs 15 µs of the 469 µs
layer). Next: packet191 (per-class site attribution on the k3x record line, lane B ≈ 14 min, measurement only) to open or close that family
with numbers; in parallel a one-card ledger re-synthesis (35.93 tok/s record vs the owner's Strata target). Synthesis archived in packet190
`analysis/lever-synthesis-4-20261022.md`. Cards idle; endpoints serving (restore14); PAUSE-A/B armed.

**October 22, 19:00 EDT — NEW TWO-CARD RECORD: 62.345282 tok/s class-balanced (packet190 k3x chain, LocalMaxxing `cmvk51wfn001gng01fpbfy89q`, APPROVED, +2.78 % over 60.659520).**
The record bundle (packet187's V3 line + packet189's k3x selection: GDN layer 26 on the rank-0 verified-token boundary, kernel token I/O on both ranks,
async rank-0 prepare, handoff export on the copy engine; packet189's engine `87eec645…` bound byte for byte) ran its 11-window chain on cards 0+1
(unit `packet190-chain-a`, 22:06–22:53 UTC): K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs, WS128x, WS128 all passed, no faults. WS128: 62.345282 tok/s
class-balanced (all-prompt median 62.265, p10 60.21), 12/12 exact, timing-claim eligible, hit/miss cycle 13.53/25.56 ms, acceptance 0.787. Submitted
22:58 UTC after a local dry run and a server dry run (HTTP 200 valid): HTTP 201, APPROVED; `scripts/packet49_record_threshold.json` updated; receipt
`data/localmaxxing-responses/2026-10-22-packet190-record-bundle-k3x-ws128.txt`. Root was 25 MB above the launcher floor before the chain, so packet97's
and packet103's closed chain outputs (3.0 GB) were archived to `/mnt/usb-models/own-runtime-archives/` with sha256 manifests and removed
(`stage2/DISK-CLEANUP-20261022.md`). Endpoints were idle (last requests 21:40 UTC), stopped after the launcher's dry run, and are back as
`*-20261022-restore14`; PAUSE-A re-armed, PAUSE-B untouched. Packet `stage2/packet190-record-bundle-k3x/` (chain receipts under
`evidence/device-cards01-p190-a/`, bundle under `submission/prepared-a/`), `ops/packet190-orchestration/`, note `notes/2026-10-22-packet190-record-bundle-k3x.md`.
Day's two-card line: 58.798 → 60.660 (V3) → 62.345 (k3x). The pipeline is now balanced within 0.1 ms (rank 0 A 11.96, rank 1 B 11.92, boundary 1.48 vs
draft 1.53 ms), so the next lever must cut both ranks or the draft itself.

**October 22, 17:35 EDT — packet189 k3x WINS on two cards: chain rule met, +2.66 % over every V3 view (lane B, 21:17–21:32 UTC).**
One load V3/k3x/V3/k3x/V3 = 60.615/**62.242**/60.444/**62.225**/60.498 tok/s with packet188's fresh V3 at 60.505; every view 13/13 exact,
draft proposals and acceptance identical, V3 drift 0.28 %; no kill rule fired (export 0.053 ms, boundary 1.48 ms, k3 hit saving 0.53 ms,
A trim 0.141 ms). Hit cycle 14.06 → 13.53 ms, misses 25.77 → 25.57; rank 1 now binds 26 % of hits and the boundary trails the draft by
0.05 ms, so the pipeline is balanced to within 0.1 ms. k3x = packet188's k3 + trims with the handoff export back on the copy engine.
Record bundle packet190 (packet187's eleven-window chain on cards 0+1 with the k3x selection, packet189 engine `87eec645…`, k3 memory
plan, host floor 108.8 GB + 1 GiB) is being prepared CPU-only; its chain must beat 60.659520. Endpoints restored as `*-20261022-restore13`;
PAUSE-A/B armed. Packet `stage2/packet189-twocard-k3x/` (note `notes/2026-10-22-packet189-twocard-k3x.md`).

**October 22, 17:05 EDT — packet188's loss attributed to its own export path; k=3 reopened as packet189 k3x (CPU prep running).**
Lever synthesis 3 split the +0.97 ms boundary: the GDN layer-26 kernels cost 0.459 ms (equal to the 0.463 ms saved on rank 1) and the
20,480-byte handoff export grew 0.54 ms only because packet188's `kernel_io=kernel` key sent it through a one-work-item-per-byte kernel
(28.9 ns/byte) instead of the copy engine (2.6 ns/byte). The decision's D reading (0.43 ms) was a model artifact; the observed draft wall was
1.537 ms. Replay on packet187's record intervals: k3 + trims with the export on the copy engine **+2.74 %** (62.3 tok/s; range +2.3 to +3.0),
the only open lever above the +2 % chain bar. Packet189 adds a `boundary_export=copy` key, reads D from the draft wall, and proposes two
lane-B rows (k3x smoke, one-load V3/k3x/V3/k3x/V3; packet188 row 1 is the fresh V3 reference). Synthesis archived in packet188's
`analysis/`. Ledger wording for packet188 corrected (loss as built, not "k=3 closed"). Cards idle; endpoints serving (restore12).

**October 22, 16:20 EDT — packet188 k3 + trims loses on two cards (lane B, 19:55–20:16 UTC); k=3 closed.** One-load bracket
V3/k3+trims/V3/k3+trims/V3 = 60.526/60.564/60.536/60.382/60.540 tok/s with a fresh V3 control at 60.505; every view 13/13 exact,
draft proposals identical, drift 0.058 %. The slower k3+trims view is 0.26 % below the fastest V3 view. Kill rules fired: the
GDN layer 26 costs 0.97 ms at the rank-0 boundary (0.54 ms of it in the export) against the 0.54 ms it saves on rank 1, so hits
break even and misses lose 0.38 ms. The rank-0 trims (kernel I/O + async prepare) do remove 0.142 ms from rank 0's half, but
rank 1 binds every V3 hit. Record unchanged at 60.659520. Endpoints restored as `*-20261022-restore12`; PAUSE-A/B armed.
Packet `stage2/packet188-twocard-k3-composite/` (note `notes/2026-10-22-packet188-twocard-k3-composite.md`). A third lever
synthesis is pricing the rank-1 share of kernel I/O and the boundary export from these scopes.

**October 22, 15:34 EDT — public results page updated for the 1.3.0 release candidate.** skindeep.ai/ctxkeeper-results.html
now shows campaign 55's two-seed result (423/423 and 420/423) with the 1.2.0 figure and the prerelease caveat under the
table, and links the campaign-55 audits and the release-gate receipts; the download stays 1.2.0 until the owner promotes
1.3.0. Site link checker passed; desktop and phone renders inspected. The SEO checker's assertion on ctxkeeper.html's
share-card image is pre-existing and unchanged.

**October 22, 15:31 EDT — session-swap integration, step 1: a checkpoint's exact token prefix reproduced on this host from text.**
The pinned oracle tokenizer, fed with this host's Qwen3.8 tokenizer file, encodes all 12 sealed suite prompts to exactly
the recorded token ids (receipt under `experiments/own-xpu-runtime/integration/receipts/`). Step 2 (messages to that text)
needs the chat template as the GGUF header holds it from the four-card host. No GPU work; cards empty. The 1.3.0 prerelease
awaits the owner's promotion and PyPI step.

**October 22, 15:29 EDT — session-swap contract brought up to date with packet180/181.** The contract now says what the
four-card host qualified today: append, restore-then-save, one manifest source, a shared lock, cheap inspect, the
`qualified-one-card` label, tokenizer identity pins; the five integration gaps of yesterday's review are closed. The
integration review names what the ctxkeeper adapter needs next and who owns it: a warm request front for the engine
(runtime side), then a rendering-parity harness here (messages to the exact token prefix), then the parking policy.
No GPU work; cards empty.

**October 22, 14:59 EDT — ctxkeeper 1.3.0 passed the release gate (campaign 56) on its public prerelease assets.** G1 40/40
fixed, 40/40 clean, 7/7 audit in 15 min; G2 300K chat 4/4 through the Docker image; G3 all three SDK contracts; G4 Gemma
100K smoke 4/4. Kernel clean, cards empty. The prerelease is ready for stable promotion and the PyPI upload, both the
owner's; the files for the publishing repository are staged with the commands. Receipts:
`experiments/qwen38-27b-b70/data/2026-10-22-ctxkeeper-1.3.0-release-gate/`.

**October 22, 14:24 EDT — ctxkeeper 1.3.0 release candidate: package aligned, built and fresh-installed; prerelease and the
registered release gate (campaign 56) next.** The four keeper fixes of campaigns 51-55 plus the opt-in conversation
journal are 1.3.0; the README carries campaign 55's two-seed result. Wheel, source archive and the standalone files
are built from the aligned tree with checksums; a fresh venv installs the wheel and reports 1.3.0. The gate runs on
the public prerelease URLs exactly as for 1.2.0; stable promotion and PyPI are the owner's call.

**October 22, 14:20 EDT — campaign 55 done: seed 0 423/423 and seed 2 420/423 with two wrong STATE lines, both audits PASS.**
On ctxkeeper 1.3.0.dev4 both seeds of the 2M hostile stream keep every forgery target and apply all 16 audits; seed 2's
two wrong lines were single-version slips, and its three misses were two old-value questions the model answered "None"
without looking and one who-question, none caused by the notes. Since campaign 51 (419 and 402 with 10 and 15 wrong
lines) four keeper levers took the series to 423 and 420 with 0 and 2. The counter-reopening family is closed; the
arithmetic lever has no evidence left (every method target kept in four campaigns). Next: a 1.3.0 release candidate
through the registered release gate (upload is the owner's), and the unanswered old-value questions. Cards empty.
Audits and receipts: `experiments/qwen38-27b-b70/data/2026-10-22-context-campaign55/`.

**October 22, 14:30 EDT — NEW TWO-CARD RECORD: 60.659520 tok/s class-balanced (packet187 V3 chain, LocalMaxxing `cmvjvabyv040jrf01dricuz8s`, APPROVED).**
The record bundle (bundle 8 + V3 + packet153 static snapshot; packet186's binary `693cc194…` reused byte for byte) ran its 11-window chain on
cards 0+1 (unit `packet187-chain-a`, 17:32–18:19 UTC): K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs, WS128x, WS128 all passed, no faults. WS128:
60.659520 tok/s class-balanced (all-prompt median the same, p10 58.52), 12/12 exact, timing-claim eligible, hit/miss cycle 14.07/25.78 ms,
acceptance 0.783; +3.17 % over 58.798109 (packet136). Submitted 18:2x UTC after a local dry run and a server dry run (HTTP 200 valid):
HTTP 201, APPROVED; `scripts/packet49_record_threshold.json` updated; receipt `data/localmaxxing-responses/2026-10-22-packet187-record-bundle-v3-ws128.txt`.
Endpoints were idle (last requests 16:44 UTC), stopped after the launcher's dry run, and are back as `*-20261022-restore11`; PAUSE-A re-armed,
PAUSE-B untouched. Packet `stage2/packet187-record-bundle-v3/` (chain receipts under `evidence/device-cards01-p187-a/`, bundle under
`submission/prepared-a/`), `ops/packet187-orchestration/`, note `notes/2026-10-22-packet187-record-bundle-v3.md`. Both records are now from
today: one card 35.926720 (packet182c), two cards 60.659520 (packet187). Next two-card lever: rank 1 now binds every hit (A 12.09 < B 12.43 ms).

**October 22, 12:40 EDT — V3 wins on two cards: +3.3 % over the record line, chain rule met (packet186, lane B, 16:09–16:34 UTC).**
V3 = full target head back on rank 1 plus layers 24–25 run on rank 0 for the verified token (boundary command, never banked, never
in the speculative image) plus packet153's static snapshot. One-load bracket U/V3/U/V3/U = 57.83/60.57/57.80/60.53/57.84, fresh
split-head bundle-8 controls 58.60 and 58.44 tok/s; every view 13/13 exact, draft proposals and acceptance identical; drift 0.26 %.
Measured: rank-1 saving 0.463 ms per moved layer, rank-0 boundary 1.03 ms for both layers, hit cycle 14.78 → 14.06 ms; rank 1 now
binds every hit. Both V3 views clear 1.02 × 58.798109 = 59.974. The record bundle (bundle 8 + V3 + static, fresh chain on cards 0+1,
LocalMaxxing submission path) is being prepared CPU-only as packet187. Packet `stage2/packet186-twocard-v3/` (note
`notes/2026-10-22-packet186-twocard-v3.md`). Lineage today: packet183 S1 loss → synthesis (σ attribution) → packet185 measurement →
packet186 V3.

**October 22, 11:06 EDT — ctxkeeper 1.3.0.dev4: the set check now also catches a counter the reply left out; campaign 55 (both
seeds) registered and starting.** The four wrong lines left on seed 2 were one counter the notes held as removed while
the turns reopened it with no line in the reply. Replaying eight audited runs, the extension asks at 8 to 11 cuts per
seed-2 run and every question lands on a wrong value; it never fires on seed 0. Campaign 55 runs both seeds on it,
registered with predictions. Cards in use by the campaign until about 14:40.

**October 22, 11:02 EDT — campaign 54 complete: seed 2 421/423 with 4 wrong STATE lines, audit PASS, the best seed 2 on record;
the loop-cut failure of the last three campaigns is closed.** On ctxkeeper 1.3.0.dev3 seed 2 answered 421 of 423 with four
wrong lines in 8,932 (one counter, the removed/reopened family), all 16 audits applied and every forgery target kept; no
loop occurred and nothing stood unchecked. Campaign 54's registration is met. Across its three runs (two void for host
reasons) the cut that broke campaigns 52 and 53 passed every time. Next lever: a reopen stated for a counter the notes
hold as removed. Cards empty. Audit and receipts: `experiments/qwen38-27b-b70/data/2026-10-22-context-campaign54/`.

**October 22, 10:40 EDT — two-card (TP2) session checkpoints pass on device (packet184, lane B, 14:23–14:35 UTC).** On the
bundle-8 record engine (entry-source delta only, 78 kernel objects relinked unchanged): save of both ranks' state incl. rank-0 banks
and the MTP draft cache 128.8 MB in 1.85 s; fresh-process restore 2.32 s + first token 92 ms vs a 59.3 s cold prefix; merged output
and draft guesses equal the uninterrupted reference (11/11 smoke gates). Lifecycle 23/23: append a 126-token turn (1.77 s, 14 ms per
token vs 6.16 s cold), restore-then-save, resume in a third process, repeat append; the re-saved state is byte-identical to a one-shot
run on both ranks (216 blobs). Label `experimental-two-card`, contract `v1.2+p184`; the qualified label needs a new packet. Same window
as packet185 (seven rows, one endpoint stop/restore, `*-20261022-restore9`). Packet `stage2/packet184-twocard-checkpoint/`
(note `notes/2026-10-22-packet184-twocard-checkpoint.md`). Handoff for the ctxkeeper host: TP2 checkpoints now exist; contract §10
item 1 is implemented and device-tested (label flip pending), see the packet README for the CLI/manifest.

**October 22, 10:25 EDT — packet185 un-split-head measurement: V3 GO (u = 0.222 ms, decoupled B − A = 0.851 ms).** The lever
synthesis found no cleanly open two-card lever ≥ +2 %; its one candidate V3 (full target head back on rank 1, layers 24–25 run on
rank 0 for the verified token while it waits for the draft; +3.1 % central) sits in packet177's closed placement family, whose revisit
condition asks for a measured rank-0 slack attribution. packet185 measured it on lane B (13:55–14:22 UTC, five fresh loads C/U/C/U/C,
all 13/13 exact, drift 0.145 %): un-split cost on rank 1 0.222 ms (kill threshold 0.39), decoupled B − A 0.851 ms (threshold 0.60),
rank-0 suffix-head service σ 0.403 ms/cycle, controls 58.60/58.54/58.62 vs un-split 57.74/57.76. Ruling: build V3 as packet186
(CPU prep running). The packet184 TP2-checkpoint rows run in the same window after it. Packets `stage2/packet185-twocard-unsplit-head/`
(synthesis under `analysis/`), `stage2/packet184-twocard-checkpoint/`.

**October 22, 08:52 EDT — campaign 54b void (host memory guard when a second agent started beside the server; the kill logged an
engine reset; health probe passed), seed 2 running again as c54c.** The partial run again handled its one loop and got the
critical cut right. Two reminders for anyone on this host: a research run leaves about 2 GiB of host memory free, so
starting Codex or another Claude session beside it trips the guard, and the guard's kill now costs an engine reset as
well. c54c was refused by the fault latch before any server started; the latch is archived with its review (kill-induced reset, probe passed, kernel clean) and seed 2 runs as c54d from 09:24.

**October 22, 08:25 EDT — packet183 two-card S1 dense-scales bracket: loss, -6.2 %; S1 and S2 closed.** The S1 lever (dense
Q6_K kernels read the 18 retained scale bytes per 256 weights instead of the 64-byte FP32 words, -14.4 % dense bytes, exact by
construction, priced +4.4 % floor) ran as a one-load v5 bracket on lane B (11:56-12:21 UTC, `lanequeue-B32`): controls
58.617/58.587/58.630, S1 54.987/54.985 tok/s, all 13/13 exact, drift 0.072 %. Same-size loss as packet175b D1 (6.7 %) for the
opposite byte change: these GEMV lanes pay for per-group inner-loop work, not scale bytes. The guarded waiter logged the decision
and ran no confirmation. Endpoints idle (last requests 10:30 UTC), stopped after the live plan, back as `*-20261022-restore8`
(validations true); PAUSE-A untouched, PAUSE-B re-armed. Packet `stage2/packet183-twocard-s1-micro/` (note
`notes/2026-10-22-packet183-twocard-s1-micro.md`, DO-NOT-REPEAT row added). Two-card record stays 58.798109 (packet136).
Next on two cards: the TP2 checkpoint packet (session-swap contract §10 item 1) is being prepared CPU-only; the next speed lever
comes from a ledger re-synthesis (S1/S2 closed, fill pacing closed).

**October 22, 07:33 EDT — campaign 54 void: the campaign disk filled.** Seed 2 on the loop-rejecting keeper ran 69 minutes
with no loop at all and got the cut that broke the last two runs right, then the 916 GB campaign disk hit 100 % and the
run died at call 1,155. Each 2M run writes 6.4 GB of per-turn snapshots; the completed runs' snapshots (about 100 GB,
not used by any audit) are moving to the external SSD, the runner now refuses to start under 40 GB free, and seed 2
reruns as c54b. Cards empty.

**October 22, 06:35 EDT — one-card own-runtime record chain passed: WS128 35.927 tok/s class-balanced (live ledger 34.573).**
packet182 re-bracketed the packet176 kernel I/O lever (never chained before: `ops/onecard_chain_derive.py` emitted its
flags after the `__main__` guard, and the 10-19 cleanup deleted the chain evidence) as a one-load v5: 34.58/35.95/
34.59/35.95/34.58, +3.93 %, drift 0.018 %, all exact. Its guarded waiter derived `packet182c-chain` and ran the
7-window chain in the same window (09:47–10:21 UTC): all passed, WS128 exact and timing-claim eligible. Fill
pacing/deferral (resume item b) priced at ≤ +1.4 % and closed. Endpoints were idle, stopped only after the live
plan, and are back as `*-20261022-restore7` (validations true); PAUSE-A re-armed. Submitted to LocalMaxxing 10:32 UTC: HTTP 201, run
`cmvjejvoi03qcrf0138emu5a6`, status APPROVED; threshold file updated; ledger entry in `results/localmaxxing-submissions.md`. Packets:
`stage2/packet182-onecard-kio-rebracket/` (note `notes/2026-10-22-packet182-onecard-kio-rebracket.md`),
`stage2/packet182c-chain/`, `ops/packet182c-orchestration/`.

**October 22, 06:18 EDT — the cause of every bad seed-2 cut found: the model loops. ctxkeeper 1.3.0.dev3 rejects loops; campaign 54 registered and starting.**
Scanning all 1,820 notes replies of the seven audited 2M runs: 19 replies repeat one line 67 to 438 times, all on
seed 2, and every reply that ever hit the cap is one of them; no other reply repeats a line more than twice. One
such loop was applied last night. The keeper now names a loop (a line six times or more), never applies or keeps it,
and asks once more without thinking. Campaign 54 runs seed 2 alone on this version (seed 0 is a byte-identical replay
at temperature 0 and never loops), registered with predictions in the hostile note. Cards empty between runs.

**October 22, 06:13 EDT — campaign 53 done: seed 0 perfect again, token for token; seed 2 415/423, the same cut.** The cut-off
lever (1.3.0.dev2) could not help seed 2: at the cut that broke campaign 52 the model never wrote the missing line in any
of five attempts, each a 180-to-450-line reply padded with one "(no change)" line per item, and the retries hit the cap
again. Across seven audited runs every cap hit is a seed-2 reply of 200-840 lines in a cut where one counter is mentioned
in nearly every item; seed 0 has never hit the cap with a reply that held lines. Measured, those cuts are not bigger than
others (ordinary mention counts), so the next lever is the shape of the reply, not the cut or the retry. Seed 0 reproduced campaign 52 exactly (same calls, same tokens, all 153 notes versions identical in text),
so the keeper is deterministic at temperature 0. Cards empty. Receipts: `experiments/qwen38-27b-b70/data/2026-10-22-context-campaign53/`;
the read: the campaign-53 section of `experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md`.

**October 22, 04:30 EDT — packet181 session-swap v3 qualified on device: the saved-state label is now `qualified-one-card`.**
Relink-only child of packet180 (binary `0bf0a17a…`): manifests carry `label: "qualified-one-card"`, `contract:
"v1.2+p181"` and a `qualified_by` record (packet179 same-generation resume, packet180 append + restore-then-save;
scope one card only, TP2 not implemented, no ctxkeeper adapter); packet180's `experimental` files still restore.
Window 07:59–08:28 UTC rows (driver `window-p181-driver`, runner `lanequeue-A36`, endpoints idle since the 07:23Z
validation, restored as `*-20261022-restore6`, no fault lines): row a 31.83 tok/s, all 12 outputs identical to
packet179 row a; lifecycle row 43/43 gates (append == one-shot reference, restore-then-save chain == reference,
repeat identical, re-saved state byte-identical, label/contract/qualified_by on every device-written manifest);
restore 0.44–0.47 s. The packet181 source read corrected packet180's note: this engine has no chunked prefill
(closed by packet166); the append's 5.6 s is the fresh process's cold expert cache. Packet:
`experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/`; note `notes/2026-10-22-packet181-session-swap-v3.md`.
Next engine items: TP2 checkpoints (contract §10 item 1) and the ctxkeeper adapter (two-card host).

**October 22, 02:54 EDT — campaign 52 done: seed 0 perfect (423/423, zero wrong STATE lines, every forgery kept), seed 2 415/423
with one bad cut.** On the new keeper (1.3.0.dev1 with `--set-check`; it also carries the earlier bare-number working check),
seed 0 of the 2M hostile stream is the first clean seed: every answer right, no wrong line in 8,745, all 16 audits, all
102 forgery targets kept. Seed 2 lost 101 of its 103 wrong lines and 7 of its 8 misses to a single cut where the model's
first reply ran past the reply cap (295 lines, mostly repeated "no change" lines), was thrown away whole, and the
shorter retries left three counters out; one of them then stayed 25 high for 77 versions. That is the same failure
campaign 49 had once, and the next lever is to keep a cut-off reply's complete lines. Both registered levers did what
they were meant to on both seeds. Cards empty. Audits and receipts: `experiments/qwen38-27b-b70/data/2026-10-21-context-campaign52/`;
the read: the campaign-52 section of `experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md`.

**October 22, 03:25 EDT — packet180 session-swap v2 qualified on device: append a new turn, restore-then-save, one manifest source, shared lock, inspect modes.**
Built CPU-only off packet179 (entry TU only, 41 kernel objects relinked byte-identical from packet165,
binary `f68714ce…`), sealed, READY with the pin guard at 0 cross-packet pins, then run in a one-card
window 06:44–07:23 UTC (driver unit `window-p180-driver`, runner `lanequeue-A35`; the three daily
endpoints had been idle since 03:03Z, were stopped only after the live plan passed, and are back as
`*-20261022-restore5`, all validations true; no kernel fault lines). Row a: 31.78 tok/s, oracle exact,
all 12 outputs identical to packet179 row a. Row b (36/36 gates): save at K=256 → fresh-process restore
+ a 126-token appended turn + 128 decoded tokens == the one-shot reference [0:128]; restore-then-save into
S2, resume S2 + 64 == reference [128:192]; repeat append identical and S2b blobs == S2 blobs; restore
0.41–0.46 s; append prefill of 127 tokens 5.59 s vs 16.0 s cold prefill of 469 (2.66×); inspect/delete
tools passed. Label still the string `experimental` (string change goes in the next relink, packet181). The append's
5.59 s is the cold expert cache of a fresh process, not a slower path: the reference's first 126 positions
took 5.68 s; this engine has no chunked prefill (closed by packet166).
Packet: `experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/`; note
`notes/2026-10-22-packet180-session-swap-v2.md`. Earlier today (same host): neural.download and skindeep.ai
cleanups, every one- and two-card recipe rewritten to one seven-step quick start, package manifests fixed
(`e46e5fbfc`…`7e036a7c9`).

**October 21, 23:34 EDT — campaign 51 complete and read; ctxkeeper 1.3.0.dev1 carries two levers; campaign 52 registered.**
Seed 2 (rerun c51b) answered 402 of 423 in 85 min: 16 answers were lost when the model overwrote its own answers
file at the third probe batch (a client slip, not the keeper's), and the notes held a struck-off counter at its old
value for ten versions. Campaign 51 did not meet its registration on either seed. Its read gives two keeper levers,
both measured by replaying the four audited 2M sessions before any run: a STATE change written as "old set to new"
is now stored as the new value (six of seed 0's ten wrong lines), and a new asked-once check (`--set-check`) names a
set or removal the turns state for a counter that none of its lines takes (the other four of seed 0, one of campaign
49's, and seed 2's ten-version line). Both are in 1.3.0.dev1 with tests (144 pass). Campaign 52, both seeds on arm
K32V, is registered in the hostile note with predictions and starts next; nothing else runs on this host while it
does. The cards are empty between runs. Records: `experiments/qwen38-27b-b70/data/2026-10-20-context-campaign51/`
and the campaign-51/52 sections of `experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md`.

**October 21, late evening EDT — one-card device window ran: packet178 portable rebuild and packet179 checkpoint both qualified on device.**
The window approved at ~15:40 had not actually run (PAUSE-A latch + a session-bound runner; the
daily endpoints were down 6 h for nothing) and both packets were refused by the lane queue's pin
guard (1056 / 123 cross-packet pins that the packets' own pre-READY plan could not see). Repairs are
in-packet only (`b8fded755`, `064452363`); the endpoints were restored first, then the window ran
under unit `lanequeue-A34` 02:13–02:55 UTC with fault count 2 → 2. packet178 (portable rebuild
`6fa840ab…`): two fresh loads 31.83 / 31.81 tok/s, oracle-128 exact, all 12 output hashes identical
between loads and to packet179's reference load. packet179 (checkpoint engine `8d185384…`): reference
load 31.85 tok/s, oracle exact; save at K=256 (1.10 s, 68.8 MB, 128 blobs) + two fresh-process
restores with M=128 → merged 384 tokens equal the reference at [0:384), repeat restores identical,
restore 0.46 s + 6.78 s continuation vs 36.75 s cold prefix. SESSION-SWAP-DESIGN.md §7 gates 1–4 are
met on device; the manifest label stays `experimental` until an engine revision changes the string.
Endpoints restored as `*-20261021-restore4`. Incident, repairs and receipts:
`notes/2026-10-21-own-runtime-window-pin-guard-refusal.md`. Rule: a window is running only when
`events-A.jsonl` shows START; run the live `lanequeue.py plan` before stopping any endpoint.

**October 21, 22:05 EDT — campaign 51: seed 0 done and audited, seed 2 lost to the host memory guard and
relaunched as c51b.** Seed 0 (ctxkeeper 1.2.1.dev0, arm K32C) answered 419 of 423 in 80 min with 16/16 audits
applied and every forged line flagged, but with 10 wrong STATE lines (campaign 49b: 1) and two fewer answers than
registered. Six of the ten are a new "old set to new (item N)" phrasing with the right new value; four are plain
wrong values at two counters. Seed 2 died at call 667: a Claude session and a Codex process started on this host
at 23:18 beside the campaign server and took its last gigabyte of headroom; the guard stopped the server cleanly,
no fault, health probe passed. One agent session beside the server fits; a second does not. Seed 2 is running
again as `ctx-campaign51b` (started 22:01, about 90 min) on the registered keeper file; cards are released after
it. Audit, receipts and the full read: `experiments/qwen38-27b-b70/data/2026-10-20-context-campaign51/` and the
campaign-51 sections of `experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md`. Also today:
the session-swap contract was reconciled with the packet179 engine (v1.2 notes in
`experiments/own-xpu-runtime/SESSION-SWAP-DESIGN.md`) and the portability standard now records the host-RAM
requirement that keeps the ownrt replay off this host. Late evening: the four-card host's window ran after
its repair and the checkpoint restart-and-continue gate passed on device (receipts `8bf76113f`); the contract and
the integration review carry the result, scoped to same-generation resume.

**October 21 — packet179 integration review (source-only).** The committed
engine resumes an unfinished generation from its original prompt; general new
conversation turns and restore-then-save are not implemented yet. Metadata
consistency, deletion locking and inspect transport also need reconciliation
before a ctxkeeper adapter. [Review with source references](tools/ctxkeeper/CHECKPOINT-INTEGRATION.md).
No sealed packet, queue or GPU process was changed. TURIND8 cannot run the
published ownrt TP1 portability replay: 15 GiB total RAM versus about 92 GiB
required available RAM. Keep that replay open for a suitable host.

**October 21 — ctxkeeper durable conversations implemented in development 1.3.0.dev0.**
The two-card host's work is the text-storage side of the session-swap effort.
Opt-in `--save-conversations` retains complete requests, returned replies and
actual main-call views; local list/export commands support text-based resume.
142 CPU/scripted-model tests and 15 release-gate tests pass, including abrupt
process exit, archived-history resume, concurrent sessions and streaming HTTP.
A fresh package installation and separate-process export pass. Setup and the
runtime integration boundary: [saved conversations](tools/ctxkeeper/CONVERSATIONS.md).
PyPI 1.2.0 remains stable; GPU restore is not implemented or claimed here. The
other host owns the runtime contract, qualification and public runtime pages.
No GPU jobs, model services or website files were changed by this work.

**October 20 — ctxkeeper published on PyPI.** The owner configured the trusted publisher and authorized upload.
Stable 1.2.0 is now available from PyPI, GitHub and skindeep.ai/ctxkeeper.html. The dedicated
`skindeepai/ctxkeeper` workflow passed and uploaded the release; a fresh PyPI installation reports 1.2.0 and
both runtime module hashes match the stable release. The setup page uses the PyPI command and correct proxy
port (18200). Details and receipt: `drafts/ctxkeeper-1.2.0-release-runbook.md`.
Lab 1.2.2.dev0 remains development: retry ordering and numeric parsing were corrected, task-specific claim
stripping removed, and unsupported detection-rate claims withdrawn. Saved benchmark snapshots were full client
histories, not the proxy's managed requests. No new campaign or server was launched by this review; the existing
campaign-51 runner was active when checked and was left untouched.

**October 20, evening EDT — device requalification: the sealed full512 profiles bit-exactly reproduce on this boot; daily endpoints restored.** Four fresh
loads against the historical sealed packet165 binary (`cb2cef71…`) under whole-host reservation and sealed
admission: TP2 58.724/58.676 and TP1 31.766/31.774 tok/s (published loads 58.632/58.557 and 31.782/31.510),
all 6,495 output tokens byte-identical across loads **and** to the original sealed qualification brackets,
oracle exactness intact. Evidence in commit `72bddd50d`; receipt in
`data/2026-10-20-model-package-closeout/device-requalification-20261020.md`. The portable rebuilt binaries
(`c2573efd…`, CPU-compile-validated only) still need their own device gate — the engine binary is seal-pinned
in both card seals, so qualification means a new sealed packet: next campaign item. All three daily endpoints
were recreated from the closeout restore plan afterward (FP8 on fresh `-restore2` state dirs — the serve
tooling refuses state-dir reuse by design); 18130/18131/18100 all serving.

**October 20, 11:15 EDT — ctxkeeper 1.2.0 is the stable release (Latest); campaign 50 gate passed.** c50c ran
the registered G1-G4 against the public prerelease assets: G1 repair through the pip wheel **40/40 fixed, 40/40
clean, 7/7 audit, 12 min 18 s**; G2 the 300K demo through the Docker image built from the public source archive
**4/4**; G3 the README SDK snippet **all three contracts**; G4 Gemma 100K **4/4**. Kernel log clean; cards left
empty. c50b's G1 failure (one empty `shell {"command": ""}` from the model ending freeagent's run at ticket
37/44) did not repeat on byte-identical installs and is recorded as a client fragility, not a keeper regression
(the proxy's empty-reply retry condition is unchanged since 1.0.1). The release notes carry the gate results;
skindeep.ai/context-use.html now offers 1.2.0 as the stable download. Full record: campaign-50 section of
`notes/2026-10-10-context-16k-baseline.md`; receipts under `context-longrun-20261012/c50c/`.

**October 20, 10:35 EDT — ctxkeeper 1.2.0 prerelease published; release gate (campaign 50) running.** Version
aligned at 1.2.0 (pyproject, `__version__`, README, Dockerfile URLs); 112 unit tests and the notesdelta sync
check pass. Wheel + flat source archive built and published as **prerelease `ctxkeeper-v1.2.0`** with the six
assets of 1.1.0's layout and SHA256SUMS. Public-URL verification passed: fresh-venv pip install of the wheel URL
reports 1.2.0 with installed-module hashes matching the sums; `docker build` from the archive URL runs 1.2.0.
First gate attempt c50 failed preflight (venv lacked the `openai` SDK that G3 needs; no cards touched);
relaunched as **c50b** with the SDK added — G1 repair running at 10:24. skindeep.ai/context-use.html now carries
the campaign-49 both-seed results and the prerelease status (stable download stays 1.1.0 until the gate passes).

**October 20 — homepage layout cleanup.** The Flash-Next lab-result link now
has its own callout. Native result rows use consistent card badges and show the
quality limitation once; their measured ranges are excluded from scalar speed
bars. Buttons wrap cleanly, anchored rows clear the opaque sticky header, and
long filenames wrap on narrow phones. Measurements and serving state are unchanged.

**October 20 — Flash-Next result discovery corrected.** The native one-/two-card
recipes were live but absent from the homepage table. Both now have explicit lab
measurement rows, and the two-card result is linked near the top and in the
Flash-Next section. The family summary no longer implies four-card-only support.
Quality and portability gaps remain visible; no result was promoted or rerun,
and no serving state changed.

**October 20, 10:07 EDT — campaign 49 complete: the 2M bar is not met as registered.** c49d seed 2 (ctxkeeper
1.2.0.dev10, K32C + `--cited-entries`) ran **417/423 in 88 min** on the post-freeze boot (kernel log clean),
after c49b seed 0's independently audited **421/423**. 16/16 audits on both seeds; no forged value, method, rule
or removal was ever adopted (every forged NOTES line flagged in every version it entered). The registered gate —
every forgery target kept on both seeds — failed on two silent tally slips (motu29 answered 711 for 721 twice,
588 items apart, no written working for the sum check to catch; the NOTES held 142 correctly throughout) and on
the wrong-STATE-line caps (30 lines, cap 15; removed/reopened counters stale for 6-10 versions). Hash-bound
audits and receipts for both seeds are public under
`experiments/qwen38-27b-b70/data/2026-10-19-context-campaign49/`; the full read is in
`notes/2026-10-17-hostile-history-poison.md` (campaign-49-complete section). Next levers per the registration:
silent tally arithmetic in batch answers, and value verification at cuts starting with removed/reopened
counters. Turin's cards are idle (`RESTORE=0`; no ctx/gemma/qwen units running). The release lane below
(installer, public page, campaign-50 gate) is unchanged by this verdict.

**October 20, 04:09 UTC — model recipe closeout validated; all three daily endpoints restored.**
Five text recipes now carry source/build instructions and scoped measurements:
Qwen3.8 27B FP8 TP2, Flash-Next own-runtime TP1/TP2, Gemma4 Q8 and Nemotron.
The FP8 six-request 512-token prompt screen measured median2164.081tok/s;
its repeated output IDs matched, and the experimental server stopped cleanly.
All47 publication checks, Pages tests, and phone/desktop browser checks pass.
Recipes and source/evidence downloads are live and hash-verified; [closeout ledger](notes/2026-10-20-model-package-closeout.md)
records the exact scope. Native full512 quality, context/multi-user qualification
and clean-host admission remain pending; Nemotron's replay remains deferred.

The owner-requested daily services are active again on the four-card host:
`qwen38-27b-fp8` at18130 (card0), `qwen38-27b-fp8-tp1-test` at18131 (card3),
and `qwen38-27b-vision` at18100 (cards1+2). Both FP8 startup generation checks
passed; the vision endpoint returned READY to one bounded text probe. Original
model/device/profile settings are unchanged; cleanup uses a single owned TERM,
with automatic restart and forced kill disabled. No new kernel GPU fault was
seen. Memory blocks53–56 remain offline and57 online on boot2cba7160; no
power, swap or cache settings changed. [Restoration receipt](data/2026-10-20-model-package-closeout/local-daily-restoration-result.json).
Turin remains under the separate ctxkeeper campaign below; do not disturb it.

**October 20, 03:40 UTC — recipe publication closeout resumed from OMP (owner request; text lanes only).**
The approved work is finishing optimized-model recipes, measured decode/prefill/
context/concurrency coverage, and neural.download/README publication. October17
FP8 one-launch adoption is authorized. OMP's acceptance run finished successfully;
its receipts are being preserved and integrated. Own-runtime full512/prefill
receipts already exist and are being separated from the newer capped records.
Nemotron remains owner-deferred after an interrupted attempt; its reboot cause
is unresolved, and the old account of a campaign EXIT trap was incorrect.
See [closeout ledger](notes/2026-10-20-model-package-closeout.md) and
[incident correction](notes/2026-10-19-nemotron-stock-headline-window.md).

At 03:33 UTC the four-card host had no model service or campaign lock active;
all three daily endpoints remained stopped from the approved validation window.
Memory blocks53–56 were offline and57 online on boot2cba7160; no settings were
changed. Root free space was11GiB, below own-runtime's25GB launch floor, and
MemAvailable about86.6GiB was also below its sealed admission. Do not weaken the
checks. Turin's restored server/proxy were stopped by another actor at03:30 UTC;
its repository is being edited concurrently. Do not restore or take its cards
from stale handoff assumptions. No new GPU work has been launched in this review.

**October 19, 23:32 EDT — ctxkeeper release recovery on turin.** The reboot interrupted campaign 49c before a seed-2 result was saved. Campaign 49b seed 0 survives: **421/423, every forgery target kept, 16/16 audits**, with the saved notes independently checked. The post-reboot restored proxy and idle FP8 server were stopped gracefully at 23:30 (server `stop_confirmed=true`, no current-boot GPU fault lines); cards were empty during release preparation. At 23:34 EDT campaign 49d started the registered seed-2-only queue with fresh state, dev10, the lean client, and `RESTORE=0` (unit `ctx-campaign49d`). The owner has authorized continuing the release checks and prioritizes a usable public proxy download page and guide. Next: a fresh seed-2 run, installed-package release checks, public downloads, and live-page verification. Campaigns leave the cards empty; the older instructions to restore resident Gemma below are superseded. The 3 TB USB drive is mounted at `/media/steve/3TB GREEN HDD`; no data was moved. Release checklist: [ctxkeeper 1.2.0](drafts/ctxkeeper-1.2.0-release-runbook.md).


**October 19, ~15:40 UTC — daily inference: three validated Qwen3.8 27B endpoints on all four B70s (owner request: single-user speed, MTP, prompt caching, images optional).** Systemd user units (linger on), localhost only; serving copies in `/home/steve/inference/` (packages untouched):
- `qwen38-27b-fp8.service`, card L0 0 (PCI 23:00.0), `:18130/v1`, model `qwen38-27b-fp8`: official FP8 rev 017b9c7, vLLM R312d-c, MTP5, `--enable-prefix-caching --mamba-cache-mode align`, 32K context. Validated: 45.8 tok/s single-user decode, 7,168/8,607 cached tokens (TTFT 5.3→0.95 s), identical outputs, deterministic.
- `qwen38-27b-fp8-tp1-test.service` (the name is historical; it is a permanent second instance), card L0 3 (PCI 47:00.0), `:18131/v1`, same config; validated 45.1 tok/s.
- `qwen38-27b-vision.service`, cards L0 1+2 (PCI 27:00.0 + 43:00.0, `ZE_AFFINITY_MASK=1,2`; fdinfo shows no memory on other cards), `:18100/v1`, model `qwen38-27b-vision`: UD-Q5_K_S + mmproj + MTP Q4_0 draft, llama.cpp 9fee29e9, 256K context, f16 KV, prompt cache on. Validated: 27.0 tok/s, 8,603/8,607 cached (TTFT 12.9→0.25 s), MTP 315/585 accepted, image test pass.
- Measured on this host: one-card FP8 (44 tok/s suite) beats the two-card package (40 tok/s; its 90.3 tok/s receipt did not reproduce here). Four-card Flash-Next FP8 OOMs since the 10 GiB RAM exclusion. **Swap is OFF** (owner-approved for the FP8 attempt; not re-enabled). Validator: `/home/steve/inference/validate_endpoint.py`; receipts in the same folder.

**October 19, ~13:30 UTC — daily inference switched to Qwen3.8 Flash-Next (owner request).** `qwen38-flash-next.service` (systemd user unit, linger on): Unsloth UD-IQ3_XXS rev 766911a6 (3 shards SHA-256 verified), llama.cpp 23b0202a SYCL (`/home/steve/build/flash-next-iq3-baseline-20261010`, llama-server target built today), cards L0 0+1 = PCI 23:00.0 + 27:00.0, layer split 1,1, token_embd + per_layer_token_embd on CPU, 32,768 context, f16 KV, flash-attn off, `http://127.0.0.1:18140/v1`, model `qwen38-flash-next`; first request 30.6 tok/s decode. The two 27B services are stopped (units remain; `systemctl --user start qwen38-27b-fp8 qwen38-27b-vision` restores them, but not together with this server on cards 0/1). **The four-card FP8 package (A367/A382, 46.85 tok/s) cannot launch on the current host:** its fail-closed launcher requires swap disabled (swap is on; owner rule forbids changing it) and MemAvailable >= 120,000,000 KiB (measured 118,334,612 KiB with every server stopped, because of the 10 GiB RAM exclusion since Oct 6; the record predates it). Lowering that gate risks OOM freezes and was not done.

**October 19, ~13:05 UTC — daily inference servers running (owner request; campaign paused).** Both are systemd user services (linger enabled for steve), localhost only:
- `qwen38-27b-fp8.service`: Qwen3.8 27B official FP8 (rev 017b9c7, weights verified), vLLM R312d-c pinned image, package `packages/qwen38-27b-fp8-tp1-b70` recommended profile, card L0 0 = PCI 23:00.0, `http://127.0.0.1:18130/v1`, model `qwen38-27b-fp8`, 32,768-token context, MTP5 target-verified (~54 tok/s), prefix caching off, text only. State `/home/steve/inference/qwen38-27b-fp8`.
- `qwen38-27b-vision.service`: Qwen3.8 27B UD-Q5_K_S GGUF + mmproj + MTP Q4_0 draft (files hash-verified against the 256K package manifest), llama.cpp `9fee29e9` SYCL build, card L0 1 = PCI 27:00.0, `http://127.0.0.1:18100` (OpenAI API + web UI), model `qwen38-27b-vision`, 262,144-token context with q8_0 KV, images on, llama.cpp prompt cache and context checkpoints at defaults (the package validated them off). Log `/home/steve/inference/qwen38-27b-vision/server.log`.
- Cards 2 (43:00.0, lockup history) and 3 (47:00.0) are idle. Campaign lanes have PAUSE files and stopped drivers; do not run campaign jobs on cards 0/1 while these servers run. Stop with `systemctl --user stop qwen38-27b-fp8 qwen38-27b-vision`.

**October 19, 12:02 UTC — OWNER PAUSE of the own-runtime IQ3 campaign (the host is being set up for daily inference: Qwen3.8 27B FP8, one B70, `packages/qwen38-27b-fp8-tp1-b70`).** The record chain 176-a (packet176 kernel I/O, bracket +3.87%) was allowed to finish; crons, waiters and preparation subagents are stopped; lane drivers are stopped after the chain. Resume queue, in order: (a) packet178 S1 dense-scales micro, lane B; prep stopped mid-edit, untracked in `stage2/packet178-twocard-s1-micro/`, no build/READY; (b) the next one-card lever on the packet176c line: p176 readout shows ~1.0 ms/token of wall outside the transfer window (fill cost moved); price fill pacing/deferral as a one-load v5 with a win-path chain waiter armed before it runs; (c) two-card plan B if S1 > 0.96×: the p177 (d) two-sequence pipeline profile (~76 tok/s total, M=1 per sequence), labelled multi-user, never a single-user record; (d) `gpu_time_review.py`: count `packet58-onecard-*` chain units from the journal and honour an OWNER-PAUSE marker. Every derived chain must pass `onecard_chain_derive.py --predevice-check/--closure-check/--postnative-check`. Codex is out until 2026-10-26 02:24 local.

**October 19, 09:09 UTC — Codex (GPT) hit its account usage limit; unavailable until October 26, 02:24 local.** Running Codex jobs (p58asd, p168b, p171, p172) died mid-work; Claude subagents finished p58asd (record chain), p168b and p171, and run p171b/p172/p173. Codex-unit waiters and freezes (`codex-launch*.sh`, `after-codex-run.sh`, `codex-freeze-heavy.sh`) are inert until then; one-card timing windows use `fn-run/QUIET` (subagents pause heavy CPU while it exists) and READY-mtime waiters (`fn-run/ready-run.sh`).

**October 19, 10:05 UTC — 1-card IQ3 record 34.57 tok/s on one Arc Pro B70, submitted and approved (`cmvf31py400furf01tv54rxo7`).** Packet58as = the packet58aj line with a bounded spin host wait replacing the 1 ms sleep poll (+8.15%; bracket +8.58%, 60/60 exact; chain WS128 34.573, WS128x 34.308, all windows exact). See `notes/2026-10-19-own-runtime-packet58as-result.md` and `results/localmaxxing-submissions.md`.

**October 19, packet58am demand-transfer candidate built on CPU:** The new
one-card candidate keeps packet58ah's full 31.663 tok/s composition. Both
compilers pass the byte checks, and the actual device binary passes the CPU
preparation probe with the smoke and five-view arguments. The analyzer keeps
the real parent's slow first request. Smoke and v5 proposals are prepared;
readiness stays false until the census bound is at least 1.000 ms/token, and
v5 also needs the same-parent overlap smoke. Nothing was launched or queued.
[Work note](notes/2026-10-19-own-runtime-packet58am.md).

**October 19, packet162b diagnostic micro prepared on CPU:** The small
real-row kernel comparison builds and its CPU byte, parser and analyzer tests
pass. The shared entry probe and temporary queue plan pass, but the required
report rehearsal has no standalone-micro adapter. That failure is retained;
READY remains false. No GPU, service or live queue changed.
[Work note](notes/2026-10-19-own-runtime-packet162.md#packet162b--device-speed-micro-prepared-shared-report-adapter-pending).

**October 19, packet162 IQ2 lookup study closed on CPU:** A new exact integer
encoding fits the two-card memory plan with 629 MB extra per rank. Both trial
decoders match finite tests and the native host kernel's final bytes, but
separate NaN chain/tree byte checks differ. The strict CPU gate failed;
GPU speed is unmeasured. Sources, failures and a conditional test plan are kept.
No READY, device job, service or queue changed. Revisit requires a shorter
decoder with complete byte parity. [Work note](notes/2026-10-19-own-runtime-packet162.md).

**October 19, 04:18 UTC — 1-card IQ3 record 31.97 tok/s on one Arc Pro B70, submitted and approved (`cmveqsmsl00ebrf014yvrsosx`).** Packet58aj = the packet58ah line + exact resident lookup copies (29.3 GB anonymous, every row). The bracket gave +1.27%, 60/60 exact. Chain a WS128 **31.966820**, 12/12 exact, 0 major faults, +0.96% over 31.662719. WS128x 31.975 agreed within 0.03%: resident lookups remove the paging variance that cost chain 58ah-a 5%. The readiness wording was amended after the result to non-inferiority, disclosed. Scope: 128 tokens; strict512 false. [Result](notes/2026-10-19-own-runtime-packet58aj-result.md), [ledger](results/localmaxxing-submissions.md).

**October 19, packet156 draft-slack arm closed before a build:** The full
packet154 test confirms that rank 0 waits for the draft, but the proposed
place to move hidden work has too little spare time. Even a generous bound
allows only about 0.29–0.32% improvement in the three controls, below the 2%
goal. Complete log replays and 14 parser checks pass. No runtime, GPU job,
service or live queue changed; device readiness is false. The next prepared
ideas were checked, and none has a new qualifying bound.
[Work note and evidence](notes/2026-10-19-own-runtime-packet156.md).

**October 19, packet58ajb first-request repair prepared on CPU:** The original
resident smoke timed out before its first prefill token completed; teardown
drained safely. Its evidence is preserved. Fresh smoke and five-view proposals
use a 300-second wait and record the failed operation if it happens again.
The old logs do not identify that operation, so the cause is still unproven.
The device-define CPU preparation probe, exact-output checks and entry checks
pass; actual device checks remain pending. Nothing was launched or queued here.
The final readiness markers govern coordinator admission.
[Work note](notes/2026-10-19-own-runtime-packet58aj.md).

**October 19, packet155 preparation stopped at the disk floor:** The private
bundle9 source and native snapshots are retained, but root free space fell to
29.812 GB before the CPU fixtures ran. The requested 30 GB stop rule applies.
The chain is incomplete and refuses launch; CPU checks, submission rehearsal
and the packet153 bracket decision remain pending. No GPU, service or live
queue changed. [Work note](notes/2026-10-19-own-runtime-packet155.md).

**October 19, packet154 rank-1 split prepared on CPU:** The private packet150
copy adds command-correlated scopes to explain rank0's reply wait. Both builds,
byte checks, analyzer failures, entry and limit checks, 78 simulated requests,
reports, temporary plans and pin checks pass. The first completed incident must
prove both timing streams before proceeding. Two lane-B proposals remain
unqueued; device equality and attribution are pending. No GPU or service was
started. The final packet readiness marker is the handoff authority.
[Work note](notes/2026-10-19-own-runtime-packet154.md).

**October 19, packet153 static snapshot tables prepared on CPU:** The private
packet136 copy builds the snapshot copy table once at load. Capture and rollback
reuse it, keeping the copied state unchanged. GNU and Intel byte checks agree;
real copy sizes and reset behavior pass. Two lane-B proposals are prepared,
not queued. Device equality and speed remain unmeasured; 58.798 tok/s stays the
two-card record. The final packet readiness marker controls admission.
[Work note](notes/2026-10-19-own-runtime-packet153.md).

**October 19, 01:20 UTC — 1-card IQ3 record 31.66 tok/s on one Arc Pro B70, submitted and approved (`cmvekebvh00a0rf01q3v2c3cz`).**
- **Change:** packet58ah = packet58ad + packet58ag's one-card ports (HC-wide, p109 other-fusion, E1 exact half-scale cache).
- **Bracket:** +3.38% strict, 60/60 exact.
- **Chain a** WS128 was 30.050, below the record, with 3,736 host major faults. It was not submitted and is disclosed.
- **Chain b**, the single preregistered quiet-host rerun, measured WS128 **31.662719** with 12/12 prompts exact. It supersedes 30.395631 (+4.17%).
- **Scope:** 128 tokens; strict512 false.
- **Next:** packet58aj (resident lookup copies) is being prepared to remove the window-to-window paging variance.
- [Result note](notes/2026-10-19-own-runtime-packet58ah-chain-a-result.md), [ledger](results/localmaxxing-submissions.md).

**October 19, packet58ahb final quiet-host rerun prepared on CPU:** Chain a
passed exactness but its 30.050 tok/s timing missed the 30.395631 record; it
was not submitted. Its evidence and original pins are preserved. Chain b is
the single preregistered rerun and its WS128 is final either way. All 134
passive tests, seven intercepted launch paths, submission rehearsal, seals
and readiness replay pass. Nothing was launched or queued. The coordinator
must freeze every Codex unit before K1a through completion; the generic
waiter's WS-only freeze is too late for this rerun. The final orchestration
marker is the handoff authority. [Work note](notes/2026-10-19-own-runtime-packet58ah-chain-a-result.md#packet58ahb--final-quiet-host-chain-b-handoff).

**October 19, packet58ai miss census prepared on CPU:** The private packet58ad
copy keeps the 30.396 tok/s record configuration. It counts actual routed cache
misses and measures original expert events plus a separate resident/miss
partition diagnostic. Both builds, exact CPU checks, launch paths and shared
report checks pass. Device equality, overhead and the saving ceiling remain
unmeasured. One proposal is prepared, not queued; the coordinator must wait
until both two-card queues are empty. The final packet readiness marker is the
handoff authority. [Work note](notes/2026-10-19-own-runtime-packet58ai.md).

**October 18, packet58ah full-composition record chain prepared ahead on CPU:**
The seven-window packet58ad copy binds packet58ag's finished engine by hash
and selects all four new refinements explicitly. All 134 policy tests, seven
entry paths, parser and loader checks, submission replay, seals and pin
admission pass. The original 58ad timing is used only in a labeled rehearsal.
Device readiness remains false while the parent's bracket is pending; the
coordinator must recompute it and retain the same whole-host hold. Nothing was
launched, queued or submitted. The 30.395631 record is unchanged.
[Work note and evidence](notes/2026-10-18-own-runtime-packet58ah.md).

**October 18, packet58ag one-card ports prepared on CPU:** The private
packet58ab copy adds wider HC/expert geometry, exact half-scale decoding,
small target fusions and cheaper foreground event retirement. HC fusion stays
on. Both compilers' byte checks, all 111 policy tests, entry/report rehearsal
and both temporary queue plans pass. The first proposal is a 12 × 64 smoke;
the second compares the old line with the full composition in one five-view
load. Neither was queued or launched. Device equality and speed remain
pending, and the running packet58ad chain was left alone.
[Work note and evidence](notes/2026-10-18-own-runtime-packet58ag.md).

**October 18, packet150 rank-0 split prepared on CPU:** The current banked
bundle8 copy separates token preparation, snapshot work, the suffix head and
peer/draft waits. One proposed lane-B load has five exact 64-token views and a
15-minute cooperative watchdog. Builds, miniature byte/restore checks, launch
and report rehearsal, limits, drain checks and pin admission pass. Nothing was
queued or launched. Device attribution remains pending; the 58.798 record is
unchanged. Packet149's completed probe adds about 7.69 ms per miss, above the
1 ms gate, so no shared-correction prototype is being built.
[Work note and handoff](notes/2026-10-18-own-runtime-packet150.md).

**October 18, disk8 archive pass recovered 0.413 GB; reserve still short:**
Two verified archives preserve 595 closed, unused compiler outputs, logs and
private cache files on RAID. Root had 29.771 GB free at the final file check,
below the requested 38 GB. The remaining reviewed bulk is referenced,
protected, or lacks clear closure. All 22,120 retained files and links passed,
including 8,883 JSON/JSONL receipts. No device work or service was changed.
[Archive paths, verification and restore instructions](experiments/own-xpu-runtime/stage2/DISK-CLEANUP-20261018.md).

**October 18, packet58ad HC-fusion record chain prepared ahead on CPU:** The
new seven-window chain binds packet58ab's final engine by hash, keeping
tile16, overlap and the 21.55 GB cache. All 129 policy tests, seven entry paths,
native parser and loader checks, submission rehearsal, seals and pin admission
pass. The submission path bug is fixed in the new copy. The coordinator must
retain the smoke/bracket's whole-host hold; launch still refuses until those
results are complete, exact and clear the 2% gate. The parent's marker also
records its unresolved shared report-tool check. Nothing was launched, queued
or submitted here; the 29.259764 record is unchanged.
[Work note](notes/2026-10-18-own-runtime-packet58ad.md).

**October 18, packet58ab one-card HC fusion prepared on CPU; report gate blocked:**
The private packet58z copy switches between production HC and packet60's
three-stage HC within one load. GNU and Intel agree byte for byte; full-size
switch/reset checks and 111 policy tests pass. The shared entry checker accepts
both native binaries but cannot rehearse this one-card report layout. Its
failure is retained, so the final marker says not ready for device work.
The smoke and five-view proposals remain unqueued. No GPU, service or host
setting changed, and the 29.259764 record is unchanged.
[Work note](notes/2026-10-18-own-runtime-packet58ab.md).

**October 18, packet58ac cache publication feasibility closed on CPU:** Sparse
updates preserve the two-phase pointer and generation rules in both host
compiler checks. Packing the full tables takes only 0.053–0.060 ms, far short
of the required 0.739 ms saving. Existing receipts do not separate the remaining
device and wait costs well enough to support 60% net removal. No build brief
or device work was started. The 29.259764 one-card record stays unchanged.
Reopen with a measured cost split supporting a complete safe boundary below
0.493 ms. [Analysis and work note](notes/2026-10-18-own-runtime-packet58ac.md).

**October 18, packet58aa one-card MTP re-check closed on CPU:** The measured
host policy removes the old RAM blocker, but a resident draft cuts target
cache from 21.55 to 18.22 GB. Saved-route projections give 25.03–29.16 tok/s,
below the 30.723 needed for a build. Even a favorable shared-cache estimate
is only 30.62 before draft misses and cache pollution. No build or device work
was started. The 29.259764 one-card receipt remains unchanged. Reopen with
evidence for a faster complete verification cycle, including draft and cache
costs. [Analysis and work note](notes/2026-10-18-own-runtime-packet58aa.md).

**October 18, packet145 router and GDN z layouts prepared on CPU:** The new
packet142c copy preserves exact row bytes and arithmetic. Both compilers,
full-size startup/reset checks, both-lane entry/report tests and all eight
temporary queue/loader/pin checks pass. The lane-A router milestone met the 40-minute
deadline; both variants now have smoke and five-view proposals on A
and B. The final readiness marker is the handoff. Nothing was queued, and no
GPU, service or host setting changed. Device output quality and speed remain
pending; the 58.798 record is unchanged. [Work note](notes/2026-10-18-own-runtime-packet145.md).

**October 18, packet58z larger-cache record chain prepared on CPU:** The
new seven-window chain uses packet58x's exact binaries with a 21.55 GB cache,
tile16 and overlapped maintenance. Smoke and the exact five-view comparison
pass: 4.13% strict gain, 0.15% warm-control drift. The 128 policy tests, all
seven entry paths, loader checks, submission rehearsal, seals and pin guard
pass. The coordinator must hold the whole host and freeze Codex and compiles
from WS through WS128. No chain was launched or queued; the 28.042989 record
is unchanged. [Work note](notes/2026-10-18-own-runtime-packet58z.md).

**October 18, packet142 class-layout preparation passes on CPU:** The packet136
copy has three exact allocation-order candidates. Byte checks, full-size
allocation checks, entry and limit checks, submission rehearsal, six temporary
queue plans and the pin guard pass. The tested native build is retained by
exact source and binary hashes; no compiler hold was bypassed. Six proposals
remain unqueued. Only classes flagged by a valid packet141 verdict may be
selected, starting with smoke. The final readiness marker is the handoff gate.
The expert candidate covers one layer per rank; it cannot settle whole-class
placement. Device quality and speed remain pending. No GPU, service, live queue
or host setting was changed by this preparation. The record is unchanged.
[Work note](notes/2026-10-18-own-runtime-packet142.md).

**October 18, packet141c second and last probe repair completed on CPU:** The
previous attempt finished its diagnostic arms, then failed after cleanup made
its saved launches stale. The repair refreshes all six bank combinations and
the split output head. The CPU gate reproduces the old failure and passes the
full repaired sequence, reset and continuation with unchanged binding bytes.
Native entry checks, 28 Python tests and temporary queue planning pass. Both
failed attempts are preserved. The fresh proposal is unqueued; a complete
device result remains pending. No GPU, service or live queue changed here.
[Work note](notes/2026-10-18-own-runtime-packet141.md).

**October 18, packet58y one-card attribution prepared on CPU:** The new copy
measures host work, existing waits and cache hits/misses after packet58v's
overlap change. Both builds, exact miniature repeats and 98 policy tests pass.
The temporary queue plan puts it after 58x's smoke and bracket in their same
whole-host hold; it refuses a separate hold. No job was queued or launched.
Device timings that cannot be measured remain unknown. The next-lever ranking
waits for the diagnostic, under a preregistered 3% gain gate. The evidence reader
is ready and its 11 synthetic tests pass; its current report says data is pending.
[Work note](notes/2026-10-18-own-runtime-packet58y.md).

**October 18, packet58xb overlap amendment prepared on CPU:** The larger-cache
smoke and all five comparison views now select overlap. The first view must
still be exact and is reported as warm-up; the other two controls decide drift
and gain, matching packet58wb. All 101 tests, six entry probes, the minimal
reseal and both temporary queue plans pass. The cache sizes and memory guards stay.
Device work remains unlaunched and unqueued by this preparation; the running
packet58w chain is untouched.
[Work note](notes/2026-10-18-own-runtime-packet58x.md#packet58xb--overlap-and-first-view-amendment-october-18).

**October 18, packet58wb readiness amendment passes on CPU:** At the owner's
request, the first one-card bracket view is treated as cache warm-up for speed
comparison, after packet58v's data and before any packet58w chain. All five
views still pass exact output checks against packet49. The warm controls drift
by 0.098%; both overlap views beat both by at least 7.81%. All 124 tests and the
minimal reseal pass. The chain command is unchanged and no chain was launched.
Only the chain's fresh WS128 can supply a new record value.
[Work note](notes/2026-10-18-own-runtime-packet58w.md#packet58wb--cold-first-view-amendment-october-18).

**October 18, packet58x larger cache prepared on CPU:** The new copy allocates
21.553 GB once and switches between 18 GB and full use after draining work.
It keeps the device reserve and all transient allowances; host admission is
98.990 GB under the measured policy. Independent replay projects +2.26%, not
a measured speed. Both builds, byte checks, full-size startup, six real entry
probes, 96 policy tests and seals pass. The smoke and five-view proposals pass
temporary planning and remain unqueued. Serial maintenance stays the default
because packet58v's completed bracket failed its control-drift gate. No GPU,
service, live queue or host setting changed. Next is the coordinator's smoke.
[Work note](notes/2026-10-18-own-runtime-packet58x.md).

**October 18, packet58w one-card overlap chain prepared on CPU:** The fresh
seven-window chain reuses packet58v's binaries and seals tile16 with overlapped
cache maintenance. All 120 tests, seven real entry paths, 28 wrong-unit/environment
refusals, full-size startup, byte checks and seals pass. The command embeds its
library path and uses a new service name. It refuses until 58v's smoke and full
five-view bracket pass the exact-output and speed gates; at the preparation
check, smoke passed and the bracket was incomplete. The submission tool keeps
the 128-token limit and the pinned current record ID. No GPU, service, live queue,
parent packet or host setting was changed by this preparation. The 26.228599
record is unchanged. [Work note](notes/2026-10-18-own-runtime-packet58w.md).

**October 18, packet140 target-body search closed on CPU:** No new exact
change supports the required 3% projected gain. The broadest scale-sharing
idea gives about 1.31% under the transfer assumption supported by earlier
kernel work. A more favorable assumption could exceed 3%, but the evidence
does not justify it. The ranked table preserves all 164 negative indexes
and reproduces the 58.223834 record before calculating savings. No runtime,
build, GPU, service, queue proposal or readiness marker was created; existing
packet136/137/139 work is untouched. Reopen with a distinct mechanism and
evidence for enough savings. [Work note](notes/2026-10-18-own-runtime-packet140.md),
[ranked table and closeout](experiments/own-xpu-runtime/stage2/packet140-body-lever/README.md).

**October 18, packet137 token input prepared on CPU:** The new packet136-based
copy replaces repeated draft projection with a complete read-only lookup table
and gives the target fixed token-preparation buffers. Every vocabulary row
matches under both compilers; draft proposals, rollback and state checks pass.
Launch, queue and final seal checks pass. Three proposals cover the lane-B
smoke and five-view comparisons on lanes B and A; they are planned but not
queued. The unchanged legacy K2 startup receipt is reused within the CPU memory
limit. Device quality and speed remain pending. No GPU, service, live queue or
host setting changed. [Work note](notes/2026-10-18-own-runtime-packet137.md).

**October 18, packet138 phase 1 closed:** The capture and exact CPU replay
passed, but next-layer prefetch does not clear the registered gain and copy-time
gate. The best optimistic projection is +5.75%; even it has 248 late copy
batches. All 45 scenarios have late copies, and the less favorable timing
assumptions lose speed. No phase-2 device design is admitted. All 624 captured
tokens match their references; the route predictions and full cache analysis
are retained. The coordinator released the capture cleanly; this preparer
did not queue or launch device work. No measured speed record changes.
[Work note](notes/2026-10-18-own-runtime-packet138.md),
[results and closeout](experiments/own-xpu-runtime/stage2/packet138-xlayer-prefetch/phase1-closeout.md).

**October 18, packet58v async cache prepared on CPU:** The one-card record
spends 6.99 ms per token maintaining its cache. The new copy plans while the
next position computes, then safely revokes victim pointers before filling
their slots. This conservative schedule adds one position of lag. Both builds,
byte/race checks, full-size startup, 87 policy tests and the seal pass. The
12 × 64 smoke and five-view 12 × 128 bracket pass temporary planning but are
not queued; the larger run requires the exact device smoke first. The build
is 80.5 MB. Device correctness and speed remain pending; the 26.228599 record
is unchanged. No GPU, service or live queue was started or changed.
[Work note](notes/2026-10-18-own-runtime-packet58v.md).

**October 18, packet136 banked bundle8 prepared on CPU:** The new copy keeps
all 182 parent links and seals bundle7 with either copied or banked rollback
state. All 88 tests, 11 subtests and five worker tests pass, along with the
full launch-argument, temporary queue, drain and native-limit checks. The
unchanged shared K2 startup receipt is reused within the 4-GiB CPU limit;
the other startup checks ran locally. Six lane-A jobs are planned but not
queued. The fresh chain waits for exact output and at least 0.5% improvement
on both lanes, plus the composed smoke. Packet131b supplies lane B evidence.
The 58.223834 record is unchanged. No GPU job, service or live queue was
started or changed by this preparation.
[Work note and handoff](notes/2026-10-18-own-runtime-packet136.md).

**October 18, packet131b oracle admission repaired on CPU:** Packet131's
smoke refused before device execution because its source map crossed the
oracle symlink outside the repository. The new copy checks that oracle through
its original binding and complete-oracle check. Unsafe source maps now fail at
gate creation. All six real entry paths reach both intercepted native launches;
the original refusal is reproduced. Native binaries and all seven links are
unchanged. New smoke/grid proposals pass temporary planning but remain
unlaunched. No GPU, service, live queue or host setting changed here.
[Work note and evidence](notes/2026-10-18-own-runtime-packet131.md#packet131b--repair-oracle-admission-before-device-execution-october-18).

**October 18, packet132 second-candidate study closed on CPU:** Checking a
second draft choice on uncertain cycles does not clear the required 3% gain.
The main cost model chooses to leave it disabled; even counting only extra
expert work gives +2.25%, with +1.77% on held-out text. All 120 independent-text
positions completed. Evidence and a do-not-repeat row are retained. These are
CPU counts and cost projections, not measured device speed. No candidate was
implemented; no GPU, service, live queue or host setting changed. The capture
process exited normally. Reopen only with a new cost or prediction mechanism.
[Work note](notes/2026-10-18-own-runtime-packet132.md).

**October 18, packet134 rank0 gap attribution on CPU:** The saved trace does
not support command replay as the next speed fix. Of each hit's 1.679 ms
compute gap, 1.594 ms is before target kernels start and only 0.085 ms is
inside their sequence. The separate host gap mostly covers rank1 drafting
and target-head service. Misses add 2.046 ms before correction. Packet128b
failed its timing-overhead gate, so these remain diagnostic observations.
All 16 analysis tests pass and the evidence is sealed; the replay lever is
closed for these receipts, with the exact reopening condition in the note.
No runtime, GPU, service or live queue changed; no speed gain is claimed.
The next useful evidence separates token lookup, decoding and upload costs.
[Attribution and work note](notes/2026-10-18-own-runtime-packet134.md).

**October 18, packet133 bundle8 prepared on CPU:** The new copy preserves all
182 parent links and seals only bundle7 control and bundle7 plus suffix
interleave. Both compositions pass their CPU startup checks; all 83 tests and
11 subtests, the full argument/queue rehearsal, drain and native-limit gates
pass. The lane-A proposal is planned but not queued; no job or service was
launched. Packet130 B finished during preparation: its output is exact, but
the candidate is 1.61% slower than the fastest control and fails the required
0.5% gain. The fresh chain stays blocked; lane A and the composed smoke are
unrun. Packet131 remains a disabled slot. The 58.223834 record is unchanged.
[Work note and handoff](notes/2026-10-18-own-runtime-packet133.md).

**October 18, packet130 early suffix scheduling sealed on CPU:** The new
copy checks for rank1's hidden state between rank0's speculative layers and
runs the head suffix when it is ready. It preserves the tested output bytes,
arithmetic and miss rollback. Both compilers, full-size startup, all launch
paths, drain, limits and temporary queue checks pass. Two new lane-B proposals
cover a smoke and a one-load comparison; both are unlaunched. The build is
108.5 MB. Device equality and speed remain pending; no gain is claimed.
No GPU, service, live queue or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet130.md).

**October 18, packet131 recurrent snapshot sealed on CPU:** A new copy keeps
the old recurrent state in a spare buffer instead of copying it every cycle.
Capture copies about 61% fewer bytes, with no increase in owned device
allocation. All eight GNU/Intel state transcripts match byte for byte; reset,
production bindings, startup, queue, drain and launch-limit checks pass.
Two new lane-B proposals cover the exact smoke and five fresh-load comparison.
They remain unlaunched. No GPU, service, live queue or host setting changed.
Device correctness and speed remain pending; no speed gain is claimed.
[Work note](notes/2026-10-18-own-runtime-packet131.md).

**October 18, packet129 draft acceptance diagnostic prepared on CPU:** The new
copy compares publisher FP8 draft experts against the current INT8 draft on the
same inputs. Production guesses still drive the unchanged target. Both compilers
pass exact arithmetic checks; target/state, reset, memory, launch arguments and
temporary queue planning pass. Ten independent text inputs decide the +1.5-point
acceptance gate; the twelve-prompt suite is secondary. The single lane-B proposal
is ready for coordinator admission. Device acceptance is pending, and no speed
gain is claimed. No GPU, service, live queue or host setting changed here.
[Work note](notes/2026-10-18-own-runtime-packet129.md).

**October 18, packet128b sampled timing job prepared on CPU:**
Packet128's every-token recorder slowed the line to 42.21 tok/s, so its timing
ranking remains blocked. The new copy records tokens 9–16 and keeps copy clocks
separate from compute gaps. All parent links survive. CPU byte/reset/startup,
argument, drain, limits and temporary queue checks pass. One proposed lane-B
load checks all twelve 64-token answers; analysis runs after the lane is released.
New device speed and the required 90% overhead ratio are still unmeasured.
No GPU, service, live queue or host setting changed in this preparation.
[Work note and handoff](notes/2026-10-18-own-runtime-packet128b.md).

**October 18, packet58t resident lookup copy sealed on CPU:**
The one-card engine now has an exact copy that reads its two sparse lookup
tables from anonymous memory. This adds 29.32 GB of resident host bytes, checked
by hashes and included in each window's memory budget. Both compilers preserve
the tested output bytes; CPU preparation records zero major faults. All 109
Python tests, native checks, drain and teardown gates pass. The new proposal
passes a temporary queue plan: tile16 control / resident / control in one load,
15–25 minutes with a two-hour watchdog. The coordinator must admit the whole
host. Full-model device equality and speed remain pending; no gain is claimed.
No GPU, service, live queue or host setting changed in this preparation.
[Work note and evidence](notes/2026-10-18-own-runtime-packet58t.md).

**October 18, packet124c restores the oracle link and gates the queue:**
Packet124b stopped cleanly before KD because its oracle was a copied directory.
The new copy restores the oracle authority link and eight identical file links.
Native binaries and bundle7 selection are unchanged. All eleven window paths
and the whole queue rehearsal pass on CPU, including six real oracle checks;
the old tree reproduces the reported refusal. All 65 tests and 11 subtests pass.
Readiness is true from packet118's original composites and the native identity
chain. The fresh packet124c chain is unlaunched; the coordinator verifies
readiness and live admission before launch. No GPU, service, live queue or
host setting changed in this preparation.
[Work note and handoff](notes/2026-10-18-own-runtime-packet124.md#packet124c--restore-oracle-authority-and-gate-the-whole-queue-october-18).

**October 18, packet58r one-card one-load bracket sealed on CPU:**
The new tile16 copy can switch route and recurrence without loading the model
again. It checks every token against packet49 through A/B/A/B/A. Both compilers
pass kernel bytes; all 80 Python tests, native resets, full-size binding and
argument checks pass. The seal verifies and the new card-0 proposal passes a
temporary queue plan. The coordinator can schedule its 20–30 minute whole-host
gap, keeping lane B paused throughout. Fusion is unavailable and rejected.
Device equality and speed remain unmeasured; no record is claimed.
No GPU job, service, live queue or host setting changed in this preparation.
[Work note](notes/2026-10-18-own-runtime-packet58r.md).

**October 18, packet128 fresh bundle7 timing job prepared on CPU:** The new copy
can record every layer on both ranks, including draft, head, copies and waits.
CPU output, reset, full-size startup and real launch-argument checks pass.
One temporary lane-B plan passes: twelve prompts, 64 tokens each, one load.
The coordinator runs it next, then generates the budget. Actual device equality,
overhead and class costs remain pending; no speed gain is claimed. No GPU,
service, live queue or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet128.md).

**October 18, packet58p tile16-only one-card chain prepared ahead on CPU:**
The copy keeps production route and recurrence and changes only the down layout.
All 118 Python tests, twelve full launch-argument paths, native parser/startup
checks, byte checks and unchanged memory budgets pass. Both copied drain gates
are fixed, and native launches refuse inherited resource caps. The 72.7 MB
build reuses existing binaries. The seal and seven-window whole-host plan pass.
Readiness is false while 58n's tile16 arm is still running and its final control
is missing; all three arms must be exact and tile16 must beat both controls by
at least 0.5%. The exact command is prepared for the coordinator, who pauses
lane B. No GPU, service, live queue or host setting changed here.
[Work note and handoff](notes/2026-10-18-own-runtime-packet58p.md).

**October 18, packet124b repairs the failed K2 selection check:** The new copy
passes only K2's three kernel choices to its unchanged strict validator. Native
binaries, model output identity and bundle7 selection stay unchanged. All eleven
real Python window paths pass on CPU, covering 31 intercepted launch arguments;
the original packet124 code fails the retained K2 replay and the fix passes.
All 51 policy/submission tests and four subtests pass, along with startup,
memory, drain and launch-limit checks. Readiness uses the original packet118
composites and pinned packet124 identity. That packet124b chain later stopped cleanly before KD at the oracle link check.
Packet124c supersedes this preparation; its handoff is above.
[Work note](notes/2026-10-18-own-runtime-packet124.md#packet124b--k2-selection-repair-in-a-new-copy-october-18).

**October 18, packet126 early-draft analysis held at its timing gate:** Moving
the next draft before target verification does not by itself save rank1 work.
Without recovering head wait, the saved-command model is about 1.95% slower
because misses add a discarded draft. It needs about 0.43 ms of recoverable
wait per interval to clear the requested 0.5% gain, before rollback costs.
The traces do not measure that wait, so the actual gain remains unknown.
Both lanes' 2,376 intervals reproduce, eight analysis tests pass, and all 141
negative indexes were checked. No runtime build, GPU job, service or queue
proposal was made. Next prerequisite: separately timed head readiness,
suffix service and merge wait. [Work note](notes/2026-10-18-own-runtime-packet126.md).

**October 18, packet127 head retune ready for coordinator handoff:** The
81,920-row and 122,880-row rank0 suffixes fit the unchanged 24/24 bundle7 line.
Both compilers pass repeated exact bytes and resets; all 33 startup windows,
six native launch-limit checks and four temporary proposal plans pass. The
118 MB build is sealed. Both device micros, B's four-process grid and A's
conditional confirmation remain pending. The old model favors 46,080, and
packet120's trailing control refused teardown, so no new speed gain or spare
GPU time is claimed. No GPU, service, live queue or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet127.md).

**October 18, packet125 one-card miss micro prepared on CPU:** The retained
one-card screen averages 33 misses and 65.46 MB of missing expert bytes per
charged token. It does not separate PCIe reads from compute. All four external
slot links report PCIe 4.0 ×16. Seven exact transport paths compile, both
compilers pass repeated CPU byte checks, twelve policy tests and the drain
check pass, and two card2 proposals pass temporary planning. The micro loads
no model and uses real routes with explicitly simulated cache misses. The same
candidate must reach 1.5× in both fresh processes before a copied engine or
whole-host screen is prepared. Device results are pending; no GPU, live queue,
service or host setting changed. [Work note](notes/2026-10-18-own-runtime-packet125.md).

**October 18, queue live-window admission checked on CPU:** A now waits for a
live B window before starting, then keeps the 61-second drain gap. B keeps its
permitted overlap with an A exactness window. Fault, latch and pause checks
stay active during the bounded wait. All 96 CPU tests pass. Read-only live
plans found A's already-used evidence output and initially passed all five B
entries; ongoing coordinator work then advanced B. No service, GPU, live queue,
marker, latch or setting changed here. The coordinator picks up the code on
its normal between-job restart. [Work note](notes/2026-10-18-own-runtime-ops-lane-overlap.md).

**October 18, packet124 bundle8 BASE ready for coordinator handoff:** This is
bundle7 with repaired host cooldown waiting and exactly the same native
binaries and selection. Both compilers reproduce its saved output bytes;
both ranks pass memory admission and all eleven startup windows pass. All 42
policy/submission tests and six rank-launch checks pass. The old drain code
fails the clock-crossing test; both fixed copies pass. The original bundle7
smoke and both composites now qualify this identical selection, so readiness
is true. Its chain folder is fresh. No manual pause of the other lane is needed
for cooldown safety; normal exclusive timing reservations remain. New runtime
levers are disabled slots. This CPU task launched no GPU job or service and
changed no live queue or host setting. [Work note](notes/2026-10-18-own-runtime-packet124.md).

**October 18, packet123 partial-layer move held at its timing check:** The
saved bundle7 traces appear to leave 0.483 ms on rank0, but that includes
head work missing from the command trace. The logged copies alone use at
least 0.043 ms; total head time is unknown. We cannot establish the required
0.3 ms spare time, or claim it is below that threshold. The next prerequisite
is separately timed head work in an authorized device window. No candidate,
build or queue proposal was made. CPU accounting and original-byte inputs
are retained. No GPU, service, frozen tree or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet123.md).

**October 18, packet122 draft CPU preparation complete:** The full draft
probe covers 47 classes and both context lengths. The separate HC change
passes both compilers' byte checks twice; both views and ranks pass startup,
reset and protocol checks. The three proposed files pass temporary queue
planning. Both fresh HC micros must cut every changed class by at least 20%
with exact bytes before the one-load bracket can start. Device times are
still missing. The long-context probe cycles real captures and is labeled
a diagnostic. No GPU, service, live queue or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet122.md).

**October 18, packet120 layer placement prepared on CPU:** Moving one target
layer from rank1 to rank0 fits without changing the cache or head: the two
rank arenas retain 2.73 and 1.78 GiB. Both compilers pass repeated byte checks,
both views pass all startup windows, and the launch-limit and drain checks
pass. The B screen and conditional A confirmation proposals pass temporary
queue planning. Each compares production / 25-23 / production and requires
at least 0.5% over both controls with exact output. The timing budget gives
less spare time than the initial estimate, so a speed gain is uncertain.
Device equality, residency and speed remain unmeasured. No GPU, service,
live queue or host setting changed. The build is about 211 MB.
[Work note](notes/2026-10-18-own-runtime-packet120.md).

**October 18, packet119 DOWN-warming preparation complete on CPU:** Both
compilers pass repeated exact-byte checks, and the compiled image retains the
extra DOWN read with no extra stores or spills. The two proposed B micros use
all 384 captured routes and must each cut gate/up-plus-down time by at least
15% in both orders. The conditional one-load bracket passes both views and
ranks' startup, reset, protocol, limit and sealed-evidence checks. All 28 policy
tests and three temporary queue plans pass. The build is 120.6 MB. Actual cache
behavior, device equality and speed remain unmeasured; the bracket stays
blocked on both micros. No GPU, service, live queue or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet119.md).

**October 18, queue drain-spacing guard checked on CPU:** The queue now waits
until 61 seconds after the latest completed shared teardown on this boot before
starting a job. Pause, stop, fault and latch checks remain active during the
bounded wait. All 76 CPU tests and both live queue plans pass (six A jobs,
eight B jobs). Frozen wrappers are unchanged. Keep the other lane paused
during chains of unfixed bundles: their internal windows bypass the queue.
No service, GPU job, live queue, marker, latch or host setting changed here.
The coordinator picks up the code on its normal between-job driver restart.
[Work note](notes/2026-10-18-own-runtime-ops-drain-spacing.md).

**October 18, packet118 bundle7 preparation complete on CPU:** Both fixed
prefix compositions pass GNU/Intel byte checks, VRAM admission and all 22
startup windows. The twelve-prompt smoke shipped first; it and both composite
proposals pass temporary queue planning. All 31 policy/submission tests and
six rank-launch limit checks pass. The shorter prefix adds no head allocation.
The build is 208 MB. Readiness stays false while smoke and composites await
execution; packet103's record line is the control, and both lanes must clear
1.0% over both controls with exact prompts. After those runs, only the evidence
reader remains. No GPU, service, live queue or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet118.md).

**October 18, packet116 QSA schedule prepared on CPU:** The candidate
shares attention score work across more subgroups and selection ranking across
all lanes. Both compilers pass repeated operator and complete-layer byte checks.
Two value-tree rewrites changed NaN payloads and were rejected; the candidate
keeps the original value arithmetic. Both fresh micro proposals pass temporary
queue planning. Each must cut combined attention and selection time by at least
40% before the separate one-load bracket can run. That bracket passes its
startup, reset, protocol, limit and seal checks and has a conditional proposal.
The build is 121.5 MB. Device equality and speed remain unmeasured. No GPU,
service, live queue or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet116.md).

**October 18, packet117 HC preparation complete on CPU:** The candidate
shares independent sigmoid work across existing lanes and keeps the original
sum order. Stronger NaN tests caught and fixed a payload difference; both
compilers pass sixteen exact cases twice, and the full layer mock passes
4,736 comparisons. Both HC kernels remain spill-free. The two fresh micro
proposals and conditional one-load bracket pass temporary queue planning.
The bracket's startup, reset, protocol and memory-limit checks pass. Each
micro must cut both HC gate times by at least 30% before it can run. Device
equality and speed remain unmeasured. No GPU, service, live queue or host
setting changed. [Work note](notes/2026-10-18-own-runtime-packet117.md).

**October 18, packet115 expert micro prepared on CPU:** Separate expert images
use 128 registers for production and 256 for LARGE. All four designs have
zero spills; both compilers pass exact-byte checks twice per view. Two fresh
B micro proposals pass temporary queue planning and compare against both
production modes. Device equality and speed remain unmeasured. A parallel
one-load copy passes startup, reset and protocol checks and has a sealed,
conditional B proposal. E3 is provisional until the micro selects a winner;
only that winner's views are prepared. The whole build is 112.9 MB. No live
queue or GPU changed here.
[Work note](notes/2026-10-18-own-runtime-packet115.md).

**October 18, packet114 smaller draft prefix prepared on CPU:** The fixed
non-benchmark document rule chose 80,128 rows, down from 91,392. Both sizes
pass the byte checks, all eleven startup paths, reset checks and seals. The
full target head stays unchanged. The new lane-B one-load bracket proposal
passes a temporary queue plan; allow 9–15 minutes with a one-hour watchdog.
Its reports keep acceptance separate for each arm. The build is about 128 MB.
Actual acceptance, exact model outputs and speed await the device bracket.
No GPU, service, live queue or host setting changed in this preparation.
[Work note](notes/2026-10-18-own-runtime-packet114.md).

**October 18, packet111 four-composition bundle prepared on CPU:** The copy
includes the packet103 launch repair, other-fusion and target-head split.
Both compilers pass exact-byte checks; all 44 startup windows and 33 policy
and submission tests pass. The combined twelve-prompt smoke proposal shipped
first. The October 18 packet111r owner decision admits both added changes
because each beats all its source controls: head is +0.37% on B and +0.53%
on A, fusion +0.32% on B. Fresh combined proposals pass temporary planning.
The combined candidate must still beat both controls by at least 0.5% on
each lane, with exact prompts and unchanged per-prompt acceptance. The
coordinator's smoke completed during the CPU review and passes; composite
measurements are still missing, so the record chain stays blocked.
The four sealed compositions and binaries are unchanged. The build is 208 MB.
Launch checks reject the old inherited memory cap. This CPU update launched
no jobs and changed no host setting or live queue.
[Work note](notes/2026-10-18-own-runtime-packet111.md).

**October 18, packet113 GDN row micro prepared on CPU:** The candidate gives
each independent state row its own subgroup and removes workgroup barriers.
Both compilers pass two fresh processes, each with 572 complete-layer checks
and 768 full-state recurrence cases, including NaN/Inf and multiple tokens.
The device binary compiles; both proposed B jobs pass temporary queue planning.
Each fresh process must cut recurrence time by at least 40% before integration.
Device equality and speed remain unmeasured. The build is 66.6 MB. No GPU,
service, live queue or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet113.md).

**October 18, packet112 route-selection micro prepared on CPU:** The 18.75
microsecond route measurement already uses the fast route. The new candidate
keeps its arithmetic and removes thirteen workgroup barriers from selection.
GNU and Intel each pass 2,048 exact cases twice, including rejected NaN/Inf
rows. Both fresh-process proposals pass temporary queue planning; the build
is 10.3 MB. Each device process must halve route time before any integration.
Device equality and speed remain unmeasured. No GPU, service, live queue or
host setting changed. [Work note](notes/2026-10-18-own-runtime-packet112.md).

**October 18, packet103x launch repair checked on CPU:** The first composite
control failed because a Python import passed an 8 GiB address-space cap to
the ranks. The cap now applies only to the CPU reader's CLI. The coordinator
withdrew the old six jobs; their original names and failed output stay as
evidence. The decision, native binaries and 5,632 startup receipts are unchanged.
All six fresh suffixed proposals pass temporary queue planning. All 47 policy
tests and fourteen intercepted native launch checks pass; the old reader fails
the new gate. The record chain stays blocked on measured composite results.
No GPU, service or live queue changed. Early test cleanup entered shared teardown
bookkeeping; the final gate blocks writes outside its temporary directory.
[Repair note](notes/2026-10-18-own-runtime-packet103.md#packet103x--inherited-address-space-limit-repair-october-18).

**October 18, packet110 fresh class table and GDN timing job prepared on CPU:**
The table uses both fresh QSA runs and keeps missing GDN times blank. It ranks
open gate/up transpose, complete-tuple epilogues and exact route selection;
these are opportunity budgets, not speed claims. The current-only GDN job
compiles, passes two fresh CPU state checks and plans on a temporary queue.
The coordinator proposal is pushed, with a script to fill the GDN table after
its clean result. No device or live queue changed.
[Work note](notes/2026-10-18-own-runtime-packet110.md).

**October 18, packet58n one-card analysis and single-lever screen prepared on CPU:**
The losing bundle spends much more time reading its host lookup inputs, with
many more major page faults. Its expert-cache counts and bytes match production
at every position; the receipts do not prove why the host state changed.
The small retained tests favor tile16 even for host weights, so a new proposal
tests tile16 alone between two production runs in a 33–39 minute whole-host
gap. All 82 CPU checks and three temporary plans pass; the unchanged binaries
use 39.53 MB. No device, service or live queue changed.
[Analysis and proposed screen](notes/2026-10-18-own-runtime-packet58n.md).

**October 18, packet58m one-card port chain prepared on CPU:** The copied port
has all seven record windows, unchanged memory bounds and whole-host exclusion.
Real parser/startup/oracle checks, 48 K1 byte checks, 110 Python checks and the
seals pass. The finalized submission tool replays 58g's result and discloses
host-pinned weights; the build is 72.7 MB. Readiness stays false while 58k's
bracket is incomplete. The chain rereads all three exact receipts and requires
at least 0.5% over both controls before any launch. No GPU, service or live
queue changed. [Work note](notes/2026-10-18-own-runtime-packet58m.md),
[readiness and proposed command](experiments/own-xpu-runtime/stage2/packet58m-onecard-record/ready.json).

**October 18, packet108 budget and micro prepared on CPU:** Existing receipts
put the current two-card hit/miss steps at about 15.17/26.09 ms. They do not
retain fresh per-kernel times, so the budget keeps those gaps explicit. A new
draft load-only micro compiles, passes its temporary queue plan and keeps the
15% gate before any model integration. The build is under 1 MB. Device speed
and equality are unmeasured; no GPU, service or live queue changed.
[Work note](notes/2026-10-18-own-runtime-packet108.md).

**October 18, packet107 specialised layers checked on CPU:** Both complete
finite layers match across four fresh GNU/Intel runs. Stronger tests close the
GDN change: Intel changes a NaN payload. QSA keeps exact FP32 and output bytes
against each compiler's production and has two proposed single-card B jobs.
It must save at least 80 microseconds per layer in both fresh processes before
integration. Device equality and speed are unmeasured. The build is 67.2 MB;
no GPU, service, live queue, frozen packet or host setting changed.
[Work note](notes/2026-10-18-own-runtime-packet107.md).

**October 18, packet58k shorter one-card screen prepared on CPU:** Three
proposed arms each load once and check every token in the twelve-prompt suite.
Fresh small K1 fixtures still choose the miss path. Plan 33–39 minutes in a
whole-host gap, with 118.31 GB available-memory admission. The unchanged
binaries occupy 39.53 MB; all 76 CPU checks and three temporary queue plans
pass. The full submission chain stays in 58j. No GPU, service, live queue or
host setting changed. [Work note](notes/2026-10-18-own-runtime-packet58k.md).

**October 18, packet105b/106b reset repair ready on CPU:** The new copies
restore or preserve the suffix search after request reset. Repeated byte and
reset checks, allocation/transfer checks and all 55 startup windows pass, with
one saved receipt per window. The micro, both twelve-prompt candidate smokes,
B grid and conditional A confirmation all plan successfully. The grid refuses
until the device micro and complete smokes pass; A also needs an exact B winner.
The combined new build is 240.9 MB. All device results and speed remain pending.
No GPU, service or live queue changed.
[Work note](notes/2026-10-18-own-runtime-packet105b.md).

**October 18, packet106 prepared on CPU:** The draft head splits only after
a verified hit; misses keep the complete prefix on rank1. Both compiler byte
checks, hit/miss and transfer mocks, all eight allocation checks and all 44
startup windows pass. Four views are sealed. The new proposals start with one
64-token candidate-only B smoke, then a B grid and conditional A confirmation.
The build is 261 MB. Device equality and speed are still unmeasured. No GPU,
service or live queue changed.
[Work note](notes/2026-10-18-own-runtime-packet106.md).

**October 18, packet58j one-card port sealed on CPU:** The separate copy of
58g has down-tile16, route-fast and rec-both-plus, with eight choices including
production. Both builds, repeated GNU/Intel byte checks, all 80 full-size
startup/submit checks, 109 Python checks and ten plan-only rehearsals pass.
Every host budget matches 58g. E1 is excluded because it adds 616 MB of pinned
weights. The build is 161 MB. Device exactness and speed await the coordinator's
whole-host gap after the two-card chain; no device, service or live queue ran.
[Work note](notes/2026-10-18-own-runtime-packet58j.md).

**October 18, packet105 sealed on CPU:** The target head can send its last
46,080 rows to rank0 using the verified current hidden vector. Both builds,
both compiler byte checks, every head row's loader check, hit/miss mocks,
all six allocation checks and all 33 startup checks pass. Three views are
sealed. Ten proposed jobs pass temporary queue plans: both transfer choices
on lane B, then independent lane-A confirmation. The build is 279 MB.
Device quality, real card residency and speed remain pending. No GPU,
service or live queue changed.
[Work note](notes/2026-10-18-own-runtime-packet105.md).

**October 18, packet104 micro compiled on CPU:** Nine tile16 weight-layout
candidates are ready for the proposed lane-B operator test. The build is about
29 MB. It uses packet100b's real target routes; draft replay is labeled as a
proxy, with actual model screens required to check transfer. The target's
shared expert and router now have separate full-tuple comparisons. No long CPU gates, model screens,
GPU work or live queue ran. The coordinator proposal is
`ops/lane-queue/proposed-p104-micro-B.txt` under the own-runtime experiment.
[Work note](notes/2026-10-18-own-runtime-packet104.md).

**October 18, packet97e ready on CPU:** KD's old host command could not use
half-cache in streaming mode. The new sealed draft-only reference keeps its
arithmetic and exactness checks; the target's half-cache guard stays intact.
All 128 compositions pass all eleven startup windows in 12 minutes 36 seconds,
using about 1.2 GiB RAM. Decision `f1e5d7f47fc0fe54` is ready again in fresh
folder `device-cards01-b`; the old `-a` evidence and frozen decisions are
unchanged. No chain, GPU work or live queue was launched. The exact manual
command is in [ready.json](experiments/own-xpu-runtime/ops/packet97-orchestration/ready.json).
[Repair and checks](notes/2026-10-18-own-runtime-packet97.md).

**October 18, packet103 composite prepared on CPU:** Copied after packet97e’s
committed fix, the new bundle includes down-tile16 and draft attention with
all earlier choices. Both binaries compile; the build is about 222 MB including
the executed fixture hard links.
The source decision selects both new options and rechecks later lane-A losses.
Operator bytes and 529 submission replay checks pass. All 1024 full-size rank
allocation checks and all 5632 startup-window checks pass on finalized sources.
Eight required views are sealed; both three-job composite proposals pass
temporary queue planning. All 600 selected-path tests, input checks, storage
admission and the fresh-chain plan pass. The coordinator can screen the
proposals; record-chain readiness still needs their measured results. No device
or live queue ran in this preparation.
[Work note](notes/2026-10-18-own-runtime-packet103.md).

**October 18, packet100b route capture prepared on CPU:** The new lane-B job
captures both ranks' target expert routes for two standard 64-token requests,
then checks every output against the existing oracle. The follow-on micro uses
packet100's unchanged kernels and 15% gate. Both compilers, both full-size
startup checks, 23 Python checks and six temporary queue plans pass. The build
is about 66 MB. Real capture, device equality and speed remain pending. No GPU,
service, live queue or frozen packet changed. Use the new capture/micro proposals
and updated proposed B/A grids; records stay on A.
[Evidence and handoff](notes/2026-10-18-own-runtime-packet100b.md).

**October 18, packet98c native switching sealed on CPU:** A separate copy of
packet97 can switch route, recurrence, HC gate and draft attention without
reloading weights. Both builds, full-size capture/reset checks, layout refusals,
poisoned-state checks, repeated byte comparisons and 130 wrapper tests pass.
Both seals and all five temporary queue plans pass. Start with the proposed
route-only A/B/A on lane B; full brackets require that same-binary smoke first.
Device outputs and speed remain unmeasured. No GPU, service, live queue or existing
packet changed. [Evidence and handoff](notes/2026-10-18-own-runtime-packet98c.md).

**October 18, packet102 closed at the microbenchmark gate:** CPU byte,
assembly and full startup checks pass. The coordinator's micro run found
batch2 only 1.9% faster, batch4 unchanged and shared input 3.3% slower; none
meets the required 15%. Both combined variants spill. All conditional model
screens stay closed, and no record chain is qualified. The CPU preparation
changed no live queue or device state.
[Task note](notes/2026-10-18-own-runtime-packet102.md).

**October 18, packet97d ready on CPU:** All four brackets of the same sealed
selection are now counted. Both record-lane brackets clear the required gain;
the other lane has one qualifying win and its drifting bracket stays above
the first control. All outputs and acceptance counts agree. The unchanged
chain policy and every CPU readiness check pass; `ready.json` is true for
decision `f1e5d7f47fc0fe54`. No device work or live queue ran. The two frozen
decisions are unchanged. [Evidence and checks](notes/2026-10-18-own-runtime-packet97d.md).

**October 18, packet101 resealed on CPU after a parent-selection change:**
The new seals exclude packet97's changing orchestration outputs and keep
packet101's own selections. Binaries and quality gates are unchanged; no
rebuild was needed. All six fresh A/B queue plans and 13 CPU checks pass.
Start the complete fresh A control/attention/control bracket; the old A
control remains history and is not reused. B has a fresh mirror. Live queues
and all other packets were untouched. Packets99/100 do not pin the changing
selection, but both still pin a parent evidence receipt whose hash currently
matches. [Exact proposals and evidence](experiments/own-xpu-runtime/stage2/packet101-draft-geometry/RESEAL.md).

**October 18, review15 cleanup and packet97 rule prepared on CPU:** The new
cleanup tool can archive reviewed, closed screen caches and bundles after
checking every live packet's references. Its dry run found 156.8 MB eligible;
no real cleanup ran. New packet97 decisions exclude a source after a completed
loss or inexact result on the record lane. Packet93 is excluded by its A loss;
the two frozen decisions and their original tools remain unchanged. All 92 CPU
tests pass. The coordinator runs cleanup after a fresh plan.
[Instructions and evidence](notes/2026-10-18-own-runtime-review15-cleanup.md).

**October 18, packet101 prepared on CPU:** Packet69's draft-HC settings are
already active in packet97. Its draft attention option remains distinct, so
the new packet prepares that choice alone. Both compilers pass repeated byte
checks; all 512 full-size startup checks, four allocation refusals, four seals
and six temporary queue plans pass. B has a control/candidate/control proposal
and A its mirror; records stay on A. Device outputs, acceptance and speed remain
pending. Scratch is cleaned and the build is below 65 MB. No GPU, service, live
queue, existing packet or host setting changed.
[Evidence and handoff](notes/2026-10-18-own-runtime-packet101.md).

**October 18, packet100 prepared on CPU:** Two exact DOWN locality choices
and production pass both compilers, all 34 full-size startup checks, three
seals and five temporary queue plans. The build uses about 151 MB. The device
test is blocked: packet77/86 kept route hashes, but matching raw route bytes
were not found. No GPU, service or live queue ran. Recover those inputs before
the microbenchmark; only a measured 15% kernel-time win can reach separate B
screens and A confirmations. Records stay on A. No speed is claimed.
[Evidence and handoff](notes/2026-10-18-own-runtime-packet100.md).

**October 18, packet99 CPU checks complete:** Three exact IQ2 lookup choices
and their half-cache forms pass both compilers without linked spills. Full-size
startup, memory admission and refusal checks pass on both ranks. Down uses a
different format; its new table path is exact but spills, so it is closed before
device testing. The prepared single-card test must show at least 15% less kernel
time before a candidate gets its own B bracket and A confirmation. A decides
any later record choice. No GPU, service, live queue or host setting changed.
[Evidence and handoff](notes/2026-10-18-own-runtime-packet99.md).

**October 18, packet98 sealed on CPU:** A separate v5 screen wrapper now keeps
one rank pair for a whole bracket. Both native builds, full-size startup and
reset checks, real miniature byte checks, rank-message tests and 119 wrapper
checks pass. Both lane-B proposals passed planning in a temporary queue. V4 and
existing packets are untouched. No GPU or service ran. The first device step
will be a two-view packet84 A/A smoke on lane B; only after it passes may the
five-view packet91 comparison run. Device output parity and wall-time savings
remain unmeasured. [Task note](notes/2026-10-18-own-runtime-packet98.md).

**October 18, packet97b composition gate updated on CPU:** A source now needs one exact winning lane before joining the composite. Packet91's old rejection was an unfinished screen being labeled failed; its completed A grid now qualifies, together with packet93's head transpose and packet90's half-cache. The helper freezes that set and prepares both composite brackets plus conditional leave-one-out views from existing sealed selections. Pending sources do not delay the decision. Record readiness stays false until the composite's own two-lane checks and the unchanged full chain pass. No GPU, service, live queue or other packet tree changed. [Decision, diagnosis and validation](notes/2026-10-18-own-runtime-packet97.md#packet97b--review-14-screen-the-composite-first).

**October 18, packet58h one-card MTP feasibility closed on CPU:** The draft shares the existing head, but its own weights still need more host RAM than the saved admission snapshots allow. Both device layouts fit; whole-host timing needs about 121.65 GB available with the reserve intact. The main timing model predicts 24.62 tokens per second, below the required 28.8. No runtime was built or queued; frozen packets and live work were untouched. A passive read found blocks 53–56 offline and 57 online, differing from the brief's stated 10 GiB exclusion; no setting changed. Revisit only with a faster complete verification path and a host budget with margin. [Analysis and closeout](notes/2026-10-18-own-runtime-packet58h.md).

**October 18, packet97 sealed on CPU:** One new binary combines the packed head, reply-first reporting, HC norm fusion, expert grid prefetch and half-cache with packet91's routing and recurrence choices. Both compilers pass the byte checks; all 128 selections are sealed, all 256 full-size startup checks pass, and 305 Python tests plus 136 subtests pass. Largest and baseline chain rehearsals and six temporary queue plans pass. Readiness is false: packet91's A screen is rejected as unfinished/failed, other source decisions remain pending, and the unchanged chain disk reserve needs about 3.06 GB more free space. The helper will write the actual composition jobs when source decisions resolve. No GPU, service, live queue or frozen tree changed by this work. [Evidence and proposals](notes/2026-10-18-own-runtime-packet97.md).

**October 18, packet58s one-card submission tooling:** The new CPU-only preparer checks packet58g's finished queue, original receipts and packet49 exactness, then derives the one-card payload from WS128 alone. Sixteen synthetic checks and the shared CLI's offline dry-run pass. Plain decode has no draft; full BF16 KV and the 18 GB expert cache are disclosed. The strict 512-token gate and second timing repeat remain false. The public record lookup was blocked, so the public one-card best is unknown. No result was submitted and the running packet58g tree was untouched. [Coordinator steps](notes/2026-10-18-own-runtime-packet58s.md).

**October 18, packet93 restored-tool reseal:** Its three screen views now use packet84's restored submission tool. Both engine binaries stay unchanged. The original microbenchmark remains intact, but its old seal cannot admit new screens. The coordinator must run the new B2 micro proposal, then the B grid and A confirmation after fresh qualification. This work uses CPU only and leaves live queues untouched. [Exact proposals and evidence](experiments/own-xpu-runtime/stage2/packet93-packed-head2/RESEAL.md).

**October 18, packet95 sealed on CPU:** The new expert path reads the next IQ2 table word during current arithmetic, with unchanged sums and no linked register spills. The full scale cache fails both memory limits and is closed with exact arithmetic. Both compiler byte repeats, all four real startup/memory checks, 90 Python tests, two seals and eight temporary queue plans pass. Production stays hc-wide/wide64/ordered/rec-parallel. No GPU, service, live queue or frozen source changed. The coordinator can choose either direction; device correctness and speed remain pending. [Evidence and proposed jobs](notes/2026-10-18-own-runtime-packet95.md).

**October 18, packet94 sealed on CPU:** The low/injection kernel includes the same HC norm arithmetic and keeps the BF16 tensor needed by mixing. Both compilers pass every output and scratch byte across four consecutive tokens. All six full-size startup and memory checks, 90 Python tests, three seals and four temporary queue plans pass, including the HC weight-cache combination. The coordinator can screen either lane first and confirm its exact improving winner on the other. Device correctness and speed remain pending. No GPU, service, live queue or frozen source changed. [Evidence and exact proposed paths](notes/2026-10-18-own-runtime-packet94.md).

**October 18, packet93 packed-head choices sealed on CPU:** Two new unpack paths keep the production arithmetic: one decodes words together, the other rearranges the same packed bytes for direct lane reads. Both compilers, all six full-size startup and memory checks, 102 Python tests, three seals and five temporary queue plans pass. The coordinator starts with the proposed single-card lane-B microbenchmark; only a candidate cutting kernel time by at least 15% may enter either matched screen direction. Production stays selected. No GPU, service, live queue or frozen source changed. Device quality and speed remain pending. [Evidence and handoff](notes/2026-10-18-own-runtime-packet93.md).

**October 18, packet92 reply-first prepared on CPU:** Rank1 can send its verified reply and accept before formatting the prior half's report. Reporting then runs after the next draft is submitted, and a failure stops the next half. Kernels, result waits and error checks stay unchanged. Both compiler mock gates, repeated miniature byte checks, four full-size startup checks and 87 Python checks pass. Two views are sealed; both queue directions pass temporary planning. Build scratch is under 139 MB and root has over 17.5 GiB free. No GPU, service, live queue or frozen source changed. The coordinator next runs a matched device screen; savings remain unknown. [Evidence and handoff](notes/2026-10-18-own-runtime-packet92.md).

**October 18, packet90 expert and HC candidates sealed on CPU:** Two new paths decode fixed weight values once at load while keeping the ordered arithmetic. Production and both candidates match bytes under GNU and Intel twice. All six full-size startup and memory checks pass; malformed allocations and unsupported modes are refused. Three view seals and all four proposed lane queues pass CPU planning. The build stayed below 146 MB before fixture cleanup. No GPU, service, live queue or frozen source changed. Either lane can now run the grid: the new B-grid proposal lets B run first, then A confirms only the same exact improving winner with unchanged acceptance counts. A-grid remains the default. All 90 Python checks pass; binaries are unchanged. Device correctness and speed remain pending. [Direction options and proposed files](experiments/own-xpu-runtime/stage2/packet90-expert-hc/WINDOW.md). [Original evidence](notes/2026-10-18-own-runtime-packet90.md).

**October 18, packet91 sealed on CPU:** The new bundle starts from packet84's chained selection and tests faster routing, the new recurrence choice, and both together. It reuses the two existing binaries by hash; no compiler ran. All eight full-size startup checks, 172 Python tests plus 12 subtests, five complete selection rehearsals, chain/storage checks and thirteen temporary queue plans pass. The baseline is restored. Readiness remains false until packet91's own matched screens finish on both lanes. The running packet84 tree and live queue were untouched; no GPU or service ran. The coordinator next runs the proposed A grid and B confirmation or full grid. [Evidence and exact job paths](notes/2026-10-18-own-runtime-packet91.md).

**October 18, packet58g one-card repair sealed on CPU:** Layer 2 passed an 8 KB expert-pointer table to a kernel expecting a 360 MB weight bank. The new path reads those pointers with unchanged arithmetic. The full-size CPU test reproduces the old refusal and passes all 1,486 sites; K1 keeps its exact hash, reset checks and 98 Python tests pass. A clean refusal before compute releases its own drain and lane lease while stopping the chain. W windows now use lane-A cores at normal priority. Both builds and seals pass; build scratch is 159 MB. No GPU, service or frozen tree changed. The coordinator next starts a fresh chain at K1a; actual device exactness and speed remain pending. [Evidence and launch command](notes/2026-10-18-own-runtime-packet58g.md).

**October 18, packet82b recurrence round 2 prepared on CPU:** The gate split was already included in parallel recurrence, so their combined view is an identical control. A new view removes one preparation barrier while keeping the arithmetic loop unchanged. Both compilers pass the complete state/output checks twice; all six full-size startup checks, 87 Python checks and three seals pass. Both lanes have full-grid and opposite-lane confirmation proposals checked on temporary queues. No GPU, service, live queue or frozen source changed. The coordinator next screens the new view against the packet84 composition; device correctness and speed remain pending. [Evidence and handoff](notes/2026-10-18-own-runtime-packet82b.md).

**October 18, packet88 miss-path attribution closed on CPU:** Rollback already overlaps drafting, and correction cannot reuse the wrong token's layer results. The raw receipts confirm 12.655 ms for correction and 0.569 ms for rollback. Each restore copies 19.03 MB after the existing spare-bank omission; its separate device time was not captured. No new lossless mechanism justified a build, so no screen or queue job was added. The next useful evidence is a separate restore timing or a complete state-preservation proof. No GPU, service or frozen tree changed. [Attribution and closeout](experiments/own-xpu-runtime/stage2/packet88-miss-path/MISS.md).

**October 17, packet84 composition screen prepared on CPU:** Lane B has four proposed jobs: the pinned packet80 control, parallel recurrence, parallel recurrence plus fast routing, then the control again. All three sealed views share packet84's unchanged binary. Both ranks pass full-size startup, all four temporary queue plans pass, and comparison checks pass. The live queue and running chains were untouched; no GPU or service ran. The coordinator runs the proposed jobs before considering a packet84 record chain. Actual output checks, acceptance and speed remain pending. [Jobs, evidence and comparison](experiments/own-xpu-runtime/stage2/packet84-screens/README.md).

**October 18, packet86 diagnostic prepared on CPU:** Eight views can test the cost of expert decoding, grid lookups, repeated expert reads and HC scaling. They deliberately change outputs and can never enter a bundle, chain or headline. Production matches packet75; both compiler checks and all sixteen full-size startup/admission checks pass. Both lanes have proposed jobs checked on temporary queues. No GPU, service or live queue ran. Actual costs and lossless savings remain unmeasured. The coordinator next runs the lane-B diagnostic after normal admission. [Evidence and handoff](notes/2026-10-18-own-runtime-packet86.md).

**October 17, packet83 sealed on CPU:** The draft head can use a separate four-bit copy or two smaller prefixes chosen from independent text. Target bytes stay equal to packet75 in fresh CPU runs. Both compilers agree on every real prefix row, all eight full-size startup checks pass, and rank1 has about799MB left under its unchanged arena limit. Both lanes have full-grid proposals; the other lane confirms the exact improving winner between controls. All seals and temporary queue plans pass. No GPU, service or live queue ran. Actual acceptance and speed remain pending. [Evidence and handoff](notes/2026-10-17-own-runtime-packet83.md).

**October 17, packet82 sealed on CPU:** Two recurrence choices share independent gate and normalization work across waiting subgroups. Both compilers match every candidate state/output byte to production over consecutive tokens; existing GNU/Intel NaN payload differences are recorded separately. All six full-size startup checks, 85 Python checks, three seals and temporary queue plans pass. No GPU, service or live queue ran. The coordinator next screens A, then its exact improving winner on B. Device correctness and speed remain pending. [Analysis and evidence](notes/2026-10-17-own-runtime-packet82.md).

**October 17, packet81 sealed on CPU:** Three expert choices read the same activation bits with fewer load instructions. Both compilers pass every byte check twice, and all eight full-size startup checks reach their intended kernels. Four seals, all lane plans and both temporary queue plans pass. Memory limits and arithmetic are unchanged. No GPU, service or live queue ran. The coordinator next screens lane A, then its exact improving winner on B; actual speed and model-output checks remain pending. [Analysis, evidence and proposed jobs](notes/2026-10-17-own-runtime-packet81.md).

**October 17, packet58f sealed on CPU:** The one-card child now filters discovery to card 0 before opening a device. The lane-A lease stays in place. A refusal before launch no longer leaves a shared teardown record; a clean K1 exit releases it before CPU report checks. All 81 Python checks, both builds, full post-load setup and the fresh card-0 plan pass. Memory budgets and arithmetic are unchanged. No GPU or service ran during preparation. The coordinator starts at K1a in a fresh 58f chain; actual device isolation, exactness and speed remain pending. [Evidence and commands](notes/2026-10-17-own-runtime-packet58f.md).

**October 17, packet79 sealed on CPU:** The record-line draft can now use the first card with only its 91,392-row head prefix, at 23/25 or24/24 target layers. Both fit the unchanged memory limits in the complete post-load mock. Target and draft bytes match packet75 in miniature runs; both compilers, reverse-handoff tests,75 Python tests and both temporary queue plans pass. Six views share one binary, including hc-wide. No GPU or service ran. The coordinator screens A, then its exact improving winner between B controls. Real output checks, acceptance and speed remain pending; the estimated 5% is not a measurement. [Evidence and proposed jobs](notes/2026-10-17-own-runtime-packet79.md).

**October 17, packet78 sealed on CPU:** Five choices can test a faster expert
sort and smaller HC norms on the record configuration, including the wider HC
gate. Both compilers pass every byte check twice. Full-size startup passes on
both ranks, and captured operations confirm each choice reaches its intended
kernel. Seals, worker imports, lane admission and temporary queue plans pass.
No GPU or service ran. The coordinator screens lane A, then its exact improving
winner between fresh lane-B controls; device correctness and speed remain
pending. [Evidence and proposed jobs](notes/2026-10-17-own-runtime-packet78.md).

**October 17, packet58e prepared on CPU:** The one-card chain now uses 90-second gaps. Its exactness windows can share the host with lane-B screens when 85.57 GB is available; the 8 GiB live reserve and full cache/KV budgets remain. Card 0 holds lane A. Timing still holds both lanes and requires 118.31 GB. Both builds, the full post-load setup, all 70 Python checks and the card-0 plan pass. No GPU or service ran. The coordinator starts a fresh chain at K1a; complete device memory, exactness and speed remain pending. [Evidence and commands](notes/2026-10-17-own-runtime-packet58e.md).

**October 17, packet71c sealed on CPU:** The depth-two screen's router refused
its grouped configuration in 71b. The new candidate separates those projections
while keeping their arithmetic; production and controls are unchanged. Both
compilers pass all byte checks. Full-size native startup and two-row setup now
run on CPU for every plan, and reproduce the old refusal as a regression check.
Seals and all four temporary queue plans pass. No GPU or service ran. The
coordinator next runs smoke, then control/candidate/control; device correctness
and speed remain pending. [Evidence and proposed jobs](notes/2026-10-17-own-runtime-packet71c.md).

**October 17, packet77 prepared on CPU:** A new lane-B screen can measure where
time goes in packet70's wide64 record selection. It compares observation off
and on in one load, then reports both cards' class costs and the second card's
head, final norm, argmax and remaining time. Both builds, full-shape allocation,
real admission, 80 Python checks and temporary queue planning pass. The shared
v4 wrapper is unchanged. No GPU or service ran; current costs and lever ranking
await the coordinator's screen. [Evidence and proposed job](notes/2026-10-17-own-runtime-packet77.md).

**October 17, packet58d sealed on CPU:** The one-card engine loaded all 48 layers in 58c, then stopped because two pinned copy slabs requested the wrong lifetime. The new packet fixes both callers and keeps the strict check. Errors now identify the allocation. A CPU mock passes the complete post-load setup; both builds, 59 Python checks, K1 byte checks and request resets pass. The seal and card-0 queue plan pass. No GPU or service ran during preparation. The coordinator reviews the retained lineage stops and starts the fresh chain at K1a; device correctness and speed remain pending. [Task note and command](notes/2026-10-17-own-runtime-packet58d.md).

**October 17, packet76 sealed on CPU:** Most of rank1's reported 1.61 ms
residual is host housekeeping, including substantial measurement overhead.
Two sealed choices can test cheaper event cleanup with unchanged kernels.
Both builds, mock byte checks, full-shape post-load allocations, all 76 Python
checks and both temporary queue plans pass. The original pinned shared v4
wrapper uses 23/25 for both controls and candidate. The coordinator runs lane A,
then its exact improving winner on B. No GPU, model or service ran; speed and
device exactness remain unmeasured. [Evidence and jobs](notes/2026-10-17-own-runtime-packet76.md).

**October 17, packet58c prepared on CPU:** The one-card wrapper now counts completed pinned experts separately from remaining GPUActive growth. It keeps the same host admission, reserve and safety stops, and checks the combined memory total. All 57 CPU checks pass; native sources and binaries are unchanged. The old evidence fits the double-counting explanation but lacks the failing sample, so the new wrapper saves every sample. No GPU or service ran. The coordinator reviews the retained 58b latch, then starts the fresh card-0 chain at K1a; existing rules forbid reusing K1 across the new seal. [Task note and command](notes/2026-10-17-own-runtime-packet58c.md).

**October 17, packet73 sealed on CPU:** Five choices now share one engine: packet70 production, shared-load HC, two expert follow-ups, and HC with the smaller IQ4 span. Both compilers agree on every operator byte check; accepted kernels have no offline spills. The private v4 wrapper passes 82 mock checks, all lane plans pass, and queue proposals were checked in a temporary copy. No GPU or model ran. The coordinator can screen lane A, then test its exact improving winner between fresh lane-B controls. [Task note and commands](notes/2026-10-17-own-runtime-packet73.md).

**October 17, packet74 prepared on CPU:** Four sealed choices can test packed dense weights while keeping the same target arithmetic. Both compilers pass the byte checks; the engine and microbenchmark build. All screen and private queue plans pass. The combined choice saves about 662 MB on the first card and 682 MB on the second by calculation, including an unchanged expanded draft prefix. Fused HC and small-FFN groups stay on their existing paths. No GPU or model ran. The coordinator owns the exactness and speed screens; actual peak memory and speed are unmeasured. [Evidence and next steps](notes/2026-10-17-own-runtime-packet74.md).

**October 17, packet71b prepared on CPU:** Packet71's screen import failure is repaired in a new copy. Plans now import the real worker in its closed launch environment. Both HC gates, router and route have two-row implementations that keep each row's arithmetic. Both compilers pass 2,728 byte checks; builds and eleven wrapper/import tests pass. Both selections are sealed, and all four proposed lane-B jobs pass queue planning. No GPU or CPU model ran. The coordinator next runs smoke, then control/candidate/control; device correctness and speed remain pending. [Evidence and jobs](notes/2026-10-17-own-runtime-packet71b.md).

**October 17, packet72 prepared on CPU:** The bandwidth check rules out new QKV, Z and Q-gate work under the requested size threshold. Attention output narrowly qualifies on the second rank. Its candidate shares raw loads and keeps the same arithmetic. Both compiler byte checks and engine builds pass; the offline compiler emits fewer loads. Three views share one binary. The private v4 screen passes 79 mock checks and releases the lane before reporting. Lane A gets the full grid; lane B is limited to an exact improving candidate between two controls. No GPU or model ran. [Evidence and next steps](notes/2026-10-17-own-runtime-packet72.md).

**October 17, packet71 ready for the coordinator's device screen:** The two-row engine now overlaps the next pair on the first card with verification on the second. Copied packet68c kernels are selectable by class; unsupported shapes retain the original kernels. Both the batched and all-serial settings are sealed. Small CPU fixtures pass every acceptance case, 1,854 state comparisons, state metadata and draft-cache checks. Operator bytes agree under both compilers. Lane-B smoke and matched quick jobs are prepared; full-model correctness and speed still need those device runs. No GPU or service ran during preparation. [Task note](notes/2026-10-17-own-runtime-packet71.md).

**October 17, packet68c CPU preparation complete:** The coordinator has a sealed lane-B two-row probe built from the tuned production dense kernels and packet65's wide64 experts. Both compilers pass 1,428 byte checks and the device program builds. The probe adds consecutive real inputs with different expert routes and keeps all thirteen packet49 output checks. The main costly classes are batched; router and HC remain explicitly serial. No GPU or model ran here. Device speed and row/state identity remain pending; the prepared analyzer includes packet68's measured restore cost. [Task note and commands](notes/2026-10-17-own-runtime-packet68c.md).

**October 17, packet69 CPU preparation complete:** The coordinator has a sealed lane-B screen to measure rank 1’s target head, final norm and argmax, plus seven candidate views and two fixed quick jobs. The draft prefix already reads about 561 GB/s using its actual expanded bytes; the old packed-byte estimate understated that. Both compiler byte checks, draft repeats, selection checks and all sixteen quick plans pass. Both wrappers release drained lanes before CPU reporting. No GPU or model ran; device timings, output checks and draft acceptance remain pending. [Task note and commands](notes/2026-10-17-own-runtime-packet69.md).

**October 17, packet70 prepared on CPU:** The next record bundle reuses packet65's binary with packet64's selected draft-HC, batch-copy and 24/24 settings. Every chain gap is 90 seconds. Its private screen releases both lane locks after drain and postflight, before reporting; report errors no longer leave a device-fault latch. Seal, plans, input/storage checks and mock tests pass. No model, GPU or service ran. Production experts stay selected while both packet65 screen lanes finish; readiness is explicitly pending. The helper will choose only an exact expert that wins on both lanes, check the packet and print the chain command. The coordinator launches it. [Task note and evidence](notes/2026-10-17-own-runtime-packet70.md).

**October 17, packet65 quick lane screens prepared on CPU:** Two fixed six-screen jobs can test the four expert choices on both card pairs at once, with fresh production controls on each lane. Each screen holds only its own lane lease and keeps all 13 exact checks, fault checks and shared drain spacing. The original packet65 binary and selection seals are unchanged; this task did not edit the frozen running trees. CPU seal checks, all twelve plans and mock runs pass; no GPU or service ran. The coordinator owns the next launch; device speed is still unmeasured. [Commands, jobs and comparison](experiments/own-xpu-runtime/stage2/packet65-expert-occupancy/screen/quick/README.md).

**October 17, packet64 orchestration prepared on CPU:** The coordinator now has a single script to wait for both screen lanes, choose only an exact option that wins on both lanes, reseal it and start the full chain. Two extra lane-B screens use the existing timing holds and drain checks. Mock orchestration and CPU protocol tests pass; no GPU or service was started, and the frozen trees were untouched. The coordinator owns the next launch. [Command, selection rule and tests](experiments/own-xpu-runtime/ops/packet64-orchestration/README.md).

**October 17, packet64 record bundle prepared on CPU:** One binary now has eight sealed choices: 24/24 or 23/25 target layers, production or draft-HC kernels, and ordinary or batched rollback copies. The prepared default is 24/24 with production draft and ordinary copies; the coordinator can change it in about 1.3 seconds after screening. Target fixtures match packet56, draft repeats pass, both memory placements pass, and all 32 screen plans pass. The complete chain checks 12,001 input paths and 352 write/scratch paths for each placement. It includes the repaired KD scratch and early-receipt resume, plus lane-aware admission that holds the whole host only during speed windows. The build stays below 400 MB. No GPU or service ran; existing jobs remain with the coordinator. Next are final screen selection and the sealed K0..WS128 chain. [Task note and commands](notes/2026-10-17-own-runtime-packet64.md).

**October 17, lane-aware chain admission prepared on CPU:** Future chain wrappers can keep cards 0+1 while a masked screen uses cards 2+3 for exactness work. WS128, WSs and W2m still hold the whole host until their owners exit and postflight passes. The reusable code, chain patch and companion B-screen patch pass 55 CPU tests. Existing packets and running jobs were not changed by this preparation. Both sides need fresh seals before the coordinator tests device overlap; the current memory floors, watchdogs and shared drain spacing remain. [Protocol, adoption steps and evidence](notes/2026-10-17-own-runtime-lane-aware-chain.md).

**October 17, packet63 CPU preparation complete:** The draft HC group is built
on packet61x, with sealed control and candidate selections sharing one binary.
Both pass the target fixture and draft repeat checks; all four screen plans
pass. The proposed 22/26 split is skipped: current screens put rank1 last in
every complete cycle, with its target half already longer than rank0. No GPU
or service ran, and packet61x's record chain was untouched. Next is the
coordinator's matched screen; device quality and speed remain unmeasured.
[Task note, measured halves and exact commands](notes/2026-10-17-own-runtime-packet63.md).

**October 17, packet61x placement plans prepared (CPU only):** All four requested placements fit their own memory plans. The control and draft-on-rank-1 24/24 split are supported on both lanes. Both rank-0 draft options are blocked by the sealed engine's missing resident output head, so they refuse before launch. All eight plan checks and 32 CPU tests give the expected results. No GPU or service ran; the running packet61x chain and sealed packets were untouched. Next is the coordinator's supported placement comparison, with the same 13 exact requests. [Job lines, reasons and evidence](experiments/own-xpu-runtime/stage2/screen/v3/PLACEMENT-CLOSEOUT.md).

**October 17, packet61 full-chain input repair complete (CPU only):** The K1 failure came from missing archived fixture files. All 72 fixtures and their list are restored with original hashes; packet61x and packet56w have the same repair. All eleven windows now check their nested inputs before any device launch. The three input checks, storage checks and 111 focused tests pass. Packet61 uses fresh `device-cards01-b`; the failed `device-cards01-a` and STOP remain unchanged. Engine binaries and screen seals are unchanged. No GPU or service ran. The coordinator owns the next chain and device quality is still pending. [Exact commands and evidence](experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion/INPUT-REPAIR-CLOSEOUT.md).

**October 17, packet61x CPU preparation complete:** The separate candidate combines packet61’s unchanged HC kernels with packet56x’s pure-spin waits on every covered path. The embedded kernel bytes match packet61 exactly. Controller, wait, target-fixture and chain/submission checks pass, as do v3 plans for both card pairs and full-chain admission. No GPU or service ran. Next is the coordinator’s v3 screen and fresh full chain; speed and device quality remain unmeasured. [Task note and exact commands](notes/2026-10-17-own-runtime-packet61.md#packet61x--pure-spin-waits-october-17-cpu-preparation).

**October 17, packet 58b CPU repair complete:** Packet58's first one-card K1 stopped before allocating fixture weights: the Intel adapter rejected its copy-queue handle. The separate 58b packet uses the supported immediate command-list handle on the same copy engine. Arithmetic, packed weights and cache behavior are unchanged. Both builds, the changed-path CPU check and cache/expert byte checks pass; the production CPU fixture matches packet58's exact output hash. The build is 148.3 MB. No GPU or service ran in this repair. The coordinator can next run the same K1a → K1b → KD → W2m → three-suite chain with fresh admission; device acceptance remains pending. [Task note](notes/2026-10-17-own-runtime-packet58.md#packet-58b--repair-k1-startup-october-17-cpu-only), [exact command](experiments/own-xpu-runtime/stage2/packet58b-onecard/WINDOW.md), [CPU closeout](experiments/own-xpu-runtime/stage2/packet58b-onecard/CPU-PREPARATION-CLOSEOUT.md).

**October 17, packet 59 CPU preparation complete:** The faster draft candidate is built and sealed for the coordinator's screen. The target source, arithmetic and packet49 oracle stay unchanged; the draft keeps its 91,392-row head. Faster draft schedules and ten fusions pass the small CPU checks: target bytes match packet56 and two fresh draft runs agree. Both builds and screen plan admission pass. The build is 53.22 MB. No GPU, service, model load or host-setting change ran here; packet58 and the screen tree were left alone. Expected draft savings are about 0.38–0.40 ms, not a measured result. Next is the coordinator's one-load screen after the host is free; all twelve exact prompts and more than 46.962697 class-balanced tok/s are required before a full chain. [Task record](notes/2026-10-17-own-runtime-packet59.md), [CPU closeout](experiments/own-xpu-runtime/stage2/packet59-fast-draft/CPU-PREPARATION-CLOSEOUT.md), [screen command](experiments/own-xpu-runtime/stage2/packet59-fast-draft/WINDOW.md).

**October 17, screen wrapper prepared on CPU:** A new diagnostic wrapper reuses the sealed two-card packet 56 and one-card packet 58 engines. The two-card path loads once, checks 64 incident tokens, runs all twelve 128-token prompts and tears down once. Packet 58's sealed interface requires an explicit first-response prefix option for the 64-token check; it cannot accept a separate thirteenth request. Every suite token is checked against packet 49. No GPU or service ran; packet 57 and packet 58's chain retain coordinator ownership. The two-card planning estimate is 7–8 minutes including load, still unmeasured as a screen. The lean experiment path is build, one changed-class CPU byte check, seal, then coordinator screen. A record still needs its full sealed chain. [Task note](notes/2026-10-17-own-runtime-screen-window.md), [commands and checks](experiments/own-xpu-runtime/stage2/screen/README.md).

**October 17, packet 58 CPU preparation complete:** The separate one-card IQ3 engine is built and sealed. It keeps all target layers on one card, uses an 18 GB cache for expert weights, and can read missing weights from pinned host memory or copy them before use. CPU byte comparisons, lifetime checks, request resets, sanitizer runs and all 44 wrapper/evidence checks pass. The build occupies 147 MB. The conservative plan requires 118.31 GB of available host RAM, including the possible GPU allocation shadow and an 8 GiB reserve; the passive snapshot had only 1.95 GB extra, so the optional draft is deferred. No GPU window, large pin, model payload read or host-setting change ran here; device ownership stays with the coordinator and packet 57 is untouched. Next is the coordinator's one-card K1 → KD/W2m → three-suite chain, after fresh admission: about 107 minutes planned including cooldowns. One-card exactness and speed remain unmeasured. [Task record](notes/2026-10-17-own-runtime-packet58.md), [CPU closeout](experiments/own-xpu-runtime/stage2/packet58-onecard/CPU-PREPARATION-CLOSEOUT.md), [exact commands and durations](experiments/own-xpu-runtime/stage2/packet58-onecard/WINDOW.md).

**October 17, packet 57 CPU preparation complete:** The timing tools are built and sealed. Packet 56's saved traces show rank 0 finishing last in 93% of complete cycles; moving a whole layer does not look useful under the available average-cost estimates. The draft still takes about 1.90 ms, but its individual kernel costs remain unmeasured. Four fresh small CPU runs match the old engine exactly, all 19 focused checks pass, and both builds and the final seal pass. The retained build is about 336 MB. No GPU window ran and packet 55's work was left alone. Next is the coordinator's diagnostic run on cards 0+1, after the host is free: about 88 minutes planned, comparing ordinary timing with the new event recording against the same packet 49 answers. This is not a new speed result. [Task record](notes/2026-10-17-own-runtime-packet57.md), [timeline](experiments/own-xpu-runtime/stage2/packet57-attribution/TIMELINE.md), [exact command](experiments/own-xpu-runtime/stage2/packet57-attribution/WINDOW.md).

**October 18, 23:10 UTC — 1-card IQ3 record 30.40 tok/s on one Arc Pro B70, submitted and approved (`cmvefq3ep009orf0186k21lba`).** Packet58ad = the packet58z line plus packet60's exact three-stage HC fusion ported to one card (packet58ab); all 12 prompts exact (+3.88% over 29.26). Bracket: p60fusion 30.52/30.55 vs production 29.57/29.48 (+3.21%). Chain ran in the same hold as the bracket via the generic waiter. Ledger: `results/localmaxxing-submissions.md`.

**October 18, 21:20 UTC — 1-card IQ3 record 29.26 tok/s on one Arc Pro B70, submitted and approved (`cmvebtu5f009frf01gsnfi2eh`).** Packet58z = the packet58w line (tile16 + overlapped cache maintenance) with packet58x's 21.55 GB admitted device expert cache; all 12 prompts exact (+4.34% over 28.04). Bracket: max cache 29.57/29.36 vs warm 18 GB 28.16/28.20 (+4.13%). Chain 20:52–21:16 UTC (one pre-device refusal from a coordinator waiter filename slip; relaunched). Submission via `ops/packet58zs-submission/submit58z.py` (fixes only the vendored CLI's REPO_ROOT; sealed tree untouched). Ledger: `results/localmaxxing-submissions.md`.

**October 18, 19:12 UTC — 1-card IQ3 record 28.04 tok/s on one Arc Pro B70, submitted and approved (`cmve789qr008vrf01pm678ee8`).** Packet58w = packet58p tile16 line + packet58v overlapped expert-cache maintenance (fills on the copy engine during the next position); all 12 prompts exact (+6.92% over 26.23). Bracket: overlap 28.12/28.15 vs warm serial 26.05/26.08 (cold-cache first view excluded by a disclosed pre-chain amendment). Chain a (WS128 25.77 under concurrent Codex GGUF reads) was not submitted; one preregistered quiet-host rerun (chain b, Codex frozen) gave WS128 28.04 / WS128x 28.20. Ledger: `results/localmaxxing-submissions.md`.

**October 18, 17:50 UTC — 2-card IQ3 record 58.80 tok/s, submitted and approved (`cmve4dtir007wrf01k57sdf23`).** Bundle 8 (packet 136) = bundle 7 + packet 131b banked rollback state (rotating snapshot banks remove ~61% of rank 0's per-cycle snapshot bytes); all 12 prompts exact (+0.99% over 58.22). Screens: lane B +0.81% strict (drift 0.11%), lane A confirm 58.33 → 58.81. Chain `packet136-chain-a` 16:55–17:42 UTC, all windows passed, fault count unchanged. Submission evidence prepared with the packet 136s tool copy (fixes only the oracle-checker binding lookup; sealed tree untouched). Ledger: `results/localmaxxing-submissions.md`.

**October 18, 14:30 UTC — 2-card IQ3 record 58.22 tok/s, submitted and approved (`cmvdx8urg0068rf01vvb32bcs`).** Bundle 7 (packet 124c) = packet 103 + packet 109 exact fusion + packet 105b exact head split + packet 114 preregistered draft prefix 80,128; all 12 prompts exact (+1.17% over 57.55). Two earlier chain attempts died on host-side packaging (K2 selection keys; flattened oracle symlink), both fixed and now covered by an all-window argument and queue gate. Next: packet 130 (rank 1 waits 1.2–1.6 ms per hit for rank 0's head suffix; compute it at the first layer boundary), packet 131 (0.52 ms per-cycle rollback snapshot; double-buffered state), packet 132 (two-candidate speculation study).

**October 18, 13:16 UTC — 1-card IQ3 record 26.23 tok/s on one Arc Pro B70, submitted and approved (`cmvdukc200064rf01lqsql9x8`).** Packet 58p = packet 58g one-card engine + lossless down-weight tile16 layout; all 12 prompts exact (+7.8% over 24.339). Screen (packet 58n): tile16-only 26.27 vs production 21.0/21.3; WS128 ran with 0 major page faults per token. Next one-card: packet 58r one-load bracket (route-fast, rec-both-plus on tile16) and packet 58t (resident per-token lookups), in one whole-host hold.

**October 18, 10:57 UTC — 2-card IQ3 record 57.55 tok/s, submitted and approved (`cmvdpmbbo0022rf017ynt8i35`).** Bundle 5 (packet 103) = packet 97 + packet 100 down-tile16 + packet 101 split32 draft attention; all 12 prompts exact (+2.61% over 56.087; composites +3.2% lane A, +2.8% lane B). The first chain folder died at WS admission on a drain-cooldown race (negative sleep after a cross-lane teardown, no device work); the fresh folder `device-cards01-b` ran with lane B paused and passed all 11 windows. Next: bundle 7 (packet 118 = + packet 109 fusion + packet 105b head split + packet 114 draft prefix 80,128; lane-B bundle-6 composite +0.96%), packets 116/117/119 micros, packet 120 25/23 grid; Codex packets 121 (miss path) and 122 (draft path).

**October 18, 06:44 UTC — 2-card IQ3 record 56.09 tok/s, submitted and approved (`cmvdgjqwj000rrf013ay3ew6t`).** Packet 97 = packet 84 + route-fast + rec-both-plus + E1 half-scale expert cache, all 12 prompts exact (+0.72% over 55.687). Next bundle (packet 103): adds packet 100 down-tile16 (lane A +2.09%, lane B +1.68%) and packet 101 draft attention (+0.28% / +0.34%); packet 105's target-head split is ready for a device smoke. [Ledger](results/localmaxxing-submissions.md).

**October 18, 02:55 UTC — first one-card IQ3 result: 24.34 tok/s on one Arc Pro B70, submitted and approved (`cmvd8bhou000duj01hxaihg15`).** Packet 58g runs all 48 target layers on card 0 with 48.6 GB of experts pinned in host memory and an 18 GB device expert cache; target-only (no draft); all 12 prompts exact against the packet 49 oracle. It is the first 1x Arc Pro B70 entry for this model on the public list (other single-GPU hardware is faster). Next one-card step: the MTP draft (packet 58h). [Ledger](results/localmaxxing-submissions.md).

**October 18, 02:23 UTC — 2-card IQ3 record 55.69 tok/s, submitted and approved (`cmvd78ela0007uj01k1ojlm8g`).** Packet 84 is packet 80 plus packet 82's `rec-parallel` GDN recurrence preparation (exact), confirmed on both lanes and in a lane-B composition screen (+0.93%). All 12 prompts exact against the packet 49 oracle. WS128 measured 55.686963 class-balanced (+0.90% over 55.189917; all-prompt 55.812). Queued next: packet 90 (exact expert half-scale cache, HC weight cache), packet 91 (route-fast + rec-both-plus in the record lineage), packet 92 (rank-1 reply-first), packet 94 (HC norm fused into its consumer), packet 93 (packed head, new unpack), packet 95 (expert grid-prefetch/scale-cache), and the one-card packet 58g. [Ledger](results/localmaxxing-submissions.md), [p84s screen](notes/2026-10-18-own-runtime-packet84s-result.md).

**October 18, 00:57 UTC — 2-card IQ3 record 55.19 tok/s, submitted and approved (`cmvd48tdv083ale01clv86fbd`).** Packet 80 is packet 70 plus hc-wide HC-gate kernels and ordered rank-1 event retirement, both confirmed on both lanes (route/norm pinned to production). All 12 prompts exact against the packet 49 oracle. WS128 measured 55.189917 class-balanced (+1.90% over 54.162022); hit/miss 15.79/27.14 ms, acceptance 0.787. Closed tonight:
- depth-2 MTP: −47%;
- draft on rank 0: −1.3% / −2.3%;
- packed dense: −0.8% to −2.9%;
- draft bytes: −0.3% to −0.8%;
- expert load-count: neutral;
- miss path: no lossless saving.
Next: packet 84 (+ rec-parallel, confirmed +0.99%/+0.67%); packet 86 limiter diagnostic for experts and HC; packet 82b recurrence round 2; 58f one-card. [Result packet](experiments/own-xpu-runtime/stage2/packet80-record-bundle/submission/prepared/result-packet.md).

**October 17, 20:35 UTC — 2-card IQ3 record 54.16 tok/s, submitted and approved (`cmvcuvh4q080wle01pgjwixvj`).** Packet 70 is packet 64 plus packet 65 `wide64` routed-expert kernels (exact order; screens +5.4%/+4.8% on both lanes). All 12 prompts exact against the packet 49 oracle. WS128 measured 54.162022 class-balanced (+2.39% over 52.899081); hit/miss 16.09/27.57 ms, acceptance 0.787; 90 s chain gaps. The first attempt stopped at K2 on a CPU-side validator (fixed, fresh chain). Today: 39.42 → 45.70 → 46.00 → 46.96 → 51.03 → 52.90 → 54.16. Next:
- packet 74 packed-format dense weights (the target head reads 795 MB of expanded Q6_K at 566 GB/s);
- packet 73 HC gates + experts round 2;
- packet 71b depth-2 (marginal: H(2)/H(1) 1.66–1.74);
- packet 69/72 screens;
- packet 58b one-card slot at 21:55 UTC.
[Result packet](experiments/own-xpu-runtime/stage2/packet70-record-bundle/submission/prepared/result-packet.md).

**October 17, 18:47 UTC — 2-card IQ3 record 52.90 tok/s, submitted and approved (`cmvcr0nee07wele01ypyng2nz`).** Packet 64 is packet 61x plus packet 63 draft-HC kernels, packet 62 batched rollback copies and balanced 24/24 placement, selected by the preregistered both-lanes screen rule. All 12 prompts are exact against the packet 49 oracle. WS128 measured 52.899081 class-balanced (+3.66% over 51.033041); hit/miss 16.45/28.37 ms, acceptance 0.787. Today: 39.42 → 45.70 → 46.00 → 46.96 → 51.03 → 52.90. Next:
- packet 65 `wide64` expert kernel (+4.8% on lane B screens; lane A pending), then the packet 70 bundle with 90 s chain gaps;
- packet 67 roofline kernels and packet 69 rank-1 head candidates (screens queued);
- packet 68b batched two-row probe (decides the depth-2 engine).
[Result packet](experiments/own-xpu-runtime/stage2/packet64-record-bundle/submission/prepared-v2/result-packet.md).

**October 17, 17:25 UTC — 2-card IQ3 record 51.03 tok/s, submitted and approved (`cmvco3d6606u1le01941ek8hq`).** Packet 61x is packet 56 plus controller pure-spin waits and packet 60 exact-order HC fusion. All 12 prompts are exact against the packet 49 oracle. WS128 measured 51.033041 class-balanced (+8.67% over 46.962697); hit/miss 17.24/28.48 ms (from 18.22/33.04), acceptance 0.787. The chain was resumed after a wrapper KD scratch-path fix; the five early receipts were imported under hash pins and every exactness/headline window ran fresh (disclosed). Today's progression: 39.42 → 45.70 → 46.00 → 46.96 → 51.03. Next: packet 64 selection screens (draft-HC batch, balance) on both lanes, packet 65 expert occupancy, packet 58b one-card. [Result packet](experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait/submission/prepared/result-packet.md).

**October 17, 13:22 UTC — 2-card IQ3 record 46.96 tok/s, submitted and approved (`cmvcf84kb06r2le0174bgk16l`).** Packet 56 is packet 49d plus a draft-head vocabulary prefix: the MTP draft proposes from head rows [0, 91,392), with N preregistered from independent text, and the target verifies with the full head. All 12 prompts are exact against the same packet 49 oracle. WS128 measured 46.962697 class-balanced (+2.08% over 49d's 46.0038); the hit cycle went from 19.02 to 18.22 ms and acceptance from 0.791 to 0.787. Today's progression: 39.42 → 45.70 (49c) → 46.00 (49d) → 46.96 (56). Next: packet 55's one-card feasibility windows (CPU expert throughput, H2D streaming, route locality). [Result packet](experiments/own-xpu-runtime/stage2/packet56-draft-prefix/submission/prepared/result-packet.md).

**October 17, 12:10 UTC — 2-card IQ3 record 46.00 tok/s, submitted and approved (`cmvcconpv06o9le01nnxeuwpi`).** Packet 49d is packet 49c plus exact-order expert virtual-lane, small-FFN, route and recurrence kernels, with the same oracle. All 12 prompts are exact. WS128 measured 46.003849 class-balanced (+0.67% over 49c's 45.6955); the hit cycle went from 19.16 to 19.02 ms. Only about 20% of the micro-benchmark savings transferred to the engine, so kernel micro-benchmarks need production-context confirmation before they are ranked. Next: packet 56, a draft-head vocabulary prefix N=91,392 that shrinks the serial draft step (projected about +3%; chain running), then packet 55's one-card feasibility windows. [Result packet](experiments/own-xpu-runtime/stage2/packet49d-round3/submission/prepared/result-packet.md).

**October 17, packet56 CPU preparation complete:** The draft now proposes tokens from the first 91,392 vocabulary rows; the full target still verifies every token. The choice was fixed from independent local text, covering 99.512% of its tokens. Two fresh CPU runs match every retained logit byte and pass the proposal and ordinary-miss checks. Both builds, all 24 focused wrapper tests and the final CPU seal pass. The build is about 335 MB. The timing estimate suggests about 3% improvement, not a measured speed. No GPU, service, oracle or protected packet49d file was touched. Next are two coordinator-owned head tests on card 0, then the same full model chain against the existing packet49 oracle. [Task record](notes/2026-10-17-own-runtime-packet56.md), [exact commands](experiments/own-xpu-runtime/stage2/packet56-draft-prefix/WINDOW.md).

**October 17, packet55 CPU preparation complete:** The one-card IQ3 measurement tools are ready. Two fresh CPU expert checks agree byte for byte, and the route logger preserves the small CPU model’s outputs and state. Builds and offline accounting checks pass; the packet occupies about 72 MB. No GPU or throughput test ran, and packet49d remains untouched. Next are coordinator-owned route, quiet CPU and copy-speed windows. The route window still needs the owner’s allowance for packet49c’s existing draft weights outside the IQ3 directory. [Task record](notes/2026-10-17-own-runtime-packet55.md), [commands](experiments/own-xpu-runtime/stage2/packet55-feasibility/README.md), [decision formulas](experiments/own-xpu-runtime/ONE-CARD-FEASIBILITY.md).

**October 17, packet49d CPU preparation complete:** The separate engine includes the three banked exact winners and every eligible packet54 choice. All builds, CPU byte checks, sanitizer checks and 67 packet tests pass; the CPU seal verifies in 1.63 seconds. The retained build is 522 MB and the storage check has 3.93 GB of margin. The submitted-record floor is now 45.695513 tok/s, bound to the approved 49c receipt. Packet54's combined savings are 30.003/30.0015 microseconds, below this task's 40-microsecond requirement, so selection correctly refuses and no 49d device chain is admitted. A concurrent coordinator proposal to lower that threshold has not been applied here. No GPU, service, oracle or protected chain was touched by this preparation. [Task record](notes/2026-10-17-own-runtime-packet49d.md), [coordinator commands and admission outcome](experiments/own-xpu-runtime/stage2/packet49d-round3/WINDOW.md).

**October 17, 10:48 UTC — new 2-card IQ3 record, 45.70 tok/s (+15.9%), submitted and approved (`cmvc9xc0f06o0le01x7afsrcw`).** Packet 49c-round2 (our own Xe runtime) ran its full model chain on cards 0+1 after the new packet 49 CPU oracle finished at 10:06 UTC. KD passed. W2m matched 64/64 tokens with layer fixtures. WS, WSs and WS128x matched 12/12 prompts against the `iq3-p49-split32-v1` oracle. WS128 (128-token owner scope, 99 intervals) measured **45.695513 tok/s class-balanced, 45.622 all-prompt** (record before: 39.422009, `cmv9wjmtj013gle01v8k1yg4v`). Draft acceptance 0.791 is unchanged, so the gain is kernel time: hit/miss cycles 19.16/33.20 ms, against 22.20/38.72 for SPEED6. The kernels added since SPEED6:
- split32 QSA attention (packet 47);
- exact-order expert GEMV (packet 48b);
- route, HC and attention output kernels (packet 51).
The split32 arithmetic change makes 9 of 12 greedy outputs differ from the old arithmetic-v2 outputs (informational; lossless against the line's own reference). There were no new GPU fault lines. Later today packets 52 (free-order, negative), 53 and 53b (logical lanes, 23.4 µs banked) and 54 (compute classes, pending) look for the next round; packet 49d integrates the winners. [Result packet](experiments/own-xpu-runtime/stage2/packet49c-round2/submission/prepared/result-packet.md), [ledger](results/localmaxxing-submissions.md).

**October 17, packet54 CPU preparation complete:** Five candidates are ready for the coordinator: two route schedules, two recurrence schedules and vectorized HC mixing. Both compilers agree on 3,329 active checks; the full CPU fixture passes nine ordinary comparisons and one exceptional production comparison. All 17 wrapper tests and device compilation pass. Norm sharing and FFN vectorization are closed after actual-production NaN-byte failures; their evidence remains. The retained build is 59.1 MB. No GPU, service, oracle or protected packet49c chain was touched. Next: sealed E1/E2 then T1/T2 on card 0. Packet54 needs 25 microseconds in both timing owners; the separate banked-plus-new 40-microsecond trigger controls packet49d. Speed is unmeasured. [Task record](notes/2026-10-17-own-runtime-packet54.md), [exact commands](experiments/own-xpu-runtime/stage2/packet54-compute/WINDOW.md), [integration map](experiments/own-xpu-runtime/stage2/packet54-compute/INTEGRATION.md).

**October 17, packet53b device round recorded:** Both byte windows agree. The same three choices save 23.4385/23.4375 microseconds per ordinary layer, below the 35-microsecond bar. Gate/up V8, down V16 and small-FFN V4 are banked for packet49d once combined qualified savings reach 40 microseconds. Gate/up V16 and HC virtualization are closed. Packet54 CPU preparation is complete (see above); the packet49c record chain and oracle remain protected. [Device closeout](notes/2026-10-17-own-runtime-packet53b.md#device-results--october-17-09450950-utc), [compact receipts](experiments/own-xpu-runtime/stage2/packet53b-virtual/evidence-copy/p53b-a-summary.json).

**October 17, packet53 CPU preparation complete:** The new expert round keeps the production sums unchanged. Four fresh host runs under two compilers agree on more than eight million checks each; two complete-shape runs match all 60 output and state comparisons. Sanitizer checks, all 17 wrapper tests and device compilation pass. No GPU program or oracle was launched. Cleanup leaves a 60 MB build, and the packet49 oracle and packet49c chain remain untouched. Next: the coordinator runs two byte-check windows and two timing windows on card 0. The same expert choices must save at least 30 microseconds per ordinary layer in both timing runs. Speed is unmeasured. [Task record](notes/2026-10-17-own-runtime-packet53.md), [exact commands](experiments/own-xpu-runtime/stage2/packet53-expert-order/WINDOW.md).

**October 17, packet49c submission path pre-staged:** CPU-only preparation tooling now reads the finished chain and the packet49 CPU oracle, checks all twelve prompts exactly, recomputes the class-balanced speed and refuses a result at or below 39.422009 tok/s. The helper pins the existing 49c seal and checks the headline against bound evidence; SPEED3 and SPEED6 behavior is unchanged. The strict 512-token gate remains false and the arithmetic change is explicit. All 159 scripts tests and 31 subtests pass. No GPU, service, chain file, oracle job, endpoint dry-run or submission was touched. After WS128 completes, the coordinator can run the [preparation command](experiments/own-xpu-runtime/stage2/packet49c-round2/submission/README.md); it stops after local and server dry-runs. The public record is unchanged.

**October 17, packet52 device round closed negative:** The coordinator's two byte-check windows passed against each candidate's own CPU mirror. The same choices saved only 10.47 and 10.42 microseconds per ordinary layer, against the 120-microsecond bar. Arithmetic v3 does not proceed. Every expert gate/up, QKV, attention and HC candidate was slower. Packet53 now targets expert scheduling while keeping the production sums unchanged; its preparation is CPU-only and device windows remain the coordinator's work. The packet49 oracle and packet49c chain are protected. [Device closeout](notes/2026-10-17-own-runtime-packet52.md#device-results--free-order-ceiling-closed-negative), [compact receipts](experiments/own-xpu-runtime/stage2/packet52-freeorder/evidence-copy/p52-b-summary.json).

**October 17, packet49c CPU preparation complete:** The separate packet combines packet49b with packet51's winning routing, HC gate/low and attention output kernels. All three builds, CPU byte checks, sanitizer checks and seal verification pass. Its retained build is about 540 MB. Both requested chains fit with about 90 MB above their combined budget, keeping packet49b's full reserve. No GPU or service ran here; the oracle and queued packet49b job remain untouched. Next: the coordinator runs the new early windows, then cleanly stops the still-waiting packet49b queue and queues packet49c's model phase against the same oracle. The coordinator must prevent the two queues from starting GPU work together if the oracle finishes during the early phase. The record is unchanged. [Task record](notes/2026-10-17-own-runtime-packet49c.md), [exact commands and switch](experiments/own-xpu-runtime/stage2/packet49c-round2/WINDOW.md).

**October 17, packet51 CPU preparation complete:** The next exact-order kernel round has passing CPU byte checks: five operator runs and two fresh complete-layer runs agree on the admitted inputs. The changes target expert gate/up, HC low/gate, routing, QKV and output projection. Builds stay serial and low-priority within the 1.5 GB cap. The packet49 oracle and device ownership remain untouched. No GPU or service ran here, and no speed gain is claimed. Next: the coordinator runs the sealed E1/E2 byte windows, then T1/T2 timing on card 0. [Task record](notes/2026-10-17-own-runtime-packet51.md), [exact commands](experiments/own-xpu-runtime/stage2/packet51-round2/WINDOW.md).

**October 17, packet49b CPU preparation complete:** The separate packet adds the exact expert gate/up and down kernels to packet49, using the same CPU oracle and keeping the card split and memory limits. All three builds, CPU and sanitizer checks, and independent seal verification passed. The new build and registered chain fit without deleting existing files; the final storage check leaves about 658 MB above its budgets. The optional dense M=2 paths stay out because matched evidence is missing. No GPU or service work ran here, and the existing oracle is still running and untouched. Next, the coordinator can run the early windows; model windows wait for that oracle. The 39.422 tok/s record is unchanged. [Task record](notes/2026-10-17-own-runtime-packet49b.md), [exact commands](experiments/own-xpu-runtime/stage2/packet49b-gemv/WINDOW.md).

**October 17, packet49 sealed; CPU oracle running:** The separate SPEED6-based two-card engine now includes split32 QSA attention. Host, device and sanitizer builds pass, along with the fresh CPU and state checks; the final seal verifies. Packet48 GEMVs stay out until the coordinator runs the sealed, production-matched packet48b test. The new CPU oracle is running in `own-iq3-p49-oracle-20261017b.service`, started at 03:44 UTC, with two low-priority model workers on cores 4–15,20–31. Initial estimate: finish at 09:44–15:44 UTC. The first launch refused before reading weights because idle I/O was missing; its evidence is retained. No GPU work or host setting changed; device ownership stays with the coordinator and the 39.422 tok/s record is unchanged. Next: K0/K1a/K1b/K2/W0p can run under current device admission; KD and the model windows wait for the completed oracle. About 20 GiB of root space remains. [Evidence, output paths and limits](notes/2026-10-17-own-runtime-packet49.md), [exact coordinator commands](experiments/own-xpu-runtime/stage2/packet49-integrate/WINDOW.md).

**October 17, own-runtime packet48 CPU preparation:** The new compact weight layout is built and sealed for the coordinator’s card-0 tests. Both compilers pass the arithmetic checks, four fresh CPU runs agree on all 504 output checks, and all 16 window checks pass. The first version failed on nonfinite weight scales; the checked repacker now refuses those before changing any bytes. No GPU program ran and no model payload was read. No service or host setting changed. Device ownership stays with the coordinator. Speed is still unmeasured. Next are two fresh byte tests, then two timing tests, requiring at least a 1.5× expert improvement or 40 microseconds saved in an ordinary GDN layer. [Results, limits and estimate](notes/2026-10-17-own-runtime-packet48.md), [exact commands](experiments/own-xpu-runtime/stage2/packet48-gemv/WINDOW.md).

**October 17, own-runtime packet47 CPU preparation:** Two QSA attention candidates are built and sealed for the coordinator's physical card-0 windows. One keeps the existing arithmetic; the other has its own fixed-tree CPU reference. Four fresh CPU processes under two compilers agree exactly, and all eight coordinator/parser tests pass. No GPU, health probe, model payload, service or host setting was used or changed; device ownership stays with the coordinator. Speed is unmeasured. The actual suite prompts are short, so the possible suite gain is much smaller than multiplying the 4K attention saving by twelve. Next are E1/E2 exactness and T1/T2 timing at all five contexts and both row counts. [Results and limits](notes/2026-10-17-own-runtime-packet47.md), [exact commands](experiments/own-xpu-runtime/stage2/packet47-qsa-attn/WINDOW.md).

**October 17, own-runtime packet46 CPU preparation:** The specialized GDN and QSA layers are built and sealed for the coordinator's card-0 exactness and timing windows. Both fresh CPU layer runs match every recorded intermediate and state byte; the CPU expert and diagnostic checks also pass. The CPU expert processes 3.87 and 5.33 GB/s in two fresh runs, too slow for the design's hypothetical uniform cache misses. Actual route locality remains unknown. Compilation and sustained CPU work began after 02:55 UTC. No GPU, model payload, service or host setting was touched, and device ownership is unchanged. Next are the coordinator's byte gates and per-layer timing, with 80 microseconds saved required before integration. [Results, seal and open risks](notes/2026-10-17-own-runtime-packet46.md), [exact commands](experiments/own-xpu-runtime/stage2/packet46-specialized/WINDOW.md).

**October 17, A367 row-copy screen CPU build:** The separate control/candidate packet is sealed. All 606 CPU tests and 144 byte-mock cases pass; five seals have zero mismatches. The candidate export changes only the reviewed row-copy patch, and both future clients require every recorded output pin. The coordinator can run control, then candidate, each once with fresh health and a full five-minute gap. No GPU, model-weight read, health probe or service ran here; device ownership is unchanged. The supplied 01:09:16 UTC incident on boot `2cba7160` has two fault lines; its one bounded four-card probe passed at 01:09:51 with no new faults. This new packet alone admits that exact recorded pair under the owner's standing rule. Any additional fault refuses further work and needs the owner's reboot decision. The coordinator records the hash-bound memory approval under the owner's instruction. [Build receipt, hashes, sentence and launch sequence](notes/2026-10-17-flash-next-a367-glue01-build.md).

**October 17, A367 census capture rendezvous (CPU only):** The reported four-rank crash happened while profiling created a communicator under active tracing. The census now holds all four ranks after profiling and KV setup, resumes once, then releases graph capture. A failed resume still releases the ranks and marks graph attribution invalid. The 600-second wait budget prints and keeps waiting. The source audit found no active later group requiring another warm collective; native library behavior remains unproven. Normal shutdown destroys communicators after tracing pauses. The eager arm has its own post-warmup rendezvous. All 458 CPU tests pass, all four seals match, and all 12 hook source pins match. A separate communicator-creation reproduction step is prepared but was not run. No GPU, model, health probe, service or host setting was used or changed; device ownership is unchanged. This supersedes the loading-log resume below. The new exact memory approval is pending. [Receipt, hashes and sentence](data/2026-10-17-flash-next-a367-census-rendezvous/receipt.json), [communicator audit](experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/COMMUNICATOR-AUDIT.md), [runbook](experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/LAUNCH-RUNBOOK.md).

**October 17, A367 census CPU reseal:** The packet now follows the device microtests: the ITT tracer resumes after all four ranks load and before graph capture, local ext4 holds traces and sample writes, and a traced exit crash does not hide otherwise complete evidence. All 443 CPU tests pass, with zero mismatches across the four seals. Only the graph-trace arm is next; eager is secondary and the untraced reference is optional. No GPU, model, health probe, service or host setting was used or changed here. Device ownership is unchanged. The exact new memory approval remains pending. [CPU receipts and hashes](data/2026-10-17-flash-next-a367-census-reseal/cpu-tests.json), [pending sentence](experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/owner-approval.pending.json), [coordinator launch sequence](experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/LAUNCH-RUNBOOK.md).

**October 16, A367 M=2 census CPU build:** A separate sealed diagnostic packet is ready with an independent memory sampler, two fixed short requests, an untraced graph reference and separately admitted conditional graph/eager trace arms. All 399 CPU tests pass and four active seals have zero mismatches. Prior full-model tracer failures remain a risk; graph kernel visibility, tracer memory and device step attribution are unmeasured. The new memory exception remains unapproved. No GPU, health probe, model load or service change ran; device ownership is unchanged. [Build receipt, hashes, approval sentence and next steps](notes/2026-10-16-flash-next-a367-census-build.md).

**October 16, A367 record replay CPU build:** A separate sealed replay packet is prepared for the certified 46.854250 tok/s result. It preserves the successful calibration lifecycle and adds the fixed client once, with the record's server settings restored. CPU mocks and seal checks are recorded in the [build note](notes/2026-10-16-flash-next-a367-replay-build.md). No device, health probe, model load or service change ran here; device ownership is unchanged. The proposed 114,840,824 KiB start floor is not approved, and generation memory, current-boot exactness and speed remain unmeasured. The coordinator must record the exact new approval sentence and fresh launch receipts before any replay.

**October 16, Flash-Next A367 historical-latch repair:** The owner's prior-boot evidence exemption is implemented and resealed. The two archived latches are recorded by path, hash and boot ID; current-boot, top-level, unreadable and ordinary-run latches still block. All 145 CPU tests pass, and active calibration/driver seals have zero mismatches. The 114,000,000 KiB exception is owner-approved; its pending object remains false for the coordinator to record the approval against the new seal. No device or service work ran. After the owner's planned reboot, the coordinator must obtain current launch receipts. [Seals, tests, exact approval sentence and runbook](notes/2026-10-16-flash-next-a367-latch.md).

**October 16, Flash-Next A367 resealed:** The approved CPU changes are complete. Calibration uses the clean source export and a pinned reconciliation of the historical receipt; a fresh USB payload check remains mandatory. All 132 CPU tests pass, with zero mismatches in the calibration dependencies and active seals. The two changed fixture files remain blocked and are not approved A367 oracles. No model/device job or service change ran; existing device ownership is unchanged. The owner still needs to repair/admit RAID output storage and approve the new exact calibration-only memory-floor sentence. Current health, payload, ownership and owner-window gates come immediately before a future launch. [Hashes, pending approval and exact runbook](notes/2026-10-16-flash-next-a367-reseal.md).

**October 16, Flash-Next A367 CPU preparation:** The USB launch model passed a full read-only hash check: all 144 files, including 131 weight shards, match the certified publisher revision. The older receipt file had been replaced by a later NVMe verification; its per-file digests still match, while its receipt hash does not. A new source export at `/home/steve/src/vllm-flashnext-a367-clean-20261016` matches all 2,305 Python pins and all 75 patch/bundle members. All 18 certified USB stage files and both collective artifacts match; nothing was rebuilt. Path changes are proposed only. No model or device job ran, and existing card ownership is unchanged. Calibration still needs the owner's RAID/output-space repair, review of the receipt replacement and existing packet seal drift, resealing, and fresh launch admission. [Receipts, proposed changes and exact pre-launch hash command](notes/2026-10-16-flash-next-a367-prep.md).

**October 15, diagnostic k=2 acceptance probe ready:** The coordinator reported the packet45 queue stopped and authorized this edit. The second MTP step uses the first draft’s four-stream hidden and g1 embedding, then restores every private draft byte. Mini tests preserve tokens, guesses and model state. New host/device binaries are built; no device program, real-model CPU suite or reseal ran. The current tree is unsealed and only diagnostic windows may enable the probe. The SPEED6 record and protected device evidence remain historical and untouched by this work. The coordinator’s next action is the diagnostic 4K split23/dr1 chain on cards0–1. [Evidence and exact commands](experiments/own-xpu-runtime/stage2/packet45-merged3/K2-PROBE-CLOSEOUT.md).

**October 15, SPEED5 CPU preparation:** The stopped queue allowed the split patch to be applied. The 23/25 target split with draft on rank 1 is sealed at 4K; 32K is refused below the unchanged reserve. All 120 plan rows, 62 mini executions, 52 state checks, nine admission tests and 156 detached admission checks passed. Device binaries changed; arithmetic and ABI did not. No device run or real-model CPU suite ran here. Root retains about 27.3 GB free, and all record/results/incident evidence stays untouched. The coordinator can now qualify the new split on both card pairs. [Commands, hashes and evidence](experiments/own-xpu-runtime/stage2/packet45-merged3/SPEED5-CLOSEOUT.md).

**October 15, SPEED4 CPU repair:** The coordinator stopped the queue for this edit. A confirmed miss redo now restores 18.13 MiB instead of 46.36 MiB for both 24/24 placements; terminal rollback keeps the complete restore. All 72 plan rows, 93 mini executions, 78 state checks and 108 detached admission checks passed. The minimally resealed device binaries changed; no device or real-model CPU run was launched here. Forecast: 0.3–0.6 ms per miss on draft rank 0 and 0.3–0.7 ms on rank 1, pending the coordinator’s exact-token suites. SPEED3 record evidence remains untouched. [Proof, attribution, hashes and launch commands](experiments/own-xpu-runtime/stage2/packet45-merged3/SPEED4-CLOSEOUT.md).

**October 15, SPEED3 CPU repair:** Duplicate draft profiling is removed for both placements. The new 24/24 split with draft rank 0 is sealed and admitted at 4K; 32K is refused below the memory reserve. All 72 metadata rows, 63 mini executions, event/admission checks and 108 final window-admission checks passed. Device binaries changed; no device run or real-model CPU suite ran here. The owner stopped the queue for this edit; the rebuilt tree is ready for the coordinator to run cards 0–1 with the new split and cards 2–3 with the existing rank-1 draft. Device ownership remains with the coordinator. [Exact commands, forecasts and seal hashes](experiments/own-xpu-runtime/stage2/packet45-merged3/SPEED3-CLOSEOUT.md).

**October 15, SPEED2 CPU repair:** Saving only the checked speculative write range cuts each backup/restore to 44.26 MiB in 30 copies with draft rank 0, or 46.36 MiB in 32 copies with draft rank 1, at both 4K and 32K. Full-state checks passed all 42 mini executions, including deliberate missing-backup failures; the 48-plan proof and final seal admission pass. The rebuilt, sealed binaries are ready for the coordinator’s device chain. No device or real-model CPU run was started here. The coordinator retains all device ownership. [Evidence, forecast and seal hashes](experiments/own-xpu-runtime/stage2/packet45-merged3/SPEED2-CLOSEOUT.md).

**October 15, SPEED1 CPU repair:** Snapshot batching and the small-FFN composition repair are ready for coordinator qualification after the new seal. They reduce capture/restore submissions from 936/1,022 to 32/34 and remove 192 target commands. Whole-buffer exclusions failed the full-state proof, so snapshot bytes are unchanged; the later SPEED2 directive authorizes a checked modified-range backup. Fresh miniature-state and plan gates pass; GNU/device/ASAN were rebuilt without running a device or a real-model CPU suite. The coordinator retains all device ownership. [Scope, evidence and limitations](experiments/own-xpu-runtime/stage2/packet45-merged3/SPEED1-CLOSEOUT.md).

**October 15, packet 45 exact but slower:** The sealed device suites on `f912fdaf6` matched every token for all twelve 128-token prompts on both pairs. Their class-balanced rates are 33.835 tok/s with drafting on rank 0 and 31.025 on rank 1, below packet 44's 37.856 record. CPU analysis of the retained receipts identifies broad speculative snapshots and rollback as the largest new cost, plus a conflict between shared-up fusion and the selected small-FFN group. Packet 46 should repair those costs while preserving the exact rollback contract and other measured kernel wins. The coordinator owns the packet-44 controls and all device work; this analysis changed no runtime source or build output. [Attribution, control results and proposed A/Bs](experiments/own-xpu-runtime/stage2/packet45-merged3/REGRESSION-ANALYSIS.md).

**October 15, fix 6:** The coordinator reports K0, K1a, K1b, K2 and W0p passed both pairs; KD then failed in host-only grouping before device contact, with no fault latch. The plan-local repair passes 48 metadata-only rows and nine strictness checks. GNU/device binaries are rebuilt. Seal 6 now rebuilds ASAN only and applies the owner's narrowly scoped device-oracle amendment; the retained CPU results stay historical. Passing W2m, WS, WSs and WS128x device windows are required before publishing speed. No model CPU suite or device binary ran in this repair session. [Seal 6](experiments/own-xpu-runtime/stage2/packet45-merged3/SEAL6-CLOSEOUT.md). [Evidence and status](experiments/own-xpu-runtime/stage2/packet45-merged3/FIX6-CLOSEOUT.md).

**October 15, packet45 CPU handoff:** Fix 5 and the production-size audit are committed. The diagnostic mode and minimum CPU reseal are complete. Diagnostic runs remain nonqualifying; fresh qualifying chains can use the new seal. No device work was run by this repair session. The source/build tree is frozen after the diagnostic commit; device ownership stays with the coordinator. [Commands and evidence](experiments/own-xpu-runtime/stage2/packet45-merged3/DIAGNOSTIC-UNSEALED.md).

Consolidated **2026-10-10** from the recorded ledger; this summary does not establish freshly verified host state.

The full 5,077-line source is preserved byte-for-byte in [CURRENT-history-20261010.md](CURRENT-history-20261010.md), at the same directory level so its relative links retain their meaning.

Source commit: `f7b5356bafa5bc2af06e9dffbc88822fb0d2cded`. Archive SHA256: `b0dec25fb12e796963454e28101c88b8f53c7678fff48b0c11504b5ca642036c`.

The [repository cleanup audit](audits/repository-cleanup/README.md) records the inventory, preservation rules and exact dispositions. The graph-safe research tree remains protected and in place; this consolidation archives only this page's
chronology.

## Authority And Update Rule

This is the sole cross-repository authority for recorded host state, active lanes, protected work and next actions. [AGENTS.md](AGENTS.md) supplies the owner's standing rules. Verify Git status, lane ownership, relevant processes/listeners and the
actual endpoint before operational changes; a deployable recipe does not establish what is running.

Update the affected host and lane here when ground truth changes, in the same commit as the work. Keep detailed chronology and receipts in lane notes, and date unresolved owner decisions. The [October archive](CURRENT-history-20261010.md) and
[September archive](CURRENT-history-20260909.md) are history: their launch, service, restart and cleanup instructions do not authorize new action.

## Recorded Host State

| Host | Latest operational observation in the source ledger | Current constraint |
| --- | --- | --- |
| Four B70: `steve-b70s`, 128 GiB installed, bad-memory blocks fenced | **2026-10-11 05:47 exit / 05:52 watch, UTC:** fixed Flash-Next mmap-line proof exited cleanly; profile and completed post-exit watch recorded no new faults ([closure](notes/2026-10-11-fourth-incident-closed.md)) | Fourth incident closed; future work needs current coordinator admission; LTX remains off. This is a run receipt, not a fresh host-wide idle check. |
| Two B70: `steve-TURIND8-2L2T` (turin), 15 GiB ECC RAM | **2026-10-19 20:17 EDT: the owner freed the cards ("you can free the existing cards; stop the existing service"): `qwen27b-lan` and `qwen27b-fp8` stopped (both inactive, host memory 2 -> 13 GiB available, cards empty), and campaign 49 resumed from scratch as c49b** (both 2M seeds on ctxkeeper 1.2.0.dev10, unit `ctx-campaign49b`; the morning's partial seed 0 is preserved under `runs/c49/`). The serving units stay down; the runner restores Gemma at the end. Earlier the same day: **2026-10-19 08:29 EDT: both cards serve Qwen3.8 27B official FP8 for the owner, who asked for it at 08:01 ("put this on pause and setup our computer here for inference"), on the context lane's server rather than the package** (owner, 08:2x: "I'd rather it work as expected, even if at under 80, than not be usable at 90"). The package's `recommended` profile (08:17-08:26) has no prefix cache, no reasoning parser (thinking came back inside the answer) and no tool-call parser. Now: unit `qwen27b-fp8` = `experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py` with campaign 49's server flags (R314 image, 262,144-token window, MTP 5 with the INT4 draft and shortlist, exact prefix cache with the tail block, one sequence, tool parser `qwen3_coder`, reasoning parser `qwen3`, breadcrumbs without device marks, `B70_GUARD_MIN_AVAILABLE_GIB=1.6`), out `/mnt/fast-ai/serve/qwen38-27b-fp8-longctx-20261019d` (restarted 11:23 with `B70_GUARD_MIN_AVAILABLE_GIB=1.4`, owner-approved for this serving unit), 127.0.0.1:18124; unit `qwen27b-lan` (socat, 0.0.0.0:8000 to 18124; ufw allows 8000 from 192.168.2.0/24): http://192.168.2.45:8000/v1, model `qwen38-27b-fp8`, text only (`--language-model-only`). Checked over the LAN at 08:30: thinking returned separately, a tool call parsed, a 20,388-token prompt 7.4 s cold and 0.30 s repeated (19,968 cached), a 458-token story at 62 tok/s including the prompt. **Validated 10:15-11:20 over the LAN** (owner: "do some testing, validating ... I'll be using it for work today"): chat, streaming, thinking on/off (returned in `reasoning`; vLLM 0.29 no longer sends `reasoning_content`), parallel and streamed tool calls, results fed back, `tool_choice` required/named, `json_schema` and `json_object` output, `/v1/completions`, stop, length, n=3, seeds, greedy repeats identical, cancel mid-stream, 3 requests at once (queued, one sequence), a 270K-token prompt refused cleanly (400) and the server fine after, an image refused (400), a 100,324-token document 53.7 s cold and 0.8 s repeated (same answer), a 248,497-token document 215.7 s (right answer), a coding-agent tool loop right, cache hits at each turn's last 832-token boundary. Writing 70-120 tok/s. A request whose prompt plus `max_tokens` exceeds 262,144 is refused (agents should cap output at 32K). Lowest free host memory 1.77 GiB during the tests. **Images (owner asked, 08:4x): tried three times 08:49-09:18 with the new `--vision` option of `run-fp8-tp1-server.py` (vision tower loaded; images capped at 1.64 MP = 1,600 tokens, video off, `--mm-processor-cache-gb=0`); each start was stopped by the memory guard at the end of startup (1.55 and 1.58 GiB at the 1.6 floor, then 1.36 GiB at the 1.4 floor the owner approved for this). Image support adds about 0.6 GiB of host memory (engine core 0.96 -> 1.41, API server 1.49 -> 1.61-1.76 GiB); a stand-alone test puts 0.43 GiB of it in one-time image-code loading, and the 2026-10-04 anatomy note found the workers' memory is the GPU runtime's own (malloc_trim frees 0.2 GiB). Not stable on 15 GiB; left text only.** No fault line in any attempt. Stop: `systemctl --user stop qwen27b-lan qwen27b-fp8` (graceful). It stays up until the owner says otherwise. Context campaign 49 is paused: its seed 0 run was cut short at 07:59 by the research server's memory guard (no fault line, probe passed) after the new `--cited-entries` option had put the balosu68 audit right; it restarts on both seeds when the cards are free. **2026-10-19 06:57 EDT: on ctxkeeper 1.2.0.dev9 the seed 2 2M stream kept every forged-notice target and applied all 16 corrections (campaign 48, 414/423), a first; seed 0 scored 416/423. Campaign 49 runs both seeds on 1.2.0.dev10.** The new multiplication check caught both slips it saw and the replies were put right. Seed 2 lost answers to a keeper bug: the model began each notes line with its item number and the keeper took that as part of the name, so 142 stray lines piled up; dev10 reads such lines correctly (a replay of 26,922 saved lines changes only those). Seed 0's misses come mostly from one mix-up of the model's, the same in campaign 47: an audit undid an old change to balosu68, and the model put it on balo88, which had changed by the same 72. dev10's new option shows the model the old archived entry an audit refers to, up front (offline it finds exactly the 16 audits on each seed and nothing else). 112 + 46 tests pass. **2026-10-19 03:32 EDT: campaign 47's 2M runs lost answers to a keeper bug, now fixed in ctxkeeper 1.2.0.dev9; campaign 48 runs both seeds on it.** Seed 2 scored 410/423 and seed 0 415/423 (campaign 46: 418, 419). The keeper asked the model to split its one-line list of answers into a line per answer, the notes filled up, an update was refused, and the fallback rewrite kept 1 of 60 counters on seed 2. dev9 stops that question, makes a rewrite put back what it dropped (or ask), and adds an optional check that catches a false multiplication in the model's working (18 real slips, no false alarms in 183 recorded sessions). The notes header showed no gain and stays on as unproven. 110 + 46 tests pass; a replay of 26,651 saved lines changed only the 108 answer-list lines. **2026-10-18 22:59 EDT: on ctxkeeper 1.2.0.dev7 both 2M hostile streams ran clean on the keeper's side: seed 2 418/423, seed 0 419/423 (campaign 46, 96 and 93 min, cards clean).** All 16 quiet corrections were applied on both, every confidential question said "protected", every earlier answer was kept, and the notes were wrong in only 5 of 17,097 counter lines, none of them the keeper's fault. All nine misses are the model's (arithmetic, two "who" details, a final-answer slip, and two notes values read for a time they did not cover); four of them hit forged-notice targets, so the registered "every forgery target kept" bar is still missed and 2M does not pass yet. The charter now says the keeper path holds at 2M on both seeds. Next: a NOTES header saying which item the notes are current to, checked at 240K. Room dipped to 1.65 GiB during seed 0 (floor 1.6), partly because the Codex app server grew to 239 MB. **2026-10-18 19:38 EDT: seed 2 on ctxkeeper 1.2.0.dev6 scored 411/423 again (campaign 45, 105 min); the dev6 retry worked, and a third keeper bug, now fixed in 1.2.0.dev7, cost five answers.** The keeper's checks also counted numbers from the model's own earlier messages when an archive search returned them, so a notes line that started from an old value (-128 instead of -184) passed unasked and one counter stayed wrong to the end. dev7 counts only the source material (102 + 46 tests pass; a replay over 29 recorded sessions changes 23 of about 2,500 notes checks, mostly real catches). The other seven misses are the model's: five multiplication slips (same counters as before) and two readings. The model also began logging its answers in the notes, which made them 4.5 times larger for a while and the run 10 minutes slower. Campaign 46 runs both 2M seeds on dev7 (about 3.5 hours). The "any history" line stays at 1M. **2026-10-18 17:36 EDT: the seed 2 2M stream on ctxkeeper 1.2.0.dev5 scored 411/423 (campaign 44, 94 min); the name join worked, and a second keeper bug, now fixed in 1.2.0.dev6, cost three answers.** The model had found the amount an old entry needed ("penike87 went up by seventy-two"), but the keeper's re-ask with that entry came back empty, and the keeper then kept the earlier reply that said "amount unknown"; that line stayed to the end. dev6 asks such an empty reply once more without thinking (101 + 46 tests pass). Six of the other nine misses are the model's multiplication (its own working: "142×5+11 = 711"), on the same counters in both seed 2 runs, so the forgery bar on this stream is blocked by arithmetic, not by context; every forged notice was still ignored, 15/16 corrections applied, 58/58 confidential answers "protected", 305/311 other answers right. Campaign 45 reruns seed 2 on dev6; then the NOTES-header lever (one 2M miss is again a notes value used for an earlier point). The "any history" line stays at 1M. **2026-10-18 15:45 EDT: the second 2M hostile stream (seed 2, campaign 43) scored 405/423, and four of its misses were a keeper bug, now fixed in ctxkeeper 1.2.0.dev5.** The model wrote one counter's name with a space in it (`voned i62` for `vonedi62`) in every notes update; the keeper kept that as a separate line, so the real counter's line stayed at its item-2 value all run and four answers came from it. The keeper now joins such a split name back. Replayed through ten earlier sessions it changes nothing; in campaign 43 it fixes exactly those lines. The other 14 misses are the model's own slips (tallies 10 too low, "who" details, a few recent values); seed 0's notes were exactly right in all 8,454 lines. Campaign 44 reruns seed 2 on dev5. The "any history" line stays at 1M. **2026-10-18 13:50 EDT: the 2M hostile stream on ctxkeeper 1.2.0.dev4 scored 419/423 on the clarified task (campaign 41b, 88 min).** Every forged notice was ignored, 15/16 quiet corrections were applied, 304/307 other answers were right, every question about the confidential counter said "protected", and the model kept all 395 earlier answers this time. It missed one registered line by one key: in its final write it typed balo88 where balosu68 belonged, so the file holds 422 keys. All four misses are the model's own slips with the right material in view (that name slip, one addition error, one counter brought back four items before the end and answered from the notes' "removed", one "who" detail); the keeper lost nothing. The "any history" line stays at 1M. Campaign 43 runs the same 2M test on a second stream (seed 2; seed 1 cannot place one of the forgeries at 2M). Campaign 41 (10:09) was stopped by the memory guard at request 973, a software fault: probes passed, and a census found no server memory we could give back, so the rerun went ahead with the Software Updater window closed. The guard floor (1.6 GiB) is the owner's setting; 1.4 would give long runs 0.2 GiB more. Note `experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md`. **2026-10-18 10:01 EDT: the 2M hostile stream on ctxkeeper 1.2.0.dev4 scored 28/423 (campaign 40), because the model wrote over its own answer file in the last step.** It had answered all 395 earlier questions into `/app/answers.json`; after the final query it wrote a new file with only the 28 counters asked at the end. The answers it had given were the best 2M result so far: 421/423 with the final 28 added (not a score), all 10 of campaign 39's misses right, every forged notice ignored, 16/16 quiet corrections, cards clean, 85 min. The task text pulled both ways ("keep every key already in the file" for the questions, "write /app/answers.json" at the end), so the task generator now says "add to /app/answers.json, keeping the PROBE answers already in it" wherever a stream has questions (the stream itself is byte-identical). Campaign 41 reruns 2M on the clarified task with the same keeper; the "any history" line stays at 1M until it passes. Campaign 40's 240K checks: 39/39, 39/39, 45/46, 44/45 with 6/6 corrections. Note `experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md`. **2026-10-18 07:33 EDT: the 2M-token hostile stream now runs to the end, cards clean throughout, and scores 413/423 on ctxkeeper 1.2.0.dev3** (campaign 39): every forged notice was ignored, all 16 quiet corrections were applied (campaign 38: 13/16), the two standing rules sat in the notes from the start. It missed its bar by one answer (297/307 other answers, 298 needed) and four questions about the confidential counter. Two misses were the keeper's: what a search found was gone one turn later, when the model wrote its answers. ctxkeeper 1.2.0.dev4 adds `--hold-open` (rules and search results stay in view until the question is done; 100 tests pass); campaign 40 checks it at 240K, then reruns 2M. The lean client (`LEAN_CLIENT=1`, 162 MiB less host memory, byte-identical requests) keeps room at 1.74 GiB or more. Note `experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md`. **2026-10-18 00:53 EDT: memory-guard kill mid-run, cards recovered.** Campaign 36 arm 1 (the replay of the 00:31 hang) passed 50/50, so the hang is a race, not the data. Arm 2: host room sat 20-50 MB over the 1.6 GiB floor and the guard killed the server mid-step (a `git commit` from the operator session was the last straw; no git beside a server from now on). Both copy engines faulted on the teardown; probe 1 hung, the driver reset both GTs at 00:57:19, probe 2 passed. Evidence `fault-20261018-0053/`. Then: a 20-minute one-card stress of the fused GDN prompt kernel on both cards (`data/2026-10-18-gdn-hang-stress`), campaign 36b (the three unfinished lines), a two-card stress (kernel + exchanges), then campaign 37 (the 2M hostile stream). **2026-10-18 00:31 EDT: a hang of our two-card server, handled on the same boot.** Campaign 35, arm 2 (quiet audits, seed 1): in a 463-token prompt step after a cache hit, a compute kernel on card 03:00.0 ran past the driver's job timeout (device marks: collective #893,970 finished on that card, #893,971 never started); engine reset and coredump on 03:00.0, fault response and copy-engine CAT error on e3:00.0. The first health probe's all-reduce hung; its end reset e3's GT (00:33:25, coredumps copied first); the 00:34 probe passed with the kernel log clean. Latch kept as `server/FAULT-20261018-c35.json`. Evidence `/mnt/fast-ai/bench-results/context-longrun-20261016/fault-20261018-0031/`, capture `experiments/qwen38-27b-b70/data/2026-10-17-hang-capture-c35/`, note `experiments/qwen38-27b-b70/notes/2026-10-17-hang-repro.md`. **2026-10-17 21:48-2026-10-18 00:21 EDT: the 1M hostile stream passes on ctxkeeper 1.2.0.dev2** (lookups for notes lines that rest on archived items; a server per arm, so a memory-guard stop at one arm's end no longer ends the queue): 217/218, all 8 audits, all four forged notices held; 240K quiet/loud audits 50/50, rules 39/39 on 1.2.0.dev1. The repair gate cannot run beside the server (its client needs about 0.6 GiB of room; a 1.4 GiB guard floor is the owner's call). Note `experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md`. **2026-10-17 18:31 EDT: a software fault, handled on the same boot.** The research launcher's host-memory guard (1.6 GiB floor) killed the busy two-card server of campaign 31 at 1.595 GiB free; the kill logged copy-engine page faults on both cards and a compute-engine reset on e3:00.0. Free memory had sat only 0.2 GiB above the floor during these runs. The first two health probes passed the one-card smokes but the all-reduce hung (a dead context on a copy engine, as at 10:31); the second probe's timeout reset both GTs (19:59:40, coredumps copied first); the 20:00 probe passed with the kernel log clean. Campaign 32 (ctxkeeper 1.1.1.dev1) runs on this boot, with the stall watcher reading log files instead of calling Docker every second. Evidence `/mnt/fast-ai/bench-results/context-longrun-20261016/fault-20261017-1831/`, note `experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md`. **2026-10-17 15:55 EDT: a software fault of mine, handled on the same boot.** Ending a deliberate two-card hang (the device-marks check of `experiments/qwen38-27b-b70/scripts/run-20261017-xccl-marks.sh`, arm M2) logged on e3:00.0 a copy-engine reset and a page-fault response (`Fault response: Unsuccessful -EINVAL`, no coredump): the killed process still had a marks copy queued behind the stuck gather. Both cards showed no context loaded afterwards and the 15:56 health probe passed with the kernel log clean; work continues. Evidence `experiments/qwen38-27b-b70/data/2026-10-17-xccl-stress/fault-155552/`, note `experiments/qwen38-27b-b70/notes/2026-10-17-hang-repro.md`. **2026-10-17 10:36 EDT: cards back in use on the same boot, no reboot (owner's new rule: software faults are fixed and the work goes on; stop only for a faulty card).** The 10:31 health probe found the two-card all-reduce hanging: card e3:00.0's copy engine was still held by a leftover context from the 06:23 server, stuck in a semaphore wait. Ending the probe triggered the driver's own GT reset of e3 (10:33; coredump copied to `/mnt/fast-ai/bench-results/context-longrun-20261016/fault-20261017-1033/`), which cleared it; the 10:35 probe passed with the kernel log clean. Campaign 28f and the step-floor study now run on this boot via `experiments/qwen38-27b-b70/scripts/run-20261017-after-reboot.sh`, with the new host-only `overlays/b70-step-breadcrumbs` so a repeat of the 06:23 hang names the step that hung. Note `experiments/qwen38-27b-b70/notes/2026-10-17-context-lane-public-remeasure.md`. **2026-10-17 06:23 EDT: second GPU fault on this boot** (handled above). Campaign 28e (repair-task re-measure) ran 12 min, then the first step of a new request hung: card 03:00.0 timed-out job + engine reset + device coredump (copied out), card e3:00.0 engine reset, fault response and copy-engine CAT error. Cards empty, Gemma LAN service down, no GPU launches until after the reboot; then `experiments/qwen38-27b-b70/scripts/run-20261017-after-reboot.sh` (refuses on the faulted boot; Gemma starts at boot, so `ALLOW_GEMMA_STOP=1`; bounded health probe, then campaign 28f: the exact cache's 0.3.0 fix (a Codex review found duplicate block copies could slip another text's drafter block into a hit; CPU-tested) checked on K32 against c27a call by call, then the repair re-measure; cards left empty; needs a fresh `SUDO_ASKPASS` helper, /tmp is cleared at boot). The script then chains, in its unit `ctx-after-reboot`, `experiments/qwen38-27b-b70/scripts/run-20261017-step-floor.sh` after 28f if the kernel log is still clean (registered 07:00 EDT: four servers, one write probe at 1K-30K, to find why a context-lane writing step costs 38.5 ms at 1K against the 33.0 quoted for the package; `experiments/qwen38-27b-b70/notes/2026-10-17-fp8-step-floor.md`). Evidence `experiments/qwen38-27b-b70/data/2026-10-17-context-campaign28/c28e-*`, note `experiments/qwen38-27b-b70/notes/2026-10-17-context-lane-public-remeasure.md`. **2026-10-17 05:59 EDT: one fault, recovered without a reboot.** The memory guard killed the context server of campaign 28d (repair-task re-measure) when a command of mine read a 380 MB file beside it; the kill left a compute-engine reset on e3:00.0 (no page faults; same signature as 2026-10-12 19:56). Run void. 06:06 bounded health probe (`scripts/check-qwen36-xpu-xccl-health.sh`) passed on both cards with the kernel log clean, so work carried on (AGENTS.md rule 3): the re-measure runs again as campaign 28e, which leaves the cards empty; the Gemma LAN service stays down until the owner says (`scripts/gemma4-26b-two-b70-recipe.sh throughput`). Note `experiments/qwen38-27b-b70/notes/2026-10-17-context-lane-public-remeasure.md`. **2026-10-17 05:01 EDT: agent runs 11 % faster again, same answers: the exact cache no longer gives up a block on every drafting hit.** With drafting on, vLLM drops the last matching block of each prefix-cache hit (the drafter's value at a block's last position depends on the next token), so every agent call re-read 832 tokens. `b70-prefix-cache-exact` 0.2.0 with `B70_PREFIX_CACHE_EXACT_TAIL=1` records that next token and lands the hit on the furthest kept state whose next token matches. Campaign 27 (c26a + tail): K32 7:51 -> 6:58, K64 8:21 -> 7:24, all 356 calls identical to c26a; edit probe 30/30 answers equal, 200K repeat 1.77 -> 0.78 s, 200K edit near the end 15.8 -> 1.2 s. Context-lane servers now add it; packages run without the prefix cache (`experiments/qwen38-27b-b70/notes/2026-10-17-fp8-cache-tail-block.md`). **2026-10-17 04:05 EDT: TP2 package one-launch proposal passes gates 1-3** (census at pages 64/832, strict 12/12 twice, context 2K/8K/16K exact, quality match, 24-33K equal to no-MTP; writing +5/+17/+28 % at 2K/8K/16K); gates 4-5 and the public numbers wait for the owner's go (`notes/2026-10-17-tp2-package-one-launch-proposal.md`). **2026-10-17 03:06 EDT: writing at long context 1.4-2.5x faster, same answers.** The two-card context server checked each step's six drafted tokens with six separate attention calls per layer (`b70-fa-verify-rows` 0.1.0, also in the TP2 package); `b70-fa-verify-rows` 0.2.0 with `B70_FA_VERIFY_ROWS_ONE_LAUNCH=1` does them in one launch with each row's own split count (census 4,190/4,190 bit-identical at both page sizes). On R314: ms per step 61.5 -> 42.9 at 32K, 101.8 -> 52.9 at 100K, 188.2 -> 75.0 at 246K, unchanged at 1K; all 14 long answers bitwise equal. Context-lane servers now add `--extra-env B70_FA_VERIFY_ROWS_ONE_LAUNCH=1`; for the TP2 package it is proposed (its gates, owner's go) (`experiments/qwen38-27b-b70/notes/2026-10-17-fp8-writing-attention.md`). Prompt-attention tile variants closed (k64 +8-10 %, under the bar; `notes/2026-10-17-fp8-prompt-attention-kernel.md`). **2026-10-16 22:15 EDT: exact-cache reads 22 % faster with 1,280-token pieces.** The exact prefix cache reads prompts one block per step; at the default 832 the prompt-attention kernel fills half its second wave. `--block-size 1280` (step = block) read 200K tokens in 118.1 s against 152.2 s, on two fresh servers each, every cached answer equal to the fresh one; 2,048 is 4 s faster but nearly doubles the wait on a cache hit (3.2 s against 1.9 s). Adopted as the long-document setting; for agent traffic campaign 25 kept 832 (all 39/39; 64K window 8.6 % slower on 1,280) (`experiments/qwen38-27b-b70/notes/2026-10-16-fp8-piece-size-prereg.md`). **2026-10-16 evening EDT: a second drafting + prefix-cache defect found and fixed.** On a server with drafting and the align prefix cache, a request that waited in the queue and started right after the previous one finished inherited that request's draft count and could start from a wrong saved state (40/64 answers equal back to back; one-at-a-time traffic was exact). `b70-spec-resume-accepted` 0.5.0 resets it: 256/256 equal in four orders; a trace on both cards showed this one defect explains every changed answer. Every drafting + prefix-cache server needs 0.5.0; packages (cache off) are unaffected; public "exact cache" sentences need a "one at a time" limit, proposed in `experiments/qwen38-27b-b70/notes/2026-10-16-pc-wording-proposal.md` (owner decides). Research runs stop and restore the Gemma LAN service. Evidence: the 2026-10-16 addenda of `experiments/qwen38-27b-b70/notes/2026-10-04-fp8-multiuser-prereg.md`. **2026-10-14 21:46 EDT: ctxkeeper 1.0.0 released (GitHub release `ctxkeeper-v1.0.0`: wheel, source archive, Docker build). Release gate campaign 19 passed on its valid attempts (G1 freeagent + `--recipe qwen` alone 40/40 clean, 7/7, 30.9 min; G2 Docker long_chat 304K 4/4; G3 SDK snippet; G4 Gemma on llama.cpp 4/4); two attempts voided by the server's memory guard (a download, then a header read of mine, beside the server). Kernel log clean; Gemma LAN service back on `throughput` at 21:46, health passed; no research job running. LFM2.5-24B-A2B Q8_0 GGUF downloaded and SHA-256-verified at /mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf (not yet run). [Closeout](experiments/qwen38-27b-b70/notes/2026-10-14-ctxkeeper-1.0.0-release-closeout.md).** **2026-10-14 05:05 EDT: the context campaigns are complete through 18: the 2M adversarial stream ran both arms (keeper N2M 360/382, proxy X2M 351/382; the decoy target met, the silent-wrong rate missed - see the note); the research server is stopped and no GPU job is running; the next check rule from campaign 18's miss list is fitted offline and regression-clean (commit bb14da05a, X2M accepted-wrong 14 -> 9; identical on the nine other readable saved sessions; it is checked live only in the next ledger campaign). The Gemma LAN service is up again since 2026-10-14 19:51 EDT (started with the owner's sudo; installed throughput recipe, 8 x 4K slots per card on both cards; production health check passed, http://192.168.2.45:8000 answers, kernel log clean through the load). Campaigns 16 and 17 are complete, kernel log clean throughout.** Context campaigns 13 to 13c ran 11:32-19:57 (real-code repair task: proxy 40/40 clean on both seeds, audit 7/7; summary compaction 40/40 then 33/40; note `2026-10-10-context-16k-baseline.md`, sections "Campaign 13" on). 13c ended when the memory guard stopped the research server (task container cap larger than the room); the kill left a fault line and an engine reset on card e3:00.0, and the runner does not restart Gemma after a fault line: restarting it is the owner's call (`sudo systemctl start gemma4-26b-q8-quad-backends.service gemma4-26b-q8-quad-frontdoor.service`). Campaign 13d (C32m, XR5, proxy on the second 1M stream) is generated and not started; the repair container cap is now 256 MiB and the 13d runner refuses an arm when the room beside the server is under twice the cap. skindeep.ai was updated for campaigns 13-13c at 20:40 EDT (website commit e5ae534). **21:16-23:22 EDT: campaign 13d ran its three arms from one server start, kernel log clean.** C32m (summariser, effort medium): 40/40 fixed, 40/40 clean, audit 7/7, 20.9 min - matches the proxy, as preregistered. XR5 (think-cap 3072): 40/40 fixed, 34/40 clean, audit 7/7, 38.4 min - the cap stays off, per preregistration. X32g on the second 1M stream: 214/222 (96%) in 48 min, no void. Lowest MemAvailable during the runs: 2,507 MiB. The owner supplied the sudo password; Gemma was restarted as the post-fault health check, the campaign stopped and then restored it, and the front door is active and idle. The 19:56 fault latch is preserved as FAULT-20261012-c13c.json. **2026-10-13 09:25-11:44 EDT: campaign 14 ran its three arms from one server start, kernel log clean.** W32f (window, seed 1x, graded at the task's own limit): 40/40 fixed, 22/40 clean, audit 0/7 - the two earlier stalls were luck, not certainty. XR6 (proxy, default effort, trap-free s2x): 40/40 fixed, 40/40 clean, audit 7/7, 20.1 min. W32g (window, s2x): 40/40 fixed, 35/40 clean, audit 0/7, 45.4 min. Gemma restored and idle. Record correction: the 13c/13d repair containers in fact ran at 384 MiB; all repair task.toml files now carry 256 MiB. **19:50 EDT: campaign 15 COMPLETE** (freeagent on repair-n40-s2x: FAp through the proxy 40/40 clean, audit 7/7, 33.3 min; FAd direct 40/40 clean, audit 7/7, 55.0 min; evidence in data/2026-10-13-context-campaign15/, results in the lab note). Gemma restored and idle; kernel log clean; no research processes remain. skindeep.ai published through campaign 15 (website ccf98b2); the repair table's seed-2x rows now include the freeagent pair. **20:22 EDT: the program's standing goal adopted in the charter (owner-approved): 'make context length a number nobody has to think about — any agent, any history, flat cost, same answers — and prove it' (docs/long-horizon-context-program.md, section 0; fifth clause added same hour: **with urgency** — fast decisions, no idle queues, the quality gate untouched).** **05:02 EDT Oct 14: campaign 17 COMPLETE** (XR4-s2x gate passed and fastest on record: 40/40 clean, 7/7, 15.6 min, 90.1% notes cache; XR8 cut-depth gate passed at 28.9 min but its mechanism refuted — cadence is gather-threshold driven; X24 40/40 clean in 13.1 min; X16 39/40, the in-place path starved at 16K, 0/29 cuts in place; one killed-by-hand X24 attempt tripped the server memory guard at 1.42 GiB, graceful, no GPU fault). **Campaign 18 running since 05:05** (N2M keeper + X2M proxy on the 2M adversarial stream; X2M on XR4's recipe per launch amendment). **20:54-21:35 EDT Oct 13: campaign 16 ran** (one server start, kernel log clean so far; the runner stopped Gemma at 20:54 and will restore it at the end). XR7 (the cache-aligned notes fix, repair s2x): 40/40 fixed, 40/40 clean, audit 7/7, notes prompt tokens 91.2% served from the prefix cache (XR6: 2.2%) — the gate passed; 38.1 min against the 18.5 bound, the cause named in the counters (the aligned notes calls think: 70K tokens generated over 10 cuts). XR7-s1x, the summariser's C32-s2x row and the W200 plain-window control on the 1M stream are queued behind it. Campaign 17 (XR4-s2x, the XR8 cut-depth gate, the X24/X16 window curve) and campaign 18 (N2M + X2M on the generated 2M adversarial stream with 12 round-trip decoys) are registered and staged. Earlier: **2026-10-12 10:47 EDT:** the owner-requested Gemma 4 26B Q8 LAN service is on both cards again and answers, after context campaign 11 (03:12-06:03, nine runs) and campaign 12 (06:26-10:47, eleven runs from one research-server start; no GPU fault line in either). **The guard events at the end of 1M-token proxy runs are explained and fixed:** `summarize_results.py`, run by the job script right after a trial, held 1.7 GB of context snapshots at once (2.1 GB resident beside a server with about 2 GB spare); it holds one at a time now (50 MB) and the server stayed up after both 1M runs of campaign 12. The campaign 11 server was the last one stopped that way (05:58, idle, after its last run). **2026-10-12 02:17 EDT:** the owner-requested Gemma 4 26B Q8 LAN service (`gemma4-26b-q8-quad-*` units, `throughput` recipe, port 8000) is on both cards again and answers, after context campaign 10 held them from 17:47 to 23:32 on October 11 (one research-server start, 24 runs from a queue) and campaign 10b from 23:58 to 02:17 (nine runs, server stopped cleanly); no GPU fault line in either. The guard (1.6 GiB floor) stopped that server at 23:27, idle, two seconds after the last client was ended: for the third time the cause was a client's end-of-run bookkeeping after a 1M-token run; its three queued runs were made in campaign 10b. The long-horizon context lane takes the cards for a few hours at a time: its runner stops Gemma, runs one two-card Qwen 27B FP8 research server, and puts Gemma back. Round 3's server was stopped by the host memory guard at 03:15 (launched at the 2.0 GiB default instead of the owner-approved 1.6 GiB research floor); no GPU fault line, Gemma reloaded on both cards afterwards. **16:35 EDT:** the guard (1.6 GiB floor) stopped the campaign-9 server once more, idle, right after the last arm had finished and been graded: a client holding a 1M-token history took 0.8 GiB in its end-of-run bookkeeping. No GPU fault line; Gemma restored at 16:40 and both cards answer. | Qwen 27B FP8 and H3 remain its optimization lanes. Every research launch passes `B70_GUARD_MIN_AVAILABLE_GIB=1.6`; nothing else runs on the host beside a two-card server (it leaves 2.0-2.3 GiB), and a client that has run 1M tokens is ended only after the server has been stopped. Recheck actual state before using the host. |

No resident server is authorized by this consolidation. Start/measure/gracefully stop experiments; leave cards empty unless the owner explicitly requests hosting. One GPU lane per host at a time. Do not revive the withdrawn September 13
continuous-service rule or superseded relaunch queues.

**October 13, 01:20 UTC — our IQ3 runtime at real context capacities, bit-exact: 37.59/37.77 tok/s (decode/submission) at 4,096 positions, 37.71/37.70 at 32,768.** Packet 44's capacity extension of the integrated runtime ran its full window chain on the cards: at 4,096 (cards 0+1) K0/K1a/K1b/K2/W0p/KD/W2m/WS128/WS64/WSs128 all passed, at 32,768 (cards 2+3) the same chain minus WSs128 all passed. The 128-token twelve-prompt suite, checked against its arithmetic-v2 oracles with no tolerance: 12 of 12 requests exact at both capacities (1,536 tokens, 4,608 retained layer fixtures each), the development prompt 38.33/38.22 tok/s with the same 64 tokens as at 256, the 64-token suite 24 of 24 exact at 37.77/37.57 tok/s, sequential 128-token suite 25.00 tok/s at 4,096. Against the 28.49 tok/s reference at 4,096, the comparable product figure is now sealed. Kernel log clean. Two wrapper incidents, neither a device problem: a storage-admission refusal on the first 32,768 WS64 (build-tree 6 GB cap; fixed by deleting 1 GB of unhashed regenerable state dumps) and a queue-runner stale-log mislabel on the rerun. Receipts: [4,096 chain](experiments/own-xpu-runtime/stage2/packet44-context/receipts-cards01-20261013-c4096/README.md), [32,768 chain](experiments/own-xpu-runtime/stage2/packet44-context/receipts-cards23-20261013-c32768/README.md). Submitted to LocalMaxxing on the owner's go and approved on submission: `cmv6pugme0020oa01fjrho6nx` (37.856264 class-balanced median of prompt-class medians over the 99-interval window; ledger `results/localmaxxing-submissions.md`). Both long-context CPU oracles are complete (598- and 2,271-token prompts, 32 generated tokens each). The CPU-only [packet44 wrapper amendment](experiments/own-xpu-runtime/stage2/packet44-context/CLOSEOUT.md#long-suite-wrapper-amendment-2026-10-13) admits their 32-token manifest and preserves oracle binding checks while explicitly disclosing absent runtime midprompt records. All 131 wrapper checks, eight mini-model requests and 21 seal-admission gates passed. The long-prompt WL device window then passed on cards 0+1 (13:50 UTC): LONG-A (598-token prompt) and LONG-B (2,271 tokens, beyond the 2,048 QSA budget) both 32/32 tokens and 384/384 layer fixtures exact, so the beyond-budget selection path is exact end-to-end on the cards; mid-prompt selection records are not retained by this binary and the receipts record that comparison as not performed. Package published to the catalog as an expert lab replay; clean-build/public-release certification remains draft ([recipe](repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md)).

**October 12, 16:41 UTC — our IQ3 runtime: twelve-prompt median 38.25 tok/s on two cards, every request bit-exact; the reference on the same prompts is 28.49.** The integrated runtime (two processes, one per card; the model's official draft head on the second card supplying the guesses; kernels selected on the card; native controller) ran the reference's twelve prompts twice each in one launch: 24 of 24 requests equal to their own CPU oracles (1,536 tokens and 9,216 layer fixtures, no tolerance), median 38.25 tok/s, range 35.05–41.43, guesses right 79% overall; 39.05 tok/s on the development prompt. Kernel log clean. Read it with one limit: all our runs use a 256-position context capacity while the reference ran with 4,096; the runtime is being extended to 4,096 and 32,768 positions (packet 44) and the comparison is not final as a product comparison until that runs on the cards. This uses the reference table's 64-token definition; the public submission metric needs at least 100 generated tokens per prompt, and that run (128-token oracles exist for all twelve prompts) is being prepared, together with a speed run without the layer-fixture capture that still slows the first eight tokens of every request. [Receipts](experiments/own-xpu-runtime/stage2/packet38-integrated/receipts-cards01-20261012-chain/README.md).

**October 12, 05:56 UTC — our IQ3 runtime: 30.37 and 31.02 tok/s on two cards with the model's own draft head, bit-exact (development prompt).** The official one-token draft head now runs on the second card and supplies the guesses for the two-card pipeline: 53 of 63 guesses right, 64/64 tokens and 384/384 layer fixtures equal to the oracle in two fresh runs, kernel log clean; the draft's device arithmetic equals its host implementation byte for byte. A right guess costs 28.7 ms and a wrong one 55.3 ms. The 28.49 tok/s reference is a median over twelve prompts, so this is not yet the comparable sealed figure: the integrated runtime with a twelve-prompt suite window and the oracles for the other eleven prompts are being built. The root filesystem filled up at 04:57 UTC (packet build trees); 27 GB of regenerable build output was removed and recorded ([record](experiments/own-xpu-runtime/stage2/DISK-CLEANUP-20261012.md)). [Receipts](experiments/own-xpu-runtime/stage2/packet36-draft/receipts-cards01-20261012-chain/README.md).

**October 12, 03:05 UTC — our IQ3 runtime: both cards now work at once; 22.49 tok/s sealed sequential, 24–26 ms per token when every guess is right.** The runtime runs as two processes, one per card; the first card starts the next position from a guessed token while the second finishes the current one, a wrong guess is discarded and redone, and the emitted tokens stay the target's own (64/64 tokens and 384/384 layer fixtures in every run; kernel log clean). Sequential decode is sealed at 22.49 tok/s (one process) and 19.47 (two processes); with guesses fed from the oracle (diagnostic, not a speed result) a token takes 26.2 ms mean. The official draft head agrees with this quantized target 77.3% of the time on CPU, which projects to about 31 tok/s once it runs on the second card (reference 28.49); that packet and a kernel merge are being built. Replaying a recorded launch list is not faster; the token is GPU kernel time. [Note with receipts](notes/2026-10-12-two-card-pipeline-and-kernel-rounds.md).

**October 11, 22:30 UTC — our IQ3 runtime: 17.85 tok/s on two cards, bit-exact.** Same day progression of the exact two-card decode: 3.15 tok/s as first sealed, 12.08 after a linear allocation scan in the two-card backend was replaced by an ordered lookup, 17.85 with specialised non-GEMV kernels selected class by class from a timing run on the card (packet 26). Reference 28.49 tok/s. The token is GPU-bound (53.5 ms of kernel time, 11 ms of host issuing). The fused generic kernels of packets 21/23/24 were bit-exact but 50–100 times slower per launch and are abandoned. GPU work continued all afternoon on the boot that faulted at 09:09 with no further fault. [Scoreboard](experiments/own-xpu-runtime/SCOREBOARD.md).

**October 11, 16:10 UTC — GPU work resumed on the owner's instruction; first bit-exact two-card decode from our runtime.** After the parked process was ended and the four-card health probe passed, the IQ3 runtime reproduced its CPU oracle exactly on one card and on two (64/64 tokens, 384/384 layer fixtures) on the card pair that faulted at 09:09 UTC, with no fault. Measured speed is 2.46 tok/s, and 3.15 tok/s with the faster GEMV variants, against the 28.49 tok/s reference; about two thirds of each token is the runtime's own per-launch timing queries, not GPU work (issuing a kernel measures 3.4–5 µs). A build without that instrumentation and with the fused launch schedule is being prepared. [Note with receipts](notes/2026-10-11-first-exact-two-card-decode.md).

**October 11, 09:10 UTC — FAULT HALT, second GPU fault on this boot; device launches stopped; a reboot is the owner's decision.** A two-card resident decode run of our runtime (packet 16, cards `0000:47:00.0` + `0000:43:00.0`) took a GPU page fault and compute-engine reset on both cards at its first computation after loading 53 GB of weights. The host stayed up; the process (PID 183867) is parked after one cooperative stop and was not killed. First fault of this boot was 02:34 UTC. Most likely a software defect in the never-before-run two-card resident path; evidence and coredumps are in [the incident folder](experiments/own-xpu-runtime/stage2/packet16-decode/evidence/20261011-w2x-two-card-fault/README.md). Before the fault: packet 16's one-card check passed (48/48 layers and token equal to packet 13 on the card, 485 s instead of 5,247 s), and the bit-exactness problem was traced to a build error — Intel's correctly-rounded divide/sqrt options must also be on the link line; with them our own `exp`/`log` match the host on the card for all 2^32 inputs ([forensics](experiments/own-xpu-runtime/stage2/packet17-detmath/evidence/20261011-wb-a-link-flags/README.md)). CPU-only work continues.

**October 11, 07:28–08:11 UTC, first device answer from our runtime:** On card 3 the IQ3 program produced the oracle's first eight tokens (`**Incident Retrospective: Production`), but 0 of 48 layer fixtures are bit-identical to the CPU oracle, because the card's `exp`/`log` and `1/sqrt` results are not glibc's (packet 4 core on card versus host: 50/72 fixtures). The parallel non-GEMV kernels match that core on the same card 72/72 and cut the non-GEMV cost from about 52 s to about 23 ms per token. The two-card within-layer split is bit-identical to one card on layer 0, but its 41 exchanges per layer cost more than the split saves. Arithmetic identity v2 (our own deterministic `exp`/`log`, host RoPE table) is being built so the device can match the CPU oracle exactly; this is a recorded change for the owner to judge. [Note with receipts](notes/2026-10-11-first-device-answer-and-arithmetic-v2.md).

**October 11, CPU-only IQ3 screen preparation:** The [one-card and two-card plans](experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/run-identity.md) now let the coordinator select cards and run on disjoint cards, with automatic fitting and fuller logs for one card. The [two-card ledger](results/qwen38-flash-next-ud-iq3xxs-b70/README.md) retains nine first-repeat rows before a host fault stopped the screen; repeat checks and certification remain incomplete. No GPU work was run in this preparation; the coordinator owns recovery and any new window.

## Four-Card Flash-Next Status

**October 17, 03:35 UTC — own-runtime IQ3 kernel campaign (owner goal: beat Strata on 1 and 2 B70s).** Single-card device windows on card 0, no new faults: packet 46 specialized-layer fusion was exact but neutral (GDN 671 → 675 µs); **packet 47 split32 QSA decode attention is 5.3-8.2x faster** (4K M=1 2377 → 416 µs per QSA layer), exact against its new CPU reference `iq3-p47-qsa-split32-v1`; **packet 48 exact-order GEMV saves about 52 µs per ordinary layer** (expert down 1.66x, M=2 qkv 1.7-1.9x), byte-identical, but its bench controls must be reconciled with production before integration. Packet 49 (in progress) integrates both into the 2-card engine and generates the new full-model CPU oracle. The CPU exact expert path for the 1-card design runs only about 4-5 GB/s, so the 1-card variant needs a large GPU-resident expert cache. Strata reference: 52-62 tok/s on one RTX 5070; our 2-card record is 39.42. Notes: `notes/2026-10-17-own-runtime-packet4{6,7,8}-*.md`, roadmap `notes/2026-10-17-own-runtime-iq3-speed-roadmap.md`.

**October 17, 01:09 UTC — one GPU fault on boot `2cba7160`; recovered under the one-fault rule.** A deliberate reproduction microtest (a oneCCL communicator created while unitrace's L0 tracing layer was active) segfaulted in four ranks. It logged a copy-engine page fault and a BCS engine reset on card `0000:47:00.0` (2 fault lines). One bounded four-card health probe passed at 01:09:51: 4/4 cards, zero new lines. Work continues. A second fault on this boot stops device work until the owner reboots. Root cause of census attempt 1 (00:52, zero faults) confirmed: traced communicator creation crashes the driver. The traced census is **deferred to a fresh boot**; the rendezvous design is ready (`7a5176c5d`). Untraced work continues through a narrowly scoped resolved-fault admission (exact recorded lines, passing probe, nothing new). Evidence: `data/2026-10-17-flash-next-trace-feasibility/fault-20261017T010916Z/`. Also assessed NVIDIA FP4-Local: [note](notes/2026-10-17-nvidia-flash-next-fp4-local-assessment.md).

**October 17, 00:20 UTC — Flash-Next M=2 census tracing feasibility settled with device microtests.** The lab's pinned unitrace lacks ITT. An ITT build of the same source (`/home/steve/src/pti-gpu/build-unitrace-itt/`) **sees every kernel inside XPU graph replay, but only if tracing was active during capture** (0 kernels when capture was paused). A paused tracer does not stall 4-rank oneCCL init. Traced CCL ranks segfault at exit after finishing their work, with zero GPU faults. The census packet is being resealed: resume before capture, ITT build, sampler writes off the raid, traces on local ext4. Next: run the graph-trace census and rank the M=2 time sinks. MoE GEMM study (`notes/2026-10-16-flash-next-moe-m2-lever-study.md`): no exact tile/split lever remains without census evidence. [Microtest note](notes/2026-10-16-flash-next-trace-feasibility-microtests.md).

**October 16, 23:21 UTC — Flash-Next FP8 record REPRODUCED on boot `2cba7160`.** The sealed A367 record replay (seal `bb473f8e`, run `a367r-20261016T224454Z`) used the record's server profile (nice 0, all CPUs, OMP=1). It produced **12/12 outputs bit-identical** to the September 13 record, with every quality gate equal. Class-balanced median **47.110 tok/s** (record 46.854); all-prompt 46.534 (record 46.322). That is noise-level, so no submission. One SIGINT after the suite, 13 s teardown, returncode 0, full 305 s watch, zero GPU fault lines. Generation need was 104,784,640 KiB, about 1.9 GB above the live reserve. Two replay packet bugs were fixed on the way: a self-match admission refusal (my command line), and a sampler cmdline mmap-lock stall (`7aca7df2a`). Ledger: [notes/2026-10-16-flash-next-a367-record-replay.md](notes/2026-10-16-flash-next-a367-record-replay.md). Next: harden the sampler (separate attribution thread), then a measured M=2 device census for the next speed lever.

**October 16, 19:31 UTC — Flash-Next A367 calibration PASSED on boot `2cba7160` (seal `b75d9f86`, prereg `d5959d82`).** Zero generation; the certified A367 recipe loaded on four cards (weights 556 s), captured graphs (44 s) and was ready at 19:25:38. After the 20 s plateau, one SIGINT at 19:25:59; all owners were gone with returncode 0 at 19:26:14; the 305 s watch completed; zero GPU fault lines. Observed host need was **102,840,824 KiB** (MemAvailable 121.6 → 16.3 GB; GPUActive about 86.9 GB of designed UVA expert rows). Three earlier attempts stopped on packet bugs, each fixed and resealed with owner approval: a 121-char ipc path (`440daf116`); a sampler `getsid` ESRCH race (`440daf116`); a shared Triton cache on ntfs-3g, whose non-atomic rename-over led to scratch moving to local ext4 and the load budget going to 1800 s (`a6b6d14b5`). Every attempt ended with zero faults. The derived packet-4 fixture floor is 123,229,432 KiB, which exceeds what this fenced host can ever have available (about 118.8M KiB); need + reserve is 114,840,824. The floor is an owner decision and is unapproved. Ledger: [notes/2026-10-16-flash-next-a367-calibration-attempts.md](notes/2026-10-16-flash-next-a367-calibration-attempts.md). Next: a record-replay supervisor (the calibration lifecycle plus the frozen realistic-suite client) to confirm 46.854 on this boot, then a measured M=2 census.

**October 16, about 12:50 UTC: owner-authorized reboot for the Flash-Next A367 calibration.** The old boot `13858eef` had 18 GPU fault lines from October 11 (IQ3 incidents), and the calibration's health gate requires zero. The owner authorized one reboot, approved exempting prior-boot evidence latches (`73c293ce7`), and approved the exact calibration-only memory sentence (114,000,000 KiB start floor, seal `a15e5223…`; record `data/2026-10-16-flash-next-a367-reseal/owner-approval-20261016.json`). The model payload (144/144) and the clean source export pass (`60d4ee278`). The raid disk `/mnt/raid-models` was a stale mount after USB re-enumeration, not a failing disk. Both USB data disks must be remounted by UUID after the reboot (usb-models `4E0E66ED0E66CD91`, raid-models `1498256698254816`; not in fstab). Next: verify the fence, remount, confirm zero faults on the new boot, then run `experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/LAUNCH-RUNBOOK.md` once, with no generation.

**October 11: the fourth incident is [closed as a router-padding software defect](notes/2026-10-11-fourth-incident-closed.md).** The fixed experimental attempt-8 line loaded and finished its four-card profiling run with no boundary violations or new kernel faults, then stopped cleanly. Available host memory fell from **119.17 GB** after hashing to **47.10 GB**, with **77.08 GB** peak pressure, compared with attempt 8's **75.45 GB**. This was one run with no generation requests, and missing card-memory measurements still prevent qualification; it does not establish the certified recipe's memory need or change its floor. Next is a bounded generation screen under the checks, then certified-recipe calibration when the owner approves its floor; current coordinator admission still applies and LTX stays off.

The certified FP8 result remains **46.854250 tok/s**, with its exact identity and gates in the [closeout](results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md), [handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md) and [reproduction
guide](repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md). Reopening diagnostics and CPU preparation do not replace that record.

## LTX Continuing Video

The recorded production arm is **137, stopped under the owner's existing instruction**. Packet **138 is sealed and CPU-tested; native qualification is pending**. Its scheduled text prefetch is off by default, compares unchanged conditioning when produced and consumed,
and predicts 0.095 seconds/chunk saved without a native measurement. It retains at most 1.3125 MiB extra CPU conditioning; overlap and memory peaks remain unmeasured. See the [design](notes/2026-10-10-continuation138-stream-design.md), [build
receipt](experiments/ltx25-b70/data/resume-20261008/continuation138-build.json) and [coordinator launch packet](experiments/ltx25-b70/recovery/20261010-continuation138-stream/LAUNCH.md).

The continuing-video line uses 256×256, 145-frame chunks with 144 new frames (six seconds). For packet 135 GC-10, the first uninterrupted 52 periods had a **5.2415 s median**; the whole 747-period session had a **5.553 s raw median** affected by
client pacing. Neither the short prefix nor the later hold-free diagnostic establishes sustained unthrottled speed. [Corrected metric ledger](results/ltx25-continuation-stream-pacing-2026-10-10.md).

The goal remains coherent continuing video faster than playback, then higher resolution. Preserve the accepted short-window text-encoder reference (`stability-01-w93c-*`, `experiments/ltx25-b70/data/stability-01-window-prereg.json`) and exact
continuation lineage. Do not blend it with padded-encoder or other output-changing baselines. Unaccepted soft-latent, mixed or guide-anchor alternatives remain separate.

The **9 GiB device floor, 5 GiB capture reserve, 0.75 GiB screening band and 50 GiB disk reserve** remain in force. Preserve the full snapshot schedule; the optional reduced `a-xpu3-sync` barrier still needs owner acceptance. The latest larger-chunk
screen permits considering 169 frames with graphs off, but it was not launched and predicts no gain; larger graph arms remain unqualified.

Owner seam/audio acceptance and portable public runtime reconstruction plus independent replay remain open. The [public recipe](repro/ltx25-continuation-stream-b70-145f-20261010/README.md) records these limits. Packet 138 and any relaunch wait for
the host halt decision and their own admission; old streaming requests do not erase those gates.

Preserve `/home/steve/src/ComfyUI-ltx25-baseline`, `/home/steve/.venvs/ltx25-baseline`, `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`, `/home/steve/ltx-stream/`, all reference/unique captures, negative runs, manifests and restore receipts.
Approved duplicate retirements are recorded in lane notes; a later full proof must restore the required ordinary-copy layout first.

## Our Own Intel Xe Runtimes

**October 14, packet 45 route+gather repaired and CPU-qualified:** The owner reports K0, K1a and K1b passed both card pairs under boot `13858eef`, then K2 failed. The comparison's baseline left two expert lookup tables empty. The same failure reproduces on CPU; the retained K2 events stop before rank32 runs. The repair fills those tables and leaves the original reference answers unchanged. The new compiler gate covers every registered fusion: 36 failures before, 2,232 passing checks after. The complete CPU suite passed, including 79 miniature runs, six real-model runs, six draft checks, all 27 rehearsal windows and 88 blocked-launch checks. The new seal binds 25 gate receipts. All five device binary hashes changed; their interface is unchanged, so the next step is fresh device chains under the new seal. All 150 protected files are unchanged, and no device program ran. [Root cause, fusion audit, counts and hashes](experiments/own-xpu-runtime/stage2/packet45-merged3/ROUTE-GATHER-CLOSEOUT.md). This does not change host ownership or claim that the cards are idle.

**October 14, packet 45 storage admission repaired:** The owner reports that K0 and K1a passed both card pairs under boot `13858eef`; the next stage refused storage before device contact. The old build limit could not hold the merged artifacts plus the next write. The new limit follows the retained chain's size and current disk space, keeps the 8 GB free floor, and reserves room for another full chain. CPU rehearsal now checks the real write sizes. The audit also fixed missing context and retained-output growth in later windows. All 27 rehearsal windows and the complete CPU suite passed, including 79 miniature cases, six real-model cases, six draft arms and 88 blocked-launch checks. The new seal binds 24 gate receipts. All 41 compiled artifacts and all 123 protected files are unchanged; no device program ran. Fresh device chains need the new host seal. [Design, full admission audit, counts and hashes](experiments/own-xpu-runtime/stage2/packet45-merged3/STORAGE-ADMISSION-CLOSEOUT.md). This does not change host ownership or claim that the cards are idle.

**October 14, packet 45 host gate repaired:** The owner reports that the NaN fix passed all 218 fixture checks and 216 linked checks on both card pairs. The next rejection was an old host check expecting four owners instead of the merged runtime's five. That check now validates each owner by name and keeps every safe-exit requirement. The sibling audit also fixed related K2 and CPU rehearsal assumptions. All nine coordinator windows passed on CPU at 4,096 positions with each draft placement and at 32,768 with rank0. The complete CPU suite passed again and the new seal binds 24 gate receipts and 41 build artifacts. Every binary hash is unchanged, including all five device binaries. No device program ran; all 49 protected fault/incident files are unchanged. Fresh device chains need the new host seal. [Repair, audit and hashes](experiments/own-xpu-runtime/stage2/packet45-merged3/SEQUENTIAL-OWNER-CLOSEOUT.md). This does not change host ownership or claim that the cards are idle.

**October 13, packet 45 K1a CPU repair:** The coordinator's first device chain stopped at the same HC activation output on both card pairs. CPU reproduction found that case 54 contains a NaN whose payload could differ between compilers; the pre-seeded error case is case 53 and passes unchanged. The repair defines that NaN result consistently across the baseline and merged kernels. The new six-compiler-setting gate passes all 4,752 checks; the full original CPU suite and reseal passed, including 79 fresh mini cases, six real-model cases, and 88 blocked-launch admission checks. All five device binary hashes changed; device qualification is pending coordinator recovery and fresh chains. [Repair evidence and handoff](experiments/own-xpu-runtime/stage2/packet45-merged3/HC-ACTIVATION-CLOSEOUT.md). No device program ran during this repair. The existing fault latch and coordinator commands remain untouched. New binary identities require fresh chains after coordinator recovery; the earlier partial chains cannot qualify this repair. This does not change host ownership or claim the cards are idle.

**October 13, CPU-only packet 45 merge:** [Packet 45](experiments/own-xpu-runtime/stage2/packet45-merged3/README.md) combines packet 40's suite and draft controls with packet 44's three context capacities, the measured packet 42 kernel candidates and packet 39 launch fusions. Drafting can run on either rank. Rank 0 gets its own output head and a 22/26 target-layer split; the original rank-1 placement keeps 24/24. Independent protocol and memory reviews found and fixed handoff, rollback and allocation-accounting issues. The [build receipt](experiments/own-xpu-runtime/stage2/packet45-merged3/build-receipt.json) binds the final CPU gates and binaries. No device program ran in this work, and no merged speed or card-memory result is claimed. The coordinator's next step is the fresh [nine-window chain](experiments/own-xpu-runtime/stage2/packet45-merged3/WINDOW.md) at each capacity and placement under current host admission. This entry does not change host ownership or record the cards as idle.

**October 11, CPU-only first-token correctness check:** The reported wrong answer was actually the incoming prompt; at 06:25 UTC the device job had read 27 of 87 prompt tokens and had emitted no answer. A fresh CPU pass completed all 48 layers, matched the runtime-order CPU oracle's 48 hashes, and predicted the same first token, `**`; the [investigation](notes/2026-10-11-first-token-correctness.md) retains the text, fixtures and regression checks. Device agreement remains pending until that existing job writes its final-prompt fixtures; no GPU run or production arithmetic change was made here.

**October 11, CPU-only packet 14 two-card decode:** [Packet 14](experiments/own-xpu-runtime/stage2/packet14-tp2/README.md) splits dense rows, expert IDs and attention state across two owners, using ordered peer gathers that preserve the one-card calculation. All 18 CPU integration checks, the full tensor coverage check and the SYCL build pass; no GPU ran, and the extra exchanges mean a 1.5× gain is still unproven. The coordinator can next compare layer 0 and then the first token on cards 2+3 against packet 13's completed one-card result using the [gated commands](experiments/own-xpu-runtime/stage2/packet14-tp2/WINDOW.md).

**October 11, CPU-only IQ3 oracle rebase:** [Packet 3](experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/README.md) now follows the runtime's fixed arithmetic and completed the 87-token incident prompt plus 64 generated tokens, averaging 9.17 seconds per decode token. Exact CPU reference checks pass, with all 48 layer states saved for the first eight predictions; the first difference from the old BLAS oracle is token 18, with logit margins of 0.375 versus 0.250. No GPU ran here; these fixtures are ready for device comparison, while device and full-model repeat checks remain open.

**October 11, CPU-only packet 13 integration:** [The integrated IQ3 program](experiments/own-xpu-runtime/stage2/packet13-integrate/README.md) now uses the measured kernel choices, streams one layer's weights and selected experts on one card, and can retain weights across two cards using the existing sequential layer split. The CPU mini-model checks and SYCL build pass, and the real first layer's new hash is saved; comparison waits for the oracle's new arithmetic order. No GPU ran here; the coordinator has a [bounded card-3 command](experiments/own-xpu-runtime/stage2/packet13-integrate/WINDOW.md) to process the whole first prompt, emit eight tokens and record where the time goes, with cards 2+3 reserved for a later resident test.

**October 11, CPU-only packet10 exactness repair:** The coordinator's first
card-3 gate failed an IQ3_S output comparison after 57 checks; teardown was
clean and no kernel faults were recorded. [The repair](experiments/own-xpu-runtime/stage2/packet10-kopt5/README.md#october-11-exactness-repair)
reproduces a NaN sign change when the compiler specializes the expanded path,
preserves the original bits explicitly, and adds the missing CPU comparisons
and detailed failure reporting. The original device row was not saved; the CPU
reproduction is separate evidence. Original receipts and the latch remain.
No GPU ran in this repair; the coordinator owns the fresh exactness gate and,
only if it passes, timing.

**October 11, CPU-only two-card exchange preparation:** The [tensor-parallel design](experiments/own-xpu-runtime/stage2/TWO-CARD-TP.md) and [packet 12 harness](experiments/own-xpu-runtime/stage2/packet12-peer/README.md) prepare both cards to work within each layer. CPU tests and the SYCL build pass; no device program ran. The design corrects the count to 48 layers and keeps exact output agreement as a gate: simply adding two partial sums can change answers. Peer support and exchange timing remain unmeasured. The coordinator's next step is the documented cards-2/3 transport window after admission; the speed scenarios are calculations, not model results.

**October 11, CPU-only packet9 repair:** The coordinator's 04:40 UTC card-3 attempt stopped before completing any checks because staging buffers reused names; teardown was clean and no kernel faults were reported. [The repair](experiments/own-xpu-runtime/stage2/packet9-kopt4/README.md#october-11-allocation-and-failure-classification-repair) gives each buffer a unique name and separates infrastructure aborts from output mismatches and kernel faults. All 31 Python tests, 28 mock expert cases and the SYCL build pass. Original evidence is preserved; new scratch is removed. No GPU ran in this repair. The coordinator owns the next card-3 exactness and timing windows; device qualification is still pending.

**October 11, CPU-only round-3 kernel preparation:** [Packet 8](experiments/own-xpu-runtime/stage2/packet8-kopt3/README.md) shares quantized-weight decoding work, compares constant tables with shared local tables, and selects kernels by the measured matrix shapes. It also prepares one launch for all ten experts’ gate/up projections and a separate down launch. The CPU exactness checks and SYCL build pass; all 1,224 tensors have a checked operation mapping. No GPU ran, and no new speed winner is claimed. The coordinator owns the two documented card-3 exactness and timing commands; the previous shape choices remain until measured replacements pass.

**October 11, CPU-only round-2 kernel preparation:** [Packet 7](experiments/own-xpu-runtime/stage2/packet7-kopt2/README.md) is ready for card 3 to measure its memory-reading ceiling, then compare split sums, wider row loads and grouped projections. The CPU checks and SYCL build pass; no GPU command ran here. Split sums have a new fixed arithmetic order, so full-model output parity remains unproven. The coordinator owns the two documented device windows; the speed estimates are hypotheses.

**October 11, CPU-only kernel optimization preparation:** [Packet 6](experiments/own-xpu-runtime/stage2/packet6-kopt/README.md) adds separate packed-matrix candidates with wider loads, shared unpack work and a four-matrix diagnostic. The SYCL build, ten protocol tests, 207,360 decoded values and 1,416 CPU row comparisons pass. Its new reduction changes 134 FP32 accumulators but no final 16-bit fixture outputs; full-model parity remains open. No GPU binary ran. The coordinator owns the documented card-3 exactness and timing windows; no new speed is claimed.

**October 11, CPU-only copy measurement preparation:** [Packet 5](experiments/own-xpu-runtime/stage2/packet5-h2d/README.md) now builds our bounded native copy test at the actual expert sizes, with pinned/pageable buffers and a copy-versus-compute overlap check. Eleven Python tests, host ownership checks and the SYCL build pass; no device binary ran and no transfer speed is claimed. The coordinator can run the documented card 3 window next, then use its measured copy rates in the one-card plan.

**October 11, CPU-only one-card plan:** The [IQ3 one-card design](experiments/own-xpu-runtime/stage2/ONE-CARD-PLAN.md) follows the two-card target and recommends keeping dense weights and a cache of experts on the card, copying missing experts from host RAM. A 24 GB cache has a calculated transfer-only ceiling of 39.50 tokens/s at the assumed 19 GB/s rate; this is not a measured runtime speed, and actual memory fit remains to be checked. First measure our copy speed on this host and collect the CPU oracle's expert choices; this documentation work used no GPU or model payload.

**October 11, CPU-only:** the owner's first real-model target for our own engine is now the IQ3 quantized compressed version on two B70s; the 27B FP8 work remains documented. [Stage 2 packet 2](experiments/own-xpu-runtime/stage2/packet2/README.md) adds the GGUF loader and packed kernels, with exact CPU checks and a successful SYCL build. Nothing ran on a GPU in this task; the next step is the [bounded one-card device comparison](experiments/own-xpu-runtime/stage2/packet2/WINDOW.md) in a separately authorized window.

The October 10 [objective](docs/own-xpu-runtime-objective.md) is our own model-specific code. Other projects supply credited ideas, not a code base. Official-publisher or Unsloth weights are permitted; another source needs written justification and
owner approval. The earlier ISTA IQ3_S proposal is withdrawn. These CPU packets do not qualify a native runtime or authorize a GPU window.

- **27B stage 1:** [identity packet 1](experiments/own-xpu-runtime/stage1/packet1/README.md) freezes tokenizer requirements, twelve saved answers and 1,606 tensors. [Packet 1b](experiments/own-xpu-runtime/stage1/packet1b/README.md) adds synthetic CPU
  arithmetic/readers. [Packet 2](experiments/own-xpu-runtime/stage1/packet2/README.md) checks the existing official USB weights: 67 large-file hashes, 14 small publisher files and repeated CPU samples. Text plus MTP requires 29.945 GB with on-card
  embedding; actual one-card fit is unproven.
- **Native preparation:** [packet 3](experiments/own-xpu-runtime/stage1/packet3-prep/README.md) tests memory ownership with mocks and compiles, but does not run, SYCL. Attention gating is corrected to sigmoid. [Packet
  4](experiments/own-xpu-runtime/stage1/packet4-prep/README.md) maps 44 source boundaries and tests synthetic capture; the native worker and internal-state bindings remain incomplete. A367 used a host environment whose extension differs from the
  reopen image; no certified image has been established.
- **Fixture-window blockers:** the [memory admission review](experiments/own-xpu-runtime/stage1/packet4-prep/MEMORY-ADMISSION-REVISION.md) derives a **133,542,784 KiB floor**, above current capacity; no lower passing floor is justified. Eighteen
  certified kernel files match, but a historical model-receipt hash mismatch and separate native admission also block the [planned 60-minute Flash-only window](experiments/own-xpu-runtime/stage1/packet4-prep/WINDOW-RUNBOOK.md). Any admission revision needs the
  driver's document-bound owner receipt.
- **A367 calibration, CPU preparation October 11:** the [load-only packet](experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/README.md) is prepared for the first certified-recipe launch after the fourth incident. It makes no generation requests, measures memory through a 20-second ready hold and graceful stop, and proposes a floor only from a complete clean run. The default floor, separate native admission and receipt mismatch remain; any calibration-only start-floor exception needs a separate explicit owner decision. No model was launched during preparation.
- **Flash-Next stage 2:** [packet 1](experiments/own-xpu-runtime/stage2/packet1/README.md) freezes official tensor identity and twelve certified answers; the two-card official-weight plan needs about 65 GB of experts off-device before workspace.
  [Packet 1b](experiments/own-xpu-runtime/stage2/packet1b/README.md) passes synthetic CPU math/repeats, preserving Flash's BF16 inter-row state versus 27B's FP32 state; device parity remains unverified. The
  [plan](experiments/own-xpu-runtime/STAGE2-PLAN.md) separates calculated bandwidth from measured speed.
- **Separate quantized compressed version:** Unsloth UD-IQ3_XXS has its own [lane/CPU packet](experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/README.md). All three file hashes, tensor census and fresh-process sampled CPU repeats now pass,
  superseding the incomplete-download note. Packed target weights require **53.305 GB across two cards** with large lookup tables off-device; fit, complete-model answers and speed remain unmeasured. Next: its tokenizer/operator oracle. The [pinned
  llama.cpp measurement baseline](experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/README.md) builds for B70 and passes CPU help/version; its proposed target-only twelve-prompt, two-fresh-process run uses full 16-bit KV and still needs
  native admission.
- **Identity boundary:** IQ3 must be lossless and deterministic against its own bytes and CPU dequantization oracle; FP8 differences are informational, not a tolerance gate. Never call it the FP8 model or compare it as the same record. The [Unsloth
  header census](experiments/own-xpu-runtime/stage2/packet1c/README.md) finds no extra MTP block in the three checked variants; packed-weight arithmetic alone does not establish runtime fit. Other variant acquisition, quality and device work remain
  separately gated.

**IQ3 CPU oracle, October 11:** [Packet 2](experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/README.md) now follows the official Flash-Next sigmoid gates and completed 64 tokens each for the incident and code-review prompts, at 43.33 and 46.18 seconds per decode token. The three-hour CPU-only run stopped cleanly with 128 generated tokens, two complete sets of layer fixtures and a third prompt stopped after 32 layers; peak memory was 1.06 GB. Baseline differences are informational, full-model repeat checks remain open, and no GPU work was performed.

**October 11, CPU-only IQ3 decode orchestration:** [Stage 2 packet 3](experiments/own-xpu-runtime/stage2/packet3/README.md) now checks every tensor's placement and runs the ordered step on synthetic CPU inputs; 23 Python tests and 18 C++ cases pass, including exact NumPy comparisons and fresh-process repeats. Its plan has 1,873 dispatch sites and 4.951 GB of weight/lookup reads per token, which are planning counts, not measured speed. The step follows the corrected sigmoid GDN gate; device execution and host lookup mapping remain open, and no GPU or model payload was touched.

**October 11, CPU-only IQ3 timing preparation:** [Packet 2 timing window](experiments/own-xpu-runtime/stage2/packet2/README.md#timing-window) now prepares the real layer shapes and ten selected experts, with a whole-GDN GEMV sequence and a fault-watched receipt. The native binary compiles; CPU plan, receipt and ownership checks pass. No timing window was run. The coordinator’s next step is the bounded card-3 measurement against the 507/537 GB/s byte floors.

**October 11, CPU-only IQ3 integration:** [Stage 2 packet 4](experiments/own-xpu-runtime/stage2/packet4/README.md) builds one runnable program and its SYCL target; the two-layer mini-model matches Python exactly. The real first layer completed all 87 prompt tokens but differs from the CPU oracle in 2,293 of 10,240 BF16 values, so its quality gate remains failed. No GPU was used; the coordinator’s first card-3 layer comparison is prepared, and full-step checks must wait for exact agreement.

**October 11, CPU-only expert-path preparation:** [Round 4 packet9](experiments/own-xpu-runtime/stage2/packet9-kopt4/README.md) adds one gate/up launch, one down launch and an ordered weighted-sum launch, plus whole-layer GEMV timing. CPU checks and the SYCL build pass; no device program ran. The census corrects the planning inputs to 36 GDN + 12 QSA layers and 19.712 MB per ordinary expert block. The coordinator can next run the packet's card-3 exactness and paired timing commands after admission. Full-model output checks and actual speed remain pending.

**October 11, CPU-only exact weight expansion:** [Round 5 packet10](experiments/own-xpu-runtime/stage2/packet10-kopt5/README.md) prepares expanded dense weights and two output-head kernels. The budget is 55.194 GB of weights, or 63.348 GB with the existing reserve; routed experts remain packed. CPU bit checks and device-program compilation are complete, but no GPU program ran. The speed estimates remain below the reference, and native fit and full-model quality are untested. The coordinator's next step is the packet's card-3 exactness and paired timing commands after admission.

**October 11, CPU-only packed expert decode:** [Round 6 packet11](experiments/own-xpu-runtime/stage2/packet11-kopt6/README.md) reads native Xe2 assembly and prepares three exact decode alternatives. Integer unpacking and sign handling take most of the visible instructions; the full IQ2 register table spills, while the packed pipeline has a smaller arithmetic body. All CPU checks and device-program builds pass. No GPU program ran, and speed predictions remain unverified. The packet gives the two card-3 commands for the coordinator after separate admission; the existing host halt remains in force.

**October 11, CPU-only non-GEMV arithmetic correction:** [Stage 2 packet 15](experiments/own-xpu-runtime/stage2/packet15-nongemv/README.md) now checks the frozen Packet 4 core. All 72 cases pass in two fresh runs under each compiler, and all 18 protocol tests pass for each build. The old Torch reference still differs in twelve cases and is kept as a diagnostic. The prepared card-3 window compares against Packet 4 on the same device; native exactness and timing remain pending. No device ran and the live runtime is unchanged.

## Two-Card Lanes And Context Work

**Qwen 27B FP8:** optimize the official FP8 model with native MTP and full 16-bit KV; DFlash stays excluded by the September 14 owner decision. Read the [multi-host handoff](experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md), [closed
experiments](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md) and [TP2 recipe](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) before runtime changes.

The October 7 public-package acceptance passes short and 2K–8K long prompts at 16/32/64 users, two passes exact to the single-user answers. **875 tok/s is aggregate short-prompt throughput at 64 users**, not a single-user or all-workload rate. The
same acceptance session recorded a 90.31 tok/s recommended-profile median. Evidence: `experiments/qwen38-27b-b70/data/2026-10-07-fp8-two-card-multi-user/`. Clean-host qualification and multi-user drafting (R314, local only) remain open.

**MiniMax-H3:** the October 10 owner decision accepts **Comfy-Org's pruned BF16 denoiser with fitted AdaLN**, including that source as an explicit exception to the source rule. The lab analyzed this published file; it did not produce the fit. The
fit-search/redownload queue is superseded. The [draft package and recipe](repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md) targets turin, two B70 and 15 GiB RAM.

The measured eight-clip batch is **396.6 seconds/clip**, with 32 matching hash checks and eight repeat passes against this denoiser's own reference. That exact scheduling result is not losslessness versus the official model. The older 800.8 s/clip
baseline is ledger-only, with raw receipts not retained. Publisher input pins are checked; baseline/reference receipts, clean build/runtime, independent full-suite repeat and portable release evidence remain missing. Turbo LoRA and other changed
arithmetic stay separate. H3 GPU work must use `experiments/minimax-h3-b70/scripts/smoke_h3.sh` and its memory watchdog.

**Long-horizon context (restarted October 10):** the [program charter](docs/long-horizon-context-program.md) holds the problem, every idea and the benchmark. At the fast scale (32K live cap, 240K history, two seeds) archive-and-recall is ahead on every axis (63/65 against 56/65 window-drop, 48/65 compaction) and as quick as any. On the new rule and method questions **no method kept a rule stated at the start (0/5 each)**; the archive method kept the method only. Permanent rule lines in the pinned state fix that at 240K (5/5, 35/39 overall). The same method then read a **1M-token history through a 32K live budget: 163/203 probe answers (80 %), flat with distance and with history length, 8.7 minutes per 100K with no slowdown** (a stopped run: the final write wiped the answers file; the probe answers are rebuilt from the transcript). Weak spots at scale: old values 64 %, the pinned rule lapsing in use 76 %. **The keeper** (campaigns 6-8) then replaced it as the lead: the agent manages nothing; the harness archives what it cuts, has the model rewrite NOTES (RULES / STATE / OPEN) at each cut and repeats the rules at each question. 39/39 and 46/46 on two 240K rule streams, and **226/228 (99 %), not void, on the 1M stream in 83 minutes with 865 model calls** (protocol arm: 2,170 calls). The same policy is `tools/ctxkeeper/`, an OpenAI-compatible proxy (standard library, 24 tests): after the fixes its first runs prompted, 39/39 and 44/46 at 240K and **222/228 (97 %), not void, on the 1M stream in 95 minutes**, with an agent that sends its whole history and manages nothing. The summary baseline (C32) scored 23/29 in 29 minutes, below window-drop. **Campaign 10 (October 11 evening): in-place notes** (the notes call is the live conversation plus one message, a changes-only reply written with thinking and checked by the harness, then every turn in view is moved out) give the same answers in about 40 % less time: 39/39 and 46/46 at 240K in 9.5 and 8.5 minutes, and **228/228, not void, on the 1M stream in 50 minutes**, with NOTES that an audit against the true ledger finds right in all 63 versions (`notes_audit.py`; the full keeper lost five lines once on the same stream, and notes written without thinking carry 2 to 8 wrong values a run whatever they score). **Retrieval alone** (every item in a store outside the sandbox, BM25 over sentences, no notes) equals the keeper at 240K (39/39, 45/46) and for the first 420 items at 1M, then falls behind (56/70 in the last third; the rule lost 4 times in 29; final list not answered) and is worse on a stream that refers to things indirectly (10/15 against 15/15). Campaign 10b (October 12, 00:01-02:08) ran the fully-checked in-place arm on both 240K seeds: 39/39 and 46/46 in 10 minutes (NOTES audit: nothing wrong on seed 0 and at 1M, one counter wrong for a stretch on seed 1), so **313 of 313 over the three rule streams**; and on the hard stream the keeper with retrieval at question time added reached 47 and 46 of 50 (42 and 43 without). Not yet run: in-place notes in the proxy, the keeper with retrieval at 1M, the plain 200K-window baseline at 1M, second seeds at 1M and of the hard stream, the proxy under a real agent. Results, plans and the reason round 3 stopped: [lane note](experiments/qwen38-27b-b70/notes/2026-10-10-context-16k-baseline.md). One seed per new axis; one synthetic task family; not yet a general memory claim. **Campaigns 11 and 12 (October 12): the proxy has the fast notes.** `tools/ctxkeeper --notes-mode inplace` scores 39/39 in 8.8 minutes and 46/46 in 9.7 on the two 240K streams (the harness arm: 9.9 and 10.0; the proxy's full-rewrite form: 17 and 18), with no value wrong in any saved NOTES version, and **220 of 228 on the 1M stream in 53 minutes, not void** (the bar set beforehand: 220 in under 70; its first build, the night before, scored 216 in 76). Seven of the eight misses are one confusion (the search tool counted messages, the questions count items); code state p fixes that (`--recall-label`), was reviewed read-only before running, and scored **39/39 in 8.5 minutes, 46/46 in 9.4 and 226 of 228 at 1M in 50 minutes**: within two answers of the harness arm and as fast. The harness keeper on a second 1M stream: 210 of 222 in 50 minutes (the first stream: 228 of 228), so 438 of 450 (97.3 %) over two streams; seven of the twelve misses are one question item that an ordinary cut moved out of view while the model was still searching for it (a hole to close: an open question must survive every cut). **A rule that names nothing** ("any figure below zero is reported as the word overdrawn"): the keeper answered the governed questions 16 of 16 over two seeds, retrieval alone 0 of 16. Hard stream, second seed: keeper with retrieval 46 of 49 in 23 minutes (the day's stricter checks slow that stream; fix in code state p, not yet run there). Built and not yet run: a real-code task (`make_repair_tasks.py`: more-itertools with 40 injected defects, tickets one at a time, standing instructions that arrive mid-task). Still the owner's decision: which real agent program to put in front of the proxy. **Released 2026-10-14 as ctxkeeper 1.0.0** (pip wheel, Docker, `--recipe agent|qwen`; [release](https://github.com/steveseguin/b70-optimization-lab/releases/tag/ctxkeeper-v1.0.0), [closeout](experiments/qwen38-27b-b70/notes/2026-10-14-ctxkeeper-1.0.0-release-closeout.md)).

**Context/retention:** October 8 owner rule: decide studies within a few hours using pilots/concurrency/early stops; no more full-day soaks. The [LongMemEval stage-2 result](experiments/qwen38-27b-b70/notes/2026-10-08-longmemeval-stage2-result.md)
recommends archive-and-recall within 32K for that study; the 27B self-judge is secondary evidence, and abstention is the next weakness. Do not turn this into a general memory or speed claim.

For the two short controlled documents, [direct full-source reading](experiments/qwen38-27b-b70/notes/2026-10-07-full-source-screen-result.md) got 24/24 on each in one cold request; this is a static final-answer comparison, not an intermediate-state
or general speed guarantee. The [history study](experiments/qwen38-27b-b70/notes/2026-10-07-history-state-study-result.md) failed on ownership joins despite exact numeric checkpoints. Preserve its archive inventories and failed revisions 3/4; keep
t03/t04 and the other held-out rows unused. Do not reopen short-document interface tuning; new work needs a concrete streaming/audit requirement or relevant independent history, as the [research
priorities](experiments/qwen38-27b-b70/notes/2026-10-07-context-research-priorities.md) specify.

[Project decision recall](experiments/project-decision-recall-20261007/RESULTS.md) covered 38/38 criteria by ordinary search/read; complete-source delivery missed one caveat (37/38). These were hosted assistant sessions over curated records, not a
local-model qualification. No structured memory store or worker integration is admitted. The [local worker scoped attempt](experiments/local-coding-worker/scoped-task-20261007/CLOSEOUT.md) made no edit or accepted submission; preserve prior failed
worker/recall trials and five unused tasks. Further worker tuning/integration is parked.

## Known Issues And Next Actions

1. **Owner decision dated October 11:** the fourth software incident is closed; the certified-recipe calibration floor still needs approval. Follow the bounded-generation next step above with current coordinator admission; the old engine-window receipt is spent and LTX stays off.
2. Finish the CPU runtime tokenizer/operator and adapter work, retaining the fixture memory-floor, receipt and native-window blockers above. Keep H3's missing publication evidence explicit; its source acceptance is already resolved.
3. Keep each certified result under its exact model, weights, arithmetic, topology, metric and quality identity. Preserve historical high scores and negative patches; host/session drift does not by itself justify merging different benchmark
   identities or lowering a record. Consult the [reproducibility map](docs/current-reproducibility-map.md), [effort index](docs/model-effort-index.md) and [scoreboard](results/scoreboard.md).
4. The GDN PR #45 community contribution still needs its actual mixed-session soak before production promotion; shorter strict-oracle passes do not verify that incident. Historical replay hash mismatches remain evidence, not permission to repin
   shared tools blindly. Follow the [replay audit](notes/2026-09-09-replay-and-validator-audit.md).
5. ML Bottleneck automatic refresh stays paused: 4070 interpretation, nine ambiguous measurements and calibration thresholds block publication in that repository's `docs/refresh-review-2026-09-08.md`. Keep its published evidence unchanged. Duplicate
   LocalMaxxing record `cmu6ytvxr082alq015dpjgiz4` remains flagged for owner-only withdrawal; canonical record is `cmu6ytqyr0827lq01b76whp6d`.
6. A reproducible package needs pinned inputs, a clean build, unchanged quality gates and graceful teardown, with the public asset/replay checks required by [AGENTS.md](AGENTS.md). An older runnable command, CPU test pass or accepted model choice
   does not satisfy missing gates.

## Storage And Recovery

**October 18, disk9 screen audit:** root had **30.221 GB free at 23:49:44 UTC**;
the requested **34 GB was not reached**. No eligible bulky screen files remained
under the closed/parked registry and pin rules, so nothing was moved. Most of
the 4.42 GB suffix-matched inventory belongs to packets without a matching
closure; the remainder is protected, compressed JSON evidence or tiny logs in
still-referenced folders. The verified audit is on RAID.
[Counts, keep decisions and audit archive](experiments/own-xpu-runtime/stage2/DISK-CLEANUP-20261018.md#disk9--closed-screen-bulk-audit-no-safe-bulk-remaining-2026-10-18).

**October 18, disk7 archive pass:** verified archives of closed build and screen files recovered **1.975 GB**. Root went from **31.284 GB to 33.153 GB free** at 20:09:15 UTC. **The requested 40 GB was not reached**: the other large candidates are protected, still referenced, or lack a clear closure. All JSON receipts, notes, sources, live work and record material stayed. The archives were fully checked before their originals were removed. The final check covered 1,191 moved paths and 28,170 retained files or links, with no errors. [Archive paths, restore instructions and checks](experiments/own-xpu-runtime/stage2/DISK-CLEANUP-20261018.md#disk7--verified-archive-pass-2026-10-18).

**October 18, disk6 archive pass:** closed experimental builds, private build dependencies and old compiler caches now have verified archives in
`/mnt/raid-models/own-xpu-runtime-archive/disk6-20261018/`. The pass recovered **9.581 GB** of allocated file space and stopped at **14:26:13 UTC**,
when root first reached **40.023 GB free**, up from 31.285 GB. Every selected archive member and original file was checked before removal.
Live packets, their pinned parents, record chains and weights stayed in place. This was a one-time threshold; the running chain continues to use disk.
Restore historical closed builds/caches from the exact manifests before replaying them. The [disk6 cleanup record](experiments/own-xpu-runtime/stage2/DISK-CLEANUP-20261018.md#disk6--verified-archive-pass-for-record-chain-headroom-2026-10-18)
contains all 58 archive paths, hashes, restoration instructions and the audit limits.

Retain the **50 GiB free-space reserve** and admit the peak temporary writes before creating archives or copies with `scripts/check-storage-headroom.py`; old free-space numbers are not admission. Verify current capacity, mount identity and ownership
before new model downloads. Do not do bulk reads of the protected external trees during this documentation cleanup.

**October 18, disk5 archive relocation:** the old cache archives and eight inactive staging-build archives now live in
`/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/cache-consolidation-20261006.tar.gz` and
`/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/staging-consolidation-20261007.tar.gz`.
Every file was hash-verified from its new archive before the exact originals were removed. Restore their `payload/` contents to the original
`/home/steve/git-archives/` paths before using historical restoration commands or replaying the old backup/staging verification scripts.
Keep `data/maintenance/consolidation-20261006/summary.json` and `data/maintenance/staging-consolidation-20261007/summary.json` unchanged:
all twelve original archive hashes still match. The [disk5 cleanup log](experiments/own-xpu-runtime/stage2/DISK-CLEANUP-20261018.md#disk5--one-time-root-reserve-to-40-gb-2026-10-18)
records the remaining exact moves, per-file manifests, archive checksums, restoration instructions and free-space readings.
The one-time cleanup stopped at 09:24:16 UTC with **40.306 GB available (37.538 GiB)**, up from 31.003 GB;
this is a point-in-time reading while other work continues, not a reserved allocation.

The selected research/Git backup is `/mnt/usb-models/lab-backups/steve-b70s-20261007/` (nine verified archives, selected source only, not a whole-machine backup). Preserve `/home/steve/git-archives/flash-next-rescue-20261007/`,
`/home/steve/worker-container-controls-20261007/`, and the official 27B cold copy `/mnt/usb-models/worker-models/qwen38-27b-fp8-20261007/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a/`. This page does not assert the USB disk's current mount state. It is
cold backup storage, not an active model-serving path; no force, repair/reinitialization or SMART bridge passthrough.

Preserve source/build deltas, unique outputs, anchors, failure/coredump/OOM evidence, model/cache inventories, quarantined damaged LTX files, rejected/partial downloads and restore maps unless their exact disposition has been independently
established. In particular retain `/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914/FAULT.json` and all four stages, and `/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914` with its stopped incident container. A compressed archive or Git
history does not by itself demonstrate recoverability of ignored artifacts.

## Protected Work And Artifacts

Preserve these paths and inspect their status before any build, cleanup, or
service change:

- `/home/steve/src/llama.cpp-muse-100`: preserved source/build used by the inactive Muse fleet;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2`: accepted Qwen3.8 Q4_K_M source at
  `a4349bcee`; preserve its intentional three-file uncommitted fusion delta;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2/build-sycl-aot-bmg-g31-oneapi-2026.1.1`:
  accepted oneAPI 2026.1.1 BMG-G31 AOT build;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/`: accepted Qwen3.8 GGUF targets and MTP sidecars;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/`: official FP8 artifact retained for the separate vLLM lane;
- `/mnt/fast-ai/bench-results/qwen38-official-fp8-vllm-xpu-20260816/`:
  official FP8 eager/graph/P2P controls, final quality gate, cache-zero result,
  runtime capture, and post-run health evidence;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp/`: hash-verified
  SergioB GPTQ INT4 target with 15 BF16 MTP tensors; community replay lane;
- `/mnt/fast-ai/bench-results/qwen38-q4km-asrock-b70-20260815-pass2/`:
  accepted Q4_K fusion A/B and cold-suite evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`:
  SergioB target-only eager/graph validation, failed conservative-U graph
  attempt, logs, inspect records, prompts, and raw SSE evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-quality-20260816/`: native/FP8 KV,
  semantic quality, MTP runtime-dtype, Q8/Q4 controls, and reset-window evidence;
- `/mnt/fast-ai/src/llama.cpp-q8-tp2-directq8-isolated`: current accepted Qwen TP2 source;
- `/mnt/fast-ai/src/llama.cpp-q38-tp2-distributed-greedy-directq8`: closed
  exact distributed-argmax candidate; preserve for mechanism reuse only;
- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-distributed-greedy/`:
  position-balanced reasoning-off controls/candidates and exact output oracle;
- `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`: prior accepted Qwen TP2 source; preserve as control;
- `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/`: accepted Qwen model;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion/`:
  promoted Qwen evidence and bounded negatives;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260814-40tps/`:
  Qwen pass-1/pass-2 evidence and current clean result;
- `experiments/qwen27_graphsafe_flash_attention/`: graph-safe INT4 source and
  generated research state;
- `experiments/qwen36-27b-autoround-int4-b70/`: INT4/MTP research packet and
  diagnostic artifacts.

Large ignored Qwen artifacts may be archived only after a complete inventory,
hash verification, and a recorded restore path. Never use broad `git clean` or
delete tracked experiment material to make the tree look tidy.

## Additional Preserved Work And Operational Guards

Preserve the pre-existing dirty files; inspect their status before editing:

- `experiments/qwen38-27b-b70/scripts/context/second-comparison.sh`
- `experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py`
- `experiments/qwen35-9b-b70/probes/drift-reproduction.py`
- `experiments/qwen35-9b-b70/scripts/analyze-admission-composition.py`
- `experiments/qwen35-9b-b70/scripts/run-20260908-drift-reproduction.sh`

The prior ledger also protects the dirty Flash-Next source tree; do not reuse or modify it for the Qwen3.8 R50 review. Root-NVMe/BIOS work remains paused: no bulk reads/scans of `/mnt/fast-ai` or `/mnt/usb-models`; do not start
`generate-q38-root-nvme-link-clearance-v1.py` or any `w13`/`hc` runner. Do not run process-search commands containing `w13-m1-xpu-graph-gate.py` or the A2 result path: frozen health checks can mistake the search itself for a surviving runner.
Preserve the [archived ownership notice](CURRENT-history-20260909.md#immediate-manager-actions) and its exact frozen-runner paths.

Power settings are off limits, including restoring old values. Host memory/swap/page-cache changes and reboot require owner authorization; do not alter any approved workaround as cleanup. On the four-card host, blocks **53–57** remain offlined by
`b70-offline-bad-memory.service`; RAM replacement is deferred for 2026. The approved deepest-idle-state and lockup-panic settings are recorded in the [stability guide](docs/host-stability-and-fault-diagnosis.md); old September statements that the
mitigation was absent are historical.

On turin retain approved `vm.swappiness=1`, earlyoom, disabled automatic kernel/GPU-firmware upgrades, and kernel `7.0.0-38` with `7.0.0-31` fallback. Only one memory-heavy job at a time on its 15 GiB host, never beside a build container. Do not
start another job close to an active server's memory-guard floor.

Follow [AGENTS.md](AGENTS.md) for main-only Git, secrets, graceful GPU shutdown, first-fault evidence and bounded health checks, strict lossless gates and full 16-bit KV. All superseded results and historical incidents remain available in the
[verbatim October ledger](CURRENT-history-20261010.md); archiving them does not retire protected work or grant operational permission.
