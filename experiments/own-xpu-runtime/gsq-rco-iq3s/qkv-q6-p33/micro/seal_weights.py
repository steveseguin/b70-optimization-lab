#!/usr/bin/env python3
"""Explicit three-tensor read/hashes plus fixed header authority; no Device."""
from pathlib import Path
import argparse,collections,hashlib,json,os,resource,stat
P=Path(__file__).resolve().parent;Q=P.parent;L=Q.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def main():
 a=argparse.ArgumentParser();a.add_argument('--read-fixed-three',action='store_true',required=True);a.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert not (Q/'evidence/three-weight-census.json').exists(),'one explicit read only'
 plan=json.loads((Q/'selection.json').read_text());metadata=L/'metadata/new-census.json';assert sha(metadata)=='b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1'
 c=json.loads(metadata.read_text());assert [x['site']['layer'] for x in plan['micro_cases']]==[0,24,40]
 for path,h in plan['source_sha256'].items():assert sha(path)==h,path
 copy=json.loads((Q/'evidence/fixture-copy.json').read_text());assert copy['passed']
 for f in copy['files']:assert sha(f['path'])==f['sha256']
 used={x['site']['shard'] for x in plan['micro_cases']};fds={};rows=[];header_bytes=0;payload_bytes=0
 try:
  for shard in c['shards']:
   if Path(shard['path']).name not in used:continue
   path=Path(shard['path']);assert path.resolve()==path;fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);fds[path.name]=(fd,shard)
   st=os.fstat(fd);assert stat.S_ISREG(st.st_mode) and identity(st)==shard['stat_identity']
   data=os.pread(fd,shard['header_bytes_read'],0);header_bytes+=len(data);assert len(data)==shard['header_bytes_read'] and hashlib.sha256(data).hexdigest()==shard['header_sha256']
  for item in plan['micro_cases']:
   site=item['site'];t=c['tensors'][site['weight']];assert t['type']=='Q6_K' and t['shape']==[10240,2560] and t['bytes']==21504000
   fd,shard=fds[site['shard']];assert site['offset']==t['file_offset'] and site['offset']>=shard['data_start'] and site['offset']+t['bytes']<=shard['file_bytes']
   digest=hashlib.sha256();counts=collections.Counter();signed=collections.Counter()
   for offset in range(0,t['bytes'],210*4096):
    n=min(210*4096,t['bytes']-offset);data=os.pread(fd,n,site['offset']+offset);assert len(data)==n and n%210==0;payload_bytes+=n;digest.update(data)
    for h in (lo|(hi<<8) for lo,hi in zip(data[208::210],data[209::210])):
     exp=h&0x7c00;frac=h&1023;kind=('nan' if frac else 'infinity') if exp==0x7c00 else ('normal' if exp else 'subnormal' if frac else 'negative_zero' if h&0x8000 else 'positive_zero');counts[kind]+=1
    for k in range(192,208):signed.update(data[k::210])
   assert sum(counts.values())==102400 and sum(signed.values())==1638400
   rows.append({'layer':site['layer'],'weight':site['weight'],'path':shard['path'],'offset':site['offset'],'bytes':t['bytes'],'sha256':digest.hexdigest(),'half_scale_categories':dict(counts),'signed_scale_counts':{str(k if k<128 else k-256):v for k,v in sorted(signed.items())}})
  for fd,shard in fds.values():assert identity(os.fstat(fd))==shard['stat_identity']==identity(os.stat(shard['path'],follow_symlinks=False))
 finally:
  for fd,_ in fds.values():os.close(fd)
 assert payload_bytes==64512000
 receipt={'passed':True,'scope':'Only micro layers0/24/40, not all22 selected sites','tensors':rows,'header_bytes_read':header_bytes,'payload_bytes_read':payload_bytes,'read_bytes':header_bytes+payload_bytes,'all_selected_three_half_scales_finite':all(not r['half_scale_categories'].get('nan') and not r['half_scale_categories'].get('infinity') for r in rows),'source_sha256':{str(x):sha(x) for x in [Path(__file__),Q/'selection.json',metadata,Q/'evidence/fixture-copy.json']},'device_executed':False}
 (Q/'evidence/three-weight-census.json').write_text(json.dumps(receipt,indent=2)+'\n')
 lines=['#pragma once','#include <array>','#include <cstdint>','namespace micro {','struct Fixed { unsigned layer; const char *shard,*weight_sha,*x,*x_sha,*y,*y_sha; uint64_t offset,dev,ino,size,mtime,ctime; };','inline constexpr std::array<Fixed,3> fixed{{']
 for item,row in zip(plan['micro_cases'],rows):
  layer=item['site']['layer'];shard=next(s for s in c['shards'] if s['path']==row['path']);x=next(f for f in copy['files'] if Path(f['path']).name==f'layer-{layer}-input.bin');y=next(f for f in copy['files'] if Path(f['path']).name==f'layer-{layer}-expected.bin')
  values=[str(layer),*[json.dumps(v) for v in [shard['path'],row['sha256'],x['path'],x['sha256'],y['path'],y['sha256']]],str(row['offset']),*[str(v)+'ULL' for v in shard['stat_identity']]];lines.append('{'+','.join(values)+'},')
 lines+=['}};','}'];(P/'fixed.hpp').write_text('\n'.join(lines)+'\n');print(json.dumps({'passed':True,'payload_bytes':payload_bytes,'headers':header_bytes,'receipt_sha256':sha(Q/'evidence/three-weight-census.json')}))
if __name__=='__main__':main()
