# Continuing SC117 engine work

Owner direction, October 24: finish making the downloaded model work in our
engine, test correctness, then continuously optimize speed without quality
loss or benchmark shortcuts. Continue until the owner stops the work or a
concrete blocker requires their decision. The previous Unsloth lane remains
closed; this direction applies to the requested SC117 target.

The target authority is the two downloaded shards at revision
`eec4e10a2c29b440a2ae85591fa11569ce752963`, with the full readback hashes in
`model-identity.json`. Do not change target weights, quantization, context
contents, sampling identity, or full 16-bit KV to obtain a faster number.
Keep all target verification for MTP. Draft-only approximations are acceptable
only insofar as the exact target still verifies every emitted token and the
completed target state matches the target-only path.

1. Complete the all-source native build and actual persistent-pair lifecycle
   check. Load the real target once with the draft available, then compare
   target-only and MTP tokens/state after a complete request reset. Preserve
   failures, source changes, physical ownership and safe teardown evidence.
2. Establish a measured baseline with complete model/run identity and honest
   prefill/decode/acceptance/memory accounting. The short correctness comparison
   is not a speed record. Use full fresh prompts and no reused prompt/KV/output
   state for benchmark claims; separate model residency from prompt reuse.
3. Profile only after correctness passes, select changes with worthwhile
   expected benefit, and test exactness before promoting speed results. Keep
   failed candidates and matching controls. No hidden precision reductions,
   hand-picked easy prompts, extrapolated records, or speed claims from
   diagnostic work. Keep operating under the user's existing host constraints.

A dedicated subagent reviews progress every 30 minutes. It should challenge
unnecessary gating, repeated builds/tests, speculative scaffolding, and low-value
work; identify the next highest-value bottleneck; and check model identity,
correctness scope and benchmark fairness. It reports recommendations to the
coordinator and records concise dated feedback here in the lane. It does not
operate GPUs, alter services/settings, or authorize a shortcut. The coordinator
owns action selection, all device operations, and evidence-backed conclusions.

## Measured next step — 06:12 UTC

The [resident baseline](baseline/RESULT.md) and [class diagnostic](profiling/RESULT.md)
are independently audited. The next single candidate is existing p33 segmented Q8
variant6, split1, restricted to the48 attention projections at N2560/K6144. It preserves
lane products, ordered accumulation, SG32 reduction and BF16 output; no precision or
model change is allowed. It replaces packed shared-memory staging with exact expanded
codes/scales, adding47,185,920 device bytes perrank. Actual native equality and speed
must be measured; the slightly larger read footprint could erase the staging benefit.
Preserve the frozen baseline binary and source closure. A dependency-proven one-TU
build is preferable to rebuilding39 unchanged objects. Test control/candidate kernels
within one owner; do not create a fresh-server timing chain. End-to-end candidate
numbers remain provisional until their control comparison is fair.

## Storage incident hold — 06:33 UTC

The candidate stopped after seven exact pairs because USB NTFS exhausted MFT records,
not free data bytes. Both owners exited/drained; there is no new classified GPU fault.
Do not promote the partial candidate or start new device work. Preserve failed receipts
and source. Complete reviewed, verified per-request lossless archival of closed baseline
state binaries, preserving six micro fixtures and all JSON; no model or filesystem-setting
changes. Resolve record capacity before root admits any further bounded device task.

## Storage recovery complete — 06:56 UTC

Verified27 archive chunks preserve every closed baseline state byte.57,045 duplicate
raw files were removed after verification, with six micro fixtures and all JSON kept.
USB archive creation/readback succeeds,11.2GB free; no new NTFS messages or GPU faults.
The storage-capacity hold is resolved for small explicitly admitted tasks, not a blanket
capacity guarantee for another large run. The original candidate remains incomplete.
Independent partial readback confirms14 arms/7pairs; next is fixed3-case paired kernel
latency/byte equality, then deliberate completion of the remaining five prompt pairs
under a new bounded identity after source/admission review. Preserve the interrupted
run and do not combine timing sessions into a full resident throughput claim.

## Exact kernel result — 07:10 UTC

The [paired kernel test](attention-q8-p33/micro/RESULT.md) passed independently:
84/84 pairs exact, all72 measured pairs retained, summed candidate/control event
latency0.21412 with both orders improved. Owner exited cleanly and target card drained.
This supports finishing the unchanged candidate's five missing correctness pairs,
not an end-to-end speed claim. New completion identity retains original indices7–11,
12requests/13dumps, original arm ordering and exact baseline comparisons. Its file
forecast is below57,045 records released by verified archival; monitor capacity and
retain any failure. Do not rerun the seven passed pairs or merge timing sessions.

