#!/usr/bin/env python3
"""Fixed41 archived-container aliases. Explicit verify, then separate release."""
from pathlib import Path,PurePosixPath
import argparse,gzip,hashlib,json,os,resource,shutil,stat,tarfile
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2]
APPRAISAL=P.parent/'capacity-appraisal.json'
APPRAISAL_SHA='1ce3320377fb1d9138a9c81596da5c591fe5431f049e728251b6d005820af03a'
USB=Path('/mnt/usb-models/own-xpu-runtime-results');USB_DEVICE=2050
DEST=Path('/home/steve/own-xpu-runtime-results/gsq-canonical-archives-a')
FLOOR=27000000000+64*1024**2
def need(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def syncdir(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
def durable(p,b):
 need(len(b)<=2*1024**2,'bounded metadata')
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 syncdir(p.parent)
def save(p,obj):durable(p,canonical(obj)+b'\n')
def name_ok(n):
 q=PurePosixPath(n);need(not q.is_absolute() and q.parts and str(q)==n and all(x not in ('','..','.') for x in q.parts),'canonical member name');return n
def grouped(path,absolute=None):
 out={}
 with gzip.open(path,'rt') as z:
  for line in z:
   need(len(line)<=16384,'bounded index row');x=json.loads(line)
   if absolute is None:
    if x['root']!='evidence':continue
    n=x['path']
   else:n=str(Path(x['path']).relative_to(absolute))
   if not n.endswith('.bin'):continue
   name_ok(n);parts=PurePosixPath(n).parts;group='initial' if parts[0].startswith('rank') else parts[0]
   rows=out.setdefault(group,{});need(n not in rows,'duplicate index member');rows[n]={k:x[k] for k in ('bytes','sha256')}
 return out
def authority(batch):
 need(type(batch)is int and 0<=batch<41,'fixed batch0..40')
 need(sha(APPRAISAL)==APPRAISAL_SHA,'immutable mapping')
 a=json.loads(APPRAISAL.read_text());need(len(a['mapping'])==41 and a['total_candidate_recovery_bytes']==3586696105,'fixed mapping extent')
 for f,h in a['authority_sha256'].items():need(sha(R/f)==h,'immutable prior inventory/closure')
 row=a['mapping'][batch];original=Path(row['original_archive']);target=Path(row['canonical_archive'])
 need(original.parent==target.parent==USB and original!=target and target.name.startswith('gsq-baseline-a-state-bins-'),'fixed archive paths')
 baseline=grouped(L/'baseline/evidence/independent-a/artifact-index.jsonl.gz')
 if row['scope']=='combined':prior=grouped(L/'qkv-q6-p33/engine/operating/evidence/device-a/artifact-index.jsonl.gz')
 elif row['scope']=='attention-prefix':prior=grouped(L/'attention-q8-p33/operating/evidence/partial-independent-a/artifact-index.jsonl.gz',USB/'gsq-attention-p33-a')
 else:raise ValueError('fixed profile')
 expected=prior[row['group']];base=baseline[row['group']]
 need(len(expected)==row['matched_members'] and sum(x['bytes'] for x in expected.values())==row['matched_raw_bytes'],'original member extent')
 need(hashlib.sha256(canonical(expected)).hexdigest()==row['member_manifest_sha256'],'original manifest hash')
 need(all(base.get(n)==v for n,v in expected.items()) and len(base)==2113,'exact canonical subset')
 need((expected==base)==row['whole_member_inventory_equal'] and len(base)-len(expected)==row['canonical_extra_members'],'exact subset/equality scope')
 return row,expected,base
def review():
 p=P/'evidence/independent-review.json';j=json.loads(p.read_text());need(j['passed'] and j['source_sha256'],'independent source review')
 for f,h in j['source_sha256'].items():need(sha(R/f)==h,'reviewed source changed')
 return sha(p)
def held(path,size):
 need(USB.resolve()==USB and USB.stat().st_dev==USB_DEVICE,'expected mounted USB')
 need(path.parent==USB and path.resolve()==path,'canonical fixed archive')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_dev==USB_DEVICE and s.st_size==size,'expected archive inode/device/extent');return fd,identity(s)
 except BaseException:os.close(fd);raise
def unchanged(fd,path,stamp):need(identity(os.fstat(fd))==stamp==identity(path.stat(follow_symlinks=False)),'held archive changed')
def compressed(fd,path,stamp,want):
 os.lseek(fd,0,os.SEEK_SET);h=hashlib.sha256();count=0
 while b:=os.read(fd,1024**2):h.update(b);count+=len(b);need(count<=stamp[2],'archive read extent')
 need(count==stamp[2] and h.hexdigest()==want,'compressed archive digest');unchanged(fd,path,stamp)
def members(fd,path,stamp,expected):
 os.lseek(fd,0,os.SEEK_SET);seen={};total=0
 with os.fdopen(os.dup(fd),'rb') as f,tarfile.open(fileobj=f,mode='r|gz') as tar:
  for member in tar:
   n=name_ok(member.name);need(member.isfile() and not member.issym() and not member.islnk() and not member.sparse and n in expected and n not in seen,'fixed unique regular member')
   need(member.size==expected[n]['bytes'],'member extent');total+=member.size;need(total<=231442500,'bounded raw stream')
   src=tar.extractfile(member);need(src is not None,'member stream');h=hashlib.sha256();count=0
   while b:=src.read(1024**2):h.update(b);count+=len(b);need(count<=member.size,'member read bound')
   need(count==member.size and h.hexdigest()==expected[n]['sha256'],'exact member bytes')
   info=member.get_info();info['type_hex']=info.pop('type').hex()
   seen[n]=dict(**expected[n],tar_metadata=info,pax_headers=dict(member.pax_headers))
 need(set(seen)==set(expected) and total==sum(x['bytes'] for x in expected.values()),'complete member inventory');unchanged(fd,path,stamp);return seen
def limits():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 need(shutil.disk_usage(DEST.parent).free>=FLOOR,'NVMe floor plus64MiB reserve')
def anchor():
 need(DEST.parent.resolve()==DEST.parent and DEST.parent.stat().st_dev!=USB_DEVICE,'canonical separate NVMe parent')
 if not os.path.lexists(DEST):DEST.mkdir(mode=0o700);syncdir(DEST.parent)
 s=DEST.lstat();need(stat.S_ISDIR(s.st_mode) and not DEST.is_symlink() and s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o700,'private NVMe metadata anchor')
def verify(batch):
 limits();review_sha=review();row,expected,base=authority(batch);anchor();d=DEST/f'batch-{batch:02d}';d.mkdir(mode=0o700);syncdir(DEST)
 result=dict(passed=False,phase='verify',batch=batch,mapping=row,helper_sha256=sha(__file__),appraisal_sha256=APPRAISAL_SHA,source_review_sha256=review_sha)
 descriptors=[]
 try:
  paths=[Path(row['original_archive']),Path(row['canonical_archive'])]
  for role,path in zip(('original','canonical'),paths):
   fd,st=held(path,row[role+'_archive_bytes']);descriptors.append((fd,path,st));compressed(fd,path,st,row[role+'_archive_sha256'])
  need(descriptors[0][2][:2]!=descriptors[1][2][:2],'distinct source/canonical inodes')
  original=members(*descriptors[0],expected);canonical_members=members(*descriptors[1],base)
  need(all(original[n]['bytes']==canonical_members[n]['bytes'] and original[n]['sha256']==canonical_members[n]['sha256'] for n in original),'verified canonical content')
  redirect=dict(schema='gsq.canonical-archive.restore.v1',batch=batch,mapping=row,original_members=original,canonical_inventory_sha256=hashlib.sha256(canonical(base)).hexdigest(),original_identity=descriptors[0][2],canonical_identity=descriptors[1][2],restore='Read and hash-bound verify the canonical archive; extract ONLY original_members. Restore original tar_metadata and pax_headers listed here. This reconstructs member bytes/metadata, not the original gzip/tar container bytes. Old receipts remain unchanged.')
  payload=gzip.compress(canonical(redirect)+b'\n',compresslevel=3,mtime=0);durable(d/'restore.json.gz',payload);need(sha(d/'restore.json.gz')==hashlib.sha256(payload).hexdigest(),'durable redirect readback')
  for fd,path,st in descriptors:unchanged(fd,path,st)
  result.update(passed=True,original_identity=descriptors[0][2],canonical_identity=descriptors[1][2],redirect_sha256=sha(d/'restore.json.gz'),original_member_count=len(original),canonical_member_count=len(base),original_raw_bytes=sum(x['bytes'] for x in expected.values()),released=False)
 except BaseException as e:result['error']=repr(e);raise
 finally:
  for fd,_,_ in descriptors:os.close(fd)
  save(d/'verified.json',result)
 return result
def release(batch):
 limits();review_sha=review();row,expected,base=authority(batch);anchor();d=DEST/f'batch-{batch:02d}'
 need(d.resolve()==d and d.is_dir() and not os.path.lexists(d/'release-start.json') and not os.path.lexists(d/'released.json'),'verified fresh release phase')
 v=json.loads((d/'verified.json').read_text());need(v['passed'] and v['phase']=='verify' and v['batch']==batch and v['mapping']==row and v['helper_sha256']==sha(__file__) and v['appraisal_sha256']==APPRAISAL_SHA and v['source_review_sha256']==review_sha,'exact successful verified authority')
 need(sha(d/'restore.json.gz')==v['redirect_sha256'],'durable restore redirect')
 with gzip.open(d/'restore.json.gz','rb') as f:raw=f.read(2*1024**2+1)
 need(len(raw)<=2*1024**2,'bounded redirect');redirect=json.loads(raw)
 need(redirect['mapping']==row and redirect['original_identity']==v['original_identity'] and redirect['canonical_identity']==v['canonical_identity'],'restore identities')
 need({n:{k:x[k] for k in ('bytes','sha256')} for n,x in redirect['original_members'].items()}==expected,'restore exact members')
 descriptors=[];result=dict(passed=False,phase='release',batch=batch,mapping=row,helper_sha256=sha(__file__),verified_sha256=sha(d/'verified.json'),redirect_sha256=v['redirect_sha256'],released=False)
 try:
  for role in ('original','canonical'):
   path=Path(row[role+'_archive']);fd,st=held(path,row[role+'_archive_bytes']);descriptors.append((fd,path,st));need(st==v[role+'_identity'],'verified archive identity unchanged');compressed(fd,path,st,row[role+'_archive_sha256'])
  need(descriptors[0][2][:2]!=descriptors[1][2][:2],'different retained canonical inode')
  save(d/'release-start.json',result)
  for fd,path,st in descriptors:unchanged(fd,path,st)
  os.unlink(descriptors[0][1]);result['released']=True;syncdir(USB)
  unchanged(*descriptors[1]);need(not os.path.lexists(descriptors[0][1]),'only original absent');result['passed']=True
 except BaseException as e:result['error']=repr(e);raise
 finally:
  for fd,_,_ in descriptors:os.close(fd)
  save(d/'released.json',result)
 return result
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--verify',action='store_true');g.add_argument('--release-verified',action='store_true');ap.add_argument('--batch',type=int);a=ap.parse_args()
 if a.plan:
  need(sha(APPRAISAL)==APPRAISAL_SHA,'fixed appraisal');j=json.loads(APPRAISAL.read_text());print(json.dumps(dict(source_only=True,operations_performed=False,batches=j['mapping'],recoverable_archive_bytes=j['total_candidate_recovery_bytes'],floor=FLOOR,scope='Verify full original+canonical compressed/member bytes, durable exact restore redirect, then separately release ONLY mapped original containers.'),indent=2));return
 need(a.batch is not None,'explicit batch');print(json.dumps(verify(a.batch) if a.verify else release(a.batch),indent=2))
if __name__=='__main__':main()
