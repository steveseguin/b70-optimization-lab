#!/usr/bin/env python3
import hashlib,json,os,struct,subprocess,mmap
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def main():
 rows=[];seen=set()
 with (B/'p33-timing').open('rb') as f:
  binary=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  for path in sorted((B/'candidate-spv').glob('*.spv')):
   b=path.read_bytes();w=struct.unpack('<'+'I'*(len(b)//4),b);i=5;names=[]
   while i<len(w):
    n=w[i]>>16;op=w[i]&65535;v=w[i+1:i+n]
    if op==15:names.append(struct.pack('<'+'I'*len(v[2:]),*v[2:]).split(b'\0')[0].decode())
    i+=n
   if not any('3p33' in n or '5p33r2' in n for n in names) or binary.find(b)<0:continue
   digest=hashlib.sha256(b).hexdigest()
   if digest in seen:continue
   seen.add(digest)
   tag='p33-'+hashlib.sha256(b).hexdigest()[:12];dump=B/('igc-'+tag)
   argv=['/usr/bin/ocloc','compile','-spirv_input','-file',str(path),'-device','0xe223','-revision_id','0','-options','-ze-opt-level=O2 -cl-fp32-correctly-rounded-divide-sqrt','-out_dir',str(B/('aot-'+tag))]
   env={k:v for k,v in os.environ.items() if not k.startswith(('IGC_','NEO_','UR_','SYCL_','ZE_'))};env.update(IGC_ShaderDumpEnable='1',IGC_DumpToCustomDir=str(dump),IGC_ShowFullVectorsInShaderDumps='1')
   with (B/(tag+'.log')).open('w') as log:r=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,env=env)
   rows.append(dict(module=str(path.relative_to(P)),sha256=hashlib.sha256(b).hexdigest(),binary_offset=binary.find(b),kernels=names,argv=argv,returncode=r.returncode,dump=str(dump.relative_to(P))))
   if r.returncode:raise RuntimeError(tag)
   print(tag,len(names),flush=True)
 (P/'candidate-modules.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
