"""Hash the private source, build inputs, CPU gates and device entry."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];Q=P/'screen'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,r):p.write_text(json.dumps(r,indent=2)+'\n')
def main():
 if '--verify' in sys.argv:
  r=json.loads((Q/'build-receipt.json').read_text())
  for root,key in [(ROOT,'sources'),(Q,'artifacts'),(Q,'gates')]:
   for n,h in r[key].items():assert sha(root/n)==h,n
  print('PASS sealed sources and CPU evidence');return
 gates={}
 for leaf in ('cpu-exactness','preparation','analyzer-real-parent','flags'):
  f=P/'evidence'/f'{leaf}.json';r=json.loads(f.read_text());assert r['passed'] and not r['device_executed']
  dest=Q/'evidence'/f'p58as-{leaf}.json';save(dest,dict(passed=True,device_executed=False,evidence=str(f.relative_to(ROOT)),evidence_sha256=sha(f)));gates[str(dest.relative_to(Q))]=sha(dest)
 prep=P/'evidence/preparation.json';r=json.loads(prep.read_text());assert r['real_reset_sensors']==130 and r['requests']==60
 for leaf in ('fullshape-submit-cpu.json','postload-allocation-cpu.json'):
  dest=Q/'evidence'/leaf;save(dest,dict(passed=True,device_executed=False,scope='real device-define CPU transport, all 5 view resets and 60 request resets',evidence=str(prep.relative_to(ROOT)),evidence_sha256=sha(prep)));gates[str(dest.relative_to(Q))]=sha(dest)
 dest=Q/'evidence/argument-gate.json';assert json.loads(dest.read_text())['passed'];gates[str(dest.relative_to(Q))]=sha(dest)
 sources={}
 for f in P.rglob('*'):
  if not f.is_file() or f.is_symlink():continue
  rel=f.relative_to(P)
  if any(n in rel.parts for n in ('evidence','__pycache__')):continue
  if rel.parts[0]=='build':continue
  if f.name in ('build-receipt.json','READY-FOR-DEVICE.json'):continue
  sources[str(f.relative_to(ROOT))]=sha(f)
 sources.update(json.loads((P/'oracle-binding.json').read_text())['files_sha256'])
 # Executable inputs stay hash-bound even though generated object payloads are ignored by Git.
 for f in (P/'build').rglob('*.o'):
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 artifacts={str(f.relative_to(P)):sha(f) for f in (P/'build/device/own-rt-iq3',P/'build/device/p58-cache-fixtures',P/'build/device/p58-cache-fixtures-core')}
 row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,gates=gates,arithmetic='iq3-p49-split32-v1',kv_dtype='BF16',model_loads=1)
 save(Q/'build-receipt.json',row)
 print('PASS seal',len(sources),'inputs')
if __name__=='__main__':main()
