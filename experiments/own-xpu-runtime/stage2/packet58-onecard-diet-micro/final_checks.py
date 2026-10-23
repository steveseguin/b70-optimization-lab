"""Final checks; --ready writes READY-FOR-DEVICE.json LAST, then re-runs the live pin guard and classifies
every pin (any cross-packet mutable pin withdraws READY). Writes evidence/final-checks.json and, with --ready,
evidence/final-pin-guard.json. Never queues; lane state is observed (hashed), never written."""
import argparse,datetime,importlib.util,json,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,OPS,EV,BUILD,limits,sha,rel,read,save,build_bytes
import run_micro
LQ=OPS/'lane-queue';NAME='proposed-p58-dietmicro-micro-B.txt'
RECEIPTS=('build','fixtures','cpu-rehearsal','admission','isa','package-rows','check-queue-rows','pin-guard','plan-B','entry-report','cpu-seal')
def verify():
 subprocess.run([sys.executable,'-B',str(P/'cpu_seal.py'),'--verify'],cwd=ROOT,check=True,stdin=subprocess.DEVNULL,capture_output=True)
 out={}
 for name in RECEIPTS:
  row=read(EV/(name+'.json'))
  if name=='entry-report':assert row['passed'] is True and row['jobs'][0]['report']['passed'] is True and row['jobs'][0]['preparation_path']['status']=='PASS',name
  else:assert row.get('device_executed') is False and row['passed'] is True,name
  out[rel(EV/(name+'.json'))]=sha(EV/(name+'.json'))
 build=read(EV/'build.json');assert build['warning_lines']==0 and {r['mode'] for r in build['records']}=={'gnu-host','intel-host','device'}
 reh=read(EV/'cpu-rehearsal.json');assert reh['gnu_intel_byte_rows_identical'] and reh['gnu']['exact_rows']==reh['gnu']['byte_equal_rows'] and reh['gnu']['nan_rows']==reh['gnu']['nan_equal_rows'] and reh['gnu']['bytes_rows']==411*3+17 and len(reh['preparation_probe_cases'])==9
 for twin in ('gnu','intel'):
  assert all(v['value_mismatches']==0 and v['nocache_value_mismatches']==0 and v['table_vs_half_value_mismatches']==0 and v['blocks']>=100000 for v in reh[twin]['stress'].values()) and all(v['fp32_mismatches']==0 and v['nocache_fp32_mismatches']==0 and v['table_vs_half_mismatches']==0 for k,v in reh[twin]['stress'].items() if k=='finite')
 isa=read(EV/'isa.json');assert all(isa['decisions'][c]['kept'] for c in run_micro.CANDIDATES) and isa['source_sha256']==sha(P/'micro.cpp')
 adm=read(EV/'admission.json');assert adm['device']['peak_bytes']<1_200_000_000 and adm['duration']['under_ten_minutes'] and adm['duration']['watchdog_seconds']==1800
 tests=(EV/'analysis-tests.log').read_text();assert tests.rstrip().endswith('OK')
 live,mirror=LQ/NAME,P/'proposals'/NAME;assert sha(live)==sha(mirror)==read(EV/'package-rows.json')['proposal_sha256']==read(EV/'check-queue-rows.json')['proposal_sha256']
 assert build_bytes()<=2_000_000_000
 pauses={p.name:sha(p) for p in sorted(LQ.glob('PAUSE-*'))};queues={p.name:sha(p) for p in sorted(LQ.glob('queue-*.txt'))}
 row=dict(passed=True,device_executed=False,queued=False,cpu_seal_sha256=sha(EV/'cpu-seal.json'),binary_sha256=read(EV/'cpu-seal.json')['binary_sha256'],receipts=out,
  build_bytes=build_bytes(),device_peak_bytes=adm['device']['peak_bytes'],expected_seconds=adm['duration']['expected_seconds'],proposal=rel(live),proposal_sha256=sha(live),
  isa_decisions={k:dict(kept=v['kept'],ratio=v['ratio']) for k,v in isa['decisions'].items()},
  lane_state_observed=dict(pause_files=sorted(pauses),queue_files=sorted(queues),note='observed only; never written by preparation'))
 save(EV/'final-checks.json',row);return row
