"""Seal bounded CPU evidence and coordinator-only smoke/quick commands."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert not (P/'screen-seal.json').exists()
 gate=json.loads((P/'fixture/receipt.json').read_text());assert gate['passed']
 # Retain the concatenated real compared state bytes, not a fabricated receipt.
 expected=bytearray();actual=bytearray()
 for case in gate['cases']:
  folder=P/'fixture'/f"fixture{case['fixture']}"
  for rank in (0,1):
   left=folder/'packet64'/f'rank{rank}/state-2147483647';right=folder/case['forced']/f'rank{rank}/state-2147483647'
   for path in sorted(left.glob('*.bin')):expected.extend(path.read_bytes());actual.extend((right/path.name).read_bytes())
 assert expected==actual and expected
 for key,data in (('expected',expected),('actual',actual)):(P/'fixture'/f'{key}.bin').write_bytes(data)
 build=P/'build-device-receipt.json'
 sources={str((P/name).relative_to(ROOT)):sha(P/name) for name in ('cpu_gate.py','pipeline.py','depth2_controller.hpp','dependent_rows.hpp','fixture/receipt.json')}
 byte=dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='dependent row transactions and exact acceptance prefixes',command=['python3','-B',str(P/'cpu_gate.py')],build_receipt_sha256=sha(build),sources=sources)
 for key in ('expected','actual'):byte[key]=dict(path=f'fixture/{key}.bin',sha256=sha(P/'fixture'/f'{key}.bin'))
 save(P/'fixture/byte-receipt.json',byte)
 jobs=[]
 for name,kind,lineage in [('serial-smoke-B','smoke',P),('smoke-B','smoke',P),('control-B','quick',P.with_name('packet64-record-bundle')/'selections/1-draft-hc-batch'),('candidate-B','quick',P),('control-repeat-B','quick',P.with_name('packet64-record-bundle')/'selections/1-draft-hc-batch')]:
  cmd=['python3','-B',str(P/'screen/screen.py'),'--kind',kind,'--lane','B','--placement','1','--lineage',str(lineage),'--seal',str(lineage/('serial-screen-seal.json' if name=='serial-smoke-B' else 'screen-seal.json')),'--binary',str(lineage/'build/device/own-rt-iq3'),'--dispatch',str(lineage/'dispatch-speed6.json'),'--output',str(P/'screen/evidence'/name)]
  jobs.append(dict(name=name,kind=kind,command=cmd,coordinator_arguments=['--fault-review','REVIEW_PATH','--authorized-device-window']))
 save(P/'screen/jobs.json',jobs)
 sys.path.insert(0,str(P.parent/'screen'));from seal import create
 create(P,'tp2',build,P/'fixture/byte-receipt.json',P/'build/device/own-rt-iq3',P/'dispatch-speed6.json',P/'screen-seal.json')
 seal=json.loads((P/'screen-seal.json').read_text());seal['depth2_kernels']='production'
 m2=json.loads((P/'fixture/m2-receipt.json').read_text());assert m2['passed'] and m2['build_receipt_sha256']==sha(build)
 for name,digest in m2['sources'].items():assert sha(ROOT/name)==digest
 seal['sources'].update(m2['sources']);seal['gates']['fixture/receipt.json']=sha(P/'fixture/receipt.json');seal['gates']['fixture/m2-receipt.json']=sha(P/'fixture/m2-receipt.json')
 for mode in ('gnu-host','intel-host'):
  for suffix in ('expected','actual'):
   path=f'fixture/{mode}-{suffix}.bin';seal['fixture_files'][path]=sha(P/path)
 metadata=json.loads((P/'evidence/metadata-gate.json').read_text());assert metadata['passed']
 seal['sources'][str(Path(metadata['plan']).relative_to(ROOT))]=metadata['plan_sha256']
 seal['gates']['evidence/metadata-gate.json']=sha(P/'evidence/metadata-gate.json')
 for f in sorted(P.glob('*.py')):seal['sources'][str(f.relative_to(ROOT))]=sha(f)
 for f in sorted((P/'screen').glob('*.py')):seal['sources'][str(f.relative_to(ROOT))]=sha(f)
 seal['sources'][str((P/'screen/placements.json').relative_to(ROOT))]=sha(P/'screen/placements.json')
 seal['sources'][str((P/'screen/jobs.json').relative_to(ROOT))]=sha(P/'screen/jobs.json')
 save(P/'screen-seal.json',seal)
 serial=dict(seal,depth2_kernels='serial');save(P/'serial-screen-seal.json',serial)
 wrapper={str(f.relative_to(ROOT)):sha(f) for f in (P/'screen').glob('*.py')}
 save(P/'screen/wrapper-seal.json',dict(passed=True,device_executed=False,sources=wrapper))
 for job in jobs:
  name=job['name'];kind=job['kind'];cmd=job['command']
  r=subprocess.run([*cmd,'--plan'],stdin=subprocess.DEVNULL,capture_output=True,text=True)
  (P/'screen'/f'{name}-plan.stderr').write_text(r.stderr);r.check_returncode();plan=json.loads(r.stdout)
  assert plan['supported'] and plan['physical_cards']==[2,3] and plan['watchdog_seconds']>=4*(180 if kind=='smoke' else 240)
  save(P/'screen'/f'{name}-plan.json',plan)
 print('PASS: production/serial seals, two smoke and three matched quick plans; no device ran')
if __name__=='__main__':main()
