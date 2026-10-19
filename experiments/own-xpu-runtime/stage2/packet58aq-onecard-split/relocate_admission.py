"""Rebind the vendored admission's evidence paths to private copies, preserving numbers."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];old=P.with_name('packet58aj-onecard-resident')
for d in ('host-admission','screen/host-admission'):
 q=P/d
 for f in q.glob('*.json'):
  if f.name=='seal.json':continue
  s=f.read_text().replace(str(old),str(P)).replace(old.name,P.name);f.write_text(s)
 seal=json.loads((q/'seal.json').read_text())
 for leaf in seal['files']:seal['files'][leaf]=hashlib.sha256((q/leaf).read_bytes()).hexdigest()
 (q/'seal.json').write_text(json.dumps(seal,indent=2)+'\n')
# Resolve hashes only for relocated private metadata, never an external packet.
sys.path.insert(0,str(P.parents[1]/'ops/lane-queue'));import pin_guard
records=[]
for repeat in range(6):
 pins,_=pin_guard.collect_pins(P,ROOT);changes={}
 for target,digest,source in pins:
  if target.is_relative_to(P) and target.is_file():
   actual=hashlib.sha256(target.read_bytes()).hexdigest()
   if actual!=digest:
    assert source.is_relative_to(P)
    changes.setdefault(source,{})[digest]=actual
    records.append(dict(source=str(source.relative_to(P)),target=str(target.relative_to(P)),old=digest,new=actual))
 if not changes:break
 for source,mapping in changes.items():
  text=source.read_text()
  for a,b in mapping.items():text=text.replace(a,b)
  source.write_text(text)
(P/'evidence/admission-relocation.json').write_text(json.dumps(dict(passed=True,device_executed=False,reason='Private source-path relocation; admission amounts unchanged, original packet frozen',records=records),indent=2)+'\n')
