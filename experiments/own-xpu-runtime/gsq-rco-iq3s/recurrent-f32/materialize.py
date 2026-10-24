#!/usr/bin/env python3
"""Materialize a private native source closure; no compiler or model invocation."""
from pathlib import Path
import json,hashlib,re,importlib.util,os
P=Path(__file__).resolve().parent;R=P.parents[3];L=P.parent
spec=importlib.util.spec_from_file_location('r32_source_transform',P/'prepare.py');T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)
sha=T.sha
if __name__=='__main__':
 parent=L/'dense-packed-block/engine/evidence/native-build.json';r=json.loads(parent.read_text());command=r['commands'][-1];linked={str(Path(x).resolve()) for x in command if x.endswith('.o')}
 old=[o for o in r['reused_object_provenance'] if str(Path(o['object']).resolve()) in linked]
 assert len(old)==39
 pins={str((R/n).resolve()):h for n,h in r['dependencies'].items()}
 for o in old:
  for n,h in o['dependencies'].items():
   if n in pins:assert pins[n]==h,n
   pins[n]=h
 # Include inactive quoted branches too, but only when the parent source receipt pins them.
 pending=list(pins)
 while pending:
  n=pending.pop();p=Path(n)
  for inc in re.findall(r'^\s*#\s*include\s*"([^"]+)"',p.read_text(),re.M):
   q=(p.parent/inc).resolve();key=str(q)
   if key in pins:continue
   rel=str(q.relative_to(R));assert rel in r['source_sha256'],('unbound quoted include',rel)
   pins[key]=r['source_sha256'][rel];pending.append(key)
 for n,h in pins.items():assert sha(Path(n))==h,n
 dest=P/'build/source-v2';assert not dest.exists(),'fresh private source required'
 sources={n:dest/Path(n).relative_to(R) for n in pins}
 dest.mkdir(parents=True)
 aliases={str(T.PARENTS[k]):k for k in T.PARENTS};changed={str(x) for x in T.PARENTS.values()}
 generated={}
 for n,out in sources.items():
  p=Path(n);text=p.read_text()
  if n in aliases:text=T.transform(aliases[n],text)
  # The reviewed adapter transform pointed at initial reviewable source files.
  text=text.replace(str(P/'source/kernels.hpp'),str(sources[str(T.PARENTS['kernels.hpp'])]))
  for original,replacement in sorted(sources.items(),key=lambda z:-len(z[0])):text=text.replace(original,str(replacement))
  out.parent.mkdir(parents=True,exist_ok=True);out.write_text(text);generated[str(out.relative_to(R))]=sha(out)
 entry_original=Path(r['commands'][0][r['commands'][0].index('-c')+1]);entry=sources[str(entry_original)]
 # New binary explicitly identifies the precision mode; remove only this wrapper flag
 # before passing to the unchanged current target argument parser.
 txt=entry.read_text();anchor='int main(int argc,char**argv){bool gsq=false,attention=false,qkv=false;'
 assert txt.count(anchor)==1
 txt=txt.replace(anchor,'int main(int argc,char**argv){std::vector<char*> args;args.push_back(argv[0]);bool precision=false;for(int i=1;i<argc;++i){if(std::string_view(argv[i])=="--recurrent-f32")precision=true;else args.push_back(argv[i]);}if(!precision)return 64;args.push_back(nullptr);argc=int(args.size()-1);argv=args.data();bool gsq=false,attention=false,qkv=false;')
 entry.write_text(txt);generated[str(entry.relative_to(R))]=sha(entry)
 # Physical includes must stay entirely in the cloned closure, except one additive policy.
 escapes=[]
 for n,out in sources.items():
  for inc in re.findall(r'^\s*#\s*include\s*"([^"]+)"',out.read_text(),re.M):
   path=(out.parent/inc).resolve()
   if path==P/'recurrent_policy.hpp':continue
   if path not in sources.values():escapes.append({'source':str(out),'include':inc})
 assert not escapes,escapes
 affected=[];reuse=[]
 for o in old:
  reason=sorted(changed&set(o['dependencies']))
  if reason:
   # Each retained .d starts with its actual translation unit; nested includes may be cpp.
   tus=[n for n in o['dependencies'] if n.endswith('.cpp')];assert tus
   affected.append({'index':o['index'],'source':str(sources[tus[0]]),'parent_source':tus[0],'parent_object_sha256':o['object_sha256'],'changed_dependencies':reason})
  else:reuse.append({'index':o['index'],'object':o['object'],'object_sha256':o['object_sha256'],'depfile_sha256':o['depfile_sha256'],'dependencies':o['dependencies']})
 assert len(affected)==20 and len(reuse)==19
 preview=P/'build/native-preview';compiler='/opt/intel/oneapi/compiler/2026.0/bin/icpx';flags=r['commands'][0][:r['commands'][0].index('-MMD')];assert flags[0]==compiler
 tus=[{'index':'entry','source':str(entry)},*affected];commands=[];objects=[]
 for row in tus:
  obj=preview/(str(row['index'])+'.o');objects.append(str(obj));commands.append(flags+['-MMD','-MF',str(preview/(str(row['index'])+'.d')),'-c',row['source'],'-o',str(obj)])
 link=[compiler,'-fsycl','-Wl,--gc-sections',*objects,*[o['object'] for o in reuse],'-lcrypto','-lze_loader','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib:/usr/lib/x86_64-linux-gnu','-o',str(preview/'gsq-recurrent-f32')]
 receipt={'status':'SOURCE_ONLY_BUILD_PLAN_NOT_EXECUTED','parent_build_sha256':sha(parent),'parent_binary_sha256':r['binary_sha256'],'parent_sources':pins,'generated_sha256':generated,'policy_sha256':sha(P/'recurrent_policy.hpp'),'materializer_sha256':sha(Path(__file__)),'source_patch_sha256':sha(P/'precision.patch'),'entry':str(entry),'translation_units_rebuild':tus,'objects_reused':reuse,'commands':commands+[link],'rebuild_count':len(tus),'reuse_count':len(reuse),'physical_include_escapes':escapes,'budget_pending':'21-TU native build needs fresh root/USB output-space admission; old250MiB one-TU forecast must not be reused','cpu_proof_executed':False,'native_executed':False}
 (P/'evidence/materialization.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'receipt_sha256':sha(P/'evidence/materialization.json'),'private_files':len(generated),'rebuild':len(tus),'reuse':len(reuse)}))
