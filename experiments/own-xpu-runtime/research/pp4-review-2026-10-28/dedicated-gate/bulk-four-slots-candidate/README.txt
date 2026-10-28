Four authenticated transport slots,256rows — CPU candidate,2026-10-28

Applied source candidate; root owns review, fullenginebuild and eventual GPU gate.
No speed, GPU parity or observed VRAM claim. No change to operator rows, math,
quantization, KV precision, native device allocations, defaulttwo slots or V1wire.
Explicit config dedicated_prefill_slots:4 requires dedicated_bulk_prefill:true and
 dedicated_prefill_pipeline:true; planner pins flag into request identity and passes
 --prefill-slots4 to each native owner. Default2 omits nativeflag and retainsV1.

V2 target prefillmap:8192header,32Bprefix and256tokens atoffset32;four1280Brecords
at1536,2816,4096,5376 (end6656);forward[4],reverse[4] regions after8192. Header
strictly binds slots4/header8192/rows256/stream/zeroreserves. RecordV2 reserved=4,
AckV2 reserved0=4 bind geometry under explicitversion2; oldV1 requireszeros.
Private provider shared header/capture/proposals/ACKoffset1024 are unchanged.
Slot fixture is transport position, not recurrentbankparity or target-rowfixture.
OP15 and OP28 admit slots0..3; allothercommand flag admissions remainunchanged.

Scheduler keeps one pending operation/socket and globallyfourunfinishedchunks.
Slot=k%4 lease survives until completeproviderACK plus source-record stability.
Source metadata/raw copied/authenticated before nohead replay, FIFO canonical
serial, promptSHA/lookahead/prefix hashes remainexact. Terminal Adoption carries
slotcount and independently checks matchingversion/slot/reserved/sourceextent.
No reset qualification; anyfailure poisons Guard, retains leases, drains workers
before mapclosure, never partially adopts/retries. Strict comparer explicitly
passes actualplan slots to existingprefix ingestion, default2 unchanged; counters
and sealed-state checks are not waived.

Memory: hostmap grows40MiB+4KiB pertarget forstream40960. Device prefill_allocate/
engine arithmetic source is unchanged; stillone256rowshadowset perowner, provider
ownedWitness stillonechunk. Native4slot allocation census mustconfirm prediction
before128Kcapacity/performanceclaim.

Validation, tasksetcores8-15 nice19:
 PYTHONPATH=engine/planning:engine/tools python3 -m unittest discover -s THISDIR -p 'test_*.py'
22PASS1.172s:15actualStage/Provider socket scheduler cases and7contract/planner/
layout/comparer cases (including3existingplanner baselinecases). Covers2/4slots,
2/3targets,10chunks2305prefix+1rowtail/twowraps,heldslot0while3laterchunkscomplete,
sourceoverwrite/ACK/cancel/refusedadoption, everyRecord/ACKfieldmutated, exacthost
layoutandregions, strictmapextent andactualslotcount propagation tocomparer.

 g++ -std=c++20 -O0 -I engine/src -I engine/planning THISDIR/test_four_slots_native.cpp -lcrypto -o FRESH
 FRESH
ActualnativeCPUfixture PASS:existingOwner/Sequence/capture/fixtureidentity/readonly
source/V1bulk plusV2run_loop10chunks2305rows/twowrap/partialtail,fullV2ACK/native
pairtrace,dump/FINISH,7badversion/reserved/slot/rawSHA/header/mapextent cases refused
before arithmetic. SyntheticCPUarithmetic, not actualmodel or Enginebuildproof.
No fullenginebuild or GPU/model launch performed by this subagent.

Retained implementation.patch +source-pins.json before/after, cpu-result.json,
initial-cpu-refusal.txt. Root must compare exactsamecontext/model/topology/policy
in fullstate+actualcanonicalpairs gate, then fairlongtiming ifstatepass.
