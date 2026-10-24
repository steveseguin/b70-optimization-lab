#!/usr/bin/env python3
"""Explicit fixed archived-baseline extraction; no inference/device operations."""
import argparse,gzip,hashlib,json,os,resource,shutil,stat,struct,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent;Q=P.parent;L=Q.parent;R=L.parents[2]
PLAN=P/'extraction-plan.json';CENSUS=L/'metadata/new-census.json';INDEX=L/'baseline/evidence/independent-a/artifact-index.jsonl.gz'
SLICE=921600

def need(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(b):return hashlib.sha256(b).hexdigest()
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def read_at(fd,n,offset):
 data=bytearray()
 while len(data)<n:
  b=os.pread(fd,min(65536,n-len(data)),offset+len(data));need(b,'short bounded read');data.extend(b)
 return bytes(data)
def verify(fd,p,st):need(identity(os.fstat(fd))==st==identity(os.stat(p,follow_symlinks=False)),'held file changed')
def regular(p,size):
 need(p.resolve()==p,'canonical fixed path');fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==size,'regular exact input extent');return fd,identity(s)
 except BaseException:os.close(fd);raise

def authority():
 plan=json.loads(PLAN.read_text())
 for name,h in plan['authority'].items():need(sha(name)==h,'fixed authority drift')
 need(plan['case']['label']=='blk.0.expsdown' and plan['case']['weight']=='blk.0.ffn_down_exps.weight','fixed single case')
 review=json.loads((L/'baseline/evidence/independent-a/review.json').read_text());need(review['passed'] and review['all12_exact'] and review['physical_drain'],'closed original baseline')
 rows={}
 with gzip.open(INDEX,'rt') as f:
  for line in f:
   r=json.loads(line)
   if r['root']=='evidence' and r['path'].startswith('prompt-00-none/') and r['path'].endswith('.bin'):
    need(r['path'] not in rows,'duplicate authority row');rows[r['path']]=r
 need(len(rows)==2113 and sum(r['bytes'] for r in rows.values())==231442500,'complete fixed request archive inventory')
 need(all(rows[n]==v for n,v in plan['required_original_members'].items()),'fixed four member authority')
 return plan,rows,json.loads(CENSUS.read_text())

def archived(plan,rows):
 a=plan['archive'];p=Path(a['archive']);fd,st=regular(p,a['archive_bytes']);chosen={};seen=set();uncompressed=0;physical=0
 try:
  with os.fdopen(os.dup(fd),'rb') as stream:
   h=hashlib.sha256()
   while b:=stream.read(256*1024):h.update(b);physical+=len(b)
   need(h.hexdigest()==a['archive_sha256'],'fixed compressed archive SHA');verify(fd,p,st);stream.seek(0)
   class Counted:
    def read(self,n):
     nonlocal physical
     b=stream.read(n);physical+=len(b);return b
   with tarfile.open(fileobj=Counted(),mode='r|gz') as tar:
    for member in tar:
     n=member.name;need(member.isfile() and not member.issym() and not member.islnk() and n in rows and n not in seen,'fixed regular unique member')
     need(member.size==rows[n]['bytes'],'member extent');seen.add(n);uncompressed+=member.size;need(uncompressed<=231442500,'archive uncompressed bound')
     src=tar.extractfile(member);need(src is not None,'member payload');h=hashlib.sha256();kept=bytearray();count=0
     while b:=src.read(65536):
      h.update(b);count+=len(b);need(count<=member.size,'member read bound')
      if n in plan['required_original_members']:kept.extend(b)
     need(count==member.size and h.hexdigest()==rows[n]['sha256'],'member exact original digest')
     if n in plan['required_original_members']:chosen[n]=bytes(kept)
   need(seen==set(rows) and uncompressed==231442500,'complete archive stream')
  verify(fd,p,st);need(set(chosen)==set(plan['required_original_members']),'four retained members');return chosen,st,physical
 finally:os.close(fd)

