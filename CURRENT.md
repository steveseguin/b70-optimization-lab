# Current Workspace State

Last reviewed: **2026-09-11 15:50 UTC** (2026-09-11 11:50 EDT); the four-B70 host section below was added then.

## Authority And Update Rule

**Four-B70 host `steve-b70s`, September12:** user selected a new-model native
baseline campaign. MiniCPM5-2B setup completed, but BF16 qualification failed
the strict output-format pilot (4/6); optimization has not started. The campaign
has exited and all four cards passed postflight. No baseline is promoted. See [lane packet](experiments/minicpm5-2b-b70/README.md).
It uses a dedicated environment and original external-drive weights, with
exclusive locks and fresh processes; no permanent listener is planned. Preserve
the older queued lanes and all protected artifacts below. Actual running state
must still be checked before another launch.

This is the sole cross-repository authority for loaded service, active lane,
protected work, and immediate next actions. Verify Git status, relevant
processes, listeners, and the actual endpoint before operational changes.
Update this page when a service starts or stops; keep experiment chronology
in lane notes.

The [archived workspace ledger](CURRENT-history-20260909.md) preserves the
previous 4,577-line page verbatim. Its live-service statements and queued
actions are historical, span multiple hosts, and are not current instructions.

## Local Host And Active Review

**Four-B70 host, September14: same-process decoder confirmation running.**
The bounded18-request `na-axis-confirm-01` is running against the unchanged
packet10 PID84255/exec33936. Six balanced OCO/COC triples cover boat, marble,
and bird with all four raw-output checks on every clip. Root reviewed the new
client and prior-screen admission; eight stdlib tests and offline admission of
161 evidence files passed. No application reload or other native work during
timing. Preserve the process and halt submissions on any failure.

**Four-B70 host, September14 16:42 UTC: decoder screen passed; small speed gain to confirm.**
PID84255 serves `http://127.0.0.1:8188` in exec33936, packet
`prepared-encoder-na-axis-10`, manifest
`d6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a`.
Four startup device checks, strict determinism, full identity and private decoder
node registration passed. Packet09 PID82046 exited0 after one SIGINT following
the reviewed source-pin correction; same computer boot and no fault recorded.
All11 `na-axis-screen-01` clips passed full original four-output raw parity;
nine scoped decodes passed the complete24-call sequence and owner/config checks.
Cache previews6.297–6.446s; median paired changes −119.528ms preview and
−83.436ms decoder. Client80638 exited0; queue empty, no fault, original dispatch
and default NA route. This is a screening gain, not a promotion or streaming
qualification. Next: preserve terminal evidence and prepare a balanced18-request
confirmation on this same application. No reload is required. Halt submissions
on failure without cycling the service.
[Screen results](experiments/ltx25-b70/notes/na-axis-screen-01-results.md).
The separate guarded CPU compiler probe exited1 after blocking an import-time
`torch.xpu.device_count` query; XPU stayed uninitialized, no model/compile calls
occurred, and LTX PID84255 remained idle and healthy. It did not reach the earlier
cache-metadata hypothesis. No retry is scheduled during confirmation.
[Guarded probe](experiments/ltx25-b70/native-cpp-block-01/guarded-v2-native-attempt-01.md).
[Corrected preparation](experiments/ltx25-b70/notes/na-axis-runtime-10-prepared.md).
This supersedes all older PID/startup statements below.

**Four-B70 host, September14 16:33 UTC: packet09 node startup rejected; zero clip requests.**
PID82046 serves `http://127.0.0.1:8188` (exec49702) with an empty queue.
All four startup device checks passed and strict determinism is enabled, but
`LTXNAAxisDecode` failed registration before router installation: its sd.py pin
incorrectly names the upstream source rather than the inherited encoder source.
No native campaign was launched, and no automatic retry follows. Preserve this
idle application and packet09 while correcting the source integration offline.
Old PID66846 exited0 after one SIGINT; computer boot remains
`8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a`, no host reboot or settings changes.
[Startup failure evidence](experiments/ltx25-b70/data/na-axis-migration-09/startup-failure.json).
This supersedes every older live PID and next-launch statement below.

**Four-B70 host, September14: decoder packet09 preparation (historical).**
Packet `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-09`
is sealed at manifest`a53e06ae5bd1be8931eff11d4e9112b850912147b37fcabf1bda064b12f419ed`.
The private original-VAEDecode integration passed9 CPU groups; the11-request
client passed14 stdlib checks and offline packet admission. Root reviewed the
node, builder, receipts and client; independent builder review found no blocker.
The new graphs change only decoder374 and retain original transformer dispatch.
Startup must prove the node is registered through object_info before requests.
[Prepared package](experiments/ltx25-b70/notes/na-axis-runtime-09-prepared.md).
PID66846/packet08 is still the live healthy application; no09 native request
or application reload has occurred yet. Next: one controlled application reload
to load09, then the bounded bare/original/cache comparison with full raw parity.

The separate C++ CPU tiny-block probe stopped after detecting unintended XPU
initialization during the first Python-boundary compile; no C++ compiled call
followed. Root checked an empty queue, no FAULT or new kernel entries, and only
the original LTX PID owning the four render devices. That probe stays separate;
its source-backed cache metadata/driver initialization hypothesis and inactive
guarded successor are preserved. Do not run CPU compilation during native timing.

**Two-B70 host, September 14: user-reported freeze during candidate startup.**
The user restarted the computer. Current boot is
`5ba85b30-0455-466a-b9fc-d9132975417e`; the prior boot ended after logs stopped
at about 09:27:55 EDT. The newest-base/V2/DFlash2 candidate never reached
readiness or benchmark requests. Its last model log is target loading, not a
completed draft or generation operation; cause remains unknown. Do not retry
this candidate unchanged. Both GPUs passed bounded compute and XCCL recovery
checks with no new kernel faults. The original R304 FP8/MTP1 service is healthy
at `http://127.0.0.1:18124/v1`, model `qwen38-27b-fp8`; post-reboot strict checks
passed 12/12 complete outputs and all 18 measured
512/2K/16K continuations match the pre-incident control, with cache zero.
Strict decode measured 54.3158 tokens/s and all recovery monitor windows passed.
Its persistent helper owns
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/restored-service`.
Preserve the stopped candidate container and all raw evidence under
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914`;
`FAULT.json` records the incident. The root fault receipt remains preserved;
the explicit recovery admission
applies only to the original qualified service. The earlier control
and exact-but-neutral projection screen remain valid separate observations.
[Incident receipt](experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/freeze-incident.json),
[final results and recovery evidence](experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-results.md).

**Four-B70 host, September14: retained profile captured; recorder failed after exact clip.**
The same packet08 PID66846 remains alive and idle, now on **compiled all48**
dispatch. One diagnostic clip matched all four original raw outputs; its graph,
component and owner evidence still passes. The recorder then rejected its own
run name during output inventory (`unregistered/protected run`). No restored
request, retry, deletion, application reload or host action followed. Client
exec11241 exited1; bounded nonblocking profiler exited0. Queue/kernel postflight
clean, no FAULT latch. This is a recorder integration failure, not a device or
numerical fault, and it supersedes the restored-dispatch claim immediately below.