## All twelve attention pairs exact — 07:16 UTC

The [separate completion](attention-q8-p33/completion/RESULT.md) independently
verifies the ten remaining arms. All24 arms of the unchanged candidate now match
the original baseline, with the interrupted session and timings kept separate.
The focused kernel gain supports retaining this exact internal candidate, not
promoting a model speed record. Next lever:22 Q6_K GDN-QKV projections N10240/K2560,
existing p33 variant6/split1, first exact CPU arithmetic and same-owner3-case micro.
GDN-QKV's aggregate profile includes mixed formats; do not label it Q6-only time.
Before another full model suite, archive verified closed candidate state binaries
to recover file records; preserve original failed-request and JSON evidence.

## Q6 micro exact and faster — 07:28 UTC

The [Q6 micro](qkv-q6-p33/micro/RESULT.md) independently passes all84 pairs against
saved baseline bytes. Summed measured event latency is0.30441 of control; both
orders improve, all72 measured pairs retained. This supports one full-engine
candidate combining the48 verified attention sites with only22 Q6 GDN-QKV sites.
The arithmetic proof covers all binary16 patterns and signed scales; three real
payloads and full output bytes are authenticated. No full22 payload rescan is
needed merely to repeat that proof. The complete model gate still compares all
original prompt tokens/full states. Finish closed candidate archival before that
suite; do not publish micro timing as model speed or merge different sessions.

## Combined full-engine measurement next — 07:40 UTC

The single-entry native build and independent source/build/operating reviews pass.
Retain original26request/27dump schedule, all12prompt pairs and unchanged cap128,
fullRESET, target verifier and BF16KV. Compare every arm to the original baseline
before another request. Record absolute resident rates and within-run MTP behavior;
a previous-binary comparison stays explicitly between runs, not a matched causal
speedup. Do not begin a third micro before measuring this engine. All27 closed
attention-state archives are verified,56,981 files released, and explicit next-run
storage admission binds the plan. Byte/file forecasts are monitored, not quotas.

## Combined actual result and iteration-cost work — 07:52 UTC

[Independent full-model readback](qkv-q6-p33/engine/operating/RESULT.md) passes all24
arms/all12prompts. Measured14.853656 target /22.133318 MTP tokens/s; both order groups
are close, all1,160accepted/364rejected guesses unchanged. Retain the combined exact
candidate internally; between-run original-binary comparison remains descriptive.
Next implement the [narrow state-bundle proposal](state-bundle/PROPOSAL.md): exact
raw bytes and logical map, independently streamed range hashes, unchangedstate.json,
explicit repeatedDUMP/RESET/FINISH proof and incomplete-write preservation. It targets
MFT/file overhead without changing model arithmetic or token timing. Qualify format
with CPU parity/failure/lifecycle and a bounded real capture; no full26speedrerun solely
for format. USB byte compression remains necessary before later full suites.

## Bundles qualified; refresh current costs — 08:24 UTC

[Independent bundle readback](state-bundle/RESULT.md) passes both prompt00 arms,
all6,324 original ranges and complete lifecycle checks. Adopt this exact evidence
format for subsequent internal runs. No further format-only model run is needed.
Next profile the current combined binary with existing class instrumentation,
one disjoint eight-output warmup and one exact prompt00 target-only request.
No rebuild is needed. These counters include prompt processing and decode and
are diagnostic costs, not throughput. Select the next worthwhile kernel from
current evidence; mixed-format class totals cannot be assigned by layer counts.
Compress verified closed combined evidence before another full suite: bundling
solves file fanout but does not reduce raw payload bytes.

## Current profile selects expert investigation — 08:34 UTC

[Current class profile](profiling/current-combined/RESULT.md) is independently exact.
Expert gate/up sum to19.45% of whole-request event time, largest combined area. Use
existing narrow attribution to join actual layer costs to formats, not proportional
layer counts. Controller fixtures9–16 sample early generated-token steps. Keep that
scope explicit; no new native build or general profiling framework. Closed combined
state archival is underway outside GPU work for future full-suite byte capacity.

## Exact attribution selects IQ3_XXS packed decode — 08:40 UTC

