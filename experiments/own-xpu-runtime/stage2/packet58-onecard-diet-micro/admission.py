"""Admission receipt: device bytes (< 1.2 GB, no model), host need, storage, duration estimate.

Duration model: packet100b's real micro-B window executed 61,440 scrub+launch cycles in 56.8 s of window time
(evidence/micro-B/window.json elapsed_seconds), i.e. ~0.92 ms per cold cycle including the scrub kernel; packet193
(82 s on device for 3 candidates: 92,160 cold cycles + warm launches + exactness + a 1.0 GB bank upload, lanequeue-B39)
confirms the model. Here: cold interleaved 384 routes x 20 repeats x 2 orders x 2 arms = 30,720 cycles plus the fresh
production-only control 384 x 20 = 7,680 cycles (35.3 s); warm strata 4 x 2 orders x 205 x 2 arms + 205 launches.
"""
import json
from build_engine import P,ROOT,P100B,P193,EV,LINEAGE,limits,read,save,sha,rel
GIB=1024**3;SCRUB=512*1024**2
RB=820;E=512;RG=640;N=10;KG=2560
GATE_BANK=E*RG*RB;REAL=2*2*RG*N*RB;EXC=2*RG*N*RB;TABLE=65536*4;SLOTS=3*E*16+3*2*N*16;OUT_G=2*RG*N*2+2*N*4+4;FIXTURES=3
CANDIDATES=['p58-diet']
def main():
 limits()
 win=read(P100B/'evidence/micro-B/window.json');cycles=384*80*2;per_cycle=win['elapsed_seconds']/cycles
 p193=read(P193/'evidence/diet-B1/window.json');p193_seconds=p193['elapsed_seconds']
 # identical arithmetic to micro.cpp's preparation receipt
 peak=SCRUB+2*GATE_BANK+REAL+EXC+TABLE+SLOTS+(2+FIXTURES)*KG*2+OUT_G+N*12+8;assert peak<1_200_000_000
 cold_cycles=384*20*2*2;control_cycles=384*20;warm_launches=205*2*2*4+205
 strata=dict(
  cold=dict(cycles_interleaved=cold_cycles,cycles_control=control_cycles,seconds=round((cold_cycles+control_cycles)*per_cycle,1),note='each cold cycle = 512 MiB scrub + one launch; indirect slots (the record line\'s path)'),
  warm=dict(launches=warm_launches,seconds=round(warm_launches*0.0006,1),note='warm (indirect), warm-direct, 2 real-row shapes, both orders; plus the production-only warm control'),
  exactness_passes=dict(launches=384*2+2*2+16*3+2*2+6*2+2,seconds=6.0,note='per route: production + candidate with a host fetch each; plus warm/direct, 16 permuted-slot routes (x3 launches), real rows, fixtures, exceptional bank'),
  bank_generation_and_upload=dict(seconds=14.0,note='host-side LCG generation of 537 MB of synthetic 820-B rows (single thread, repack_row per row) + 31 MB real/exceptional rows + 256 KiB table + H2D'),
  startup_and_jit=dict(seconds=10.0,note='2 gate/up kernels (production, candidate) + the scrub kernel JIT'))
 total=sum(v['seconds'] for v in strata.values())
 rehearsal=read(EV/'cpu-rehearsal.json');probe=next(c['prepare_receipt'] for c in rehearsal['preparation_probe_cases'] if c['prepare_receipt'])
 assert probe['planned_device_peak_bytes']==peak,'binary and admission disagree on the device peak: %d vs %d'%(probe['planned_device_peak_bytes'],peak)
 isa=read(EV/'isa.json');assert all(isa['decisions'][c]['kept'] for c in CANDIDATES),'only ISA-kept candidates are admitted'
 row=dict(passed=True,device_executed=False,schema='packet58dm.admission.v1',lane='B',physical_card=2,pci='0000:43:00.0',candidates=CANDIDATES,
  device=dict(peak_bytes=peak,declared_upper_bound=1_200_000_000,model_load=False,
   components=dict(scrub=SCRUB,gate_bank=GATE_BANK,up_bank=GATE_BANK,real_rows_layer0_24=REAL,exceptional_bank=EXC,halfcache_table=TABLE,slot_tables=SLOTS,inputs=(2+FIXTURES)*KG*2,outputs=OUT_G)),
  host=dict(required_available_bytes=10*GIB,reserve_bytes=8*GIB,anonymous_budget_bytes=2*GIB,binary_estimate_bytes=260*1024**2,
   note='whole-host admission applies (the window driver stops the owner endpoints); the micro itself stages 3.4 MB chunks, 10 MB of fixtures, 21 MB of real rows and 10 MB of exceptional rows'),
  storage=dict(minimum_root_free_bytes=25_000_000_000,planned_write_bytes=96*1024**2,expected_samples_bytes=int((cold_cycles+control_cycles+warm_launches+2000)*260)),
  duration=dict(per_cold_cycle_seconds=round(per_cycle,5),parent=rel(P100B/'evidence/micro-B/window.json'),packet193_window_seconds=round(p193_seconds,1),strata=strata,expected_seconds=[60,int(total*3)],estimate_seconds=round(total,1),watchdog_seconds=1800,under_ten_minutes=total*3<600,
   per_candidate_seconds=dict(cold=round(cold_cycles*per_cycle,1),warm=round(warm_launches*0.0006,1))),
  identity=dict(route_count=384,cold_repeats=20,warm_repeats=200,passes=2,orders=['AB','BA'],control_order='P',warmups_excluded=5,gateup='p58ag_exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true,0,Cached=true> (820-B rows, halfcache table, indirect slots)',candidate='p58ag_diet::GateUp',
   isa_dynamic_per_weight={k:dict(candidate=v['candidate_dynamic_per_weight'],production=v['production_dynamic_per_weight'],ratio=v['ratio']) for k,v in isa['decisions'].items()}))
 save(EV/'admission.json',row);print(json.dumps(dict(peak_bytes=peak,estimate_seconds=row['duration']['estimate_seconds'],expected_seconds=row['duration']['expected_seconds'])))
if __name__=='__main__':main()
