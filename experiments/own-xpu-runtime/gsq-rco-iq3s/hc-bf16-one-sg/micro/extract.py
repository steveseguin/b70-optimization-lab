#!/usr/bin/env python3
"""Fixed bounded HC extraction; default checks metadata only, never a Device."""
import argparse,gzip,hashlib,json,os,resource,shutil,stat
from pathlib import Path
P=Path(__file__).resolve().parent;Q=P.parent;L=Q.parent
PLAN=P/'extraction-plan.json'
PLAN_SHA='f4c2293aa33b6c976014c45d44264e89a78b645cbbdfde76fcc09a9433e935ae'
PREFIX='prompt-00-none/rank0/state-2147483647/'
def need(x,m):
 if not x:raise ValueError(m)
def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):return digest(Path(p).read_bytes())
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def read_at(fd,n,off):
 out=bytearray()
 while len(out)<n:
  b=os.pread(fd,min(65536,n-len(out)),off+len(out));need(b,'short bounded read');out.extend(b)
 return bytes(out)
def regular(p,n):
 need(p.resolve()==p,'canonical path');fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==n,'regular exact extent');return fd,identity(s)
 except BaseException:os.close(fd);raise
def held(fd,p,s):need(identity(os.fstat(fd))==s==identity(os.stat(p,follow_symlinks=False)),'held input changed')
def metadata(p,h):
 need(p.stat().st_size<2*1024**2,'bounded metadata');fd,s=regular(p,p.stat().st_size)
 try:b=read_at(fd,s[2],0);held(fd,p,s);need(digest(b)==h,'metadata digest '+str(p));return b
 finally:os.close(fd)
def index(p,h):
 need(sha(p)==h,'authority index digest');rows={}
 with gzip.open(p,'rt') as f:
  for line in f:
   r=json.loads(line)
   if r['root']=='evidence' and r['path'].startswith(PREFIX):
    need(r['path'] not in rows,'duplicate authority');rows[r['path']]=r
 return rows
def authority():
 need(sha(PLAN)==PLAN_SHA,'fixed extraction plan');p=json.loads(PLAN.read_text())
 r=json.loads(metadata(Path(p['review_path']),p['review_sha256']))
 need(r['passed'] and r['physical_drain'] and r['kernel_fault_baseline_unchanged'],'qualified current capture closure')
 need(len(r['owners'])==2 and all(o['safe_to_exit'] and o['in_flight']==0 and o['live_bytes']==0 and o['exit_code']==0 for o in r['owners']),'both safe owners')
 need(r['baseline_review_sha256']==p['original_baseline_review_sha256'] and r['baseline_index_sha256']==p['original_baseline_index_sha256'],'original baseline binding')
 baseline=L/'baseline/evidence/independent-a';need(sha(baseline/'review.json')==p['original_baseline_review_sha256'],'original review digest')
 need(json.loads((baseline/'review.json').read_text())['passed'],'original baseline pass')
 old=index(baseline/'artifact-index.jsonl.gz',p['original_baseline_index_sha256'])
 current=index(Path(p['review_path']).parent/'artifact-index.jsonl.gz',p['profile_artifact_index_sha256'])
 bundle=Path(p['bundle_path']);row=current[PREFIX+'state.bundle'];need(row['sha256']==p['bundle_metadata_sha256']['state.bundle'],'bundle authority')
 data={}
 for name,h in p['bundle_metadata_sha256'].items():
  if name=='state.bundle':continue
  rr=current[PREFIX+name];need(rr['sha256']==h,'metadata authority');data[name]=metadata(bundle.parent/name,h);need(len(data[name])==rr['bytes'],'metadata extent')
 seal=data['state-seal.txt'].decode().splitlines();need(seal==['GSQ_STATE_SEAL_V1',str(row['bytes']),row['sha256'],p['bundle_metadata_sha256']['state-index.tsv'],p['bundle_metadata_sha256']['state.json']],'exact seal')
 lines=data['state-index.tsv'].decode().splitlines();need(lines[0]=='GSQ_STATE_BUNDLE_V1','bundle schema');entries={};cursor=0
 for line in lines[1:]:
  n,o,z,h=line.split('\t');o=int(o);z=int(z);need(n not in entries and o==cursor and z>=0,'unique contiguous bundle');entries[n]=(o,z,h);cursor+=z
 need(cursor==row['bytes'],'bundle complete extent');state=json.loads(data['state.json']);ranges={}
 census=json.loads((L/'metadata/new-census.json').read_text());graph=json.loads((L/'graph/new-plan.json').read_text())
 pins=json.loads((Q/'source-pins.json').read_text())
 for rel,h in pins.items():need(sha(L.parents[2]/rel)==h,'source authority '+rel)
 need([c['label'] for c in p['cases']]==['blk.0.hc.a.low','blk.0.hc.a.inject'],'fixed two cases')
 for c in p['cases']:
  need(c['columns']==10240 and c['rows']==(320 if c['label'].endswith('low') else 4),'fixed shapes')
  t=census['tensors'][c['weight']];need(t==c['tensor'] and t['type_id']==30 and t['bytes']==c['rows']*20480,'complete BF16 tensor')
  s=next(s for s in census['shards'] if Path(s['path']).name==t['shard']);need(s==c['shard'],'fixed shard metadata')
  for v in c['ranges'].values():
   n=v['name'];need(entries[n+'.bin']==(v['offset'],v['bytes'],v['sha256']),'selected bundle span')
   need(state['buffers'][n]==v['sha256'] and old[PREFIX+n+'.bin']['sha256']==v['sha256'] and old[PREFIX+n+'.bin']['bytes']==v['bytes'],'original exact selected range')
   need([x['label'] for x in graph['launches'] if n in x['outputs']]==[v['unique_writer']],'unique producer')
   if n in ranges:need(ranges[n]==v,'shared range identity')
   ranges[n]=v
 need(len(ranges)==3 and sum(v['bytes'] for v in ranges.values())==21128,'fixed unique range budget')
 return p,row,ranges
