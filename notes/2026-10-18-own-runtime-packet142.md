# Packet142 — class layout prepared ahead of packet141

CPU-only preparation began at 19:09 UTC, October 18; 75-minute limit.
The current two-card record remains 58.798 tok/s. This task makes no speed claim.

The new packet copies frozen packet136 bundle8. Every inherited symbolic-link
object is preserved; original destinations are recorded in `copy142.json`.
Non-allowlisted dependencies are local snapshots. The packet49 oracle remains
bound only through `oracle-binding.json` and `shared_oracle.py`.

The three preregistered candidates are attention-order512,
expert-gate-up-order512 and hc-gate-low-order512. They retain byte-identical
copies in consumer order, capped at 512 MiB per rank, with complete consumer
tuples only. This is a bounded prefix of each class, not full-class coverage.
Physical adjacency is an allocator hypothesis, not a guarantee. Both sets are
loaded before timing; view changes only bind existing buffers and recapture.
The expert arm keeps the accepted halfcache, packed rows and kernels. It does
not repeat packet104/104b's losing gate/up tile16 transpose.

The conservative maximum leaves 3,531,201,420 bytes on rank0 and 249,398,566
bytes on rank1 under the unchanged 30 GiB arena ceiling. Actual allocation
census and full-shape checks are still required. Host admission adds 1 GiB for
the two retained banks to the inherited 97 GiB allowance.

Git pull refused unrelated dirty work; fetch confirmed shared HEAD and
origin/main at e77a3cb0f209fab6838a869cc81584e4eaaed6d3. No unrelated file,
frozen packet, live queue, service, device, host setting or process was changed.

The initial build stopped before device linking when copied inherited objects
put build material at 306,110,535 bytes, above the 300 MB limit. Replacing these
redundant local copies with hash-bound links to the allowed frozen binary
objects reduced build material to 257,586,144 bytes. The refusal is retained;
no cap was raised. Source snapshots are tracked separately in `native-base`.

## CPU proofs and corrections, 19:39 UTC

The initial 512 MiB class bank was too small for one complete expert gate/up
consumer pair (550,502,400 bytes), so the registered variants are now
attention-order600, expert-gate-up-order600 and hc-gate-low-order600. The fixed
600 MiB cap leaves at least 157,123,878 bytes within rank1's unchanged 30 GiB
arena ledger. Host admission adds 1200 MiB to 97 GiB. No host setting changed.
The first whole-matrix copy hit CopyEngine's 128 MiB limit in the CPU fixture;
32 MiB load-time chunks fix that. Neither correction changes arithmetic.

All twelve full-shape fresh/switch checks and twelve real-parser startups passed.
These use numerical allocations and never read model payloads. All six rollback
capture pairs stay identical after normalizing the alternate weight allocation IDs;
request-state reset covers every mutable allocation, and boundaries neither allocate
nor write weights. The final guard rejects a different class before any mutation;
its rebuild is waiting behind the one-card hold through the compiler arbiter.

GNU and Intel each passed two fresh runs over real matrix dimensions with synthetic
finite bytes: 679,424,000 weight bytes, 2,163,264 FP32 checks and 55,616 output rows.
All four output transcript hashes agree; peak child RSS was 548,568 KiB. No model
or GGUF payload was read. The entry and queue gates are still being finalized.

The packet's own offline prepare_submission replayed a local copy of packet136's
chain bundle through its real payload/attestation checks and rederived
58.798108759182306 tok/s. A corrupt WS128 summary hash was refused. An inherited
validator looked for the oracle checker in the generic source map; the local copy
now validates it through the genuine oracle binding and shared-oracle seal.
This is rehearsal evidence only; no external submission and no new speed claim.

Local closure checks found inherited absolute native includes of packet136's
kernel_guard.hpp. They now name the byte-identical local copy. Historical metadata
and inactive v5 helpers are retained under lineage-inputs rather than treated as
current pins. The compiler, active runtime and wrapper source closures are local;
only allowed oracle/model inputs and hash-pinned frozen binaries remain external.

