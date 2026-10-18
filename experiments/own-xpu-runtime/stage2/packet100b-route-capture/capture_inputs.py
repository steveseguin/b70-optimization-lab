"""Validate live capture receipts and construct a deterministic micro route set.

No synthetic fallback. All 64 tokens/all layers/both ranks remain in capture;
micro checkpoints 1/16/32/64 were fixed before seeing IDs or timing results.
"""
import hashlib,json,struct
from pathlib import Path
from capture_identity import P,ROOT,verify,verify_identity
from common import D,read,require,sha,save,compare_tokens
CAPTURE=P/'evidence/capture-B'
MANIFEST=P/'evidence/route-inputs.json'
ROUTES=P/'evidence/routes.bin'
CHECKPOINTS=(1,16,32,64)
RANK_BYTES=64*24*120

def validate_rank(raw,meta,rank,prompt,outputs):
 require(len(raw)==RANK_BYTES,'capture rank byte extent')
 require(meta.get('schema')=='packet100b.rank-routes.v1' and meta.get('diagnostic_only') is True,'rank schema')
 require(meta.get('rank')==rank and meta.get('bytes')==len(raw),'rank identity')
 require(hashlib.sha256(raw).hexdigest()==meta.get('sha256'),'rank bytes changed')
 expected=[dict(fixture=i+1,position=len(prompt)-1+i,input_token=prompt[-1] if i==0 else outputs[i-1]) for i in range(64)]
 require(meta.get('steps')==expected,'accepted target step identity changed')
 rows=[]
 for step in range(64):
  for local in range(24):
   offset=(step*24+local)*120;chunk=raw[offset:offset+120]
   routes=list(struct.iter_unpack('<III',chunk))
   require(all(e<512 and begin==0 and count==2560 for e,begin,count in routes),'invalid full DOWN routes')
   require(len({e for e,_,_ in routes})==10,'router must select ten distinct experts')
   rows.append(dict(fixture=step+1,rank=rank,layer=rank*24+local,offset=offset,
                    sha256=hashlib.sha256(chunk).hexdigest()))
 return rows

