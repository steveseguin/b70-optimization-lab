#!/usr/bin/env python3
"""Root-only explicit manifest seal after fixed extraction/native receipts exist."""
import argparse,hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent;P=O.parent;Q=P.parent;L=Q.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def cases_schedule(extraction):
 assert len(extraction['cases'])==2;cases=[]
 for c,(label,weight,rows) in zip(extraction['cases'],[('blk.0.hc.a.low','blk.0.hc_attn_down.weight',320),('blk.0.hc.a.inject','blk.0.hc_attn_inject.weight',4)]):
  assert c['label']==label and c['rows']==rows and c['tensor_bytes']==rows*20480
  f=c['files'];assert set(f)=={'input','output','weights'} and f['input']['bytes']==20480 and f['output']['bytes']==rows*2 and f['weights']['bytes']==rows*20480
  cases.append(dict(layer=0,label=label,weight=weight,rows=rows,columns=10240,fixtures=dict(input=f['input'],expected=f['output']),packed_weights=f['weights'],shard_identity=c['shard_identity']))
 assert cases[0]['fixtures']['input']==cases[1]['fixtures']['input'],'shared exact input fixture'
 schedule=[dict(warmup=warm,cycle=cycle,case=((cycle//2)+j)%2,order=['B','A'] if cycle%2 else ['A','B']) for warm,n in ((True,4),(False,24)) for cycle in range(n) for j in range(2)]
 return cases,schedule

def main():
 a=argparse.ArgumentParser();a.add_argument('--seal-manifest',action='store_true',required=True);a.add_argument('--build-sha256',required=True);a.add_argument('--binary-sha256',required=True);args=a.parse_args();out=O/'manifest.json';assert not out.exists(),'exclusive manifest'
 extraction=json.loads((P/'evidence/extraction.json').read_text());review=json.loads((P/'evidence/independent-extraction-review.json').read_text());build=json.loads((P/'evidence/native-build.json').read_text());proof=json.loads((Q/'evidence/cpu-proof.json').read_text())
 assert extraction['passed'] and not extraction.get('error') and review['passed'] and review['extraction_receipt_sha256']==sha(P/'evidence/extraction.json')
 assert build['passed'] and sha(P/'evidence/native-build.json')==args.build_sha256 and build['binary_sha256']==args.binary_sha256 and sha(build['binary'])==args.binary_sha256
 assert proof['passed'] and proof['proof']['passed']
 assert sha(P/'fixed.hpp')==extraction['fixed_header_sha256']==review['fixed_header_sha256']
 for f,h in extraction['source_sha256'].items():assert sha(f)==h,f
 for f,h in json.loads((O/'parent-pins.json').read_text()).items():assert sha(f)==h,f
 parent=L/'iq4nl-down-direct/micro';prior=json.loads((parent/'evidence/device-a/review.json').read_text());assert prior['passed']
 for name in ('startup.hpp','handshake.py'):assert sha(P/name)==sha(parent/name),'qualified ACK source unchanged'
 cases,schedule=cases_schedule(extraction)
 files=[P/n for n in ('extract.py','runner.cpp','selected.hpp','startup.hpp','handshake.py','fixture_schema.hpp','fixed.hpp','build.py','source-pins.json','extraction-plan.json','evidence/extraction.json','evidence/independent-extraction-review.json','evidence/native-build.json')]+[Q/n for n in ('one_sg.hpp','policy.hpp','selection.json','evidence/cpu-proof.json')]+[O/n for n in ('once.py','prepare.py','test_once.py','README.md','parent-pins.json','once.patch')]+[parent/'evidence/device-a/review.json']
 manifest=dict(schema='gsq.hc-bf16-one-sg.native-micro-manifest.v1',cases=cases,schedule=schedule,authority={str(f):sha(f) for f in files},pairs=56,kernels=112,device_bytes=6677776,device_cap_bytes=8*1024**2,pinned_bytes=1048576,transfer_bytes=6712768,transfer_cap_bytes=8*1024**2,native_build_sha256=args.build_sha256,binary_sha256=args.binary_sha256,startup=dict(real_backend_before_ready=True,deadline_seconds=60,actual_native_target_fd_before_ack=True,positive_contact_and_ack_required=True),proof_scope='Two fixed layer0 HC BF16 low/inject shapes; full saved BF16 exactness and isolated balanced AB/BA; no fullmodel throughput claim',native_admitted=False)
 with out.open('x') as f:f.write(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(dict(passed=True,manifest_sha256=sha(out),device_executed=False)))
if __name__=='__main__':main()
