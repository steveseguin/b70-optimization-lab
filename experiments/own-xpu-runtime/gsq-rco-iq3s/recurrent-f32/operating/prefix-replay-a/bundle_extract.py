"""Independently verify sealed raw state bytes and return the legacy logical map."""
import hashlib,json,os,re,stat
from pathlib import Path
CAP=256*1024**2;META=1024**2;ROWS=4096
FILES={'state.bundle','state-index.tsv','state.json','state-seal.txt'}
def require(v,msg):
 if not v:raise ValueError('state bundle: '+msg)
def identity(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mode,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)
def pairs(values):
 out={}
 for k,v in values:require(k not in out,'duplicate JSON key');out[k]=v
 return out
def number(s):
 require(re.fullmatch(r'0|[1-9][0-9]{0,19}',s) is not None,'canonical bounded integer');v=int(s);require(v<=CAP,'extent exceeds cap');return v
def digest(s):return hashlib.sha256(s).hexdigest()
def hexhash(s):return type(s)is str and re.fullmatch('[0-9a-f]{64}',s) is not None
def logical_name(s):
 require(type(s)is str,'buffer key');name=('alternate-'+s[len('alternate:'):] if s.startswith('alternate:') else s)+'.bin'
 require(len(name)<=240 and re.fullmatch('[A-Za-z0-9_.:-]+',name) is not None,'buffer filename');return name
def read_selected(directory,wanted):
 """Caller must first have a successful DUMP reply; closure remains RESET/FINISH."""
 path=Path(directory);require(path.resolve()==path,"canonical capture path");d=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);fds={};stamps={}
 try:
  ds=os.fstat(d);require(stat.S_ISDIR(ds.st_mode),'directory');require(set(os.listdir(d))==FILES,'incomplete/unexpected files')
  for name in sorted(FILES):
   fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=d);fds[name]=fd;s=os.fstat(fd)
   require(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'regular single-link file');require(0<=s.st_size<=(CAP if name=='state.bundle' else META),'file bound');stamps[name]=identity(s)
  def small(name):
   fd=fds[name];n=stamps[name][2];data=bytearray()
   while len(data)<n:
    b=os.read(fd,min(65536,n-len(data)));require(b,'metadata truncated');data.extend(b)
   return bytes(data)
  seal=small('state-seal.txt').decode('ascii');require(seal.endswith('\n'),'seal newline');fields=seal[:-1].split('\n')
  require(len(fields)==5 and fields[0]=='GSQ_STATE_SEAL_V1','seal schema');size=number(fields[1]);payload_sha,index_sha,state_sha=fields[2:];require(all(map(hexhash,(payload_sha,index_sha,state_sha))),'seal hashes')
  require(size==stamps['state.bundle'][2],'bundle size')
  index=small('state-index.tsv');state=small('state.json');require(digest(index)==index_sha and digest(state)==state_sha,'metadata digest')
  obj=json.loads(state,object_pairs_hook=pairs);require(type(obj)is dict and type(obj.get('buffers'))is dict,'state buffer inventory')
  expected={}
  for key,h in obj['buffers'].items():
   name=logical_name(key);require(name not in expected and hexhash(h),'state names/hash');expected[name]=h
  require(0<len(expected)<=ROWS,'state inventory bound')
  text=index.decode('ascii');require(text.endswith('\n'),'index newline');lines=text[:-1].split('\n');require(lines[0]=='GSQ_STATE_BUNDLE_V1' and len(lines)==len(expected)+1,'index inventory count')
  offset=0;result={};whole=hashlib.sha256();captured={};fd=fds['state.bundle']
  for line in lines[1:]:
   fields=line.split('\t');require(len(fields)==4,'index row fields');name,a,b,h=fields
   require(name in expected and name not in result and hexhash(h) and expected[name]==h,'missing/duplicate/unknown buffer or hash');start=number(a);length=number(b)
   require(start==offset and length<=size-offset,'gap/overlap/out-of-range');part=hashlib.sha256();left=length;selected=bytearray() if name in wanted else None
   if selected is not None:require(length==wanted[name],'selected range extent')
   while left:
    data=os.read(fd,min(65536,left));require(data,'truncated payload');part.update(data);whole.update(data);left-=len(data)
    if selected is not None:selected.extend(data)
   require(part.hexdigest()==h,'buffer bytes differ');result[name]=h;offset+=length
   if selected is not None:captured[name]=bytes(selected)
  require(offset==size and not os.read(fd,1) and whole.hexdigest()==payload_sha,'trailing/full payload hash');require(set(result)==set(expected),'complete original inventory');result['state.json']=state_sha
  for name,fd in fds.items():require(identity(os.fstat(fd))==stamps[name]==identity(os.stat(name,dir_fd=d,follow_symlinks=False)),'file changed/replaced')
  now=os.stat(path,follow_symlinks=False);require(stat.S_ISDIR(now.st_mode) and (now.st_dev,now.st_ino)==(ds.st_dev,ds.st_ino) and set(os.listdir(d))==FILES,'directory changed')
  require(set(captured)==set(wanted),'all selected ranges present')
  return dict(logical_map=result,captured=captured,whole_sha256=whole.hexdigest(),payload_bytes=size,range_count=len(expected),snapshots={n:[v[0],v[1],v[2],v[5],v[6]] for n,v in stamps.items()})
 finally:
  for fd in fds.values():os.close(fd)
  os.close(d)