The explicit six-row admission receipt corrects the intermediate arena-margin
arithmetic above: the conservative rank1 margin is **155,895,078 bytes**.
Actual rank1 margins are 163,267,878 / 235,767,078 / 412,714,278 bytes for
attention / expert gate-up / HC gate-low. Coverage is 27 / 2 / 96 weight tensors
per rank respectively. The expert arm covers one layer per rank, while HC gate/low
covers all 24 layers per rank. This coverage limits any future negative inference.
All 182 inherited symbolic-link objects and every allowed external binary hash
passed the closure audit. No foreign process or stale coordination marker was touched.

## Entry preparation while the compiler waits

The final native rebuild waits through ops/compile_turn.py behind the whole-host
hold. Its recorded owner has exited; the marker remains coordinator-owned and
was not changed. Preliminary CPU-only probes simulate only the missing final
composition predecessor, and are explicitly **not** final readiness receipts.
They exercise the real unit/environment checks and intercept both native launches,
then cover all 65 bracket requests and corrupted-output cooperative teardown.
The first entry probe found a doubled vendor-root path in the inherited suite
loader. The packet142 worker now resolves its bound metadata against the real
repository root. The oracle authority itself is unchanged. The metadata helper
also keeps plan stdout to one JSON object while retaining the full authority check.
The preliminary plan parses with 4800 s watchdog and 720–1200 s estimate.

All six new proposal files now exist under ops/lane-queue and have local mirrors.
No live queue was edited. Final real-seal entry tests and temporary queue planning
remain pending. This intermediate state is published so the coordinator can see
why the final marker is absent; it grants no device-launch readiness.

## Qualified implementation retained, 19:55 UTC

The compiler hold persisted after its owner exited. I interrupted only my own
waiting CPU build and shape processes (1592722 and 1605193); no compiler bypass,
GPU signal, service operation or coordination-marker edit occurred. The extra
native pre-validation refusal was the only uncompiled C++ change. It is retained
as lineage-inputs/qualified-v5/deferred-early-bank-refusal.patch and is not adopted.
The Python config checker already blocks wrong-bank switches before native
execution, and native class_select still refuses them before rebinding weights.

The active C++ source is restored exactly to the packet142 build that had already
passed all CPU gates. reuse_qualified.py verifies every recorded native source and
inherited object, both native binaries, the shape fixture and both byte-test
binaries. It retains the original build receipt and all CPU receipts unchanged.
Only the build driver's artifact-path/source-map bookkeeping differs. The new
build receipt labels this as reuse, not a new compilation. The composition seal,
updated safety and six-row admission gate now pass; real-seal entry/limit/worker
and temporary queue planning are running next.

A concurrent two-card-host push rejected the third milestone push. Incoming changes
had no overlap with dirty files and no suspicious emptied files; the only deleted
file was replaced package-version metadata. Main merged cleanly, preserving every
unrelated unstaged edit; the merge index contained incoming paths only. The merge
and packet142 milestone were then pushed immediately.

## Final CPU closeout, 20:08 UTC

All final gates pass against one composition seal: twelve full-shape runs and
twelve parser startups; four matching GNU/Intel transcripts; six rank/class
admissions; six complete wrapper entries with twelve wrong-unit/environment
refusals; twelve real rank exec boundaries and six finite-cap refusals; all
78 smoke/bracket requests and both corrupted-output cooperative-stop paths;
six temporary queue plans; and the live ops pin guard. The wrapper probes reach
both native exec boundaries with the actual closed environment and screen-<job>
unit convention; native execution and operational context are explicitly simulated.
The real oracle authority and all source/identity checks run. No synthetic device
receipt is retained as device evidence.

