"""Offline IGC evidence, preserving only gzip assembly/metadata and hashes."""
import argparse,gzip,hashlib,json,os,re,resource,shutil,subprocess,time,struct
from pathlib import Path
P=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--family',choices=['launch','tiny'],required=True);a=ap.parse_args();B=P/'build'/a.family
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
if shutil.disk_usage('/').free<8*1024**3:raise SystemExit('STOP: filesystem below8GiB')
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
def sha(data):return hashlib.sha256(data).hexdigest()
rows=[];artifacts=[];seen=set()
binary=(B/('p42-tiny' if a.family=='tiny' else 'p42-launch-floor')).read_bytes()
for spv in sorted((B/'spv').glob('*.spv')):
 if shutil.disk_usage('/').free<8*1024**3:raise SystemExit('STOP: filesystem below8GiB before offline module')
 data=spv.read_bytes();digest=sha(data)
 if digest in seen or binary.find(data)<0:continue
 words=struct.unpack('<'+'I'*(len(data)//4),data);i=5;names=[]
 while i<len(words):
  count=words[i]>>16;op=words[i]&65535
  if not count:raise ValueError('bad SPIRV instruction')
  if op==15:names.append(struct.pack('<'+'I'*(count-3),*words[i+3:i+count]).split(b'\0')[0].decode())
  i+=count
 if not names:continue
 seen.add(digest);tag=digest[:12];dump=B/('igc-'+tag);output=B/('ocloc-'+tag)
 env={k:v for k,v in os.environ.items() if not k.startswith(('IGC_','NEO_','SYCL_','UR_','ZE_'))};env.update(IGC_ShaderDumpEnable='1',IGC_DumpToCustomDir=str(dump),IGC_ShowFullVectorsInShaderDumps='1')
 cmd=['/usr/bin/ocloc','compile','-spirv_input','-file',str(spv),'-device','0xe223','-revision_id','0','-options','-ze-opt-level=O2 -cl-fp32-correctly-rounded-divide-sqrt','-out_dir',str(output)]
 with (B/('offline-'+tag+'.log')).open('w') as log:r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise SystemExit('offline compiler failed: '+tag)
 dest=P/(a.family+'-assembly');dest.mkdir(exist_ok=True)
 for f in sorted(dump.glob('*.asm')):
  text=f.read_text();name=text.splitlines()[0].removeprefix('//.kernel ');instructions=[]
  for line in text.splitlines():
   s=re.sub(r'^\([^)]*\)\s*','',line.strip());m=re.match(r'([a-z][^\s]*)\s+(?:\((\d+)\|M(\d+)\))?',s)
   if m:instructions.append((m[1],line))
  ze=next(dump.glob('*.zeinfo'),None);metadata=''
  if ze:
   txt=ze.read_text();start=txt.find('  - name:            '+name+'\n');end=txt.find('  - name:',start+10);metadata=txt[start:end if end!=-1 else None] if start>=0 else ''
  payload=metadata.split('payload_arguments:',1)[-1].split('per_thread_payload_arguments:',1)[0];pairs=re.findall(r'offset:\s+(\d+)\s+size:\s+(\d+)',payload)
  extent=max([int(off)+int(size) for off,size in pairs]or[0]);target=dest/f.name;target=target.with_suffix('.asm.gz');target.write_bytes(gzip.compress(f.read_bytes(),mtime=0))
  rows.append(dict(kernel=name,assembly=str(target.relative_to(P)),sha256=sha(f.read_bytes()),instructions=len(instructions),memory_messages=sum(op.startswith(('load.','store.','send','atomic.')) for op,_ in instructions),slm_messages=sum('.slm.' in op for op,_ in instructions),barriers=sum('barrier' in line.lower() for _,line in instructions),cross_thread_extent_bytes=extent,slm_pointer_arguments=len(re.findall(r'addrmode:\s+slm',metadata)),execution_env=dict(re.findall(r'^      (\w+):\s+([^\n]+)',metadata.split('payload_arguments:')[0],re.M))))
 for f in sorted(dump.glob('*.zeinfo')):
  target=dest/(f.name+'.gz');target.write_bytes(gzip.compress(f.read_bytes(),mtime=0));artifacts.append(dict(path=str(target.relative_to(P)),sha256=sha(f.read_bytes())))
 artifacts.append(dict(spv=str(spv.relative_to(P)),sha256=sha(spv.read_bytes()),command=cmd,device_executed=False))
 # All generated binary/raw IR dumps are scratch. Hash then discard.
 for folder in (dump,output):
  for f in folder.rglob('*'):
   if f.is_file() and (f.name=='output.bin' or f.suffix in ('.bin','.progbin')):artifacts.append(dict(discarded=str(f.relative_to(P)),bytes=f.stat().st_size,sha256=sha(f.read_bytes())))
  shutil.rmtree(folder)
(P/(a.family+'-assembly.json')).write_text(json.dumps(dict(device_executed=False,binary_sha256=sha(binary),compiler='ocloc Xe2 0xe223 rev0',rows=rows,artifacts=artifacts,static_counts_not_dynamic_cost=True),indent=2)+'\n')
if not rows:raise SystemExit('no compiled assembly; missing SPIR-V link dump')
print(a.family,len(rows),'assembly rows')
