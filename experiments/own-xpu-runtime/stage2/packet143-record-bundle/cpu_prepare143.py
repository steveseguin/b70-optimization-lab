"""Seal every composition only after its own CPU proofs; never fabricate a pass."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from compositions import P,ROOT,read,save,sha,native,key,path,all_compositions
GATES=('bytes143','memory143','submission-rehearsal143','full-shape143','policy143','drain143','limits143')
def verify_map(rows):
 for n,h in rows.items():assert sha(ROOT/n)==h,'CPU source changed: '+n

def sources():
 paths=set()
 for base in (P/'native-base',P/'v5',P/'lineage-inputs/vendor/repo',P/'lineage-inputs/submission-tools',P/'lineage-inputs/orchestration'):
  paths.update(f for f in base.rglob('*') if f.is_file() and not f.is_symlink() and f.suffix in ('.py','.hpp','.cpp','.inc','.bf16','.tsv') and 'build' not in f.relative_to(base).parts and 'evidence' not in f.relative_to(base).parts)
 paths.update(f for f in P.glob('*') if f.is_file() and f.suffix in ('.py','.hpp','.cpp','.inc','.bf16','.tsv'))
 paths.update(P/'lineage-inputs'/n for n in ('bundle8-selection.json','bundle8-memory-plan.json','token-table-receipt.json','component-registration.json','record-threshold.json'))
 # Oracle is validated through its binding, never read through a source alias.
 return {str(f.resolve().relative_to(ROOT)):sha(f) for f in paths if not f.is_relative_to(P/'oracle')}
def prepare():
 build=read(P/'v5/evidence/build.json');assert build['passed'];verify_map(build['sources']);verify_map(build['artifacts'])
 gates={n:read(P/'evidence'/(n+'.json')) for n in GATES}
 for name,row in gates.items():
  assert row['passed'] is True and row['device_executed'] is False,name
  verify_map(row.get('sources',{}))
 assert len(gates['full-shape143']['runs'])==32 and gates['full-shape143']['model_payload_read'] is False
 assert len(gates['bytes143']['rows'])==64 and gates['bytes143']['compositions']==16
 closure=sources();closure.update({str((ROOT/n).resolve().relative_to(ROOT)):h for n,h in build['sources'].items()});closure.update(build['artifacts'])
 closure.update({str((P/'evidence'/(n+'.json')).relative_to(ROOT)):sha(P/'evidence'/(n+'.json')) for n in GATES})
 # Compositions are all sealed against a common fixed runtime and individual
 # config/memory bytes. Selecting one later never requalifies source changes.
 from memory143 import plan
 for s in all_compositions():
  dest=path(s);dest.mkdir(parents=True,exist_ok=True)
  for leaf,row in [('composition.json',s),('selection.json',native(s)),('memory-plan.json',plan(s))]:save(dest/leaf,row)
  (dest/'dispatch-speed6.json').write_bytes((P/'dispatch-speed6.json').read_bytes())
  artifacts={}
  for mode in ('device','gnu-host'):
   target=dest/'build'/mode/'own-rt-iq3';target.parent.mkdir(parents=True,exist_ok=True)
   if not target.exists():target.symlink_to(os.path.relpath(P/'v5/build'/mode/'own-rt-iq3',target.parent))
   artifacts[str(target.relative_to(dest))]=sha(target)
  bound=dict(closure,**{str((dest/n).relative_to(ROOT)):sha(dest/n) for n in ('composition.json','selection.json','memory-plan.json','dispatch-speed6.json')})
  save(dest/'gate.json',dict(passed=True,device_executed=False,composition=s,proofs={n:sha(P/'evidence'/(n+'.json')) for n in GATES}))
  fixture=P/'evidence/mini-byte-reference.json.gz'
  for n in ('expected','actual'):(dest/(n+'.bin.gz')).write_bytes(fixture.read_bytes())
  save(dest/'screen-seal.json',dict(schema='own-runtime.screen.cpu-seal.v1',passed=True,device_executed=False,arithmetic='iq3-p49-split32-v1',profile='tp2',sources=bound,artifacts=artifacts,gates={'gate.json':sha(dest/'gate.json')},fixture_files={n+'.bin.gz':sha(dest/(n+'.bin.gz')) for n in ('expected','actual')},composition=s))
 wrapper=dict(schema='packet143.cpu-composition.v1',passed=True,device_executed=False,sources=closure,compositions={key(s):sha(path(s)/'screen-seal.json') for s in all_compositions()},binary_sha256=sha(P/'v5/build/device/own-rt-iq3'))
 save(P/'cpu-seal.json',wrapper);save(P/'placement-validation/wrapper-seal.json',wrapper)
 return verify()
def verify():
 snapshot=P/'lineage-inputs/orchestration';ops=P.parents[1]/'ops/packet143-orchestration'
 for f in snapshot.iterdir():assert (ops/f.name).read_bytes()==f.read_bytes(),'orchestration differs: '+f.name
 row=read(P/'cpu-seal.json');assert row['passed'] is True and row['device_executed'] is False
 checks={}
 def bind(path,digest):
  path=path.resolve()
  if path in checks:assert checks[path]==digest,'conflicting identity'
  checks[path]=digest
 def mapping(entries):
  for n,h in entries.items():bind(ROOT/n,h)
 mapping(row['sources']);assert len(row['compositions'])==16
 for s in all_compositions():
  dest=path(s);bind(dest/'screen-seal.json',row['compositions'][key(s)])
  seal=read(dest/'screen-seal.json');mapping(seal['sources'])
  for group in ('gates','artifacts','fixture_files'):
   for name,h in seal[group].items():bind(dest/name,h)
 for f,h in checks.items():assert sha(f)==h,'CPU source changed: '+str(f)
 assert read(P/'placement-validation/wrapper-seal.json')==row
 return row
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');a=ap.parse_args();prepare() if a.seal else verify();print('16 composition seals PASS')
