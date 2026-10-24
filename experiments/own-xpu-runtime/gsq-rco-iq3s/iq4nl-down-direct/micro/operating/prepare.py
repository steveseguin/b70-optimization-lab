#!/usr/bin/env python3
"""Seal fixed1-case/28-pair schedule after extraction+build; no Device."""
import argparse,hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent;P=O.parent;Q=P.parent;L=Q.parent
BUILD_SHA='d1c5e5d02b674c7b2531559b721e35a7fa1322dcb21970e4b86840f239abb95e'
BINARY_SHA='dcd67040535733a8271191d6fe6feccee4e14eff30f8c13d76e52fd0db9fda5b'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--seal-manifest',action='store_true',required=True);a.parse_args();out=P/'manifest.json';assert not out.exists(),'exclusive manifest'
 extraction=json.loads((P/'evidence/extraction.json').read_text());review=json.loads((P/'evidence/independent-extraction-review.json').read_text());build=json.loads((P/'evidence/native-build.json').read_text());proof=json.loads((Q/'evidence/cpu-proof.json').read_text());startup=json.loads((P/'evidence/startup-tests.json').read_text())
 assert extraction['passed'] and not extraction.get('error') and review['passed'] and review['actual_extraction_receipt_sha256']==sha(P/'evidence/extraction.json')
 assert build['passed'] and sha(P/'evidence/native-build.json')==BUILD_SHA and build['binary_sha256']==BINARY_SHA
 assert proof['passed'] and proof['proof']['passed'] and startup['passed'] and startup['tests']==8
 assert len(extraction['cases'])==1 and sha(P/'fixed.hpp')==extraction['fixed_header_sha256']==review['fixed_header_sha256']
 for f,h in extraction['source_sha256'].items():assert sha(f)==h,f
 c=extraction['cases'][0];assert c['label']=='blk.0.expsdown' and c['weight']=='blk.0.ffn_down_exps.weight'
 f=c['files'];cases=[dict(layer=c['layer'],label=c['label'],weight=c['weight'],consumed_experts=c['consumed_experts'],fixtures=dict(input=f['input'],routes=f['routes'],expected=f['output'],status=f['status']),sparse_weights=f['slices'],shard_identity=c['shard_identity'])]
 schedule=[dict(warmup=warm,cycle=cycle,case=0,order=['B','A'] if cycle%2 else ['A','B']) for warm,n in ((True,4),(False,24)) for cycle in range(n)]
 files=[P/n for n in ('extract.py','runner.cpp','selected.hpp','startup.hpp','handshake.py','fixed.hpp','build.py','once.py','source-pins.json','extraction-plan.json','evidence/extraction.json','evidence/independent-extraction-review.json','evidence/native-build.json','evidence/startup-tests.json')]+[Q/n for n in ('direct.hpp','policy.hpp','selection.json','evidence/cpu-proof.json')]+[O/'prepare.py',O/'test_once.py',O/'README.md']
 manifest=dict(schema='gsq.iq4nl-direct.native-micro-manifest.v1',cases=cases,schedule=schedule,authority={str(f):sha(f) for f in files},pairs=28,kernels=56,device_bytes=471974600,device_cap_bytes=512*1024**2,pinned_bytes=1048576,transfer_bytes=474741560,transfer_cap_bytes=512*1024**2,native_build_sha256=BUILD_SHA,binary_sha256=BINARY_SHA,startup=dict(real_backend_before_ready=True,deadline_seconds=60,actual_native_target_fd_before_ack=True,positive_contact_and_ack_required=True),proof_scope='One fixed original layer0 IQ4_NLdown; exact fullsaved BF16/status and isolatedAB/BAevents; no fullmodel throughput claim',native_admitted=False)
 with out.open('x') as f:f.write(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(dict(passed=True,manifest_sha256=sha(out),device_executed=False)))
if __name__=='__main__':main()
