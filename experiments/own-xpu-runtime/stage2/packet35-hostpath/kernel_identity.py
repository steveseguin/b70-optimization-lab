"""CPU-only source and embedded SPIR-V identity audit. Never loads a device binary.

The embedded module hash is stronger than entry-point-name equivalence: a body,
constant, or helper change must fail even when a mangled kernel name stays fixed.
"""
import argparse, hashlib, importlib.util, json, re, struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'packet29-merged'
ROOT=HERE.parents[3]
def sha(data): return hashlib.sha256(data).hexdigest()
def load(name, path):
 spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def source_rows(base):
 gate=load('identity_math_'+base.name.replace('-','_'),base/'math_gate.py')
 overlay=load('identity_overlay_'+base.name.replace('-','_'),base/'kernel_overlay.py')
 rows={};files={}
 for path in gate.closure():
  name=str(path.relative_to(ROOT)).replace('packet29-merged','PACKET').replace('packet35-hostpath','PACKET')
  raw=path.read_text();text=overlay.apply(path,raw);files[name]=sha(raw.encode())
  if (base/'submission_overlay.py').exists():
   submission=load('identity_submission_'+base.name.replace('-','_'),base/'submission_overlay.py')
   text=submission.apply_submission_overlay(path,text)
  bodies=[]
  for m in re.finditer(r'\.\s*(parallel_for|single_task)(?:<[^;]*?>)?\s*\(',text):
   match=re.search(r'\[(?:=|&)?\]\s*(?:\([^;]*?\))?\s*(?:\[\[.*?\]\])?\s*\{',text[m.end():],re.S)
   if not match:raise ValueError('unsupported lambda '+str(path))
   start=m.end()+match.start();body=m.end()+match.end()-1;end=body+1;depth=1
   while depth:
    depth+=(text[end]=='{')-(text[end]=='}');end+=1
   bodies.append(dict(kind=m[1],sha256=sha(text[start:end].encode())))
  if bodies:rows[name]=bodies
 return files,rows

def offload_section(data):
 assert data[:6]==b'\x7fELF\x02\x01','requires little-endian ELF64'
 shoff=struct.unpack_from('<Q',data,40)[0];entsize,count,strings=struct.unpack_from('<HHH',data,58)
 headers=[struct.unpack_from('<IIQQQQIIQQ',data,shoff+i*entsize) for i in range(count)]
 h=headers[strings];names=data[h[4]:h[4]+h[5]]
 sections=[]
 for h in headers:
  name=names[h[0]:].split(b'\0')[0].decode()
  if name=='__CLANG_OFFLOAD_BUNDLE__sycl-spir64':sections.append(data[h[4]:h[4]+h[5]])
 assert len(sections)==1,'missing/ambiguous embedded device section'
 return sections[0]

def spirv(binary):
 data=binary.read_bytes();section=offload_section(data);starts=[];offset=0
 while True:
  offset=section.find(b'\x03\x02\x23\x07',offset)
  if offset<0:break
  if offset+20<=len(section):
   magic,version,generator,bound,schema=struct.unpack_from('<5I',section,offset)
   if schema==0 and 0x10000<=version<=0x10600 and bound>0:starts.append(offset)
  offset+=4
 assert starts,'no SPIR-V images (compression/new format requires a new parser)'
 modules=[]
 for start,limit in zip(starts,starts[1:]+[len(section)]):
  offset=start+20;names=[];instructions=0
  while offset+4<=limit:
   word=struct.unpack_from('<I',section,offset)[0];count,op=word>>16,word&65535
   if count==0:break
   assert offset+count*4<=limit,'SPIR-V image boundary/word count error'
   if op==15: # OpEntryPoint: model, id, NUL-terminated UTF-8 name, interface ids.
    names.append(section[offset+12:offset+count*4].split(b'\0')[0].decode())
   offset+=count*4;instructions+=1
  assert not any(section[offset:limit]),'unparsed nonzero bytes after SPIR-V instructions'
  modules.append(dict(sha256=sha(section[start:offset]),bytes=offset-start,instructions=instructions,kernel_names=sorted(names)))
 return dict(binary_sha256=sha(data),modules=sorted(modules,key=lambda x:(x['kernel_names'],x['sha256'])),kernel_names=sorted(n for m in modules for n in m['kernel_names']))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source-only',action='store_true');ap.add_argument('--output',type=Path,default=HERE/'kernel-identity.json');a=ap.parse_args()
 oldfiles,oldbodies=source_rows(BASE);newfiles,newbodies=source_rows(HERE)
 sources=dict(passed=oldbodies==newbodies,kernel_lambda_count=sum(map(len,newbodies.values())),kernel_bodies=newbodies,source_sha256=newfiles,changed_source_files=[p for p in sorted(set(oldfiles)|set(newfiles)) if oldfiles.get(p)!=newfiles.get(p)])
 registry={name:dict(before=sha((BASE/name).read_bytes()),after=sha((HERE/name).read_bytes())) for name in ('kernel-registry.json','k2-class-registry.json')}
 registry_pass=all(v['before']==v['after'] for v in registry.values())
 images={}
 if not a.source_only:
  for name in ('own-rt-iq3','nongemv-fixtures','k2-fixtures','jit-smoke'):
   before=BASE/'build/device'/name;after=HERE/'build/device'/name
   if not before.exists() or not after.exists():
    images[name]=dict(passed=False,reason='compile-only binary missing',before_exists=before.exists(),after_exists=after.exists());continue
   b,n=spirv(before),spirv(after)
   images[name]=dict(passed=b['modules']==n['modules'],names_equal=b['kernel_names']==n['kernel_names'],before=b,after=n)
 report=dict(schema='packet35.device-kernel-identity.v1',passed=sources['passed'] and registry_pass and bool(images) and all(v['passed'] for v in images.values()),device_executed=False,source=sources,registries=registry,registries_equal=registry_pass,binaries=images,scope='Exact kernel lambda source hashes, unchanged kernel/class registries, exact embedded SPIR-V module bytes and OpEntryPoint names. Host source differences require separate review. Source-only does not close binary identity.')
 # Store each module/name list once. Binary references retain exact multiplicity
 # and order; no evidence is dropped by this lossless JSON representation.
 modules={}
 for entry in images.values():
  for side in ('before','after'):
   if side not in entry:continue
   metadata=entry[side]
   for module in metadata['modules']:
    identity=module['sha256']
    if identity in modules:assert modules[identity]==module
    modules[identity]=module
   entry[side]=dict(binary_sha256=metadata['binary_sha256'],modules=[m['sha256'] for m in metadata['modules']],kernel_entry_points=len(metadata['kernel_names']),kernel_names_sha256=sha(json.dumps(metadata['kernel_names'],separators=(',',':')).encode()))
 report['spirv_modules']=modules
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(output=str(a.output),passed=report['passed'],source_passed=sources['passed'],kernels=sources['kernel_lambda_count'],binaries={n:{k:v for k,v in x.items() if k in ('passed','names_equal','reason')} for n,x in images.items()})))
 if not sources['passed'] or not registry_pass or (not a.source_only and not report['passed']):raise SystemExit(1)
if __name__=='__main__':main()
