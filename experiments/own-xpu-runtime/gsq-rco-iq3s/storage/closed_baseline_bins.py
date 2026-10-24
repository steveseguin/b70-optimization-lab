#!/usr/bin/env python3
"""Explicit fixed closed-baseline archive, verified prune, and offload phases.
No model/device/service operations. No automatic phase continuation or retries.
"""
import argparse,gzip,hashlib,io,json,os,resource,shutil,stat,tarfile
from pathlib import Path,PurePosixPath
P=Path(__file__).resolve().parent;L=P.parent
SOURCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a')
DEST=Path('/home/steve/own-xpu-runtime-results/gsq-baseline-bin-archive-a')
USB=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a-state-bins.tar.gz')
INDEX=L/'baseline/evidence/independent-a/artifact-index.jsonl.gz';INDEX_SHA='e8137dddb0929d5476d27a8a774539a77d595aeb296e9d0ec778ceec066a6982'
REVIEW=L/'baseline/evidence/independent-a/review.json';REVIEW_SHA='f662fcecf93c92f90006c09c05d4a4c02e71e84ae9d8c82dbff3fdfc39ebb5bb'
PRESERVE={f'prompt-00-none/rank{rank}/state-2147483647/{name}.bin' for rank,names in [(0,['blk.0.gdn.gated','blk.0.attention','blk.23.qsa.y','blk.23.attention']),(1,['blk.47.qsa.y','blk.47.attention'])] for name in names}
CAP=384*1024**2;FLOOR=27000000000+64*1024**2

def require(v,msg):
 if not v:raise ValueError(msg)
def identity(st):return [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,st.st_uid,st.st_gid,st.st_nlink]
def sha_stream(f):
 h=hashlib.sha256()
 while b:=f.read(256*1024):h.update(b)
 return h.hexdigest()
def sha(path):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb') as f:
  a=identity(os.fstat(f.fileno()));require(stat.S_ISREG(a[5]),'regular file');h=sha_stream(f);require(a==identity(os.fstat(f.fileno())),'changed during hash');return h
