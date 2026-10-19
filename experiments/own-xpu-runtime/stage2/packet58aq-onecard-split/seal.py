"""Seal p58aq CPU evidence and its actual queue implementation; no device authority."""
import hashlib,json,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];Q=P/'screen'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,r):p.write_text(json.dumps(r,indent=2)+'\n')
def main():
 if '--verify' in sys.argv:
  row=json.loads((Q/'build-receipt.json').read_text())
  for root,key in ((ROOT,'sources'),(Q,'artifacts'),(Q,'gates')):
   for n,h in row[key].items():assert sha(root/n)==h,n
  print('PASS packet58aq sealed inputs');return
 exact=json.loads((P/'evidence/cpu-exactness.json').read_text())
 for r in exact['records']:
  assert r['binary_sha256']==sha(P/'build'/r['compiler']/'own-rt-iq3')
  assert r.get('view_resets')==6 and r['resets']==72 and r['real_sensor_samples']==156
 prep=json.loads((P/'evidence/preparation.json').read_text())
 assert prep['target_binary_sha256']==sha(P/'build/device/own-rt-iq3')
 assert prep['native_source_sha256']==sha(P/'native/generated/main.cpp')
 assert prep['probe_source_sha256']==sha(P/'native/preparation_probe.cpp')
 assert prep['real_reset_sensors']==156 and prep['view_resets']==6
 gates={}
 for leaf in ('argument-gate.json','fullshape-submit-cpu.json','postload-allocation-cpu.json'):
  f=Q/'evidence'/leaf;r=json.loads(f.read_text());assert r['passed'] and not r['device_executed'];gates['evidence/'+leaf]=sha(f)
 for leaf in ('cpu-exactness','preparation','analyzer-real-parent','report-adapter','flags','k1-help'):
  f=P/'evidence'/f'{leaf}.json';r=json.loads(f.read_text());assert r['passed'] and not r['device_executed']
  dest=Q/'evidence'/f'p58aq-{leaf}.json';save(dest,dict(passed=True,device_executed=False,evidence=str(f.relative_to(ROOT)),evidence_sha256=sha(f)));gates[str(dest.relative_to(Q))]=sha(dest)
 sources={}
 for f in P.rglob('*'):
  if not f.is_file() or f.is_symlink():continue
  rel=f.relative_to(P)
  if any(x in rel.parts for x in ('build','evidence','__pycache__')):continue
  if f.name in ('build-receipt.json','READY-FOR-DEVICE.json','ready.json','vendor.json'):continue
  if f.suffix in ('.py','.cpp','.hpp','.h','.json','.tsv','.bf16','.md'):
   sources[str(f.relative_to(ROOT))]=sha(f)
 sources.update(json.loads((P/'oracle-binding.json').read_text())['files_sha256'])
 artifacts={}
 for mode in ('device','gnu-host','intel-host'):
  for leaf in ('own-rt-iq3','p58-cache-fixtures','p58-cache-fixtures-core','fullshape-submit'):
   f=P/'build'/mode/leaf
   if f.exists():artifacts[str(f.relative_to(P))]=sha(f)
 # Private inherited object identities are explicitly retained as build inputs.
 inherited={str(f.relative_to(ROOT)):sha(f) for f in (P/'build').rglob('*.o') if f.is_file()}
 sources.update(inherited)
 size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file());assert size<=300_000_000
 row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,gates=gates,
  arithmetic='iq3-p49-split32-v1',resident_lookups=True,diagnostic_only=True,submission_eligible=False,
  cache_allocation_bytes=21552729600,kv_dtype='BF16',retained_build_bytes=size,
  shared_report_schema='frozen five-view checker cannot generate six-view 32-token inputs; private report_adapter.py passes actual real report functions',
  source_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip())
 save(Q/'build-receipt.json',row)
 # Root receipt uses the same artifacts; screen gate paths stay explicitly rooted.
 save(P/'build-receipt.json',dict(row,gates={'screen/'+n:h for n,h in gates.items()}))
 print('PASS sealed',len(sources),'sources',size,'build bytes')
if __name__=='__main__':main()
