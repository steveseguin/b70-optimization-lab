#!/usr/bin/env python3
"""Seal fixed micro schedule after successful bounded extraction; no Device."""
import argparse,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;Q=P.parent;L=Q.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--seal-manifest',action='store_true',required=True);a.parse_args();out=P/'manifest.json';assert not out.exists(),'no overwrite'
 extraction=json.loads((P/'evidence/extraction.json').read_text());proof=json.loads((Q/'evidence/cpu-proof.json').read_text());assert extraction['passed'] and not extraction.get('error') and proof['passed'] and proof['proof']['passed'];assert sha(P/'fixed.hpp')==extraction['fixed_header_sha256']
 for f,h in extraction['source_sha256'].items():assert sha(f)==h,f
 cases=[]
 for c in extraction['cases']:
  f=c['files'];cases.append(dict(layer=c['layer'],label=c['label'],weight=c['weight'],consumed_experts=c['consumed_experts'],fixtures=dict(input=f['input'],routes=f['routes'],expected=f['output'],status=f['status']),sparse_weights=f['slices'],shard_identity=c['shard_identity']))
 assert [c['label'] for c in cases]==['blk.0.expsgate','blk.22.expsup','blk.46.expsgate']
 schedule=[dict(warmup=warm,cycle=cycle,case=(cycle+j)%3,order=['B','A'] if cycle%2 else ['A','B']) for warm,n in ((True,4),(False,24)) for cycle in range(n) for j in range(3)]
 files=[P/n for n in ('extract.py','prepare.py','runner.cpp','selected.hpp','fixed.hpp','build.py','once.py','source-pins.json','test_once.py','evidence/extraction.json')]+[Q/n for n in ('block.hpp','selection.hpp','micro-plan.json','evidence/cpu-proof.json')]+[L/'qkv-q6-p33/micro/evidence/device-a/review.json',L/'profiling/current-attribution/evidence/device-a/review.json']
 manifest=dict(schema='gsq.iq3xxs-block.native-micro-manifest.v1',cases=cases,schedule=schedule,authority={str(f):sha(f) for f in files},pairs=84,kernels=168,device_bytes=963610200,device_cap_bytes=1024**3,pinned_bytes=1048576,transfer_bytes=965690280,transfer_cap_bytes=1024**3,proof_scope='Three sparse real-route cases, exact fullsavedBF16+status, isolatedAB/BAeventtiming; notfullmodel throughput',native_admitted=False)
 with out.open('x') as f:f.write(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(dict(passed=True,manifest_sha256=sha(out),device_executed=False)))
if __name__=='__main__':main()
