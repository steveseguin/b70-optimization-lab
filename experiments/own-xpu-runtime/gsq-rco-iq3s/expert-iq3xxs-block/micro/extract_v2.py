#!/usr/bin/env python3
"""Fixed closed-bundle ranges + consumed packed expert slices; explicit read stage."""
import argparse,gzip,hashlib,importlib.util,json,os,resource,stat,struct,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;Q=P.parent;L=Q.parent;R=L.parents[2]
SOURCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-current-attribution-a')
REVIEW=L/'profiling/current-attribution/evidence/device-a/review.json';REVIEW_SHA='469fe156e317fc1aa93a56cf2a803d8d0c1cf786e13fe6d391d7eb50c883c7aa'
BASE_INDEX=L/'baseline/evidence/independent-a/artifact-index.jsonl.gz';BASE_SHA='e8137dddb0929d5476d27a8a774539a77d595aeb296e9d0ec778ceec066a6982'
CENSUS=L/'metadata/new-census.json';CENSUS_SHA='b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1'
SLICE=640*980

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(v).hexdigest()
def need(v,s):
 if not v:raise ValueError(s)
def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def read_at(fd,n,off):
 b=bytearray()
 while len(b)<n:
  x=os.pread(fd,min(65536,n-len(b)),off+len(b));need(x,'short bounded read');b.extend(x)
 return bytes(b)
def verify(fd,path,before):need(ident(os.fstat(fd))==before==ident(os.stat(path,follow_symlinks=False)),'held source changed')
def open_regular(path,limit):
 need(path.resolve()==path,'canonical fixed source');fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);s=os.fstat(fd)
 try:need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<=s.st_size<=limit,'source type/extent');return fd,ident(s)
 except BaseException:os.close(fd);raise

def authority():
 need(sha(REVIEW)==REVIEW_SHA and sha(BASE_INDEX)==BASE_SHA and sha(CENSUS)==CENSUS_SHA,'fixed audited authorities')
 r=json.loads(REVIEW.read_text());need(r['passed'] and r['physical_drain'] and r['explicit_repeat_and_closed_stamp_verified'] and r['kernel_fault_baseline_unchanged'],'closed attribution run')
 need(r['ownership']['returncodes']==[0,0] and not r['ownership']['retained_pids'],'owners closed')
 for f,h in json.loads((Q/'source-pins.json').read_text()).items():need(sha(R/f)==h,'source checkpoint drift')
 plan=json.loads((Q/'micro-plan.json').read_text());need([x['label'] for x in plan['cases']]==['blk.0.expsgate','blk.22.expsup','blk.46.expsgate'],'fixed three cases')
 old={}
 with gzip.open(BASE_INDEX,'rt') as f:
  for line in f:
   x=json.loads(line)
   if x['root']=='evidence' and x['path'].startswith('prompt-00-none/') and x['path'].endswith('.bin'):need(x['path'] not in old,'duplicate baseline row');old[x['path']]=x
 return plan,r,json.loads(CENSUS.read_text()),old