Queue planning first caught inherited object alias paths, then scratch-relative
submission artifact names. Object pins now name their immutable resolved targets.
The offline rehearsal now retains its six parent-only artifacts under local
lineage-inputs. Each artifact is byte-identical to the first successful rehearsal;
the parent's 58.798108759182306 score and corrupt-receipt refusal are unchanged.
The two pin refusals are retained in evidence/queue-first-pin-refusal.log and
evidence/queue-second-pin-refusal.log. The final queue implementation snapshots
are hash-bound locally and checked against the live implementation at planning.

Build storage is 288,775,204 bytes, below 300 MB; root free space remains above
25 GB. The 4 GiB CPU limits, nice19 and CPU affinity were retained. No model/GGUF
payload was read, no GPU or service was launched, no live queue was edited, no
foreign process was signaled, and no host setting changed. The compiler hold
was left untouched. Only the coordinator can select classes flagged by a valid
packet141 verdict, each with its own smoke before its five-view bracket.

The completed source/evidence commit is pushed before READY-FOR-DEVICE.json is
written. That marker is the final repository content write, binds the commit and
six proposal hashes, and explicitly leaves device quality/performance pending.

## Packet142c — offline report repair, October 18

The attention smoke finished with twelve exact 64-token requests, then failed
while importing its reporter. The oracle manifest loader puts the packet root
before v5 on Python's search path. The late `compare` import therefore picked
the root reporter while `build_engine` still referred to v5, causing the
missing `check_map` error. All nine root/v5 duplicate modules now have unique
v5 names, with their active imports and helper references updated.

The new CPU report gate reproduces that exact historical failure after the real
manifest import, then runs smoke and five-view bracket reporting through the
real `bracket_job.py` entry with the same search path. It retains only test
results; its synthetic device-shaped fixtures are temporary. The shared report
function is also used by normal post-device reporting.

The real attention smoke report was regenerated offline. The original failure,
window, summaries and every original device file are hash-checked and unchanged;
the original fault count remains two. A separate regeneration receipt binds the
fixed reporter, retained execution seal, unchanged native inputs and oracle.
The normal bracket reader accepts the regenerated smoke. No device or model
payload was read, and no GPU process, service, sudo, setting or live queue was
used. Arithmetic remains `iq3-p49-split32-v1`; no speed result is claimed.

The minimal reseal preserves prior source and CPU receipt bytes in
`lineage-inputs/pre-142c.json.gz`. Only Python source identities and dependent
receipt hashes change; native binaries, native sources, numerical inputs and
recorded results do not. Existing CPU proofs are explicitly labeled as reused,
not newly measured. The build census initially refused because it counted the
completed device smoke's 25,775,792-byte driver cache as build material. It now
excludes retained evidence; the unchanged build is 288,775,204 bytes, under the
same 300 MB cap. Nothing was discarded.

All six proposals use fresh packet142c job/output names and are planned on
temporary queue copies before writing the permitted proposal files. Attention
smoke is already satisfied; its fresh smoke proposal is fallback only. Expert
gate/up and HC gate/low still require their own fresh smoke before their
brackets. All three brackets remain unrun. Packet141 selection requirements
remain in force. The compact report archive and restoration details are linked
from the packet README.

Pull refused the unrelated dirty orchestration tree. Fetch confirmed main and
origin/main both at `4a12843ddbb955f384b277c63b9f93d8c3ff47fa` before editing.
Only packet142, its six proposal files and this note belong to this repair.

Final CPU validation passes: historical report collision refusal, smoke and
five-view bracket reporting, all six real entry paths plus twelve unit/environment
negatives, twelve rank-exec boundaries plus six capped-launch negatives, all 78
worker requests and corrupted-output cooperative teardown, the pre-exec limit
gate, and drain/refusal/timing safety tests. Temporary queue planning, the live
pin guard and `ops/rehearse_entry.py` pass for all six proposals. The recovered
attention report also passes the real bracket reader. Readiness is written last.
