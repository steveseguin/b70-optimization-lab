#!/usr/bin/env python3
"""Root-only explicit manifest seal after fixed extraction/native receipts exist."""
import argparse,hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent;P=O.parent;Q=P.parent;L=Q.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def cases_schedule(extraction):
 assert len(extraction['cases'])==3;cases=[]
 expected=[('blk.0.gdn.z','blk.0.attn_gate.weight',12,6144),('blk.1.gdn.qkv','blk.1.attn_qkv.weight',13,10240),('blk.2.gdn.z','blk.2.attn_gate.weight',23,6144)]
 for layer,(c,(label,weight,t,rows)) in enumerate(zip(extraction['cases'],expected)):
  extent=rows*10*{12:144,13:176,23:136}[t]
  assert c['label']==label and c['rows']==rows and c['tensor_bytes']==extent
  f=c['files'];assert set(f)=={'input','output','weights'} and f['input']['bytes']==5120 and f['output']['bytes']==rows*2 and f['weights']['bytes']==extent
  cases.append(dict(layer=layer,label=label,weight=weight,type_id=t,rows=rows,columns=2560,fixtures=dict(input=f['input'],expected=f['output']),packed_weights=f['weights'],shard_identity=c['shard_identity']))
 schedule=[dict(warmup=warm,cycle=cycle,case=((cycle//2)+j)%3,order=['B','A'] if cycle%2 else ['A','B']) for warm,n in ((True,4),(False,24)) for cycle in range(n) for j in range(3)]
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
 parent=L/'hc-bf16-one-sg/micro';prior=json.loads((parent/'operating/evidence/device-a/review.json').read_text());assert prior['passed']
 for name in ('startup.hpp','handshake.py'):assert sha(P/name)==sha(parent/name),'qualified ACK source unchanged'
 cases,schedule=cases_schedule(extraction)
 files=[P/n for n in ('extract.py','runner.cpp','selected.hpp','startup.hpp','handshake.py','fixture_schema.hpp','fixed.hpp','build.py','source-pins.json','extraction-plan.json','evidence/extraction.json','evidence/independent-extraction-review.json','evidence/native-build.json')]+[Q/n for n in ('block.hpp','arithmetic.hpp','selection.hpp','selection.json','evidence/cpu-proof.json')]+[O/n for n in ('once.py','prepare.py','test_once.py','README.md','parent-pins.json','once.patch')]+[parent/'operating/evidence/device-a/review.json']
 manifest=dict(schema='gsq.dense-packed-block.native-micro-manifest.v1',cases=cases,schedule=schedule,authority={str(f):sha(f) for f in files},pairs=84,kernels=168,device_bytes=35331072,device_cap_bytes=64*1024**2,pinned_bytes=1048576,transfer_bytes=37764096,transfer_cap_bytes=64*1024**2,native_build_sha256=args.build_sha256,binary_sha256=args.binary_sha256,startup=dict(real_backend_before_ready=True,deadline_seconds=60,actual_native_target_fd_before_ack=True,positive_contact_and_ack_required=True),proof_scope='Three fixed dense Q4_K/Q5_K/IQ4_XS shapes; full saved BF16 exactness and isolated balanced AB/BA; no fullmodel throughput claim',native_admitted=False)
 with out.open('x') as f:f.write(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(dict(passed=True,manifest_sha256=sha(out),device_executed=False)))
if __name__=='__main__':main()