[Profile/postmortem](experiments/ltx25-b70/notes/retained-multiblock-profile-01-results.md)
preserves the trace and exact clip. Offline analysis and a corrected recorder
continue; do not rerun the failed campaign. The saved profile is sufficient for
the next source investigation: decoder geometry-mask construction and native
operation wrapper overhead. No speed promotion or streaming qualification.

The inactive [per-call decoder axis cache](experiments/ltx25-b70/notes/na-axis-cache-01.md)
now passes23 CPU exactness/lifecycle groups, including unchanged SDPA inputs and
call order. Root reviewed the patch and tests. Its source-derived untiled path
reduces522 axis builds to100 with at most1,878 bytes predicted cached payload;
the general cap is256KiB plus allocator/metadata overhead. Native shape coverage,
full-clip equality and speed remain pending. The startup-only scoped router
passed11 actual Kitchen CPU dispatcher lifecycle groups with XPU access
blocked; root reviewed source/tests. [Routing gate](experiments/ltx25-b70/notes/na-axis-router-cpu-01.md).
No installed or loaded runtime source changed. Next: private original-VAEDecode
node integration, complete native shape/route receipts, then a sealed packet and
bounded original/cache/original clip comparison. Keep the C++ experiment separate.

The independent [private C++ operator prototype](experiments/ltx25-b70/native-cpp-ops-01/README.md)
built once on CPU and passed119 operator/fake comparisons with exact outputs.
Small matched CPU dispatch observations are favorable but do not predict XPU
speed; larger RMS samples include a loss and substantial noise. Root reviewed
the C++ source and test/timing drivers. This namespace has CPU implementations
only; compiled tiny-block, XPU and full-clip qualification remain pending.
At16:07UTC the application was still healthy and idle on compiled all48 with
the same boot, empty queue and no kernel/fault evidence after the CPU work.
[Observation](experiments/ltx25-b70/data/retained-profile-final-observation-01.json).

**Four-B70 host, September14: packet08 native screen complete; original selected.**
PID66846 serves `http://127.0.0.1:8188`, manifest
`a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b`.
All12 screen03 clips match all four original raw outputs, including all48
compiled blocks. Compiled previews7.38–8.04s remain slower than adjacent original
controls6.39–6.59s; median penalties1.273s preview/0.927s samplers. No promotion.
Client exec97668 exited0; server exec53546 is idle on restored dispatch with
all48 retained. Queue empty, clean kernel postflight and no FAULT latch.
[Native results](experiments/ltx25-b70/notes/multiblock-screen-03-results.md).
Old PID56711 exited0 after one SIGINT. Same host boot; no computer reboot,
driver reset or power/memory changes. [Startup](experiments/ltx25-b70/data/multiblock-migration-08/startup.json).

Next: complete and review the packet08-only retained diagnostic profiler client,
then one warmed compiled clip with bounded nonblocking stack sampling and one
restored control after all gates pass. This reuses the current application;
no profiler/GPU diagnostic request has occurred yet. It must bind screen03's
same-process qualification and preserve full-output/receipt/identity/fault gates.
The CPU traversal improvement is not a native video speed claim. This supersedes
older live PID56711/packet07 and running-client statements below.

**Four-B70 host, September14: packet07 screen complete; original dispatch selected.**
PID56711 serves `http://127.0.0.1:8188`, manifest
`afdbad186a6873a286f93e9d1e715f6bf4c17e1552d75dbce2a3e03c0a1f35c1`.
All 12 screen02 clips match all four original raw outputs, including all48
compiled blocks. Warm compiled previews7.59–7.65s remain slower than adjacent
restored controls6.37–6.45s (median penalty1.214s preview/1.167s samplers).
Client exec40600 exited0. Server exec70494 is idle on restored dispatch with
all48 retained; queue empty, clean kernel postflight and no FAULT latch.
[Native results](experiments/ltx25-b70/notes/multiblock-screen-02-results.md).
Old PID39793 exited cleanly after one SIGINT. Same computer boot, no host reboot,
driver reset or settings changes. [Startup](experiments/ltx25-b70/data/multiblock-migration-07/startup.json).

A subsequent offline replay measured only52.5ms potential savings from compact
receipt serialization across528 calls, with all parsed fields equal. This is
CPU/filesystem attribution, not a native speed result; no reload is warranted
for it alone. A corrected native-class CPU fixture then measured0.480s per528
route calls with fake compute, preserving1584 state/registry boundaries. The
separate profile points to repeated metadata traversal; this is not native
speed attribution. The inactive single-traversal state/hook candidate then
passed all60 existing lifecycle checks and measured0.313s in the same CPU
fixture versus earlier0.480s. No native speed claim; focused alias/None-state
gates and native qualification remain pending. Next: finish those focused CPU
checks and prepare the next native comparison without touching live packet07.
[Candidate and CPU cost](experiments/ltx25-b70/notes/onepass-state-04-cpu.md).
[Replay evidence](experiments/ltx25-b70/notes/serializer-replay-cpu-01.md),
[metadata attribution](experiments/ltx25-b70/notes/metadata-dispatch-cpu-02-results.md).
This supersedes PID39793/packet06 and running-client statements below.

**Four-B70 host, September14: multiblock screen complete; exact but slower.**
PID39793 serves `http://127.0.0.1:8188` on packet06, manifest
`3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394`.
All 32 clips passed all four original raw-output comparisons, including all48
compiled blocks. Median all48 penalty was +1.303 seconds versus adjacent
restored controls; no speed promotion. The client exited zero. The application
is idle on restored dispatch, queue empty, kernel postflight clean and no FAULT
latch; all three compiled selections remain retained. Server exec38020.
PID17769 exited after one SIGINT; same host boot, no computer reboot, driver
reset or power/memory-setting changes. [Native results](experiments/ltx25-b70/notes/multiblock-screen-01-results.md).

The next inactive adjacent-state reuse03 patch passed all 60 CPU checks for
both parent and candidate, preserving three validation boundaries while
removing two adjacent duplicate state checks per block call. Native quality
and speed remain pending. Prepare its sealed runtime and bounded comparison,
then perform any necessary controlled application reload within authorized work.
[Patch and CPU evidence](experiments/ltx25-b70/notes/adjacent-state-reuse-03-cpu.md).
This supersedes earlier process, inactive-packet and running-client statements below.

**Four-B70 host, September 14: native block compilation exact; paired timing complete.**
PID17769 serves `http://127.0.0.1:8188`, server `encoder-server-compiler-05`,
packet `prepared-encoder-compiler-05`, manifest
`45dc23a7c0a0a234412e31a36225716edf60bb16ad342d96fe12f65139bccbe5`.
All nine compiler-screen-04 clips match all four original raw outputs. Five
compiled clips covered three scenes; both native stages passed eager/compiled
and compiled/repeat checks. Two emitted graphs each retain15 native RMS, six
sigmoid and two tanh-GELU calls. This qualifies block24 only, with no demonstrated
speed win (warm compiled median6.607s; restored boat about6.49s).
Postflight: empty queue, matching identity, clean kernel and no FAULT latch.

