"""Admission receipt: device bytes per phase (< 1.2 GB, no model), host need, storage, duration estimate.

Duration model: packet100b's real micro-B window executed 61,440 scrub+launch cycles (384 routes x 80 x 2
candidates, 512 MiB scrub each) in 56.8 s of window time (evidence/micro-B/window.json elapsed_seconds),
i.e. ~0.92 ms per cold cycle including the scrub kernel. Packet162b's 1,600 warm events took ~1 s.
"""
import json
from build_engine import P,ROOT,P100B,EV,LINEAGE,limits,read,save,sha,rel
GIB=1024**3;SCRUB=512*1024**2
GATE_BANK=512*640*840;DOWN_BANK=512*2560*360;REAL=2*12800*840;OUT_G=25684;OUT_D=51244
def main():
 limits()
 win=read(P100B/'evidence/micro-B/window.json');cycles=384*80*2;per_cycle=win['elapsed_seconds']/cycles
 # identical arithmetic to micro.cpp's preparation receipt: scrub + max(phase) + 256 B of small buffers (routes, active)
 phase_gateup=SCRUB+2*GATE_BANK+REAL+2*2560*2+OUT_G+256;phase_down=SCRUB+DOWN_BANK+6400*2+OUT_D+256
 peak=max(phase_gateup,phase_down);assert peak<1_200_000_000
 cold_cycles=384*20*2;warm_launches=(205)*2;strata=dict(
  gateup_cold=dict(cycles=cold_cycles,seconds=round(cold_cycles*per_cycle,1)),down_cold=dict(cycles=cold_cycles,seconds=round(cold_cycles*per_cycle,1)),
  gateup_warm_real_noload=dict(launches=warm_launches*4,seconds=round(warm_launches*4*0.0006,1)),down_warm_noload=dict(launches=warm_launches*2,seconds=round(warm_launches*2*0.0006,1)),
  exactness_passes=dict(launches=384*2+8,seconds=5.0),bank_generation_and_upload=dict(seconds=20.0,note='host-side LCG generation of 1.0 GB of synthetic rows (single thread) + H2D'),
  startup_and_jit=dict(seconds=10.0))
 total=sum(v['seconds'] for v in strata.values())
 rehearsal=read(EV/'cpu-rehearsal.json');probe=next(c['prepare_receipt'] for c in rehearsal['preparation_probe_cases'] if c['prepare_receipt'])
 assert probe['planned_device_peak_bytes']==peak,'binary and admission disagree on the device peak'
 row=dict(passed=True,device_executed=False,schema='packet192.admission.v1',lane='B',physical_card=2,pci='0000:43:00.0',
  device=dict(phase_gateup_bytes=phase_gateup,phase_down_bytes=phase_down,peak_bytes=peak,declared_upper_bound=1_200_000_000,model_load=False,
   components=dict(scrub=SCRUB,gate_bank=GATE_BANK,up_bank=GATE_BANK,down_bank_tile16=DOWN_BANK,real_rows_layer0_24=REAL)),
  host=dict(required_available_bytes=10*GIB,reserve_bytes=8*GIB,anonymous_budget_bytes=2*GIB,binary_estimate_bytes=200*1024**2,
   note='whole-host admission applies (the window driver stops the owner endpoints); the micro itself stages 3.4 MB chunks, 30 MB of fixtures and 21 MB of real rows'),
  storage=dict(minimum_root_free_bytes=25_000_000_000,planned_write_bytes=64*1024**2,expected_samples_bytes=int((cold_cycles*2+warm_launches*6+800)*230)),
  duration=dict(per_cold_cycle_seconds=round(per_cycle,5),parent=rel(P100B/'evidence/micro-B/window.json'),strata=strata,expected_seconds=[30,int(total*3)],estimate_seconds=round(total,1),watchdog_seconds=1800,under_ten_minutes=total*3<600),
  identity=dict(route_count=384,cold_repeats=20,warm_repeats=200,passes=2,warmups_excluded=5,gateup='p90exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true>',down='p100::Kernel<2>'))
 save(EV/'admission.json',row);print(json.dumps(dict(peak_bytes=peak,estimate_seconds=row['duration']['estimate_seconds'],expected_seconds=row['duration']['expected_seconds'])))
if __name__=='__main__':main()