def measured():
 verify()
 require(CAPTURE.is_dir(),'real route capture pending')
 window=read(CAPTURE/'window.json');coord=read(CAPTURE/'lane-coordination.json')
 require(window.get('schema')=='packet100b.capture-window.v1' and window.get('diagnostic_only') is True,'capture window schema')
 require(all(window.get(k) is True for k in ('passed','device_executed','device_complete','lease_released')),
         'capture needs clean released device window')
 require(window.get('child_still_running') is False and not window.get('stop_reasons') and not window.get('child_retained'),'capture failed or retained')
 require(coord.get('passed') is True and coord.get('released_before_report') is True,'capture lease release unproved')
 require(read(CAPTURE/'run/teardown.json').get('drained') is True,'capture ranks not drained')
 identity=read(CAPTURE/'identity.json');verify_identity(identity)
 require(window['identity']==identity,'window identity differs')
 for name,digest in window['files'].items():require(sha(CAPTURE/name)==digest,'capture file changed: '+name)
 report=read(CAPTURE/'run/report-inputs.json')
 require(report.get('passed') is True and report.get('device_isolation',{}).get('passed') is True and report.get('lane')=='B','capture proof incomplete')
 entries=read(P/'suite.snapshot.json')['prompts']
 admission=read(CAPTURE/'run/input-admission.json')
 require(admission.get('passed') is True and admission.get('one_model_plan_identity') is True,'model input admission missing')
 require([r['input_bundle_hashes'] for r in admission['inputs']]==[e['input_bundle_hashes'] for e in entries],'model input identity changed')
 require([r['prompt_id'] for r in report['requests']]==[e['prompt_id'] for e in entries],'wrong capture prompts/order')
 sources={};all_rows=[];sample_rows=[];packed=bytearray()
 def bind(path):sources[str(path.relative_to(ROOT))]=sha(path)
 for f in ('window.json','identity.json','lane-coordination.json','run/report-inputs.json','run/teardown.json','run/input-admission.json'):bind(CAPTURE/f)
 for entry,reported in zip(entries,report['requests']):
  name=entry['prompt_id'];dest=CAPTURE/'run'/name
  result=read(dest/'receipt.json');bind(dest/'receipt.json')
  require(result==reported,'request receipt/report mismatch')
  require(result.get('passed') is True and result.get('exact_oracle') is True,'exact output required')
  prompt_path=ROOT/entry['input_bundle']/'tokens.txt'
  require(sha(prompt_path)==entry['input_bundle_hashes']['tokens.txt'],'prompt changed')
  prompt=list(map(int,prompt_path.read_text().split()));bind(prompt_path)
  oracle=ROOT/entry['oracle_directory']
  require(sha(oracle/'receipt.json')==entry['oracle_receipt_sha256'],'oracle receipt changed')
  expected=D.CHECK.token_record(oracle);compare_tokens(result['tokens'],expected,64,name)
  require(sha(oracle/'result.json')==read(oracle/'receipt.json')['result_sha256'],'oracle output changed')
  require(result['binary_sha256']==identity['binary_sha256'] and result['prompt_token_sha256']==D.token_hash(prompt),'request model/prompt identity')
  bind(oracle/'receipt.json')
  bind(oracle/'result.json')
  for rank in (0,1):
   binary=dest/f'rank{rank}/routes.bin';meta=dest/f'rank{rank}/routes.json'
   raw=binary.read_bytes();rows=validate_rank(raw,read(meta),rank,prompt,result['tokens'])
   bind(binary);bind(meta)
   for row in rows:
    row.update(prompt_id=name,path=str(binary.relative_to(ROOT)))
    all_rows.append(row)
    if row['fixture'] in CHECKPOINTS:
     selected=dict(row,micro_offset=len(packed));sample_rows.append(selected)
     packed.extend(raw[row['offset']:row['offset']+120])
 require(len(all_rows)==6144 and len(sample_rows)==384,'complete capture strata required')
 require(sum(f.stat().st_size for f in CAPTURE.rglob('*') if f.is_file())<=50_000_000,'capture exceeds disk budget')
 for path in (P/'packet-seal.json',P/'suite.snapshot.json',P/'selection.json',P/'capture_inputs.py'):bind(path)
 manifest=dict(schema='packet100b.real-routes.v1',passed=True,ready=True,diagnostic_only=True,
  device_executed=True,source='normal packet97 record-line engine; head=production; exact oracle outputs',
  model_inputs=admission['inputs'],selection=read(P/'selection.json'),
  target_down=dict(rows=2560,columns=640,experts=512,selected=10,route_stride_bytes=12),
  exact_requests=2,tokens_per_request=64,all_route_vectors=6144,micro_route_vectors=384,
  micro_checkpoint_fixtures=list(CHECKPOINTS),rows=all_rows,micro_rows=sample_rows,
  route_bytes_sha256=hashlib.sha256(packed).hexdigest(),sources=sources,
  routing_weights='not consumed by DOWN; weights belong to the following ordered mixture',
  no_speed_claim=True)
 return manifest,bytes(packed)

def materialize():
 row,raw=measured()
 require(not MANIFEST.exists() and not ROUTES.exists(),'fresh route outputs required')
 ROUTES.write_bytes(raw);save(MANIFEST,row)
 return row

def require_ready():
 require(MANIFEST.is_file() and ROUTES.is_file(),'real route capture pending')
 row,raw=measured()
 require(read(MANIFEST)==row and ROUTES.read_bytes()==raw,'capture qualification binding changed')
 return row

if __name__=='__main__':
 from build_engine import limits
 limits();print(json.dumps({k:v for k,v in require_ready().items() if k not in ('rows','micro_rows','sources')},indent=2))
