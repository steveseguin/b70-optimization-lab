"""Admission receipt: device bytes per phase (< 1.2 GB, no model), host need, storage, duration estimate.

Duration model: packet100b's real micro-B window executed 61,440 scrub+launch cycles in 56.8 s of window time
(evidence/micro-B/window.json elapsed_seconds), i.e. ~0.92 ms per cold cycle including the scrub kernel; packet192
(34 s on device for 30,720 cold cycles + 2,460 warm launches + exactness + 1.0 GB bank upload) confirms the model.
Per candidate the cold stratum is 384 routes x 20 repeats x 2 orders x 2 arms = 30,720 cycles (28.3 s).
"""
import json
from build_engine import P,ROOT,P100B,P192,EV,LINEAGE,limits,read,save,sha,rel
GIB=1024**3;SCRUB=512*1024**2
GATE_BANK=512*640*840;DOWN_BANK=512*2560*360;REAL=2*12800*840;EXC=2*640*10*840;DEXC=2560*10*360;OUT_G=25684;OUT_GA=OUT_G+12800;OUT_D=51244;FIXTURES=3
CANDIDATES={'exp-diet':'gateup','exp-act-epilogue':'gateup','down-diet':'down'}
def main():
 limits()
 win=read(P100B/'evidence/micro-B/window.json');cycles=384*80*2;per_cycle=win['elapsed_seconds']/cycles
 p192=read(P192/'evidence/issue-floor-B1/window.json');p192_seconds=(p192['finished_utc_ns']-p192['started_utc_ns'])/1e9
 # identical arithmetic to micro.cpp's preparation receipt: scrub + max(phase) + 256 B of small buffers (routes, active)
 phase_gateup=SCRUB+2*GATE_BANK+REAL+EXC+(2+FIXTURES)*2560*2+OUT_GA+256;phase_down=SCRUB+DOWN_BANK+DEXC+(1+FIXTURES)*640*10*2+OUT_D+256
 peak=max(phase_gateup,phase_down);assert peak<1_200_000_000
 cold_cycles=384*20*2*2;warm_launches=205*2*2
 strata=dict(
  cold=dict(candidates=3,cycles_per_candidate=cold_cycles,cycles=3*cold_cycles,seconds=round(3*cold_cycles*per_cycle,1),note='each cold cycle = 512 MiB scrub + one launch (the epilogue control adds the act launch, ~0.01 ms)'),
  warm=dict(launches=warm_launches*(3+2+1),seconds=round(warm_launches*6*0.0006,1),note='gate/up candidates: warm + 2 real shapes; down: warm'),
  exactness_passes=dict(launches=384*(4+2)+120,seconds=12.0,note='per route: production, act twin, two gate/up candidates; down production + candidate; plus fixtures, each with a host fetch'),
  bank_generation_and_upload=dict(seconds=22.0,note='host-side LCG generation of 1.0 GB of synthetic rows (single thread) + 20 MB exceptional banks + H2D'),
  startup_and_jit=dict(seconds=15.0,note='14 kernels (6 production/candidate/act + scrub instantiations) JIT'))
 total=sum(v['seconds'] for v in strata.values())
 rehearsal=read(EV/'cpu-rehearsal.json');probe=next(c['prepare_receipt'] for c in rehearsal['preparation_probe_cases'] if c['prepare_receipt'])
 assert probe['planned_device_peak_bytes']==peak,'binary and admission disagree on the device peak'
 isa=read(EV/'isa.json');assert all(isa['decisions'][c]['kept'] for c in CANDIDATES),'only ISA-kept candidates are admitted'
 row=dict(passed=True,device_executed=False,schema='packet193.admission.v1',lane='B',physical_card=2,pci='0000:43:00.0',candidates=list(CANDIDATES),
  device=dict(phase_gateup_bytes=phase_gateup,phase_down_bytes=phase_down,peak_bytes=peak,declared_upper_bound=1_200_000_000,model_load=False,
   components=dict(scrub=SCRUB,gate_bank=GATE_BANK,up_bank=GATE_BANK,down_bank_tile16=DOWN_BANK,real_rows_layer0_24=REAL,exceptional_gateup_bank=EXC,exceptional_down_bank=DEXC)),
  host=dict(required_available_bytes=10*GIB,reserve_bytes=8*GIB,anonymous_budget_bytes=2*GIB,binary_estimate_bytes=260*1024**2,
   note='whole-host admission applies (the window driver stops the owner endpoints); the micro itself stages 3.4 MB chunks, 31 MB of fixtures, 21 MB of real rows and 20 MB of exceptional banks'),
  storage=dict(minimum_root_free_bytes=25_000_000_000,planned_write_bytes=96*1024**2,expected_samples_bytes=int((3*cold_cycles+warm_launches*6+5000)*300)),
  duration=dict(per_cold_cycle_seconds=round(per_cycle,5),parent=rel(P100B/'evidence/micro-B/window.json'),packet192_window_seconds=round(p192_seconds,1),strata=strata,expected_seconds=[60,int(total*3)],estimate_seconds=round(total,1),watchdog_seconds=1800,under_ten_minutes=total*3<600,
   per_candidate_seconds=dict(cold=round(cold_cycles*per_cycle,1),warm=round(warm_launches*2*0.0006,1))),
  identity=dict(route_count=384,cold_repeats=20,warm_repeats=200,passes=2,orders=['AB','BA'],warmups_excluded=5,gateup='p90exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true>',down='p100::Kernel<2>',act='p193diet::ActProduction (silu_product twin)',
   isa_dynamic_per_weight={k:dict(candidate=v['candidate_dynamic_per_weight'],production=v['production_dynamic_per_weight'],ratio=v['ratio']) for k,v in isa['decisions'].items()}))
 save(EV/'admission.json',row);print(json.dumps(dict(peak_bytes=peak,estimate_seconds=row['duration']['estimate_seconds'],expected_seconds=row['duration']['expected_seconds'],per_candidate=row['duration']['per_candidate_seconds'])))
if __name__=='__main__':main()