[Independent narrow trace](profiling/current-attribution/RESULT.md) verifies6,912
events and baselineexact model state. IQ3_XXS gate/up55.122711ms is the largest
combined format cost in this fixed early-generated sample. Prepare one blockwise
decode candidate, no added resident weight cache. Preserve exact decode equations,
strided lane chain, SG32tree, BF16rounding, ten per-slot gathered inputs/routes/status.
Reuse prior format proofs and validate only the new arithmetic/loop/binding delta,
then bounded native exactness and latency before full-engine adoption. Root's initial
shared-input assumption was corrected from actual graph before implementation.
Do not extrapolate sample shares into a promised whole-model gain.

## Expert micro incomplete; qualify the full engine separately — 09:22 UTC

The [fixed-route native micro](expert-iq3xxs-block/micro/RESULT.md) matches all84
output/status pairs and records shorter candidate events, but its1.366second owner
ended before passive physical-device observation. Preserve the failed qualification;
do not retroactively attest its GPU identity or promote its timings. No repeat micro
is planned. The unchanged34-site block kernel has compiled into the full engine,
with complete512-expert banks and dynamic routes, unchanged memory/precision and
all original model checks. The next independent qualification is the original26-request
resident suite with positive physical contact required for both ranks, complete
baseline token/state equality and safe closure. Separate-process timings remain
descriptive; the short internal corpus is not the public512-token gate.

## Expert full-engine qualification passes — 09:33 UTC

[Independent full result](expert-iq3xxs-block/engine/operating/RESULT.md) verifies all24
baseline-exact arms and54 closed bundles, both physical contacts and safe teardown.
Resident target15.732355/MTP23.303290 tokens/s; unchanged acceptance and memory.
Retain the exact candidate internally. Do not relabel the incomplete micro or infer
a causal cross-session speedup. Archive only the54 audited bundle payloads after
verified compression/readback, preserving all other metadata/draft evidence.
Inspect the largest unchanged measured format, IQ4_NL expert-down, before selecting
another exact kernel delta. No redundant profiling campaign yet. Keep the explicit
[broader coverage plan](expert-iq3xxs-block/engine/PUBLICATION-GAPS.md) for publication;
twelve short prompts do not establish universal model correctness or quality.

## Archive complete; broaden coverage alongside source work — 09:41 UTC

[All54 target bundles](storage/expert-block-closed/RESULT.md) are losslessly archived,
all216 phases verified. Prepare six requests on the current qualified973489 binary,
without rebuilding: originalprompt00 cap512, the existing untemplated512-input real
text continuation cap512, and a preregistered roughly2048-input fact task cap128,
each target/MTP with fullRESET. Retain EOS/truncation and rubric failures. This adds
sequence/context/task coverage but is not an independent full-model reference.
The next source-only kernel candidate removes local staging/barrier from IQ4_NL
expert-down while preserving original decode8/lane sum/tree/BF16. No assumed speedup;
one actual-case AB/BA discriminator is needed after focused new-address checks.

## Broader coverage passes; next micro and capacity boundary — 10:12 UTC

[Coverage-b](coverage/RESULT.md) independently passes all6 requests/14bundles.
Two512-output pairs exact;2084-input fact task exact84/EOS and all six facts right.
Full-text readback retains cap-limited incomplete outputs. Coverage-a startup refusal
is preserved; additive startup128/RPC512 distinction fixes transport only.
ContinueIQ4_NL direct-global one-case discriminator after reviewed exact fixture
extraction and native build. CPU13,193checks pass; backend-contact ACK must precede
all GPU work. No predicted speed gain or model integration yet. Root27.35GB after
141MB old npm download-cache cleanup; USB4.56GB. Micro fits, but another full26suite
requires additional verified evidence capacity first. Do not lower reserves or use
the faulty RAID. Broader closed captures remain raw pending any explicit archival.


## October24 10:36UTC — IQ4 decision and next dense candidate

IQ4 direct-global passes28 exact pairs and actual physical/closure qualification,
but all24 measured pairs show1.67855 times original latency. Reject it without
Engine integration or a tuning detour; [result](iq4nl-down-direct/micro/RESULT.md).
Prepare the [19-site Q6 extension](dense-q6-p33/PROPOSAL.md), reusing qualified
arithmetic and testing only new selector/geometry/storage behavior before native
qualification. A future full suite first needs verified evidence capacity.


## October24 10:42UTC — Q6 native preparation complete

The19-site extension passes309selector checks, one native entry compile and12
operating mocks. Actualmetadata plan a173939f also passes; noGPU execution yet.
Coverage14bundles archived to682,929,437B with56verified phases. Consolidate41
proven duplicate older archives only after fullpayload verification/durable
restore redirects to reach the unchanged full-suite evidence floor.


## October24 10:53UTC — full Q6 screen running

