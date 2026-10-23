"""Sealed-state checks (after package_rows): real entry plan, private-copy lanequeue plan, shared entry/report
rehearsal, live pin guard. CPU only; never queues, never launches, never touches PAUSE/STOP or queue files.
Writes evidence/check-queue-rows.json."""
import importlib.util,json,subprocess,sys,tempfile,time
from pathlib import Path
from build_engine import P,ROOT,OPS,EV,limits,sha,rel,read,save
sys.path.insert(0,str(OPS));import launch_env
PROPOSAL=OPS/'lane-queue/proposed-p58-dietmicro-micro-B.txt'
def run(name,argv,env,timeout=600):
 t=time.monotonic();out=EV/(name+'.log')
 with out.open('w') as f:r=subprocess.run(argv,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 return dict(step=name,returncode=r.returncode,seconds=round(time.monotonic()-t,1),log=rel(out))
def main():
 limits();subprocess.run([sys.executable,'-B',str(P/'cpu_seal.py'),'--verify'],cwd=ROOT,check=True,stdin=subprocess.DEVNULL,capture_output=True)
 steps=[];env=launch_env.environment()
 steps.append(run('check-entry-plan',['/usr/bin/python3','-B',str(P/'run_micro.py'),'--plan','--lane','B'],env));assert steps[-1]['returncode']==0,'entry plan'
 plan=json.loads((EV/'check-entry-plan.log').read_text());assert plan['passed'] and not plan['device_executed'] and plan['host_required_available_bytes']==10*1024**3;save(EV/'plan-B.json',plan)
 with tempfile.TemporaryDirectory(prefix='p58dm-plan-') as d:
  (Path(d)/'queue-B.txt').write_bytes(PROPOSAL.read_bytes())
  steps.append(run('check-private-lanequeue-plan',['/usr/bin/python3','-B',str(OPS/'lane-queue/lanequeue.py'),'plan','--lane','B','--directory',d],env));assert steps[-1]['returncode']==0,'private lanequeue plan'
 steps.append(run('check-entry-rehearsal',['/usr/bin/python3','-B',str(OPS/'rehearse_entry.py'),str(PROPOSAL),'--report','--json'],env,timeout=1200))
 text=(EV/'check-entry-rehearsal.log').read_text();warn=[l for l in text.splitlines() if l.startswith('WARN')];report=json.loads(text[text.index('{'):]);job=report['jobs'][0]   # WARN lines (non-failing) precede the JSON
 for key in ('storage_floor','wall_deadlines','preparation_path','gate_identity'):assert job[key]['status']!='FAIL',(key,job[key])
 assert all(b['passed'] for b in job['binaries']) and job['report']['passed'] and job['passed'],'shared entry/report rehearsal'
 save(EV/'entry-report.json',report)
 spec=importlib.util.spec_from_file_location('p58dm_pin_guard_live',OPS/'lane-queue/pin_guard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 rows=[json.loads(l) for l in PROPOSAL.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')];assert len(rows)==1
 guard=m.check_job(rows[0]);assert guard['passed'] and guard['packet']==str(P),guard;save(EV/'pin-guard.json',dict(passed=True,device_executed=False,check_job=guard))
 save(EV/'check-queue-rows.json',dict(passed=True,device_executed=False,queued=False,live_queue_modified=False,proposal_sha256=sha(PROPOSAL),steps=steps,
  entry_rehearsal=dict(warnings=warn,packaging={k:job[k]['status'] for k in ('storage_floor','wall_deadlines','preparation_path','gate_identity')},binaries=[b['passed'] for b in job['binaries']],report=job['report'].get('cases')),
  pin_guard=dict(pins=guard['pins'],manifests=guard.get('manifests'))))
 print(json.dumps(dict(passed=True,steps=[(s['step'],s['returncode'],s['seconds']) for s in steps],pins=guard['pins'])))
if __name__=='__main__':main()