def ranges(directory,capture,old,case):
 # Only metadata and the four named ranges; no claim of rehashing entire bundle.
 files={};fds={};stamps={};chosen={}
 try:
  need(directory.resolve()==directory and {x.name for x in directory.iterdir()}=={'state.bundle','state-index.tsv','state.json','state-seal.txt'},'sealed fixed bundle inventory')
  for name in ('state-index.tsv','state.json','state-seal.txt','state.bundle'):
   fd,st=open_regular(directory/name,256*1024**2 if name=='state.bundle' else 1024**2);fds[name]=fd;stamps[name]=st
   if name!='state.bundle':files[name]=read_at(fd,st[2],0);need(digest(files[name])==capture['physical_sha256'][name],'audited bundle metadata')
  seal=files['state-seal.txt'].decode().splitlines();need(len(seal)==5 and seal[0]=='GSQ_STATE_SEAL_V1' and int(seal[1])==stamps['state.bundle'][2] and seal[2]==capture['physical_sha256']['state.bundle'],'audited payload seal')
  need(digest(files['state-index.tsv'])==seal[3] and digest(files['state.json'])==seal[4],'seal metadata binding')
  state=json.loads(files['state.json']);offset=0;seen=set();wanted={case[k]+'.bin':k for k in ('input','routes','output','status')};index=files['state-index.tsv'].decode('ascii').splitlines();need(index[0]=='GSQ_STATE_BUNDLE_V1','index schema')
  expected={('alternate-'+k[10:] if k.startswith('alternate:') else k)+'.bin':h for k,h in state['buffers'].items()}
  for line in index[1:]:
   name,a,b,h=line.split('\t');start=int(a);length=int(b);need(str(start)==a and str(length)==b and name not in seen and name in expected and expected[name]==h and start==offset and 0<=length<=stamps['state.bundle'][2]-offset,'complete contiguous index');seen.add(name);offset+=length
   if name in wanted:
    role=wanted[name];key=str(directory.relative_to(SOURCE)/name);row=old[key];need(row['bytes']==length and row['sha256']==h and length==case[('route' if role=='routes' else role)+'_bytes'],'original baseline range authority')
    data=read_at(fds['state.bundle'],length,start);need(digest(data)==h,'used bundle range hash');chosen[role]=dict(data=data,offset=start,bytes=length,sha256=h,original_baseline_path=key)
  need(seen==set(expected) and offset==stamps['state.bundle'][2] and set(chosen)==set(wanted.values()),'full metadata inventory and all used ranges')
  for n,fd in fds.items():verify(fd,directory/n,stamps[n])
  return chosen,stamps
 finally:
  for fd in fds.values():os.close(fd)