def durable(p,b):
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 need(sha(p)==digest(b),'copied fixture readback')
def syncdir(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--extract',action='store_true');args=ap.parse_args();plan,rows,census=authority()
 if not args.extract:print(json.dumps(dict(source_only=True,case=plan['case'],archive_bytes=90040912,archive_uncompressed_bytes=231442500,maximum_weight_payload_bytes=9216000,retained_fixture_bytes=64160,executed=False),indent=2));return
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 need(shutil.disk_usage(P).free>=27000000000+32*1024**2,'root floor plus32MiB reservation')
 dest=P/'fixtures';need(not dest.exists() and not (P/'fixed.hpp').exists() and not (P/'evidence/extraction.json').exists(),'fresh one extraction only');dest.mkdir()
 receipt=dict(passed=False,schema='gsq.iq4nl-direct.extraction.v1',source_sha256={str(p):sha(p) for p in (Path(__file__),PLAN,Q/'direct.hpp',Q/'policy.hpp',Q/'evidence/cpu-proof.json')},cases=[],device_executed=False,payload_bytes_read=0,archive_compressed_bytes_read=0,archive_uncompressed_bytes_read=0,header_bytes_read=0,fixture_bytes=0,scope='Whole fixed archive verified; only four state members retained and consumed expert slices read; no fulltensor/bank hash')
 fd=None
 try:
  chosen,st,compressed_read=archived(plan,rows);receipt.update(archive_identity=st,archive_sha256=plan['archive']['archive_sha256'],archive_compressed_bytes_read=compressed_read,archive_uncompressed_bytes_read=231442500)
  prefix='prompt-00-none/rank0/state-2147483647/';names={'input':'blk.0.expsact','routes':'blk.0.routes.down','output':'blk.0.expsdown','status':'blk.0.expsdown.status'}
  data={role:chosen[prefix+name+'.bin'] for role,name in names.items()};need([len(data[n]) for n in names]==[12800,120,51200,40],'exact fixture extents')
  route_values=[struct.unpack_from('<III',data['routes'],i*12) for i in range(10)];ids=sorted({e for e,b,n in route_values if e<512 and b<=2560 and n<=2560-b and n>0});need(0<len(ids)<=10,'bounded consumed expert set')
  t=census['tensors']['blk.0.ffn_down_exps.weight'];need(t['type_id']==20 and t['dimensions']==[640,2560,512] and t['bytes']==512*SLICE,'exact raw IQ4 down tensor')
  shard=next(s for s in census['shards'] if Path(s['path']).name==t['shard']);path=Path(shard['path']);fd,st=regular(path,shard['file_bytes']);need(st==shard['stat_identity'],'model stat authority')
  header=read_at(fd,shard['header_bytes_read'],0);need(digest(header)==shard['header_sha256'],'held raw header authority');receipt['header_bytes_read']=len(header)
  need(t['file_offset']>=shard['data_start'] and t['file_offset']+t['bytes']<=st[2],'authenticated tensor extent');pieces=[];slices=[]
  for expert in ids:
   off=t['file_offset']+expert*SLICE;b=read_at(fd,SLICE,off);pieces.append(b);slices.append(dict(expert_id=expert,source_offset=off,bytes=SLICE,sha256=digest(b)));receipt['payload_bytes_read']+=len(b)
  verify(fd,path,st);files={}
  for role,b in data.items():
   target=dest/f'blk.0.expsdown-{role}.bin';durable(target,b);files[role]=dict(path=str(target),bytes=len(b),sha256=digest(b),original_baseline_path=prefix+names[role]+'.bin');receipt['fixture_bytes']+=len(b)
  b=b''.join(pieces);target=dest/'blk.0.expsdown-slices.bin';durable(target,b);files['slices']=dict(path=str(target),bytes=len(b),sha256=digest(b))
  c=dict(label='blk.0.expsdown',layer=0,weight='blk.0.ffn_down_exps.weight',source_shard=str(path),shard_identity=st,tensor_offset=t['file_offset'],tensor_bytes=t['bytes'],routes=route_values,consumed_experts=ids,slices=slices,files=files);receipt['cases'].append(c)
  strings=[c['label'],c['weight'],c['source_shard']]
  for role in ('input','routes','output','status','slices'):strings += [files[role]['path'],files[role]['sha256']]
  header=['#pragma once','#include <array>','#include <cstdint>','namespace micro {','struct Fixed {unsigned layer;const char *label,*weight,*shard,*x,*x_sha,*routes,*routes_sha,*y,*y_sha,*status,*status_sha,*slices,*slices_sha;uint64_t dev,ino,size,mtime,ctime;unsigned used;std::array<unsigned,10> ids;};','inline constexpr std::array<Fixed,1> fixed{{','{'+','.join(['0',*[json.dumps(s) for s in strings],*[str(x)+'ULL' for x in st],str(len(ids)),'{'+','.join(map(str,ids+[0]*(10-len(ids))))+'}'])+'},','}};','}']
  durable(P/'fixed.hpp',('\n'.join(header)+'\n').encode());syncdir(dest);syncdir(P);verify(fd,path,st)
  need(receipt['archive_compressed_bytes_read']<=2*plan['archive']['archive_bytes'] and receipt['payload_bytes_read']<=9216000 and receipt['fixture_bytes']==64160,'actual read bounds');receipt['fixed_header_sha256']=sha(P/'fixed.hpp');receipt['passed']=True
 except BaseException as e:receipt['passed']=False;receipt['error']=repr(e);raise
 finally:
  if fd is not None:os.close(fd)
  with (P/'evidence/extraction.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 print(json.dumps(dict(passed=True,receipt_sha256=sha(P/'evidence/extraction.json'))))
if __name__=='__main__':main()