def pin_guard():
 spec=importlib.util.spec_from_file_location('p58dm_pin_guard_final',LQ/'pin_guard.py');m=importlib.util.module_from_spec(spec);m and spec.loader.exec_module(m)
 rows=[json.loads(l) for l in (LQ/NAME).read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
 checks=[m.check_job(r) for r in rows];assert all(c['passed'] and c['packet']==str(P) for c in checks)
 pins,manifests=m.collect_pins(P);oracle={(p,h) for p,h,s in pins if s.name=='oracle-binding.json'};classes={};cross=[]
 for p,h,s in pins:
  if p.is_relative_to(P) and p.resolve().is_relative_to(P.resolve()):key='packet-private'
  else:
   reason=m.immutable_reason(p,h,P,oracle,m.STAGE);key=reason or 'CROSS-PACKET MUTABLE'
   if not reason:cross.append(str(p))
  classes[key]=classes.get(key,0)+1
 return dict(check_job=[dict(job=r['name'],passed=c['passed'],pins=c.get('pins')) for r,c in zip(rows,checks)],collected_pins=len(pins),manifests=len(manifests),
  ready_in_closure=any(Path(x).name=='READY-FOR-DEVICE.json' for x in manifests),classes=classes,cross_packet_mutable_pins=len(cross),cross_examples=cross[:10])
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--ready',action='store_true');a=ap.parse_args();limits()
 ready=P/'READY-FOR-DEVICE.json'
 if a.ready and ready.exists():sys.exit('READY-FOR-DEVICE.json already exists; withdraw it first')
 row=verify();print('final checks PASS: seal',row['cpu_seal_sha256'][:16],'device binary',row['binary_sha256'][:16])
 if not a.ready:return
 seal=read(EV/'cpu-seal.json');checks=dict(row['receipts'],**{rel(EV/'final-checks.json'):sha(EV/'final-checks.json')})
 marker=dict(schema='packet58dm.readiness.v1',ready=True,ready_for_device=True,device_executed=False,queued=False,diagnostic_only=True,measurement_only=True,speed_claim=False,model_output_claim=False,
  created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),proposal=row['proposal'],proposal_sha256=row['proposal_sha256'],job_name=read(EV/'package-rows.json')['rows'][0]['job'],
  native_command=run_micro.native_command(),binary_sha256=row['binary_sha256'],expected_seconds=row['expected_seconds'],watchdog_seconds=run_micro.WATCHDOG,device_peak_bytes=row['device_peak_bytes'],candidates=run_micro.CANDIDATES,
  decision_rule=dict(gate='candidate <= 0.85 x production cold AND warm (both launch orders) after device byte identity on every claimed stratum; warm-direct and the real-row strata are reported, not gated',
   kill_rules=['any byte difference in a claimed stratum on the device (value difference; withholds the candidate) - NaN-only strata (f2, exceptional) are compared by is-NaN per word and a payload-order-only difference never kills','production cold/warm disagreement with the fresh production-only pass > 10 % (withholds the verdict)','any stratum with p90/median > 1.5 (host disturbance; withholds the verdict)'],
   isa_gate='the candidate reduced the single-lane dynamic instruction count per weight offline (evidence/isa.json: 15.66 -> 12.02, ratio 0.767) with no spills',source='coordinator ruling 2026-10-23 (packet58-onecard-diet-micro brief)'),
  sources=seal['sources'],checks=checks,next_action='The lane-B window driver may admit the ONE proposal row through the existing device guards (endpoints stopped by the driver; whole-host admission). No retry, no reseal after a result exists.')
 ready.write_text(json.dumps(marker,indent=2)+'\n')   # must be the last artifact write
 try:guard=pin_guard()
 except Exception as error:
  ready.rename(EV/('withdrawn-ready-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S')+'.json'));sys.exit('READY withdrawn: pin guard refused: '+str(error)[:600])
 save(EV/'final-pin-guard.json',dict(passed=guard['cross_packet_mutable_pins']==0,device_executed=False,**guard))
 if guard['cross_packet_mutable_pins']:
  ready.rename(EV/('withdrawn-ready-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S')+'.json'));sys.exit('READY withdrawn: cross-packet mutable pins '+str(guard['cross_examples']))
 run_micro.execution_gate()
 print(json.dumps(dict(ready=True,pins=guard['collected_pins'],classes=guard['classes'],cross_packet_mutable_pins=0)))
if __name__=='__main__':main()
