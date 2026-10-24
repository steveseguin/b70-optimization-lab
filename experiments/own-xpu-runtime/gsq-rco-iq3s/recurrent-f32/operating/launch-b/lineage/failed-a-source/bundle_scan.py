"""Pinned independent bundle parser, with streamed F32 low-bit telemetry."""
from pathlib import Path
import hashlib,importlib.util,os,json,stat,re,struct
PARENT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/evidence/device-a/audit.py')
PARENT_SHA='4013acb3216fe908edda3761089a11377e9513f025c99d0442d9792386b5c594'
assert hashlib.sha256(PARENT.read_bytes()).hexdigest()==PARENT_SHA
s=importlib.util.spec_from_file_location('f32_parent_bundle_auditor',PARENT);OLD=importlib.util.module_from_spec(s);s.loader.exec_module(OLD)
require,stamp,snapshot,number,unique,digest=(getattr(OLD,n) for n in ('require','stamp','snapshot','number','unique','digest'))
CAP,META,FILES=OLD.CAP,OLD.META,OLD.FILES
def stream_bundle(path,expected,semantic_oracle=True):
 """Independent range parser with authoritative original per-name byte lengths."""
 require(set(expected) and 'state.json' in expected,'original inventory')
 fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);opened={};stamps={};physical={}
 try:
  ds=os.fstat(fd);require(set(os.listdir(fd))==FILES,'sealed four-file inventory')
  for name in sorted(FILES):
   f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd);opened[name]=f;st=os.fstat(f)
   require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and 0<=st.st_size<=(CAP if name=='state.bundle' else META),'bounded regular file');stamps[name]=st
  def small(name):
   chunks=[];left=stamps[name].st_size
   while left:
    b=os.read(opened[name],min(65536,left));require(b,'metadata truncation');chunks.append(b);left-=len(b)
   value=b''.join(chunks);physical[name]=digest(value);return value
  seal=small('state-seal.txt');require(seal.endswith(b'\n'),'seal newline');fields=seal.decode('ascii')[:-1].split('\n')
  require(len(fields)==5 and fields[0]=='GSQ_STATE_SEAL_V1','seal fields');length=number(fields[1])
  require(all(re.fullmatch('[0-9a-f]{64}',h) for h in fields[2:]),'seal digests')
  index=small('state-index.tsv');state=small('state.json')
  require(digest(index)==fields[3] and digest(state)==fields[4],'metadata seal')
  if semantic_oracle:require(len(state)==expected['state.json']['bytes'] and digest(state)==expected['state.json']['sha256'],'byte-exact baseline state.json')
  obj=json.loads(state,object_pairs_hook=unique);require(type(obj.get('buffers')) is dict,'state inventory')
  state_names={}
  for key,h in obj['buffers'].items():
   name=('alternate-'+key.split(':',1)[1] if key.startswith('alternate:') else key)+'.bin'
   require(name not in state_names,'aliased state names');state_names[name]=h
  require(set(state_names)==set(expected)-{'state.json'},'all original buffer names')
  require(index.endswith(b'\n'),'index newline');lines=index.decode('ascii')[:-1].split('\n')
  require(lines[0]=='GSQ_STATE_BUNDLE_V1' and len(lines)==len(expected) and 0<len(state_names)<=4096,'bounded complete index')
  require(length==stamps['state.bundle'].st_size==sum(x['bytes'] for k,x in expected.items() if k!='state.json'),'original total payload extent')
  seen={};offset=0;whole=hashlib.sha256();precision={}
  for line in lines[1:]:
   parts=line.split('\t');require(len(parts)==4,'index row fields');name,start,size,h=parts
   require(name in state_names and name not in seen and h==state_names[name],'exact indexed range name/hash')
   if semantic_oracle:require(h==expected[name]['sha256'],'original baseline range hash')
   start=number(start);size=number(size);require(start==offset and size==expected[name]['bytes'] and size<=length-offset,'exact original length/contiguous range')
   part=hashlib.sha256();left=size;tail=b"";non_bf16=0;words=0
   recurrent=name.endswith((".gdn.state.bin",".gdn.history.bin","ple.history.bin"))
   while left:
    data=os.read(opened['state.bundle'],min(left,256*1024));require(data,'payload truncated');whole.update(data);part.update(data);left-=len(data)
    if recurrent:
     joined=tail+data;end=len(joined)//4*4;non_bf16+=sum((v&65535)!=0 for (v,) in struct.iter_unpack('<I',joined[:end]));words+=end//4;tail=joined[end:]
   require(part.hexdigest()==h,'actual range bytes differ');seen[name]=h;offset+=size
   if recurrent:require(not tail and words*4==size,'F32 range words');precision[name]={'words':words,'non_bf16_words':non_bf16}
  require(offset==length and not os.read(opened['state.bundle'],1) and whole.hexdigest()==fields[2],'complete physical payload')
  physical['state.bundle']=whole.hexdigest();seen['state.json']=digest(state)
  for name,f in opened.items():require(stamp(os.fstat(f))==stamp(stamps[name])==stamp(os.stat(name,dir_fd=fd,follow_symlinks=False)),'file changed during streaming')
  now=os.stat(path,follow_symlinks=False);require(stat.S_ISDIR(now.st_mode) and (now.st_dev,now.st_ino)==(ds.st_dev,ds.st_ino) and set(os.listdir(fd))==FILES,'directory changed')
  differences=[n for n,h in seen.items() if h!=expected[n]['sha256']]
  return dict(recurrent_precision=precision,logical_map=seen,physical_sha256=physical,snapshots={n:snapshot(st) for n,st in stamps.items()},payload_bytes=length,ranges=len(state_names),semantic_baseline_required=semantic_oracle,baseline_hash_differences=differences,state_json_original_length_equal=len(state)==expected['state.json']['bytes'])
 finally:
  for f in opened.values():os.close(f)
  os.close(fd)
