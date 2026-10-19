"""Final CPU-only readiness: all gates and proposals checked, READY written last."""
import argparse,json,os,subprocess,time
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
ap=argparse.ArgumentParser();ap.add_argument('--ready',action='store_true');a=ap.parse_args();limits()
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip()=='main'
for name,lanes in [('one-card','A'),('two-card','AB')]:
 p=P/name
 checks={}
 for leaf in ['build.json','identity-check.json','analyzer-tests.json','report512-test.json','preparation-build.json','preparation-probe.json','device-path-imports.json','flags.json']:
  f=p/'evidence'/leaf;r=json.loads(f.read_text());assert r['passed'],(name,leaf);checks['evidence/'+leaf]=sha(f)
 assert json.loads((p/'evidence/preparation-probe.json').read_text())['device_executed']is False
 for lane in lanes:
  stem=('one'if name=='one-card'else'two')+'-'+lane
  report=P/'evidence'/('rehearse-'+stem+'.json');r=json.loads(report.read_text());assert r['passed']and len(r['jobs'])==2
  for job in r['jobs']:assert job['passed']and job['report']['passed']and not job['service_started']
  checks['shared-report-'+lane]=sha(report)
  lines=[json.loads(s)for s in (P/'evidence'/('plan-'+stem+'.log')).read_text().splitlines()if s.startswith('{')]
  assert len(lines)==2 and all(r['plan']=='passed'for r in lines)
  checks['lanequeue-plan-'+lane]=sha(P/'evidence'/('plan-'+stem+'.log'))
 seal=json.loads((p/'seal.json').read_text())
 for leaf,h in seal['files'].items():assert sha(p/leaf)==h,(name,leaf)
 identity=json.loads((p/'identity.json').read_text());assert sha(p/'build/device/own-rt-iq3')==identity['binary_sha256']
 budget=json.loads((p/'budget.json').read_text());assert budget['device_floor_bytes']==25_000_000_000 and budget['cpu_stop_bytes']==27_000_000_000 and budget['multiplier_over_scaled_measured']<=3
 for lane in lanes:
  for attempt in ['a','b']:assert not(p/'evidence'/f'device-full512-{lane}-{attempt}').exists(),'output already used'
 if a.ready:save(p/'READY-FOR-DEVICE.json',dict(ready=True,device_executed=False,queued=False,created_utc_ns=time.time_ns(),seal_sha256=sha(p/'seal.json'),checks=checks,scope='CPU preparation passed; actual512 prefill/performance/long-output quality unmeasured',oracle_cap=128,full_output_oracle_exact=False,shared_prepare_subcheck='WARN: schema lacks one-card argv/private4MB constant support; separate sandboxed probes passed',synthetic_report_scope='shared64/128 plus local512; no synthetic performance claims'))
 print(name,'final checks PASS', 'READY written'if a.ready else'READY not written')
if a.ready:
 proposals=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'
 save(P/'READY-FOR-DEVICE.json',dict(ready=True,device_executed=False,queued=False,created_utc_ns=time.time_ns(),
  packets={name:sha(P/name/'READY-FOR-DEVICE.json')for name in ['one-card','two-card']},
  proposals=[dict(path=str((proposals/f'proposed-p163-{name}-{lane}.txt').relative_to(ROOT)),sha256=sha(proposals/f'proposed-p163-{name}-{lane}.txt'))for name,lane in [('one-card','A'),('two-card','A'),('two-card','B')]],
  record_choice='packet136 bundle8 remains current; packet155 parked after W0p failure before timing; one-card packet58aj',
  actual512_measurements=False,full_output_oracle_exact=False,scope='CPU preparation only; choose one two-card lane proposal; no queue action'))
