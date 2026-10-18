# Packet145 — router and GDN z exact load-time order

Preparation started 2026-10-18 at 21:16 UTC on steve-b70s. CPU only; no GPU,
model payload, service, live queue, sudo or host-setting operation is authorized.
Root free space was about 30 GB. Pull refused unrelated dirty orchestration;
fetch confirmed HEAD and origin/main at 5b660ab676c190a45b4cc9b18943dc0f6f458d19.

The new `stage2/packet145-router-gdnz-layout` vendors packet142 after its 142c
report/import repair. Source commit and original hashes are in
`lineage-inputs/vendor-origin.json`. Original symlink objects are preserved,
including immutable inherited objects; active source and import dependencies
are local. The packet49 oracle remains bound by its original binding/helper.
Packet142 and every other existing packet remain untouched.

The two variants preserve every stored row byte and the selected FP32 arithmetic
and reduction order. Router copies the complete four-projection fused/shared
tuple in consumer order, including Q6 and Q8 shared-branch shapes. GDN z copies
only that projection class in layer order. These are allocation-order hypotheses,
not claims that separate allocations are physically adjacent or faster.

This differs from packet104/104b's closed row transposes, packet112's probability
selection changes, packet140's unsupported standalone savings hypotheses, and
packet142's mixed attention-prefix bank. The rationale is packet141's newly
measured router 1.86× and gdn.z 1.30× cold/warm gaps. These gaps are diagnostic;
combined engine savings with the separately queued attention arm are unmeasured.

Both native compilers build through `ops/compile_turn.py`. CPU commands use
`nice -n 19 taskset -c 8-15,24-31 python3 -B ... < /dev/null`. CPU address limits
are set only inside CPU command entrypoints. Native exec rehearsals preserve
unlimited inherited limits and reject a finite address cap. The closed launch
environment is vendored directly from `ops/launch_env.py`.

The first full-shape capture comparison refused the router Q8 fallback. Its
host audit embeds weight addresses in `p30integrated::Small` metadata; copied
weights intentionally have different addresses. The retained diagnostic checks
show unchanged kernel types and all other bindings. The fixture now verifies
each metadata pointer against its actual binding, normalizes only the four
copied weight-pointer slots to their original allocations, and compares every
other operation byte. This is a CPU audit repair; native kernels are unchanged.
An attempted padding-serializer adjustment was disproved by the byte dump and
reverted. The byte fixture also covers Q8 shared projections and Q8 GDN z.

All eight full-shape fresh/switch runs and eight real-parser startups pass.
The five-view checks include six rollback bank pairs, complete mutable-state
reset, immutable weight extents, allocation identity and invalid-selection
refusals. No model data is read: allocations are numerical CPU tokens.

| Variant | Rank | Copied bytes | Tensors | Arena margin bytes |
| --- | ---: | ---: | ---: | ---: |
| router-order600 | 0 | 229,473,280 | 96 | 3,838,599,052 |
| router-order600 | 1 | 229,908,480 | 96 | 556,360,998 |
| gdnz-order600 | 0 | 371,712,000 | 18 | 3,696,360,332 |
| gdnz-order600 | 1 | 373,800,960 | 18 | 412,468,518 |

Router covers 24 complete layer tuples per rank; GDN z covers all 18 relevant
layers per rank. The bank cap is unchanged at 600 MiB per rank. No view-boundary
weight copy/allocation is added. Physical device residency is unmeasured.

Restoring the inherited fixture archive briefly tripped the build-material
postcheck at 303,539,910 bytes. Removing only this task's regenerable linked
entry objects brought it below the unchanged 300 MB cap; source, binaries,
receipts and failure evidence were retained. No reserve or host limit was raised.

The proposal contract is lane-specific: A cards 0+1; B cards 2+3. Each variant
has a 12×64 smoke and one-load five-view 12×128 bracket per lane. A bracket must
load its own variant's same-lane smoke. All proposals use `screen-<job>` units,
fixed environment, oracle, admission, drain and getrlimit checks. Only temporary
queue copies are planned; no live queue is edited.

Readiness remains pending until the entry, report and pin gates are complete.
GNU/Intel synthetic bytes are CPU evidence only. The 58.798108759182306 record
is unchanged; exact model outputs and any speed effect need coordinator device
work. No proposal is queued by this preparation.

## Milestone 1 — router lane A ready, 2026-10-18T21:32:20.130495+00:00

The first lane-A readiness marker was written after 16.0 minutes; the post-marker
pin correction below was required before it was usable. Both
compilers passed two fresh byte transcripts each: 52,915,200 copied weight
bytes, 699,781 FP32 chain checks and 15,361 output rows; all four hashes match.
Peak byte-test child RSS was 267,528 KiB; native compilation peaked at
735,512 KiB. Build material is 290,573,357 bytes.

All eight real entries and sixteen wrong-unit/environment refusals pass; both
lanes retain their correct native BDF mask. Sixteen launch-limit probes cover
both native ranks and capped-launch refusal. The worker checks cover all 78
smoke/bracket requests plus corrupted-output cooperative teardown. All eight
real report paths (variant × lane × smoke/bracket) pass through the actual
manifest-induced import path. The first report fixture needed its lane and
conditions updated to match each new entry; no production report was bypassed.

The router-A proposal passes temporary queue planning, ops/rehearse_entry.py
and the live pin guard. The guard initially rejected inherited object alias
paths; canonical resolved immutable ELF paths fix the source map. The original
build receipt and driver are retained, and every native/source/binary hash was
verified unchanged before this bookkeeping reseal. The final A entry was
rechecked after the report-only fixes.

The marker is written last and scopes readiness to router smoke on lane A.
Other proposal mirrors are staged locally; their external files and final
all-lane handoff follow in milestone 2. No GPU, service or live queue changed.

The post-marker pin check caught a cross-packet proposal-file pin in the first
marker. It now binds the byte-identical proposal mirror inside packet145.
Temporary planning and loader/pin checks were repeated; the corrected marker
is written last and checked read-only after writing. No device launch occurred.

## Milestone 2 — both variants, both lanes, 2026-10-18T21:35:29.612204+00:00

All eight external proposals and matching local mirrors now pass temporary
queue planning, ops/rehearse_entry.py and the live pin guard. Final report
coverage is eight real-entry smoke/bracket combinations. The final readiness
marker is written last and checked read-only afterward. Total preparation
time before this marker is 19.1 minutes; build material is
290,573,357 bytes and root free space remains above 25 GB.

The coordinator updated ops/pin_guard.py during this work. Only its new local
snapshot changed here; all final plans checked that snapshot against the live
implementation. No existing ops source or live queue was changed by this task.
The local-mirror marker binding remains in use regardless of that guard update.
The first scoped marker and its original gate snapshots remain provenance;
the final marker supersedes them for admission.

Git whitespace checking reports inherited trailing whitespace/blank lines in
vendored patches, native snapshots and historical logs. Those original bytes
are intentionally preserved. The 51.88 MiB legacy fixture archive is inherited
reproduction evidence; retention-census.json binds all large tracked artifacts
and explains restoration. No generated cache is committed.

Device exactness and performance are still pending. No model read, GPU work,
service, sudo, live queue, foreign-process signal or host setting changed.

The corrected lane-A marker was pushed at 21:33:44 UTC, 17.35 minutes after
preparation began, within the 40-minute milestone. Coordinator-owned review
files appeared afterward; they are preserved and excluded from this commit.
This preparation itself did not queue or launch a device job.