The bounded18-request `compiler-timing-01` completed on this same process, with
all original-output checks passing. Median compiled-minus-adjacent-control mean
was+99.797ms preview and+17.977ms sampler intervals: a measured speed loss, not
promotion. The application is idle on restored dispatch, with the qualified
compiled candidate retained and no fault. Across both campaigns27 clips passed,
including11 compiled clips. [Paired results](experiments/ltx25-b70/notes/compiler-timing-01-results.md).

An inactive registry-binding reuse patch removes one duplicate full registry
walk per lifecycle validation while keeping all late-mutation/ownership checks.
Parent and candidate native CPU lifecycle gates passed; no GPU speed result or
deployment. Next: qualify overhead changes and prepare bounded multi-block
selection without per-block application reloads. Continuous real-time generation
remains incomplete. [Patch and CPU evidence](experiments/ltx25-b70/notes/compile-registry-reuse-01-cpu.md).
The multi-block successor now passes CPU qualification. Initial five-block
capture failed at graph9 under the unchanged recompile_limit8; its preserved
successor uses private per-block compiler entry frames and passed10graphs,
20 block cases with exact eager/repeated outputs, plus54 native CPU lifecycle
checks. Packet06 is prepared and inactive, manifest
`3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394`;
its launcher check-only passed. PID17769/packet05 remain unchanged and idle;
passive kernel/fault checks passed. Next: finish the bounded multiblock client,
then a necessary controlled application reload and native GPU qualification.
No new GPU speed/quality result or application reload in this preparation.
[CPU fix and preparation](experiments/ltx25-b70/notes/multiblock-private-entry-02.md).

[Exact native results](experiments/ltx25-b70/notes/compiler-screen-04-results.md),
[scaling/guard audit](experiments/ltx25-b70/notes/compiler-screen-04-conditional-scaling-audit.md),
[prepared source](experiments/ltx25-b70/notes/native-activations-runtime-05-prepared.md).
This supersedes all earlier process and failed-candidate state below.

**Four-B70 host, September14: native RMS compiler successor running.** One
controlled LTX application replacement completed: PID6502 exited cleanly after
one SIGINT; render ownership cleared and the port was available. The computer
was not rebooted. PID12199 now serves `http://127.0.0.1:8188` from
`encoder-server-compiler-04`, packet `prepared-encoder-compiler-04`, manifest
`c4e0f7e56fc7bbc51101894d79d279dd9886f07272868dc99cc7953c647a65c9`.
Four-card startup checks and strict after-import determinism passed; endpoint
identity matched. No fault latch. The candidate preserves original native RMS
calls inside one compiled block; small CPU gates passed, native GPU/full-clip
qualification failed in compiler-screen-03: audio differences fell from5,923 to10
bytes; video remains54 bytes different. Both eager clips matched all original
outputs (warm7.954s). The first compiled block failed before repeat/stage2/full
clip; no speed result is qualified. Queue empty, kernel clean, no FAULT latch.
The numerical gate remains failed; do not retry it. Next is remaining rounding
localization. [Result](experiments/ltx25-b70/notes/compiler-screen-03-results.md).
This supersedes PID6502 and historical blocked/fault states below.
[CPU qualification](experiments/ltx25-b70/notes/native-rms-cpu-qualification-01.md),
[prepared source](experiments/ltx25-b70/notes/native-rms-runtime-04-prepared.md).
The separate native activation successor is now CPU-qualified:21 guard checks,
four tiny block cases, and two emitted graphs each retaining15 RMS/six sigmoid/
two GELU calls. It is not deployed; native GPU and full-clip parity remain
pending. Prepare its immutable packet/client before another necessary controlled
application reload. [Candidate and exact scope](experiments/ltx25-b70/notes/native-activations-cpu-qualification-01.md).

**Two-B70 host, September 14: AMD transfer tests authorized.** The unchanged
FP8 service at localhost:18124 passed 12/12 full-output reference checks and
short/16K continuation controls. A newest-upstream candidate with the accepted
arithmetic overlay is being built for a bounded projection-dispatch and DFlash2
screen. The original service is still running during CPU preparation; one
controlled maintenance transition will precede exclusive GPU testing. No new
runtime or speed result is promoted. Evidence root:
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914`.
[Preregistration](experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-prereg.md).

**Four-B70 host recovered after an external boot, September14.** Current boot
`8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a` differs from the faulted boot; all three
old processes are absent. Four-card copy/compute and clean-kernel checks passed,
with render ownership clear after exit. The original FAULT was preserved
byte-for-byte under `external-boot-recovery-01/historical-FAULT.json` and an
explicit recovery admission was recorded there. No reboot, driver reset or host
setting change was performed by this agent. This supersedes the blocked status
below; the full generation goal remains incomplete.

The prepared decoder mask-extent candidate passed all16 small XPU:3 native
mask/attention cases, including BF16/F32 and exact repeats. Kernel postflight is
clean and render devices were released. Full-clip parity and speed are still
unmeasured; installed Comfy Kitchen remains unchanged. Compiler packet03 is now
running as PID6502 at `http://127.0.0.1:8188`, server directory
`encoder-server-compiler-03`, manifest
`9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980`.
Startup four-card checks and strict after-import determinism passed; endpoint
identity matched. Campaign `compiler-screen-02` completed two exact eager clips
(warm control6.262s), then stopped on first native compiled block24 mismatch:
54 differing video bytes and5,923 audio bytes, finite/layout-matched. No compiled
full clip, repeat or speed result is qualified. The queue is empty, PID6502
remains present, the compiler gate is failed, and kernel postflight is clean.
Preserve the process/evidence; do not retry the failed gate. Next is numerical
localization, with native RMS reduction decomposition a source-supported
hypothesis. [Failure and evidence](experiments/ltx25-b70/notes/compiler-screen-02-results.md).
[Recovery evidence](experiments/ltx25-b70/notes/external-boot-recovery-01.md).

**LTX goal blocked on host recovery, September14.** The same kernel fault and
pending-interrupt native clients were revalidated across three consecutive goal
turns. Prepared source work is saved, but the next meaningful steps require a
healthy native runtime: compiler exactness/speed and actual continuation quality.
No new native request, restart or reboot was performed. Generation remains about
6.4s per clip; the full real-time goal is incomplete. Do not continue producing
synthetic-only qualification as a substitute for those native measurements.
[Recovery handoff and resume order](experiments/ltx25-b70/notes/native-progress-recovery-handoff.md).

