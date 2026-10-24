#!/usr/bin/env python3
"""Copy only the six fixed 52KiB baseline fixtures; never read weight payloads."""
from pathlib import Path
import gzip,hashlib,json,os,stat
P=Path(__file__).resolve().parent;L=P.parents[1];ROOT=L.parents[2]
BASE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a')
INDEX=L/'baseline/evidence/independent-a/artifact-index.jsonl.gz'
INDEX_SHA='e8137dddb0929d5476d27a8a774539a77d595aeb296e9d0ec778ceec066a6982'
CENSUS_SHA='103fe5152fbd6298371663c28b018846ff69973f015861c4e1be7fd82202fd91'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def schedule(warmups=4,cycles=24):
    return [{'warmup':phase=='warmup','cycle':n,'case':(n+j)%3,'order':['A','B'] if n%2==0 else ['B','A']} for phase,count in [('warmup',warmups),('measured',cycles)] for n in range(count) for j in range(3)]
def main():
    assert sha(INDEX)==INDEX_SHA
    scales=L/'attention-q8-p33/evidence/scale-census.json';assert sha(scales)==CENSUS_SHA
    meta=L/'metadata/new-census.json';assert sha(meta)=='b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1'
    c=json.loads(meta.read_text());weights={x['weight']:x for x in json.loads(scales.read_text())['tensors']}
    rows={}
    with gzip.open(INDEX,'rt') as f:
        for line in f:
            r=json.loads(line)
            if r['root']=='evidence':rows[r['path']]=r
    assert not (P/'manifest.json').exists(),'no overwrite'
    (P/'fixtures').mkdir(exist_ok=True);cases=[];total=0
    for layer,rank,inp,weight in [(0,0,'gdn.gated','ssm_out'),(23,0,'qsa.y','attn_output'),(47,1,'qsa.y','attn_output')]:
        name=f'blk.{layer}.{weight}.weight';w=weights[name];t=c['tensors'][name];assert t['type']=='Q8_0' and t['shape']==[2560,6144]
        shard=next(s for s in c['shards'] if Path(s['path']).name==t['shard'])
        item={'layer':layer,'weight':w,'shard':shard,'fixtures':{}}
        for kind,buf,extent in [('input',inp,12288),('expected','attention',5120)]:
            rel=f'prompt-00-none/rank{rank}/state-2147483647/blk.{layer}.{buf}.bin';r=rows[rel];assert r['bytes']==extent
            src=BASE/rel;assert src.resolve()==src
            fd=os.open(src,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd,'rb') as f:
                before=os.fstat(f.fileno());assert stat.S_ISREG(before.st_mode) and before.st_size==extent
                data=f.read(extent+1);assert len(data)==extent and hashlib.sha256(data).hexdigest()==r['sha256'];assert identity(before)==identity(os.fstat(f.fileno()))==identity(src.stat())
            dest=P/'fixtures'/f'layer-{layer}-{kind}.bin'
            with dest.open('xb') as f:f.write(data)
            item['fixtures'][kind]={'path':str(dest),'bytes':extent,'sha256':r['sha256'],'original_path':str(src),'original_stat':identity(before)};total+=extent
        cases.append(item)
    assert total==52224
    manifest={'schema':'gsq.attention-q8.micro-preparation.v1','copied_bytes':total,'weight_payload_reads':False,'device_execution':False,'cases':cases,'schedule':schedule(),'allocation_bytes':106481664,'pinned_transfer_bytes':1048576,'authority':{str(x):sha(x) for x in [INDEX,scales,meta,L/'baseline/evidence/independent-a/review.json',L/'graph/new-plan.json',L/'integration/evidence/full-native-build.json',L/'native-qualification/runner.cpp']}}
    (P/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Paths and digests are compiled constants, not caller-supplied model paths.
    lines=['#pragma once','#include <array>','#include <cstdint>','namespace micro {','struct Fixed { unsigned layer; const char *shard,*weight_sha,*x,*x_sha,*y,*y_sha; uint64_t offset,dev,ino,size,mtime,ctime; };','inline constexpr std::array<Fixed,3> fixed{{']
    for a in cases:
        s=a['shard'];x=a['fixtures']['input'];y=a['fixtures']['expected'];w=a['weight'];vals=[str(a['layer']),*[json.dumps(v) for v in [s['path'],w['payload_sha256'],x['path'],x['sha256'],y['path'],y['sha256']]],str(w['file_offset']),*[str(v)+'ULL' for v in s['stat_identity']]]
        lines.append('{'+','.join(vals)+'},')
    lines+=['}};','}'];(P/'fixed.hpp').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'copied_bytes':total,'manifest_sha256':sha(P/'manifest.json'),'weight_payload_reads':False}))
if __name__=='__main__':main()