All41canonical consolidations passed82explicit verify/release phases, recovering
3,586,696,105B. Originalmemberbytes/tarmetadata remain restorable via tracked
redirects; original compressed identities are historical only. BothQ6owners have
actualphysicalcontact, no monitorerror. Fixed26suite runs with originalexactness
gates. IQ2simpleblockhoist is closed by source appraisal: existingdecode8 already
amortizes metadata. AfterQ6 result, refresh currentclass attribution before choosing
next kernel; integerroute-rank earlyexit is a source-supported possibility only.


## October24 11:05UTC — Q6 exact pass, current class diagnostic running

Independent54bundle/24arm audit8e9c passes,16.169987target/23.436774MTP,
188,743,680B extra device allocation. Small MTPdifference is descriptive only;
priorbinary broadcoverage does not transfer. Fourprompt00bundles now verified
canonical references,443,486,336B recovered,all8phasesPASS. Samebinary class
profile f71f started11:05: excluded8warmup+originalprompt00target128,fullstate
checks,6bundles, no throughputclaim. No additionalnativebuild. Nextclassaudit
sourcepreparing while root owns GPU. Coach10:56 review retained; next11:26:38.


## October24 11:12UTC — class storage-guard incident

Class-a stopped after excluded8warmup, before measuredprompt, due to recharging
full828,545,228B forecast after captures. Both processes exit1/cooperative stop;
backendteardown0/safe/zero live, descriptorsdrained/nofault. No speedresult. Source
review/mocks missed stateful space consumption; rootowned admission. Incident3eab
and exactfailed sources preserved. Additive b retains2GiB+128MiB and corrects
remainingpayload: before request2,T+2D=241,141,832B, notT+D. Fourprompt01bundles
verified canonical/released,443,486,336B,failedrun retained. No automatic retry.


## October24 11:17UTC — corrected class-b running

Actualplan a0a274f5 passes, independentreviewc910 and7focused lifecycle tests pass.
Samea0f9binary,2requests,fullstate checks. Exact rawbudget stages694327500→462885000
→241141832→231442500→9699332→0 after confirmedRESET/DUMP/FINISH. Metadata128MiB
remains headroom at eachstage; payload-only threshold mocks are not a promise of
physicalcompletion with zero metadataheadroom. Bothphysicalcontacts/nofirsterror.
Rootowns native run36036; source-only additiveactualauditorBpreparing. FailedA
unchanged. No settings/precisionchange or automatic retry.


## October24 11:20UTC — current class-B audit passes

Actual30ed538b passes6bundles/2requests/428halves/fullbaseline/closedbudgetstage5.
Whole214-position classsum12,582.182396ms, notwallthroughput orclass-by-phase.
QKV1320.441,expertDown1094.233,GDNz984.660,expertGate938.435/up925.481,
route700.988,QSAqgate639.101ms. HClow+injectsum1448.613ms. Source appraisals
compare smallBF16projection geometry/occupancy to integer-onlyroute ranking;
no implementation yet. Allownersclosed/drained/nofault. OriginalAfailedpreserved.

## October24 11:35UTC — selected HC geometry discriminator

Select one-SG workgroups for the192 BF16 HC low/inject sites; their combined
1448.613ms is11.513% of the current diagnostic event sum. Same ordered arithmetic,
SG32 reduction, BF16 output and unchanged weights/KV. The focused CPU proof passes
16,666 geometry/address/admission checks plus3 source-identity tests (60f2ceea).
Two fixed real layer0 shapes N320/N4,K10240 will each receive24 measured balanced
AB/BA pairs after4 excluded pairs. Native results are still absent. No engine
integration before measured benefit. Incremental Git compaction verified refs,
HEAD, index and connectivity unchanged; remaining exact capture deduplication
is prepared separately to recover usable headroom without weakening floors.

## October24 11:43UTC — HC geometry closed, next fusion appraisal

Native review9498 passes all56 exact pairs/112 kernels, physicalACK/drain and
unchangedfault/vision. Low51.7969→51.1587µs (B/A.987679), inject48.9495→49.0451
(1.001953), all24/case retained. Benefit too small; no engine integration or
extra run. Appraise fused expert gate/up work next: current device classes
sum1863.916ms/12,582.182ms; preserve per-output arithmetic and all intermediates.
Existing p6 fusion is not a usable drop-in. Independently verified canonical
recovery of40 closed Q6 measured bundles frees4,434,863,360B; all80 phases pass.
Root old-download-cache cleanup41.7MB preserves installed tools and model data.
