#!/usr/bin/env python3
"""Source-only exact-parent transform. No compiler, model or operation invocation."""
from pathlib import Path
import json,hashlib,difflib
P=Path(__file__).resolve().parent;R=P.parents[3];L=P.parent
BASE=L/'integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2'
PARENTS={'plan.hpp':BASE/'packet3/step/plan.hpp','kernels.hpp':BASE/'packet194-expert-diet-engine/kernels.hpp','adapter.cpp':BASE/'packet194-expert-diet-engine/adapter.cpp'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def one(s,a,b):
 if s.count(a)!=1:raise ValueError('nonunique parent anchor '+a[:90])
 return s.replace(a,b)
def transform(name,s):
 if name=='plan.hpp':
  for old in ['buffer(tag + "history", {ch, 3});','buffer(tag + "state", {g.vh, g.d, g.d});','buffer(t + "ple.history", {4 * g.h, 9});']:
   s=one(s,old,old[:-2]+', Scalar::f32);')
 elif name=='kernels.hpp':
  s=one(s,'// All floating tensors are BF16 except F32 routing probabilities and scratch.','// Activations/KV remain BF16; flag16 selects F32 GDN matrix/conv/PLE histories.')
  s=one(s,'  float* f(int slot)const{return static_cast<float*>(p[slot]);}','  float* f(int slot)const{return static_cast<float*>(p[slot]);}\n  float recurrent(int slot,size_t i,int flags)const{return (flags&16)?f(slot)[i]:b(slot,i);}\n  void put_recurrent(int slot,size_t i,float x,int flags)const{if(flags&16)f(slot)[i]=x;else put(slot,i,x);}')
  s=one(s,' if(s.op==conv&&s.extra!=0',' if((s.flags&16)&&s.op!=conv&&s.op!=gdn)throw std::invalid_argument("F32 recurrent flag on non-recurrent op");\n if(s.op==conv&&s.extra!=0')
  s=one(s,'b(1,W*3*(s.extra?s.extra:1));','n[1]=W*3*(s.extra?s.extra:1)*((s.flags&16)?4:2);')
  s=one(s,'b(5,48*128*128);','n[5]=48*128*128*((s.flags&16)?4:2);')
  s=one(s,'a.b(row?7:5,state+k)*decay','a.recurrent(row?7:5,state+k,s.flags)*decay')
  s=one(s,'a.put(7,state+k,t.x[256+k]);','a.put_recurrent(7,state+k,t.x[256+k],s.flags);')
  s=one(s,'history[j]=a.b(1,ch*hist+j);','history[j]=a.recurrent(1,ch*hist+j,s.flags);')
  s=one(s,'a.put(4,ch*hist+j,history[j]);','a.put_recurrent(4,ch*hist+j,history[j],s.flags);')
 elif name=='adapter.cpp':
  s=one(s,'#include "'+str(BASE/'packet194-expert-diet-engine/kernels.hpp')+'"','#include "'+str(P/'source/kernels.hpp')+'"\n#include "'+str(P/'recurrent_policy.hpp')+'"')
  anchor=' ng::Shape shape{};shape.capacity=s.g.context;shape.extent=s.extent;shape.budget=s.g.budget;'
  s=one(s,anchor,anchor+'\n if(s.special==Special::normal&&(s.op==Op::gdn||s.op==Op::conv)){\n  const int input=s.op==Op::gdn?3:1;\n  if(s.ni<=input||s.no!=2)throw std::invalid_argument("recurrent state binding shape");\n  shape.flags|=recurrent_f32::admit(s.types[input],s.types[s.ni+1],Scalar::bf16,Scalar::f32,s.implementation);\n }')
 else:raise ValueError(name)
 return s
if __name__=='__main__':
 build=L/'dense-packed-block/engine/evidence/native-build.json';b=json.loads(build.read_text());pins={};patch=[];generated={}
 for name,p in PARENTS.items():
  rel=str(p.relative_to(R));assert sha(p)==b['source_sha256'][rel];pins[rel]=sha(p);old=p.read_text();new=transform(name,old)
  out=P/'source'/name;out.write_text(new);generated[str(out.relative_to(R))]=sha(out)
  patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=rel,tofile=str(out.relative_to(R))))
 (P/'precision.patch').write_text(''.join(patch))
 affected=[]
 for obj in b['reused_object_provenance']:
  changed=sorted(set(obj['dependencies'])&{str(p) for p in PARENTS.values()})
  if changed:affected.append({'index':obj['index'],'object':obj['object'],'object_sha256':obj['object_sha256'],'changed_dependencies':changed,'translation_units':[n for n in obj['dependencies'] if n.endswith('.cpp')]})
 receipt={'status':'SOURCE_CHECKPOINT_NO_COMPILER_OR_EXECUTION','parent_native_build_sha256':sha(build),'parent_binary_sha256':b['binary_sha256'],'source_sha256':pins,'generated_sha256':generated,'policy_sha256':sha(P/'recurrent_policy.hpp'),'transform_sha256':sha(Path(__file__)),'affected_reused_objects':affected,'requires_current_entry_rebuild':True,'old_39_object_reuse_allowed':False,'full_private_include_relocation_pending':True}
 (P/'evidence/source-checkpoint.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'affected_reused_objects':len(affected),'receipt_sha256':sha(P/'evidence/source-checkpoint.json')}))