def syncdir(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
def durable(p,b):
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 need(sha(p)==digest(b),'copied readback')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--extract',action='store_true');a=ap.parse_args();p,row,ranges=authority()
 if not a.extract:print(json.dumps(dict(passed=True,executed=False,model_payload_bytes=6635520,unique_state_bytes=21128)));return
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'placement');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 need(shutil.disk_usage(P).free>=27000000000+32*1024**2,'root floor +32MiB')
 dest=P/'fixtures';need(not dest.exists() and not (P/'fixed.hpp').exists() and not (P/'evidence/extraction.json').exists(),'one fresh extraction')
 dest.mkdir();receipt=dict(passed=False,source_sha256={str(f):sha(f) for f in [Path(__file__),PLAN,Q/'one_sg.hpp',Q/'policy.hpp',Q/'evidence/cpu-proof.json',P/'fixture_schema.hpp']},cases=[],device_executed=False,model_payload_bytes_read=0,bundle_bytes_read=0,header_bytes_read=0,scope='Only three authenticated bundle ranges and two complete model tensors; no whole-bundle or whole-model rehash claim')
 fds=[]
 try:
  bundle=Path(p['bundle_path']);fd,bs=regular(bundle,row['bytes']);fds.append(fd);data={}
  for n,v in ranges.items():
   b=read_at(fd,v['bytes'],v['offset']);need(digest(b)==v['sha256'],'selected original range');data[n]=b;receipt['bundle_bytes_read']+=len(b)
  held(fd,bundle,bs);receipt['bundle_identity']=bs
  # Both fixed shard headers are checked, even though both selected tensors are in shard0.
  census=json.loads((L/'metadata/new-census.json').read_text());models={}
  for s in census['shards']:
   path=Path(s['path']);mf,ms=regular(path,s['file_bytes']);fds.append(mf);need(ms==s['stat_identity'],'held shard identity');b=read_at(mf,s['header_bytes_read'],0);need(digest(b)==s['header_sha256'],'raw header digest');receipt['header_bytes_read']+=len(b);models[path.name]=(mf,ms,path)
  files={}
  for n,b in data.items():
   target=dest/(n+'.bin');durable(target,b);files[n]=dict(path=str(target),bytes=len(b),sha256=digest(b))
  initializers=[]
  for c in p['cases']:
   t=c['tensor'];mf,ms,path=models[t['shard']];need(t['file_offset']>=c['shard']['data_start'] and t['file_offset']+t['bytes']<=ms[2],'tensor span');b=read_at(mf,t['bytes'],t['file_offset']);receipt['model_payload_bytes_read']+=len(b);held(mf,path,ms)
   target=dest/(c['weight']+'.bin');durable(target,b);cf={role:files[v['name']] for role,v in c['ranges'].items()};cf['weights']=dict(path=str(target),bytes=len(b),sha256=digest(b))
   receipt['cases'].append(dict(label=c['label'],rows=c['rows'],source_shard=str(path),shard_identity=ms,tensor_offset=t['file_offset'],tensor_bytes=t['bytes'],files=cf))
   strings=[c['label'],c['weight'],str(path)]
   for role in ['input','output','weights']:strings += [cf[role]['path'],cf[role]['sha256']]
   initializers.append('{'+','.join(['0',str(c['rows']),*[json.dumps(s) for s in strings],*[str(v)+'ULL' for v in ms]])+'},')
  text='#pragma once\n#include "fixture_schema.hpp"\nnamespace micro {\ninline constexpr std::array<Fixed,2> fixed{{\n'+'\n'.join(initializers)+'\n}};\n}\n';durable(P/'fixed.hpp',text.encode());syncdir(dest);syncdir(P)
  held(fd,bundle,bs)
  for mf,ms,path in models.values():held(mf,path,ms)
  need(receipt['model_payload_bytes_read']==6635520 and receipt['bundle_bytes_read']==21128 and receipt['header_bytes_read']<=11024528,'fixed read budgets')
  for f,h in receipt['source_sha256'].items():need(sha(f)==h,'post extraction source drift')
  receipt.update(passed=True,fixed_header_sha256=sha(P/'fixed.hpp'))
 except BaseException as e:receipt.update(passed=False,error=repr(e));raise
 finally:
  for fd in fds:os.close(fd)
  durable(P/'evidence/extraction.json',(json.dumps(receipt,indent=2)+'\n').encode());syncdir(P/'evidence')
 print(json.dumps(dict(passed=True,receipt_sha256=sha(P/'evidence/extraction.json'))))
if __name__=='__main__':main()
