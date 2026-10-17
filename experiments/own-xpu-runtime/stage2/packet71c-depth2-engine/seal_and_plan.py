"""Seal changed operator bytes and plan worker imports; never run a CPU model."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert not (P/'screen-seal.json').exists()
 build=P/'build-device-receipt.json';fixture=P/'fixture/m2-receipt.json'
 unfused=json.loads((P/'evidence/unfused.json').read_text());assert unfused['passed']
 full=json.loads((P/'evidence/fullshape.json').read_text());assert full['passed'] and len(full['admissions'])==10
 for name,digest in full['sources'].items():assert sha(ROOT/name)==digest,name
 m2=json.loads(fixture.read_text());assert m2['passed'] and m2['build_receipt_sha256']==sha(build)
 jobs=[]
 for name,kind,lineage in [('serial-smoke-B','smoke',P),('smoke-B','smoke',P),('control-B','quick',P.with_name('packet64-record-bundle')/'selections/1-draft-hc-batch'),('candidate-B','quick',P),('control-repeat-B','quick',P.with_name('packet64-record-bundle')/'selections/1-draft-hc-batch')]:
  cmd=['/usr/bin/python3','-B',str(P/'screen/screen.py'),'--kind',kind,'--lane','B','--placement','1','--lineage',str(lineage),'--seal',str(lineage/('serial-screen-seal.json' if name=='serial-smoke-B' else 'screen-seal.json')),'--binary',str(lineage/'build/device/own-rt-iq3'),'--dispatch',str(lineage/'dispatch-speed6.json'),'--output',str(P/'screen/evidence'/name)]
  jobs.append(dict(name=name,kind=kind,command=cmd,expected_seconds=180 if kind=='smoke' else 240,coordinator_arguments=['--fault-review','REVIEW_PATH','--authorized-device-window']))
 save(P/'screen/jobs.json',jobs)
 sys.path.insert(0,str(P/'screen'))
 from import_check import launch
 imports=launch('B');save(P/'evidence/worker-import-check.json',imports)
 # Load the existing seal creator under its own imports; both common modules
 # provide the same source/fixture binding contract.
 import importlib.util
 spec=importlib.util.spec_from_file_location('screen_sealer',P.parent/'screen/seal.py');creator=importlib.util.module_from_spec(spec);spec.loader.exec_module(creator)
 creator.create(P,'tp2',build,fixture,P/'build/device/own-rt-iq3',P/'dispatch-speed6.json',P/'screen-seal.json')
 seal=json.loads((P/'screen-seal.json').read_text());seal['depth2_kernels']='production'
 seal['sources'].update(full['sources'])
 seal['sources'].update(unfused['sources'])
 seal['gates']['evidence/unfused.json']=sha(P/'evidence/unfused.json')
 for mode in ('gnu-host','intel-host'):
  for suffix in ('expected','actual'):
   path=f'fixture/{mode}-unfused-{suffix}.bin';seal['fixture_files'][path]=sha(P/path)
 seal['gates']['evidence/fullshape.json']=sha(P/'evidence/fullshape.json')
 seal['scope']='changed operator CPU byte gates; inherited packet71 transaction design; full-model device checks pending'
 for mode in ('gnu-host','intel-host'):
  for suffix in ('expected','actual'):
   path=f'fixture/{mode}-{suffix}.bin';seal['fixture_files'][path]=sha(P/path)
 metadata=json.loads((P/'evidence/metadata-gate.json').read_text());assert metadata['passed']
 seal['sources'][str(Path(metadata['plan']).relative_to(ROOT))]=metadata['plan_sha256']
 # External oracle-result symlinks remain under D.oracle_inputs' pinned
 # receipt validation; do not weaken the generic in-repository path gate.
 seal['sources'].update({name:digest for name,digest in imports['files'].items()
                         if (ROOT/name).resolve().is_relative_to(ROOT) and '..' not in Path(name).parts})
 for f in sorted(P.glob('*.py')):seal['sources'][str(f.relative_to(ROOT))]=sha(f)
 for f in sorted((P/'screen').glob('*.py')):seal['sources'][str(f.relative_to(ROOT))]=sha(f)
 for name in ('screen/placements.json','screen/jobs.json','packet71-copy.json'):seal['sources'][str((P/name).relative_to(ROOT))]=sha(P/name)
 for name in ('evidence/metadata-gate.json','evidence/worker-import-check.json'):seal['gates'][name]=sha(P/name)
 save(P/'screen-seal.json',seal);save(P/'serial-screen-seal.json',dict(seal,depth2_kernels='serial'))
 wrapper={str(f.relative_to(ROOT)):sha(f) for f in (P/'screen').glob('*.py')}
 save(P/'screen/wrapper-seal.json',dict(passed=True,device_executed=False,sources=wrapper))
 for job in jobs:
  r=subprocess.run([*job['command'],'--plan'],stdin=subprocess.DEVNULL,capture_output=True,text=True)
  name=job['name'];(P/'screen'/f'{name}-plan.stderr').write_text(r.stderr);r.check_returncode();plan=json.loads(r.stdout)
  assert plan['supported'] and plan['physical_cards']==[2,3] and plan['watchdog_seconds']>=4*job['expected_seconds']
  assert plan['worker_import_check']['passed']
  save(P/'screen'/f'{name}-plan.json',plan)
 print('PASS: production/serial seals, worker imports, two smoke and three quick plans; no device/model ran')
if __name__=='__main__':main()
