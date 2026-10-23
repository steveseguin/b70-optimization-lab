"""Seal the packet's CPU closure (own files only; parents are provenance records). --seal writes
evidence/cpu-seal.json; --verify re-hashes it. Pins are own-packet paths plus this packet's proposal and
the frozen v4-lanes wrappers, so the live pin guard sees zero cross-packet mutable pins."""
import argparse,json,sys
from pathlib import Path
from build_engine import P,ROOT,NATIVE,BUILD,EV,LINEAGE,limits,sha,rel,read,save
PROPOSAL=P.parents[1]/'ops/lane-queue/proposed-p58-dietmicro-micro-B.txt';WRAPPER=P.parent/'screen/v4-lanes'
RECEIPTS=('build.json','fixtures.json','cpu-rehearsal.json','admission.json','isa.json','analysis-tests.log','cpu-host-gnu.jsonl','cpu-host-intel.jsonl','do-not-repeat-search.txt')
def closure():
 files=set()
 for pattern in ('*.py','*.cpp','*.hpp','*.json','*.md','.gitignore'):files.update(p for p in P.glob(pattern) if p.is_file() and p.name!='READY-FOR-DEVICE.json' and p.name!='cpu-seal.json')
 files.update(p for p in NATIVE.rglob('*') if p.is_file());files.update(p for p in LINEAGE.iterdir() if p.is_file());files.update(p for p in (P/'proposals').glob('*.txt'))
 files.update(BUILD/('micro-'+m) for m in ('gnu-host','intel-host','device'));files.update(p for p in (BUILD/'fixtures').iterdir())
 files.update(EV/n for n in RECEIPTS);files.update(p for p in (EV/'isa').glob('*.asm.gz'));files.add(PROPOSAL)
 files.update(WRAPPER/n for n in ('common.py','conditions.py','cpu_seal.py','chain_devices.py','devices.py','drain_gate.py','fault_review.py','lane_admission.py','screen.py','wrapper-seal.json'))
 return {rel(f):sha(f) for f in sorted(files) if f.is_file()}
def parents_verified():
 inputs=read(LINEAGE/'parent-inputs.json');rows=[]
 for p in inputs['parents']:
  if 'parent_relpath' in p:
   assert sha(ROOT/p['parent_relpath'])==p['parent_digest'],'parent changed: '+p['name'];rows.append(p['name'])
 for p in read(P/'native-provenance.json')['parents']:
  assert sha(ROOT/p['parent_relpath'])==p['parent_digest'],'native parent changed: '+p['name'];rows.append(p['name'])
 return rows
def seal():
 limits();build=read(EV/'build.json');modes={r['mode']:r['sha256'] for r in build['records']}
 for name in RECEIPTS[:5]:assert read(EV/name)['passed'] is True and read(EV/name)['device_executed'] is False,name
 tests=(EV/'analysis-tests.log').read_text();assert tests.rstrip().endswith('OK') and 'Ran 9 tests' in tests,'analyzer tests'
 isa=read(EV/'isa.json');assert all(isa['decisions'][c]['kept'] for c in ('p58-diet',)) and isa['source_sha256']==sha(P/'micro.cpp')
 row=dict(schema='packet58dm.cpu-seal.v1',passed=True,device_executed=False,binary_sha256=modes['device'],host_twins={k:modes[k] for k in ('gnu-host','intel-host')},
  proposal=rel(PROPOSAL),proposal_sha256=sha(PROPOSAL),parents_verified_in_place=parents_verified(),sources=closure())
 save(EV/'cpu-seal.json',row);print('sealed',len(row['sources']),'files; device',modes['device'][:16])
def verify():
 row=read(EV/'cpu-seal.json');assert row['passed'] is True and row['device_executed'] is False
 for name,digest in row['sources'].items():assert sha(ROOT/name)==digest,'sealed file changed: '+name
 assert row['sources']==closure(),'source closure changed; reseal required'
 parents_verified();return row
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');ap.add_argument('--verify',action='store_true');a=ap.parse_args()
 if a.seal:seal()
 else:verify();print('seal verified')