def syncdir(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
def record(p,j):
 data=(json.dumps(j,indent=2)+'\n').encode();require(len(data)<=1024**2,'bounded receipt')
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 syncdir(Path(p).parent)
def relative(name):
 p=PurePosixPath(name);require(not p.is_absolute() and p.parts and all(s not in ('','..','.') for s in p.parts) and str(p)==name and name.endswith('.bin'),'relative bin path');return p.parts
class Budget:
 def __init__(self,root,cap,floor):self.root=root;self.cap=cap;self.floor=floor;self.written=0
 def before(self,n):
  require(self.written+n<=self.cap,'archive quota exceeded');require(shutil.disk_usage(self.root).free>=self.floor+n,'archive filesystem reserve');self.written+=n
class Limited:
 def __init__(self,f,b):self.f=f;self.b=b
 def write(self,data):self.b.before(len(data));return self.f.write(data)
 def flush(self):return self.f.flush()
 def tell(self):return self.f.tell()
class HashReader:
 def __init__(self,f):self.f=f;self.h=hashlib.sha256();self.n=0
 def read(self,n=-1):
  require(0<=n<=1024**2,'bounded tar read');b=self.f.read(n);self.h.update(b);self.n+=len(b);return b
class Job:
 """Paths/rows injected only by tiny tests; CLI has no caller path arguments."""
 def __init__(self,source,dest,rows,preserve,cap=CAP,floor=FLOOR,authority=None):
  self.source=Path(source);self.dest=Path(dest);self.rows=rows;self.preserve=set(preserve);self.cap=cap;self.floor=floor;self.authority=authority or {};self.root_fd=None
  require(set(self.preserve)<=set(rows),'preservation subset')
  for n,r in rows.items():relative(n);require(type(r['bytes'])is int and r['bytes']>=0 and len(r['sha256'])==64,'index entry')
 def open_root(self):
  require(self.source.resolve()==self.source and self.source.is_dir(),'canonical source root');self.root_fd=os.open(self.source,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);self.root_id=identity(os.fstat(self.root_fd))[:2]
 def close_root(self):
  if self.root_fd is not None:os.close(self.root_fd);self.root_fd=None
 def check_root(self):require(identity(os.stat(self.source,follow_symlinks=False))[:2]==self.root_id,'source root changed')
 def parent(self,name):
  self.check_root();parts=relative(name);fd=os.dup(self.root_fd)
  try:
   for part in parts[:-1]:
    new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=new
   return fd,parts[-1]
  except BaseException:os.close(fd);raise
 def source_file(self,name):
  parent,leaf=self.parent(name)
  try:
   fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent);st=os.fstat(fd)
   require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==self.rows[name]['bytes'],'source type/alias/extent')
   return os.fdopen(fd,'rb'),identity(st)
  except BaseException:
   if 'fd' in locals():os.close(fd)
   raise
  finally:os.close(parent)
 def verify_archive(self,f):
  start=identity(os.fstat(f.fileno()));f.seek(0);seen=set()
  with tarfile.open(fileobj=f,mode='r|gz') as tar:
   for member in tar:
    require(member.isfile() and not member.issym() and not member.islnk(),'regular tar entries only');relative(member.name)
    require(member.name in self.rows and member.name not in seen,'unexpected/duplicate tar member');seen.add(member.name)
    row=self.rows[member.name];require(member.size==row['bytes'],'tar size');stream=tar.extractfile(member);require(stream is not None,'tar payload');h=sha_stream(stream);require(h==row['sha256'],'tar payload digest')
  require(seen==set(self.rows),'complete tar inventory');require(identity(os.fstat(f.fileno()))==start,'archive modified');f.seek(0);digest=sha_stream(f);require(identity(os.fstat(f.fileno()))==start,'archive modified while hashing');return digest,start
 def archive(self):
  require(not os.path.lexists(self.dest),'exclusive archive destination');require(self.dest.parent.resolve()==self.dest.parent,'canonical archive parent')
  require(shutil.disk_usage(self.dest.parent).free>=self.floor+self.cap,'archive full quota and reserve')
  self.dest.mkdir(mode=0o700);syncdir(self.dest.parent);self.open_root();budget=Budget(self.dest,self.cap,self.floor)
  try:
   record(self.dest/'archive-start.json',{'phase':'copy-only','authority':self.authority,'source':str(self.source),'entries':len(self.rows),'preserve':sorted(self.preserve),'quota':self.cap,'floor':self.floor,'source_root_identity':self.root_id})
   seen=set()
   with (self.dest/'state-bins.tar.gz').open('xb') as raw,(self.dest/'source-stat.jsonl.gz').open('xb') as statraw:
    with gzip.GzipFile(fileobj=Limited(raw,budget),mode='wb',filename='',mtime=0,compresslevel=3) as gz,gzip.GzipFile(fileobj=Limited(statraw,budget),mode='wb',filename='',mtime=0,compresslevel=3) as sz:
     with tarfile.open(fileobj=gz,mode='w|',format=tarfile.PAX_FORMAT) as tar:
      for name,row in sorted(self.rows.items()):
       f,before=self.source_file(name)
       with f:
        require(tuple(before[:2]) not in seen,'source alias');seen.add(tuple(before[:2]));reader=HashReader(f)
        info=tarfile.TarInfo(name);info.size=row['bytes'];info.mode=stat.S_IMODE(before[5]);info.uid=before[6];info.gid=before[7];info.mtime=before[3]//10**9
        tar.addfile(info,reader);require(reader.n==row['bytes'] and reader.h.hexdigest()==row['sha256'],'source differs from audited index');require(identity(os.fstat(f.fileno()))==before,'source changed during copy')
        sz.write((json.dumps({'path':name,'stat':before},separators=(',',':'))+'\n').encode())
    for f in (raw,statraw):f.flush();os.fsync(f.fileno())
   syncdir(self.dest)
   with (self.dest/'state-bins.tar.gz').open('rb') as f:digest,archive_id=self.verify_archive(f)
   receipt={'passed':True,'phase':'all-members-readback-verified','archive_sha256':digest,'archive_identity':archive_id,'archive_bytes':archive_id[2],'source_stat_sha256':sha(self.dest/'source-stat.jsonl.gz'),'entries':len(self.rows),'source_bytes':sum(x['bytes'] for x in self.rows.values()),'source_root_identity':self.root_id,'authority':self.authority,'preserve':sorted(self.preserve),'restore':'Verified archive contains only exact original relative .bin names; restore missing files under the fixed baseline root, checking each SHA against the immutable baseline index. Never overwrite existing files without separate review.'}
   record(self.dest/'copy-verified.json',receipt);return receipt
  except BaseException as e:
   try:record(self.dest/'archive-failure.json',{'passed':False,'error':repr(e),'prune_allowed':False})
   except BaseException:pass
   raise
  finally:self.close_root()
 def snapshots(self):
  result={}
  with gzip.open(self.dest/'source-stat.jsonl.gz','rt') as f:
   for line in f:
    require(len(line)<=4096,'bounded stat row');x=json.loads(line);require(x['path'] in self.rows and x['path'] not in result,'stat inventory');result[x['path']]=x['stat']
  require(set(result)==set(self.rows),'complete source stats');return result
 def prune(self):
  require(self.dest.resolve()==self.dest,'canonical archive destination');require(not os.path.lexists(self.dest/'prune-start.json') and not os.path.lexists(self.dest/'prune-failure.json'),'no prune retry')
  copy=json.loads((self.dest/'copy-verified.json').read_text());require(copy['passed'] and copy['authority']==self.authority and copy['preserve']==sorted(self.preserve),'copy authority');require(sha(self.dest/'source-stat.jsonl.gz')==copy['source_stat_sha256'],'source stat binding');snaps=self.snapshots();self.open_root();removed=0;removed_bytes=0
  fd=os.open(self.dest/'state-bins.tar.gz',os.O_RDONLY|os.O_NOFOLLOW)
  try:
   with os.fdopen(fd,'rb') as arc:
    digest,aid=self.verify_archive(arc);require(digest==copy['archive_sha256'] and aid==copy['archive_identity'],'archive replacement/change');require(self.root_id==copy['source_root_identity'],'source root replacement')
    # All metadata/parent permissions before first unlink; per-file hash immediately
    # before its unlink. A late change yields retained partial-prune evidence.
    for name in self.rows:
     parent,leaf=self.parent(name)
     try:
      require(identity(os.stat(leaf,dir_fd=parent,follow_symlinks=False))==snaps[name],'source metadata changed')
      if name not in self.preserve:require(os.access('.',os.W_OK|os.X_OK,dir_fd=parent),'source parent not writable')
     finally:os.close(parent)
    record(self.dest/'prune-start.json',{'phase':'incomplete-until-prune-verified','authority':self.authority,'archive_sha256':digest,'source_stat_sha256':copy['source_stat_sha256'],'original_root':str(self.source),'expected_removed':len(self.rows)-len(self.preserve),'preserved':sorted(self.preserve),'restore_map':'Tar member names are exact original relative .bin paths. All JSON files and directories are retained.'})
    for name,row in sorted(self.rows.items()):
     if name in self.preserve:continue
     f,before=self.source_file(name)
     with f:
      require(before==snaps[name] and sha_stream(f)==row['sha256'] and identity(os.fstat(f.fileno()))==before,'changed source before unlink')
      require(identity(os.fstat(arc.fileno()))==aid and identity(os.stat(self.dest/'state-bins.tar.gz',follow_symlinks=False))==aid,'archive no longer held original')
      parent,leaf=self.parent(name)
      try:
       require(identity(os.stat(leaf,dir_fd=parent,follow_symlinks=False))==before,'source replaced before unlink');os.unlink(leaf,dir_fd=parent);os.fsync(parent)
      finally:os.close(parent)
     removed+=1;removed_bytes+=row['bytes']
    for name in self.preserve:
     f,before=self.source_file(name)
     with f:require(before==snaps[name] and sha_stream(f)==self.rows[name]['sha256'],'preserved micro changed')
    result={'passed':True,'phase':'audited-bin-files-pruned','removed':removed,'removed_bytes':removed_bytes,'preserved':sorted(self.preserve),'archive_sha256':digest,'source_json_and_directories_untouched':True,'authority':self.authority}
    record(self.dest/'prune-verified.json',result);return result
  except BaseException as e:
   try:record(self.dest/'prune-failure.json',{'passed':False,'error':repr(e),'removed':removed,'removed_bytes':removed_bytes,'archive_retained':True,'retry_allowed':False})
   except BaseException:pass
   raise
  finally:self.close_root()

 def offload(self,usb,reserve=2*1024**3):
  usb=Path(usb);require(usb.parent.resolve()==usb.parent and not os.path.lexists(usb),'fresh canonical USB archive')
  require(not os.path.lexists(self.dest/'offload-start.json'),'no offload retry')
  prune=json.loads((self.dest/'prune-verified.json').read_text());copy=json.loads((self.dest/'copy-verified.json').read_text())
  require(prune['passed'] and prune['authority']==copy['authority']==self.authority,'verified prune before USB offload')
  fd=os.open(self.dest/'state-bins.tar.gz',os.O_RDONLY|os.O_NOFOLLOW)
  try:
   with os.fdopen(fd,'rb') as src:
    digest,aid=self.verify_archive(src);require(digest==copy['archive_sha256'] and aid==copy['archive_identity'],'verified local archive')
    require(usb.parent.stat().st_dev==copy['source_root_identity'][0] and usb.parent.stat().st_dev!=os.fstat(src.fileno()).st_dev,'USB expected source filesystem distinct from local archive')
    require(shutil.disk_usage(usb.parent).free>=reserve+aid[2],'USB copy reserve')
    record(self.dest/'offload-start.json',{'archive_sha256':digest,'usb':str(usb),'authority':self.authority})
    fdout=os.open(usb,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fdout,'wb') as dst:
     src.seek(0)
     while b:=src.read(256*1024):
      require(shutil.disk_usage(usb.parent).free>=reserve+len(b),'USB reserve during copy');dst.write(b)
     dst.flush();os.fsync(dst.fileno())
    syncdir(usb.parent);require(identity(os.fstat(src.fileno()))==aid,'local archive changed during offload')
    require(sha(usb)==digest,'USB complete readback hash');result={'passed':True,'phase':'USB-archive-readback-verified','archive_sha256':digest,'archive_bytes':aid[2],'usb':str(usb),'usb_identity':identity(os.stat(usb,follow_symlinks=False)),'authority':self.authority}
    record(self.dest/'offload-verified.json',result);return result
  except BaseException as e:
   try:record(self.dest/'offload-failure.json',{'passed':False,'error':repr(e),'local_archive_retained':True,'retry_allowed':False})
   except BaseException:pass
   raise
 def release_local(self,usb):
  receipt=json.loads((self.dest/'offload-verified.json').read_text());copy=json.loads((self.dest/'copy-verified.json').read_text())
  require(receipt['passed'] and receipt['authority']==self.authority and receipt['usb']==str(usb),'offload authority')
  fd=os.open(usb,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb') as remote:
   h,ident=self.verify_archive(remote);require(h==receipt['archive_sha256']==copy['archive_sha256'] and ident==receipt['usb_identity'],'USB archive reverified before local release')
   local=self.dest/'state-bins.tar.gz'
   require(os.fstat(remote.fileno()).st_dev==copy['source_root_identity'][0] and os.fstat(remote.fileno()).st_dev!=os.stat(local,follow_symlinks=False).st_dev,'USB expected source filesystem distinct from local archive before release')
   require(identity(os.stat(local,follow_symlinks=False))==copy['archive_identity'] and sha(local)==h,'local archive identity')
   record(self.dest/'local-release-start.json',{'archive_sha256':h,'usb':str(usb),'authority':self.authority})
   require(identity(os.fstat(remote.fileno()))==ident and identity(os.stat(usb,follow_symlinks=False))==ident,'USB archive changed')
   require(identity(os.stat(local,follow_symlinks=False))==copy['archive_identity'],'local archive replaced');local.unlink();syncdir(self.dest)
  result={'passed':True,'phase':'local-archive-released-after-verified-USB-copy','usb':str(usb),'archive_sha256':h,'metadata_and_restore_map_retained':True,'authority':self.authority}
  record(self.dest/'local-release-verified.json',result);return result

def all_rows():
 require(sha(INDEX)==INDEX_SHA and sha(REVIEW)==REVIEW_SHA,'immutable audited authority')
 review=json.loads(REVIEW.read_text());require(review['passed'] and review['all12_exact'] and review['index_sha256']==INDEX_SHA,'closed baseline proof')
 rows={}
 with gzip.open(INDEX,'rt') as f:
  for line in f:
   require(len(line)<=4096,'bounded index row');x=json.loads(line)
   if x['root']=='evidence' and x['path'].endswith('.bin'):
    require(x['path'] not in rows,'duplicate index');rows[x['path']]={'bytes':x['bytes'],'sha256':x['sha256']}
 require(len(rows)==57051 and sum(x['bytes'] for x in rows.values())==6248947500,'fixed bin census');return rows
def batch_names():return ['initial','warmup-none','warmup-mtp']+[f'prompt-{i:02d}-{mode}' for i in range(12) for mode in (['none','mtp'] if i%2==0 else ['mtp','none'])]
def select_batch(rows,batch):
 require(type(batch)is int and 0<=batch<27,'fixed batch0..26');name=batch_names()[batch]
 chosen={n:r for n,r in rows.items() if (n.split('/')[0] in ('rank0','rank1') if name=='initial' else n.split('/')[0]==name)}
 require(len(chosen)==2113 and sum(r['bytes'] for r in chosen.values())==231442500,'exact per-request bin census');return name,chosen
def authority(batch):
 name,rows=select_batch(all_rows(),batch)
 return Job(SOURCE,DEST/f'chunk-{batch:02d}',rows,PRESERVE&set(rows),authority={'index_sha256':INDEX_SHA,'review_sha256':REVIEW_SHA,'helper_sha256':sha(__file__),'batch':batch,'name':name})
def prepare_destination(batch):
 require(DEST.parent.resolve()==DEST.parent,'canonical NVMe anchor parent')
 if not os.path.lexists(DEST):DEST.mkdir(mode=0o700);syncdir(DEST.parent)
 st=DEST.stat();require(not DEST.is_symlink() and DEST.resolve()==DEST and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'private NVMe anchor')
 if batch:
  prior=DEST/f'chunk-{batch-1:02d}/local-release-verified.json';j=json.loads(prior.read_text());require(j['passed'] and j['authority']['batch']==batch-1 and j['authority']['helper_sha256']==sha(__file__),'previous batch fully offloaded/released')
def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--archive',action='store_true');g.add_argument('--prune-verified',action='store_true');g.add_argument('--offload-verified',action='store_true');g.add_argument('--release-local-verified',action='store_true');ap.add_argument('--batch',type=int);a=ap.parse_args()
 if a.plan:
  rows=all_rows();summary=[dict(batch=i,name=select_batch(rows,i)[0],files=2113,bytes=231442500) for i in range(27)];print(json.dumps({'source':str(SOURCE),'destination':str(DEST),'batches':summary,'preserved':sorted(PRESERVE),'archive_quota_per_batch':CAP,'reserve_floor':FLOOR,'operations_performed':False},indent=2));return
 require(a.batch is not None,'explicit batch required');require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19');require(os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper CPU affinity');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));job=authority(a.batch)
 usb=USB.with_name(f'gsq-baseline-a-state-bins-{a.batch:02d}.tar.gz')
 if a.archive:prepare_destination(a.batch);result=job.archive();phase='archive'
 elif a.prune_verified:result=job.prune();phase='prune'
 elif a.offload_verified:result=job.offload(usb);phase='offload'
 else:result=job.release_local(usb);phase='release'
 P.joinpath('evidence').mkdir(exist_ok=True);record(P/'evidence'/f'chunk-{a.batch:02d}-{phase}.json',result);print(json.dumps(result))
if __name__=='__main__':main()
