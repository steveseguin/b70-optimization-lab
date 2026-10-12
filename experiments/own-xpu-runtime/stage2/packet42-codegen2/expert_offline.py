import gzip,hashlib,json,os,shutil,struct,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build/expert'
rows=[]
for spv in B.glob('*.spv'):
 data=spv.read_bytes();w=struct.unpack('<'+'I'*(len(data)//4),data);i=5;names=[]
 while i<len(w):
  n=w[i]>>16;op=w[i]&65535;v=w[i+1:i+n]
  if op==15:names.append(struct.pack('<'+'I'*len(v[2:]),*v[2:]).split(b'\0')[0].decode())
  i+=n
 if not any('p42expert' in n for n in names):continue
 if shutil.disk_usage('/').free<8*1024**3:raise RuntimeError('STOP: root free < 8 GiB')
 dump=B/'igc';out=B/'aot';cmd=['/usr/bin/ocloc','compile','-spirv_input','-file',str(spv),'-device','0xe223','-revision_id','0','-options','-ze-opt-level=O2 -cl-fp32-correctly-rounded-divide-sqrt','-out_dir',str(out)]
 env={k:v for k,v in os.environ.items() if not k.startswith(('IGC_','NEO_','UR_','SYCL_','ZE_'))};env.update(IGC_ShaderDumpEnable='1',IGC_DumpToCustomDir=str(dump),IGC_ShowFullVectorsInShaderDumps='1')
 with (B/'ocloc.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env)
 rows.append(dict(command=cmd,returncode=r.returncode,spv=str(spv.relative_to(P)),sha256=hashlib.sha256(data).hexdigest(),names=names))
 if r.returncode:raise RuntimeError('ocloc failed')
(P/'expert-offline.json').write_text(json.dumps(dict(device_executed=False,rows=rows),indent=2)+'\n')
print('compiled offline',len(rows))