**Four-B70 host, September14: kernel incident; GPU requests halted.**
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json` is present.
The first compiler-screen-01 eager control clip completed generation, but client
PID96119 became stuck in a kernel cross-CPU TLB wait during post-request work.
CPU13/CPU6 soft lockups, RCU stalls and blocked system tasks are recorded.
Only eager mode ran: no compiled candidate/block execution or completed oracle
qualification. PID95931 remains present with an empty queue; one client SIGINT
was sent, exit unconfirmed. No reboot/reset/restart or host-setting changes were
performed after the fault. The stale campaign `running` status is superseded by
this incident and the fault latch. **No new GPU requests until recovery and
health are established.** Preserve all failed/current clip files and the earlier
25/25 exact encoder results. [Incident and evidence](experiments/ltx25-b70/notes/compiler-screen-01-kernel-incident.md).

Subsequent source progress: the same boot/client kernel wait persists. One
bounded CPU-stack diagnostic timed out without a captured backtrace; no retry,
reboot or new GPU request. Future compiler packet03 is prepared with explicit
host-fault detection; its copied launcher correctly refuses current FAULT.
Runtime remains on packet02, never migrated to03.
[Preparation and fault revalidation](experiments/ltx25-b70/notes/kernel-fault-source-progress-01.md).

Further offline work prepared a continuation graph constructor (13 source tests
passed) and two inactive loader-memory patches. The loader's tiny Torch CPU
test did not finish: PID102144 remains present with SIGINT pending; no numerical
pass or RAM-saving result exists. No further Torch/GPU test retries on this
faulted host. The last durable test artifact is the extracted candidate source,
which does not identify the exact stalled instruction.
[Loader candidate and incomplete test](experiments/ltx25-b70/notes/loader-memory-candidate-02.md);
[continuation source checks](experiments/ltx25-b70/notes/continuation-graph-constructor-cpu.md).

The float-anchor provider and closed continuation graph are now implemented
offline. Thirteen byte-reader tests and12 integration checks passed without
Torch imports; frame extraction also matched independently read final frames
from all three protected originals, whose full-image hashes still matched.
No new video saved or generated. Native tensor construction, runtime deployment,
predecessor lineage, delivery state, continuation quality and speed remain
unqualified. [Implementation and evidence](experiments/ltx25-b70/notes/continuation-anchor-provider-01.md).

Offline continuation work now includes a bounded four-tensor verifier/frame
reader and a single-request coordinator with predecessor binding, explicit sink
acknowledgements, atomic metadata checkpoints and a three-capture admission
limit. Fifteen reader tests and15 simulated coordinator tests pass. Both25/24
frame delivery modes matched independent byte reads for all three original
reference captures, with their four tensor hashes intact. No GPU request,
playback, generation-speed result or footage deletion occurred. Transport,
cleanup, native continuation and playback remain pending; host FAULT persists.
[Bounded state and delivery evidence](experiments/ltx25-b70/notes/continuation-stream-state-01.md).

The inactive continuation verifier now uses exact integer bit intersections
for F32 finite checks. All65 affected bit/reader/provider/state checks pass;
paired scalar/candidate verification of the three original captures produced
identical receipts and all four original hashes. Provisional faulted-host CPU
medians were304.38ms scalar versus44.04ms candidate for full capture verification.
This is verification overhead only, not a generation-speed improvement or
promotion. No GPU request, restart or host-setting change occurred.
[Exact candidate, patch and timing limits](experiments/ltx25-b70/notes/finite-f32-bit-intersections-01.md).

An inactive streaming comparison client now checks complete F32 archive bytes
without importing Torch or loading entire tensors. Fifteen contract tests and
seven arithmetic tests pass. Saved baseline02 and resident-split03 match all
four baseline01 outputs; a different-prompt marble capture correctly fails.
The old comparer and frozen callers remain unchanged. Historical-evidence
reports cannot satisfy a live gate; no generation-speed gain or runtime
qualification is claimed. Host FAULT remains present.
[Candidate and exact evidence](experiments/ltx25-b70/notes/streaming-comparison-01.md).

An inactive one-line decoder candidate removes GPU scalar readbacks when the
attention-window maximum is already available as a Python integer. All17,728
source/integer extent cases pass and the complete AST differs only in that
extent expression. No native mask, attention, full-clip parity or speed result
exists yet. Installed runtime source remains unchanged; FAULT still prevents
native tests. [Patch and qualification scope](experiments/ltx25-b70/notes/na-mask-extent-01.md).
The separate small native mask/attention gate is prepared; its check-only run
correctly halted before importing Torch under the existing fault.
[Gate and refusal evidence](experiments/ltx25-b70/notes/na-mask-extent-native-gate.md).

**Historical startup, superseded by the fault above: native compiler comparison.**
PID95931 serves `http://127.0.0.1:8188` from prepared-encoder-compiler-02,
manifest `f1fc467a4620caabac9065e72fb7fd1628db437d1c977c86237bb0378ef8f952`.
Endpoint identity and strict after-import determinism match the startup receipt.
The bounded nine-request compiler-screen-01 is active; inspect its progress
under `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/compiler-screen-01`
before any new GPU request. It checks one native block24 with the original
control encoder, both native stage outputs against eager/repeat calculations,
and every completed clip against all four original raw references. No compiled
speed or correctness result is claimed before those gates finish.
PID78769 exited cleanly after one controlled SIGINT to load this new application
code; the computer was not rebooted. No fault latch at startup. This supersedes
the idle PID78769 statements below. [Preregistration](experiments/ltx25-b70/data/compiler-screen-01-prereg.json)
and [native gate](experiments/ltx25-b70/notes/ltx-block-compile-node-ready.md).

**Four-B70 host, September14: encoder comparison complete; compiler integration next.**
All25 encoder-screen-02 clips passed strict four-output original-reference parity
and all four unload transitions passed. No convincing speed winner: warm medians
6.364s control-before,6.377s crop,6.430s small-state,6.441s combined,6.643s
control-after. Small-state residency fixes the observed loaded-byte accounting
drift, but has no demonstrated full-clip speed gain. PID78769 is idle on control,
generation5, at `http://127.0.0.1:8188`; no fault latch. Preserve this process
while preparing the compiler successor; no competing GPU requests. Next is a
bounded one-native-block exact compilation gate, then full-clip verification if
it passes. [Results](experiments/ltx25-b70/notes/encoder-screen-02-results.md).
This supersedes the active-screen statements immediately below.

**Four-B70 host, September14: strict startup fixed; encoder comparison started.**
PID78769 serves `http://127.0.0.1:8188` from prepared-encoder-03 / encoder-server-02.
Startup identity matches the endpoint and the after-import receipt verifies
strict determinism (enabled, warning-only off). Encoder-screen-02 is running;
reuse this process and inspect its progress before any new GPU request.
The first screen on PID75850 stopped after one completed control clip: all four
outputs matched baseline bytes, but strict-mode qualification failed because
Comfy import reset warning-only mode. The corrected launcher restores the
original import order;11 CPU regression checks passed. Only the launcher differs
between the immutable packets. No quality gate was waived. Evidence and exact
scope: [startup correction](experiments/ltx25-b70/notes/encoder-strict-startup-fix.md).
User clarified that routine application reloads should not cause approval
pauses or stop optimization; the host-reboot/power/restart-chain constraints
remain. This supersedes all earlier pending-approval and process statements below.

