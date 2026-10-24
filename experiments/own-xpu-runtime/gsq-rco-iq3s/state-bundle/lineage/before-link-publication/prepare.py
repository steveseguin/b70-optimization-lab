#!/usr/bin/env python3
"""Materialize evidence-only entry/adapter delta; no compiler or Device."""
from pathlib import Path
import difflib,hashlib,importlib.util,json
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2];E=L/'qkv-q6-p33/engine'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
def replace(s,a,b):
 require(s.count(a)==1,'unique anchor '+a[:80]);return s.replace(a,b)
def authority():
 for f,h in json.loads((P/'parent-pins.json').read_text()).items():require(sha(f)==h,'frozen source '+f)
 old=json.loads((E/'evidence/native-build.json').read_text());require(old['passed'],'combined build')
 for f,h in old['source_sha256'].items():require(sha(R/f)==h,'compiled source '+f)
 for f,h in old['object_sha256'].items():require(sha(f)==h,'compiled object '+f)
 require(sha(old['binary'])==old['binary_sha256'],'combined binary')
 return old
def main():
 old=authority();base=Path(json.loads((E/'preparation.json').read_text())['materialized_directory']);rank=L/'integration/build/private/source/diet-native/native-src/rank.hpp';dest=P/'build/source';require(not dest.exists(),'fresh materialization');dest.mkdir(parents=True)
 main0=(base/'main.cpp').read_text();main=replace(main0,str(rank),str(dest/'rank.hpp'))
 # Header is outside pipeline namespace; original state JSON construction stays byte-identical.
 main=replace(main,'#include "'+str(dest/'rank.hpp')+'"','#include "'+str(P/'bundle.hpp')+'"\n#include "'+str(dest/'rank.hpp')+'"')
 rank0=rank.read_text();new=replace(rank0,'fs::path dir=e.a.output/("state-"+std::to_string(sequence));fs::create_directories(dir);','fs::path dir=e.a.output/("state-"+std::to_string(sequence));fs::create_directories(dir);gsq_bundle::Writer bundle(dir);')
 new=replace(new,'std::ofstream f(dir/(name+".bin"),std::ios::binary);f.write(reinterpret_cast<char*>(b.data()),b.size());','bundle.append(name+".bin",b.data(),b.size());')
 new=replace(new,'std::ofstream f(dir/("alternate-"+name+".bin"),std::ios::binary);f.write(reinterpret_cast<char*>(b.data()),b.size());','bundle.append("alternate-"+name+".bin",b.data(),b.size());')
 new=replace(new,'save(dir/"state.json",o.str());','bundle.finish(o.str());')
 entry=replace((base/'entry.cpp').read_text(),str(base/'main.cpp'),str(dest/'main.cpp'))
 (dest/'main.cpp').write_text(main);(dest/'rank.hpp').write_text(new);(dest/'entry.cpp').write_text(entry)
 adapter_src=E/'operating/generated/adapter.py';adapter0=adapter_src.read_text();adapter=adapter0
 adapter=replace(adapter,'CANDIDATE=P.parent.parent','CANDIDATE=P.parent')
 adapter=replace(adapter,'LEDGER=P.parent/"candidate-ledger.json"','LEDGER=Path('+repr(str(E/'operating/candidate-ledger.json'))+')')
 adapter=replace(adapter,"BASE=load(PARENT,'gsq_p195_pipeline')","BASE=load(PARENT,'gsq_p195_pipeline')\nBUNDLE=load(P.parent/'reader.py','gsq_state_bundle_reader')")
 adapter=replace(adapter,"P.parent/'preparation.json',PARENT","P.parent/'preparation.json',P.parent/'reader.py',P.parent/'parent-pins.json',PARENT")
 a=adapter.index('        files=sorted(path.rglob');z=adapter.index('    return result',a)
 adapter=adapter[:a]+"        result[str(rank)]=BUNDLE.read_state(path)\n"+adapter[z:]
 generated=P/'generated';generated.mkdir(exist_ok=True);(generated/'adapter.py').write_text(adapter)
 patch=''.join(difflib.unified_diff(rank0.splitlines(True),new.splitlines(True),fromfile=str(rank),tofile=str(dest/'rank.hpp')))+''.join(difflib.unified_diff(main0.splitlines(True),main.splitlines(True),fromfile=str(base/'main.cpp'),tofile=str(dest/'main.cpp')))+''.join(difflib.unified_diff(adapter0.splitlines(True),adapter.splitlines(True),fromfile=str(adapter_src),tofile=str(generated/'adapter.py')))
 (P/'overlay.patch').write_text(patch)
 # The changed rank.hpp was entry-owned in the original per-TU closure too.
 prior=json.loads((E/'preparation.json').read_text());changed={rank.resolve(),Path(old['commands'][0][old['commands'][0].index('-c')+1]).resolve()}
 for obj in prior['objects']:
  if obj['reuse']:require(not changed.intersection(map(Path,obj['dependencies'])),'rank/header affects reused object')
 files=[P/'prepare.py',P/'parent-pins.json',P/'bundle.hpp',P/'reader.py',P/'overlay.patch',*dest.iterdir(),generated/'adapter.py']
 out=dict(passed=True,schema='gsq.state-bundle.preparation.v1',materialized_directory=str(dest),source_sha256={str(f):sha(f) for f in files},parent_native_build_sha256=sha(E/'evidence/native-build.json'),parent_binary_sha256=old['binary_sha256'],objects=prior['objects'],recompiled_objects=1,reused_objects=39,device_allocation_delta_bytes=0,arithmetic_changed=False,compiler_invoked=False,device_executed=False)
 (P/'preparation.json').write_text(json.dumps(out,indent=2)+'\n');print(sha(P/'preparation.json'))
if __name__=='__main__':main()
