import json,hashlib,os,subprocess,gzip,shutil,struct,importlib.util,re
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build/extras'
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 if shutil.disk_usage('/').free<8*1024**3:raise RuntimeError('STOP below8GB free')
 binary=(B/'p42-extras').read_bytes();seen=set();rows=[];commands=[];modules=[]
 for f in (B/'spv').glob('*.spv'):
  data=f.read_bytes();words=struct.unpack('<'+'I'*(len(data)//4),data);i=5;names=[]
  while i<len(words):
   n=words[i]>>16
   if words[i]&65535==15:names.append(struct.pack('<'+'I'*(n-3),*words[i+3:i+n]).split(b'\0')[0].decode())
   i+=n
  if any('9p42extras' in name for name in names):modules.append(dict(file=str(f),kernels=names))
 (P/'extras-modules.json').write_text(json.dumps(modules,indent=2)+'\n')
 (P/'extras-evidence').mkdir(exist_ok=True)
 spec=importlib.util.spec_from_file_location('analysis',P.parent/'packet33-codegen/analyze.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.P=P
 for row in json.loads((P/'extras-modules.json').read_text()):
  f=Path(row['file']).resolve();blob=f.read_bytes();sha=hashlib.sha256(blob).hexdigest()
  if sha in seen or binary.find(blob)<0:continue
  seen.add(sha);dump=B/('igc-'+sha[:12]);aot=B/('aot-'+sha[:12]);cmd=['/usr/bin/ocloc','compile','-spirv_input','-file',str(f),'-device','0xe223','-revision_id','0','-options','-ze-opt-level=O2 -cl-fp32-correctly-rounded-divide-sqrt','-out_dir',str(aot)];env={k:v for k,v in os.environ.items() if not k.startswith(('IGC_','NEO_','UR_','SYCL_','ZE_'))};env.update(IGC_ShaderDumpEnable='1',IGC_DumpToCustomDir=str(dump),IGC_ShowFullVectorsInShaderDumps='1')
  with (B/('ocloc-'+sha[:12]+'.log')).open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env)
  commands.append(dict(command=cmd,returncode=r.returncode,spv_sha256=sha,native_offset=binary.find(blob)));print(sha[:12],r.returncode,flush=True)
  if r.returncode:raise RuntimeError('ocloc failed')
  sections=mod.binary_text_sections(dump)
  for asm in dump.glob('*entry_*.asm'):
   record=mod.parse(asm);record['atomic_memory_ops']=len(re.findall(r'^.*\batomic_[a-z]+\.[^\n]*',asm.read_text(),re.M));pair=sections.get(record['kernel']);dat=asm.with_suffix('.dat');selected=bool(pair and dat.exists() and pair[1].startswith(dat.read_bytes()) and not any(pair[1][len(dat.read_bytes()):]))
   if not selected:continue
   target=P/'extras-evidence'/(sha[:12]+'-'+asm.name+'.gz');target.write_bytes(gzip.compress(asm.read_bytes(),mtime=0));record.update(assembly_gzip=str(target.relative_to(P)),spv_sha256=sha,offline_binary_selected=selected,gen_sha256=hashlib.sha256(pair[1]).hexdigest());rows.append(record)
  for file in dump.iterdir():
   if file.is_file():file.unlink()
  dump.rmdir()
  for file in aot.iterdir():
   if file.is_file():file.unlink()
  aot.rmdir()
 (P/'extras-codegen.json').write_text(json.dumps(dict(device_executed=False,commands=commands,kernels=rows,counting_note="packet33 static parser; memory_messages excludes atomic_* opcodes separately counted; barriers counts barrier-related instructions, not logical barriers"),indent=2)+'\n')
if __name__=='__main__':main()