**Four-B70 host, September14: authorized LTX replacement completed.**
User approved the restart and clarified that optimization must continue without
an unnecessary application-restart approval pause. Original PID24848
stopped cleanly after one SIGINT. Replacement PID75850 is ready at
`http://127.0.0.1:8188`; endpoint identity matches the encoder-server-01 receipt,
the queue is empty and the fault latch is absent. Host LAN IP is10.0.0.65, but
the application listens on localhost only. The immutable prepared-encoder-02
packet is active. The preregistered encoder-screen-01 comparison is now running
on this process; inspect its live progress before any new GPU work. An initial launcher
preflight exited before Torch import because the old TCP socket was in TIME-WAIT;
after its observed expiry, the bind check passed and the replacement started.
Evidence: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-migration-01.json`
and `encoder-server-01/`. This supersedes pending-replacement statements below.

**Four-B70 host, compiler preparation: routed CPU gates pass; inactive.**
The native block adapter passed its initial 29 checks; the additive ownership
guard passed 51 checks with the compiler callback itself in the full options
registry. Both stage token counts and two seeds matched video/audio outputs
exactly and repeated identically, with two compiled graphs and no graph breaks.
These are tiny CPU fixtures, not native-weight GPU or speed results. The
[checkpoint header census](experiments/ltx25-b70/notes/native-block-header-census.md)
records native block dimensions and mixed stored dtypes without loading weights.
A subsequent [executing-patcher lifecycle gate](experiments/ltx25-b70/notes/ltx-block-compile-pre-run-lifecycle.md)
passed 25 CPU checks for live owner anchoring, late changes, clone behavior and
cleanup. A subsequent [real bound CPU capture](experiments/ltx25-b70/notes/ltx-bound-lifecycle-capture-cpu.md)
passed one 64-video/26-audio-token case with the lifecycle callback present:
both outputs exact and repeatable, one compiled graph and zero graph breaks.
Native GPU correctness/overhead and broader cases remain unqualified. The
cancelled optional CPU compilation attempt is preserved separately. The
[continuation audit](experiments/ltx25-b70/notes/continuation-source-boundary.md)
also records two-stage mask loss and unresolved audio timing before streaming.
PID24848 remains idle, fault-free and unchanged; the encoder v2 maintenance
approval is still pending after multiple goal turns. The prepared launcher again
passed its read-only check. Further measured speed work is waiting on that
decision; do not infer approval from automatic continuation. Compiler work is
separate from that immutable packet.
See the [route gate](experiments/ltx25-b70/notes/ltx-block-compile-route-cpu.md).

**Four-B70 host, encoder runtime v2: GPU screen prepared, maintenance pending.**
Startup, actual placement/unload diagnostics and the 25-request bounded client
are complete. Eight startup, ten diagnostics and eight client CPU tests pass;
the copied launcher's read-only check passed and all 1,214 packet files still
match their hashes. No new GPU request, runtime change or server replacement
occurred. PID24848 remains running and idle, with its original identity and no
fault latch. The new `encoder-server-01` directory does not exist. One deliberate
graceful replacement is needed to load v2; do not start a second process beside
the current server or create a retry/restart chain. The next action is a
maintenance decision for the [concrete launch and screen](experiments/ltx25-b70/notes/encoder-runtime-v2-ready.md).
The source snapshot is `prepared-encoder-02`, manifest SHA256
`920d0e35774f298c9b11f80b3dd5e3708d0541f914e4c1857e96493bfd7282a8`.

**Four-B70 host, encoder integration follow-up: inactive source packet built.**
The four encoder variants now pass 17 CPU lifecycle tests and four integration
tests through tiny real Gemma4/CLIP/LTX projection paths. Review fixed a shared
clone policy bypass; integration also fixed rejection of CLIP's stock compute
dtype setting. Original patches and earlier receipts remain preserved. A new
non-Git source snapshot under `prepared-encoder-01` inventories 1,205 files and
keeps all baseline graph inputs except explicit encoder options. Every staged
file hash and the unchanged loaded-source hashes passed verification. No GPU
job, server restart or runtime edit occurred. PID24848 remains the loaded idle
service; no new speed claim. Next: finish startup identity/client and actual
placement diagnostics before any maintenance decision or the bounded 25-request
comparison. See the [source packet and remaining gates](experiments/ltx25-b70/notes/encoder-runtime-packet.md).

**2026-09-14 UTC, two-B70 host: bounded worker comparison finished; FP8 ready.**
Readable tool output passed stable acceptance and independent agent review on all
five original issues, plus one confirmation each of the formerly failed hardware
and zero-cost tasks. Both new held-out issues failed. The readable profile remains
opt-in/experimental; original defaults and model performance qualification stay
unchanged. All generated patches remain unmerged, with human review pending.
[Results and evidence](experiments/local-coding-worker/overnight-2026-09-14-results.md).
The original 3/5 trial and first failed profile screen remain frozen separately.

One unchanged qualified FP8 TP2/MTP1 server remains healthy at `127.0.0.1:18124`,
33,024 total capacity / 4,096 scheduling batch / one active sequence. Exact helper
state/logs: `/mnt/fast-ai/bench-results/local-worker-20260914/server/`.
All nine corrected-campaign CPU containers stopped before patch export. No model
patch was applied to either source checkout. No server restart, inference
optimization, host-setting change, local GPU fault or cloud fallback occurred.
The eight-hour authorization was an upper bound; this bounded model campaign is
closed. No queued model/GPU tasks remain in this lane.
Use the existing endpoint for subsequent worker jobs; do not launch a competing
GPU lane. [Worker commands and API capacity](worker/README.md).
Preserve independent four-card LTX work and its fault-halt state above.

**Four-B70 host, post-stability LTX diagnostics: next runtime candidates prepared.**
One 15-second nonblocking py-spy attachment and one unchanged clip completed on
PID24848; all four output tensors matched baseline-01. The trace points to
repeated CPU copies of tiny encoder RMSNorm weights and layer scalars totaling
only 1.47 MiB. The opt-in small-state residency patch passed 12 real Gemma4 CPU
lifecycle tests; it includes a scoped accounting correction and must not be
stacked with the separate generic accounting patch. It is inactive.
Stock whole-model compilation was rejected by source audit. Default CPU
Inductor changed BF16 values despite deterministic repeats; preserving rounding
passed 6/6 toy cases. An actual native LTXAV block CPU fixture then passed both
stage token counts: two compiled graphs, zero graph breaks, both outputs exact.
These are CPU preparation gates, not GPU speed/quality results. No server restart
or runtime patch occurred; the server is idle and fault-free. Diagnostic media
was pruned after exact verification. Next work is a bounded runtime integration
packet for small-state residency/cropping and one-block compilation; do not use
the unsafe stock compile node or inject code into the live process.
See [profile result](experiments/ltx25-b70/notes/stack-profile-01-results.md),
[small-state candidate](experiments/ltx25-b70/notes/encoder-small-state-audit.md),
and [compiler block gate](experiments/ltx25-b70/notes/ltx-block-compile-cpu.md).

**2026-09-14 UTC, two-B70 host: official FP8 quickstart replay complete.**
The public-source helper ran one R304 TP2/MTP1 server at 33,024 capacity /
4,096 batch / one sequence. Strict 12/12 complete outputs matched the qualified
reference; all six practical requests passed with exact repeated outputs and
zero cached tokens. Single-replay decode 54.201 tok/s; no optimization promoted.
The documented exact-owned stop passed, all owned processes/listeners are gone,
and both GPUs/XCCL plus the full journal postflight passed. State and logs are
under `/mnt/fast-ai/bench-results/qwen-fp8-flagship-20260914`; the hash-bound
[results packet](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-flagship-results.md)
records public commit, image/model checks and remaining installation limits.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, September13, LTX campaign started toward the revised goal.**
User requires one second of new video in **under one second**, at24fps with no
quality/losslessness sacrifice. Final output floor is256x256; <=3s is only an
intermediate marker. Minimal rolling review footage is authorized, including
deleting older verified campaign outputs while preserving compact hashes and
receipts. Existing model/reference artifacts stay protected. The first bounded
work completed [30 sequential requests over10 fixtures](experiments/ltx25-b70/notes/stability-01-results.md)
on the existing PID24848 endpoint: all exact repeats passed, median preview6.515s,
p956.680s, no faults/OOM. Physical memory stayed within observed bounds while
the encoder's reported offload grew690→2718MiB; source/CPU work supports an
accounting defect. Longer soaks remain deferred. Verified pruning reclaimed607MB,
retaining three campaign previews totaling170KB plus compact receipts. Two
inactive candidate patches target accounting and unnecessary hidden-state CPU
copies; no runtime change or further restart occurred. The server is idle.
See the updated [plan](experiments/ltx25-b70/PLAN.md).


**2026-09-13 EDT, two-B70 host: final FP8 prefill pass complete and stopped.**
Official 27B FP8, R304 TP2/MTP1, measured 512/2048 inputs at 2,857/3,679 input
tokens/s with 4096 capacity/batch. All 36 measured outputs repeated exactly;
strict 12/12 original-reference parity, decode −0.13%. Profiling found FP8 matrix
operations dominant and no justified quick candidate; defaults retained and
prefill campaign closed. Owned server stopped, both GPUs/XCCL and journal
postflights passed. [Results](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md).
Raw root `/mnt/fast-ai/bench-results/qwen-fp8-prefill-focus-20260914`.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, 2026-09-13 22:23 EDT: exact-output LTX speed result.**
User prioritizes first usable clip within a few seconds, while retaining exact
baseline outputs. Baseline PID11499 exited cleanly after one planned SIGINT;
new ComfyUI PID24848 owns `127.0.0.1:8188`, with the same exclusive locks,
strict deterministic mode and cache-none computation. All four small startup
preflights passed, with no device fault. Resident model components and exact
layer placement are startup extensions; generated outputs and prompt encodings
are always recomputed. **Validated warm 256x256/25-frame clips take 6.44–7.10 s
to playable preview**, using all four B70s: transformer split across XPU0/1,
encoder XPU2 and VAEs XPU3. Three boat repeats and marble/bird reference scenes
match all four original tensors bitwise. Exact float media export also passed.
Matched warm boat client medians improved 7.85×; first split initialization took
81.21 s to preview. BasicGuider was exact but neutral and is not selected.
The one-second clip is not yet continuous real time; prolonged operation remains
untested. The transformer stays resident; the encoder still partially offloads.
Server is idle with split components retained. Further variants
use this same process; no restart chains/power/swap/cache-drop/driver changes.
See [speed campaign handoff](experiments/ltx25-b70/SPEED-HANDOFF.md).
The [LTX north star and plan](experiments/ltx25-b70/PLAN.md) now define the next
milestones: bounded stability validation, exact clips under1s, coherent streaming,
then sustained generation above24fps. The later start instruction is recorded above.
Original baseline remains frozen; new process identity is under the original
evidence root's `speed-server/`. Use `profile-clip.py --server-run` pointing there.

**2026-09-13 21:47 EDT, two-B70 host: bounded prefill follow-up complete.**
4B TP2, 9B TP2 and 27B INT4 TP1 measured at 256/512 input tokens, one user,
cache zero; all 108 measured requests repeat exactly and all three strict suites
match their original qualified outputs 12/12. One 4B TP2 profiler trace is
retained; no new runtime candidate or decode record promoted. All three owned
servers are stopped, both GPUs/XCCL and journal postflights passed. [Results](experiments/qwen38-27b-b70/notes/2026-09-14-prefill-followup-results.md),
raw evidence `/mnt/fast-ai/bench-results/qwen-prefill-followup-20260914`.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, 2026-09-13 20:42 EDT: LTX baseline bring-up.** User authorized
a very short native-precision clip and deterministic repeat checks. One local
ComfyUI server (historical PID 11499, `127.0.0.1:8188`) ran with exclusive device
locks; all four cards passed its small copy/compute preflight. **Baseline complete,
original server since replaced as described above:** three fixed-seed 256x256/25-frame generations are bitwise identical
across images, video/audio latents and waveform, with strict determinism and zero
cached nodes. First/repeat server times were 97.590/54.009/52.774 seconds. Exact
float video/audio export passed independent decode round-trip verification.
No GPU fault, OOM or tiled-VAE fallback occurred. This establishes one-prompt,
same-process repeatability, not cross-process or other-model parity. The RAID transformer and encoder failed fresh
SHA-256 checks; rejected bytes and failed receipts are preserved. The transformer
was repaired by replacing 79 damaged bytes, and the encoder by replacing 112.
All five final component files passed publisher/direct-I/O hashes; the generation
gate is now open. Rejected files and partial downloads remain preserved. Preserve the server, source and environment at
`/home/steve/src/ComfyUI-ltx25-baseline` and
`/home/steve/.venvs/ltx25-baseline`; no restart chain or power-setting changes.
See [verified baseline and reuse instructions](experiments/ltx25-b70/README.md). Evidence root:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

**Four-B70 host, 2026-09-13 after 20:17 EDT reboot: LTX 2.5 pivot.** User
requested parking the completed Flash-Next campaign, archiving its checkpoint
to USB, then focusing on LTX 2.5. Recent LTX, YuE2 and MiniCPM downloads were
located on the RAID, now mounted read-only. Corsair's read-only mount failed
with an NTFS chkdsk recommendation; Qwen archive verification/reclaim is
pending, and the internal checkpoint remains intact. No GPU workload was
launched. The active task is storage/download review and LTX bring-up planning;
prior queued four-card launch instructions are superseded. See the
[pivot and storage review](notes/2026-09-13-ltx25-focus-and-storage-review.md).

**2026-09-13 20:30 EDT, two-B70 host: short-prefill campaign complete.**
Measured 4B/9B W4A16 and 27B INT4/FP8 at c1 with 128/256/512-token inputs.
All 324 measured requests were cache-zero and output-exact across off/on/off;
each model passed 12/12 full-suite candidate/control and original-reference
parity. A direct-output allocation screen showed +3.0% on 4B, +2.1% on 9B,
and neutral 27B results, with strict decode differences below 0.3%. Existing
serving defaults remain unchanged; this is a single-process screen, not a new
promotion. See the [results and replay](experiments/qwen38-27b-b70/notes/2026-09-13-short-prefill-results.md)
and [complete summary](experiments/qwen38-27b-b70/data/2026-09-13-short-prefill/summary.json).
All four model stages are stopped, optimization flags removed, both GPUs/XCCL
and final journal postflights passed. No power, swap, cache-drop, driver or
reboot changes. Raw evidence remains at
`/mnt/fast-ai/bench-results/qwen-short-prefill-20260913`.

**2026-09-13 19:32 EDT, two-B70 host: R308 work complete.** The optional
single-request repair for Qwen3.5 4B and 9B is published, anonymously pullable,
and verified on the live site. Both models passed 60/60 oracle checks,
52/52 boundary checks on each of two fresh speculative servers, and all four
strict comparisons 12/12. Public-parent reconstruction matched all 17 runtime
hashes. Source/evidence integrity, guide tests, recipe CI and Pages deployment
passed. See the [qualification note](experiments/qwen35-4b-b70/notes/2026-09-13-r308-qualified-single-request.md)
and [completion receipt](experiments/qwen35-4b-b70/data/2026-09-13-r308-single-request-qualification/evidence/publication/completion.json).
All owned model and preview servers are stopped; both GPUs and XCCL passed
final health checks. No power, swap, driver, or reboot changes were made.
Scope is TP1, fixed depth 3, one active request: boundary capacity 256 and strict
capacity 1024. Clean-host certification, concurrent speculation and a new 32K
profile remain outside this qualification. R307 failures and diagnostic roots
remain preserved in the linked evidence; existing defaults retain their
original identities.

**Four-B70 Flash-Next closeout, 2026-09-13:** user requested finishing Fable's
optimization campaign and publishing existing results. A340-A394 is closed:
46.854250 tok/s approved realistic-suite record, +23.87% vs previous line;
A382/A394 repeated 32K depth median 44.052 tok/s with equal output hashes.
[Closeout](results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md) owns the wins,
nonpromoted trials and remaining certification limits. No server or optimization
chain is running. The separate disabled single-session draft is set aside.
User constraints remain: no AI power-setting changes and no repeated restarts.

**Four-B70 host, 2026-09-13 20:10 UTC recovery:** A394 depth repeats pass, but
teardown rc is 143 and another host interruption followed. No workload running;
hold Flash-Next launches pending teardown/host-restoration review. Git damage
restored from the already-pushed A394 commit; evidence USB mounted read-only,
RAID unmounted. See [recovery evidence](notes/2026-09-13-a394-freeze-recovery.md).
Follow-up: full Git fsck passes, NVMe reports zero media/errors; offline audit
found stop-protocol mismatch, stale health receipts and a nested-cleanup race.
See [teardown audit and next gates](notes/2026-09-13-a394-teardown-audit.md).

**2026-09-13 (EDT):** the whole INT4/W4A16 runtime is rebased onto stock vLLM XPU
v0.29.0 as **R304** (`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16`,
pushed and anonymously pullable): the R294b overlays ported as net diffs, the kernel
library rebuilt from public sources (vllm-xpu-kernels 0.1.14.1, which carries upstream
GDN fix #544, plus the lab's oneDNN r137a/r137b/r221), and three open upstream vLLM
fixes applied verbatim (#53059 alias guard, #51565 GDN first-chunk, #53542 active width).
It fixes two failures that were live on R294b: every one-token prompt and every
(1+K)-token prompt at depth K degenerated into single-character walls (30/30). Strict
gates 12/12 at published speed on the 4B, 9B and FP8-27B lanes under the recipe contract
(`verify-image-contract.sh` v0290 digest set); the INT4-27B pair is running. The 4B and
9B and both 27B recipes, packages and compose packets now point at R304 (all gates 12/12, long context 18/18,
high concurrency reproduced; kernel library reproduced bit-identically from a clean clone). The 9B scheduled-draft
profile runs on R306 (`@sha256:f124c6fb`, R304 plus its overlays and a contiguous-staging fix for upstream PR #53542). Serve with `VLLM_USE_V2_MODEL_RUNNER=0` (the launchers pin it; v0.29.0
defaults XPU to the V2 runner, which has no draft INT4 head). Details:
`experiments/qwen38-27b-b70/notes/2026-09-12-rebase-onto-vllm-v0290.md`.

**2026-09-11 (EDT):** the Qwen3.5 4B/9B and Qwen3.8 27B INT4 lanes finished the
class-consistent FP16 linear work (R290-R293 overlays, `VLLM_XPU_FP16_LINEAR_CLASSPAD`):
the R224 32-row pieces re-read the vocabulary projection once per 32 rows, 25-56% of
throughput on the 4B/9B and 3-8% on the 27B, removed losslessly. 27B package staged
on R293 (`packages/qwen38-27b-int4-fixed-k-tp2-b70`, rows R295-R298); the R293
image is built locally (`sha256:40d46730`) and awaits the GHCR push
(`repro/qwen38-27b-autoround-int4-b70/scripts/publish-r293-image-ghcr.sh`). No
containers running after 19:03 EDT; both cards passed postflight.

Host: `steve-TURIND8-2L2T`, **two B70s**. At the verification time above,
no Docker containers are running; all PR45 review servers were stopped.
Both GPUs and XCCL passed final postflight. Recheck actual process and endpoint
state before operational changes.

Target-oracle follow-up completed: both fresh compiled target-only strict tests
passed, all five comparisons were 12/12 exact, and 96 additional probes passed.
All owned containers stopped; localhost 18124 is closed and postflight passed. See
[preregistration](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/target-oracle-20260909.md).
The six-hour soak has not been started.

The active task is correctness and reproducibility review. An isolated
Qwen3.8 27B official-FP8 R50 baseline/candidate comparison completed for PR #45:
normal-suite parity passed, tiny-prompt screens failed, candidate not promoted.
The initial review model containers were stopped; both GPUs and XCCL passed
postflight. Follow-up isolated the fresh one-token GDN routing defect: the
phase-guard candidate passed 120/120 probes, two fresh compiled MTP full suites,
12/12 baseline/fresh-repeat parity and pre/post workload screens. The campaign
is complete and stopped, not a permanent service. See the
[preregistered follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-followup-plan.md).
Read the
[maintainer validation record](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/README.md)
for the candidate identity, completed tests and outstanding gates.

The previous Gemma listener and Qwen3.5 active-lane claims are superseded by
this observation. Preserve the existing Qwen3.5 work listed below. Run one
GPU lane at a time; verify endpoint and health independently of an image tag.

## Working Recipes And Candidates

- **Qwen3.8 27B FP8 TP2:** the [reproduction packet](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)
  owns the lab-qualified R187 configuration, exact-output concurrency limits
  and historical results. Its certification remains `candidate-portable-repro`;
  it is not a verified beginner setup. Consult the
  [multi-host handoff](experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md) and
  [do-not-repeat index](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md) before work.
- **PR #45 classifier fix:** separate R50 candidate, not promoted into the
  above recipe. Actual-source CPU checks pass against both source copies.
  Normal GPU suite passed 12/12 exact baseline/candidate parity, but both
  failed tiny-prefill screens; compilation-disabled candidate also failed.
  Sustained mixed-session validation remains unperformed; not a verified fix.
  A separate maintainer GDN phase guard fixes the local one-token symptom in
  the [bounded follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-20260909/README.md),
  but is not promoted as the contributor's incident resolution.
- **Gemma 4 26B Q8:** [result/handoff](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
  and [standalone recipe](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
  preserve the measured setup. Their existence does not mean Gemma is loaded.
- Other lane status belongs in the [model effort index](docs/model-effort-index.md)
  and [reproducibility map](docs/current-reproducibility-map.md).
  The [scoreboard](results/scoreboard.md) is historical measurement evidence,
  not service state.

## Known Issues And Next Actions

1. Before promoting the GDN local fix, run the contributor's actual mixed-session
   soak. The matched-image MTP0/MTP1 strict-oracle matrix now passes; the
   multi-hour incident remains unverified. PR #45 is merged as a community
   contribution, not a production promotion.
2. Reproduce one selected recipe end to end: pinned inputs, build, launch,
   quality gate and clean teardown. Correct defects found along that route
   before additional speed tuning.
3. Audit recent changes by affected runtime, shared harness and published
   recipe. The [September 8 review](notes/2026-09-08-targeted-correctness-cleanup.md)
   was bounded: syntax checks are not execution coverage, and commit author
   labels do not establish which model wrote a change.
4. Three promoted Flash-Next replay paths now use exact frozen verifier
   snapshots; four replay clients now stop their servers on failure. Bundle
   chains were restored and verified from the public base. See the
   [audit record](notes/2026-09-09-replay-and-validator-audit.md).
   The broader 229 historical experimental hash mismatches were not blindly
   repinned. Four-card runtime replay remains untested on this two-card host.
5. Keep ML Bottleneck automatic refresh paused. Numerical fixture tests are
   now separated from refreshed-data checks. The ingestion parser correction
   passes 94 tests and resolves the 3060 interpretation in a migration test.
   Publication still blocks on the 4070, nine ambiguous measurements and
   calibration thresholds. Published evidence remains unchanged. Details are in
   that repository's `docs/refresh-review-2026-09-08.md`.

## Other Host: Four-Card Work

MiniMax M2.7 INT4 and Flash-Next TP4 belong to the **four-B70 host**, not
this two-card machine. The [MiniMax post-reboot note](notes/NEXT-minimax-after-reboot.md)
is that host's resume packet; its remount, driver and launch instructions
must not be applied here. It records an unresolved bring-up validation after
a driver wedge, not a successful serving result. On the owning host, avoid
polling `xpu-smi` during initialization, verify the four devices and use its
bounded health checks before continuing.

Flash-Next history and accepted identities live in its
[handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md) and
[result packet](results/qwen38-flash-next-fp8-b70/README.md).
Historical reboot notices in the archive do not describe this boot.

### Four-B70 host, 2026-09-11: Qwen3.5-9B W4A16 lane closed, Flash-Next next

The Qwen3.5-9B W4A16 one-B70 lane on `steve-b70s` is closed and published: the
static depth-3 headline (113.27 tok/s) stands, and a second operating
configuration - one server for every batch size, draft depth scheduled by
batch size on three pure-Python overlays over R276 - is promoted in the
[guide](repro/qwen35-9b-w4a16-b70/README.md#one-server-for-every-batch-size-campaigns-cudynm1--cudynm1r-2026-09-11),
[package](packages/qwen35-9b-w4a16-b70/package.json) and
[performance index](results/scoreboard.md): 110.7 tok/s at one user, 1,184 at
64 users, exact through 32 users, 18/18 exact 2K-32K. The env-knob ladder for
single-user decode on this lane is exhausted (defaults optimal on every axis);
what remains is kernel work (fused INT4 draft head) recorded in the
[campaign note](experiments/qwen35-9b-b70/notes/2026-09-10-one-server-for-every-batch-size.md).
No lane container is running. The next active lane on this host is Qwen3.8
Flash-Next (its [handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md)).

### Four-B70 host, 2026-09-13: Flash-Next lossless MTP1 at 46.85 tok/s (record approved)

The Flash-Next lane's step-timing decomposition (A340-A358) put 8.7 ms of the 42.7 ms
two-row verify step in vLLM's Python serial GDN path and showed the cost is in neither its
kernels nor its glue. The kernel extension's own exact serial mode, gated to four verifier rows
by the served build, accepts two when `_xpu_C.abi3.so` is rebuilt from the lane's kernel head
(`bbae3c5` over `e421889`, [series](patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md)).
With that mode selected the verify step is 33.7 ms and every output pin holds (kernel probe
bit-identical; exact-2K `afffd211…`, exact-4K `1d833e5f…` on four servers; 12/12 suite outputs
equal to the 37.83 record). Certified on three servers (A364, A365, A366: short 53.4, exact-2K
48.2, exact-4K 48.5 tok/s) and recorded on a fourth (A367: **46.854250 tok/s** class-balanced,
LocalMaxxing [`cmtzask41000nlq011f16bpbc`](https://www.localmaxxing.com/runs/cmtzask41000nlq011f16bpbc)
approved). Guide [`repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/`](repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md),
package `packages/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/`, narrative in the
[result packet](results/qwen38-flash-next-fp8-b70/README.md). Host notes: two silent freezes hit
launches started 60-90 s after the previous server's teardown (swap toggle); leave five minutes
between a stop and the next launch. Unused models (laguna-s-2.1, muse-glimmer, the 9B pair) were
moved to `/mnt/raid-models` with symlinks left in place; root NVMe at 301 GB free. No lane
server is running.

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

Pre-existing dirty Qwen3.5 work at review start; inspect and preserve:

- `experiments/qwen35-9b-b70/probes/drift-reproduction.py`
- `experiments/qwen35-9b-b70/scripts/analyze-admission-composition.py`
- `experiments/qwen35-9b-b70/scripts/run-20260908-drift-reproduction.sh`

The prior ledger also protects the dirty Flash-Next source tree; do not
reuse or modify it for the Qwen3.8 R50 review. Root-NVMe/BIOS work remains
paused. Retain the existing frozen-runner guards: no bulk reads/scans of
`/mnt/fast-ai` or `/mnt/usb-models`; do not start
`generate-q38-root-nvme-link-clearance-v1.py` or any `w13`/`hc` runner.
Do not run process-search commands containing
`w13-m1-xpu-graph-gate.py` or the A2 result path: frozen health checks can
mistake the search itself for a surviving runner. See the
[archived ownership notice](CURRENT-history-20260909.md#immediate-manager-actions)
for the original guard and its recorded false positives.

Do not place new model downloads on NVMe based on an old free-space report.
Verify current capacity, mount identity and lane ownership first. Follow
[AGENTS.md](AGENTS.md) for main-only Git, secrets, runtime isolation,
quality gates and exact publication requirements.