def consumed(routes):
 need(len(routes)==120,'ten route slots');values=[struct.unpack_from('<III',routes,i*12) for i in range(10)];ids=set()
 for expert,begin,count in values:
  if expert<512 and begin<=640 and count<=640-begin and count:ids.add(expert)
 need(ids and len(ids)<=10,'bounded consumed expert IDs');return values,sorted(ids)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--extract',action='store_true');a=ap.parse_args();plan,review,census,old=authority()
 if not a.extract:print(json.dumps(dict(passed=True,source_only=True,cases=plan['cases'],payload_read=False,max_weight_slice_bytes=18816000,fixture_bytes=192480),indent=2));return
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));dest=P/'fixtures';need(not dest.exists() and not (P/'fixed.hpp').exists() and not (P/'evidence/extraction.json').exists(),'one extraction, no retry');need(shutil.disk_usage(P).free>=27000000000+32*1024**2,'root floor plus32MiB extraction reservation');dest.mkdir()
 receipt=dict(passed=False,cases=[],payload_bytes_read=0,header_bytes_read=0,bundle_bytes_read=0,source_sha256={str(f):sha(f) for f in (Path(__file__),Q/'block.hpp',Q/'selection.json',Q/'micro-plan.json',Q/'source-pins.json',REVIEW,BASE_INDEX,CENSUS)},device_executed=False,scope='Only four named bundle ranges and consumed expert slices percase; no wholebundle/model/tensor rehash claim')
 fds={}
 try:
  for case in plan['cases']:
   layer=int(case['label'].split('.')[1]);rank=layer//24;relative=f'prompt-00-none/rank{rank}/state-2147483647';capture=next(x for x in review['bundle_captures'] if x['path']==relative);need(capture['baseline_semantic_oracle_required'] and capture['inventory_and_lengths_exact'],'qualified completed bundle')
   copied,stamps=ranges(SOURCE/relative,capture,old,case);route_values,ids=consumed(copied['routes']['data']);t=census['tensors'][case['weight']];need(t['type_id']==18 and t['dimensions']==[2560,640,512] and t['bytes']==512*SLICE,'fixed tensor')
   shard=next(x for x in census['shards'] if Path(x['path']).name==t['shard']);path=Path(shard['path'])
   if path.name not in fds:
    fd,st=open_regular(path,shard['file_bytes']);need(st==shard['stat_identity'],'model immutable identity');fds[path.name]=(fd,path,st)
    header=read_at(fd,shard['header_bytes_read'],0);need(digest(header)==shard['header_sha256'],'authenticated raw header');receipt['header_bytes_read']+=len(header)
   fd,path,st=fds[path.name];need(t['file_offset']>=shard['data_start'] and t['file_offset']+t['bytes']<=st[2],'authenticated tensor span');pieces=[];slices=[]
   for expert in ids:
    off=t['file_offset']+expert*SLICE;data=read_at(fd,SLICE,off);pieces.append(data);slices.append(dict(expert_id=expert,source_offset=off,bytes=SLICE,sha256=digest(data)));receipt['payload_bytes_read']+=len(data)
   verify(fd,path,st);case_files={}
   for role,x in copied.items():
    target=dest/f'{case["label"]}-{role}.bin';data=x.pop('data');receipt['bundle_bytes_read']+=len(data)
    with target.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    need(sha(target)==x['sha256'],'fixture readback');case_files[role]=dict(path=str(target),**x)
   payload=b''.join(pieces);target=dest/f'{case["label"]}-slices.bin'
   with target.open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
   need(sha(target)==digest(payload),'sparse slice readback');case_files['slices']=dict(path=str(target),bytes=len(payload),sha256=digest(payload))
   receipt['cases'].append(dict(label=case['label'],layer=layer,weight=case['weight'],source_shard=str(path),shard_identity=st,tensor_offset=t['file_offset'],tensor_bytes=t['bytes'],routes=route_values,consumed_experts=ids,slices=slices,files=case_files,bundle_directory=str(SOURCE/relative),bundle_stamps=stamps,audited_whole_bundle_sha256=capture['physical_sha256']['state.bundle']))
  for fd,path,st in fds.values():verify(fd,path,st)
  need(receipt['payload_bytes_read']<=18816000 and receipt['bundle_bytes_read']==192480,'fixed bounded payload reads')
  lines=['#pragma once','#include <array>','#include <cstdint>','namespace micro {','struct Fixed {unsigned layer;const char *label,*weight,*shard,*x,*x_sha,*routes,*routes_sha,*y,*y_sha,*status,*status_sha,*slices,*slices_sha;uint64_t dev,ino,size,mtime,ctime;unsigned used;std::array<unsigned,10> ids;};','inline constexpr std::array<Fixed,3> fixed{{']
  for c in receipt['cases']:
   strings=[c['label'],c['weight'],c['source_shard']]
   for role in ('input','routes','output','status','slices'):strings += [c['files'][role]['path'],c['files'][role]['sha256']]
   ids=c['consumed_experts'];lines.append('{'+','.join([str(c['layer']),*[json.dumps(x) for x in strings],*[str(x)+'ULL' for x in c['shard_identity']],str(len(ids)),'{'+','.join(map(str,ids+[0]*(10-len(ids))))+'}'])+'},')
  lines+=['}};','}']
  with (P/'fixed.hpp').open('x') as f:f.write('\n'.join(lines)+'\n');f.flush();os.fsync(f.fileno())
  for directory in (dest,P):
   fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
  receipt['fixed_header_sha256']=sha(P/'fixed.hpp');receipt['passed']=True
 except BaseException as e:receipt['passed']=False;receipt['error']=repr(e);raise
 finally:
  for fd,_,_ in fds.values():os.close(fd)
  with (P/'evidence/extraction.json').open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n');f.flush();os.fsync(f.fileno())
 print(json.dumps(dict(passed=True,receipt_sha256=sha(P/'evidence/extraction.json'),payload_bytes_read=receipt['payload_bytes_read'],bundle_bytes_read=receipt['bundle_bytes_read'])))
if __name__=='__main__':main()
