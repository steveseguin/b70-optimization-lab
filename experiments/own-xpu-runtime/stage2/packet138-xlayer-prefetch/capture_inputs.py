"""Validate a real, drained capture; no synthetic or missing-data fallback."""
import hashlib,json,struct
from pathlib import Path
from shared_oracle import P,ROOT,sha,read
STEPS=48;LAYERS=24;STRIDE=26744;RANK_BYTES=STEPS*LAYERS*STRIDE
CAPTURE=P/'evidence/capture-B';MANIFEST=P/'evidence/capture-inputs.json'
def require(v,s):
 if not v:raise ValueError(s)
def validate_rank(raw,meta,rank,prompt,outputs):
 require(len(raw)==RANK_BYTES,'capture rank byte extent')
 require(meta.get('schema')=='packet138.rank-capture.v1' and meta.get('diagnostic_only') is True,'rank schema')
 require(meta.get('rank')==rank and meta.get('bytes')==len(raw) and meta.get('stride')==STRIDE,'rank/stride identity')
 require(hashlib.sha256(raw).hexdigest()==meta.get('sha256'),'rank bytes changed')
 expected=[dict(fixture=i+1,position=len(prompt)-1+i,input_token=prompt[-1] if i==0 else outputs[i-1]) for i in range(STEPS)]
 require(meta.get('steps')==expected,'accepted target identity changed')
 for i in range(STEPS*LAYERS):
  routes=list(struct.iter_unpack('<III',raw[i*STRIDE:i*STRIDE+120]))
  require(all(e<512 and begin==0 and n==2560 for e,begin,n in routes),'invalid routes')
  require(len({e for e,_,_ in routes})==10,'duplicate route')
 return STEPS*LAYERS

def measured():
 from capture_identity import verify,verify_identity
 from input_gate import validate_manifest
 verify();require(CAPTURE.is_dir(),'real capture pending')
 w=read(CAPTURE/'window.json');coord=read(CAPTURE/'lane-coordination.json')
 require(w.get('schema')=='packet138.capture-window.v1','window schema')
 require(all(w.get(k) is True for k in ('passed','device_executed','device_complete','lease_released')),'clean released window required')
 require(w.get('child_still_running') is False and not w.get('child_retained') and not w.get('stop_reasons'),'failed/retained window')
 require(coord.get('passed') is True and coord.get('released_before_report') is True,'release missing')
 require(read(CAPTURE/'run/teardown.json').get('drained') is True,'drain missing')
 identity=read(CAPTURE/'identity.json');verify_identity(identity);require(w['identity']==identity,'identity changed')
 for name,digest in w['files'].items():require(sha(CAPTURE/name)==digest,'capture file changed: '+name)
 suite=validate_manifest(read(P/'suite.snapshot.json'));report=read(CAPTURE/'run/report-inputs.json')
 require(report.get('passed') is True and report.get('device_isolation',{}).get('passed') is True and report.get('lane')=='B','isolation missing')
 require([r['prompt_id'] for r in report['requests']]==[e['prompt_id'] for e in suite['prompts']],'prompt coverage')
 rows=[];sources={}
 for name in ('window.json','identity.json','lane-coordination.json','run/report-inputs.json','run/teardown.json'):
  sources[str((CAPTURE/name).relative_to(ROOT))]=sha(CAPTURE/name)
 for e,reported in zip(suite['prompts'],report['requests']):
  dest=CAPTURE/'run'/e['prompt_id'];result=read(dest/'receipt.json')
  require(result==reported and result.get('passed') is True and result.get('exact_reference') is True,'request exactness')
  require(result['tokens']==e['expected_tokens'],'every-token reference mismatch')
  require(result['exact_oracle']==(e['split']=='sanity') and result['analysis_included']==e['analysis_included'],'reference scope')
  prompt=list(map(int,(ROOT/e['input_bundle']/'tokens.txt').read_text().split()))
  for rank in (0,1):
   binary=dest/f'rank{rank}/capture.bin';meta=dest/f'rank{rank}/capture.json'
   count=validate_rank(binary.read_bytes(),read(meta),rank,prompt,result['tokens'])
   rows.append(dict(prompt_id=e['prompt_id'],category=e['category'],analysis_included=e['analysis_included'],rank=rank,vectors=count,path=str(binary.relative_to(ROOT)),sha256=sha(binary),metadata=str(meta.relative_to(ROOT))))
   for f in (binary,meta,dest/'receipt.json'):sources[str(f.relative_to(ROOT))]=sha(f)
 require(sum(f.stat().st_size for f in CAPTURE.rglob('*') if f.is_file())<=1_000_000_000,'capture exceeds 1 GB')
 return dict(schema='packet138.real-capture.v1',passed=True,device_executed=True,diagnostic_only=True,arithmetic='iq3-p49-split32-v1',
  rows=rows,sources=sources,exact_reference_requests=13,cpu_oracle_requests=1,analysis_requests=12,tokens_per_request=48,
  record=dict(stride=STRIDE,routes=[0,120],router_input_bf16=[120,5120],output_streams_bf16=[5240,20480],router_logits_bf16=[25720,1024]),no_speed_claim=True)
def materialize():
 row=measured();require(not MANIFEST.exists(),'fresh manifest required');MANIFEST.write_text(json.dumps(row,indent=2)+'\n');return row
def require_ready():
 require(MANIFEST.exists(),'real capture pending');row=measured();require(read(MANIFEST)==row,'capture manifest changed');return row
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 print(json.dumps(require_ready(),indent=2))
