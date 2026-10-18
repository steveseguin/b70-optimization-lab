"""Exact CPU router replay on real accepted captures; no synthetic fallback."""
import argparse,ctypes,gzip,hashlib,json,os,resource,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,r):
 raw=(json.dumps(r,indent=2,allow_nan=False)+'\n').encode()
 Path(p).write_bytes(gzip.compress(raw,mtime=0) if str(p).endswith('.gz') else raw)

def library(name='gnu'):
 row=json.loads((P/'evidence/replay-build.json').read_text())
 for p,h in row['sources'].items():assert sha(ROOT/p)==h,p
 entry=next(e for e in row['libraries'] if e['compiler']==name);path=ROOT/entry['path'];assert sha(path)==entry['sha256']
 lib=ctypes.CDLL(str(path));ptr=ctypes.c_void_p
 lib.p138_router.argtypes=[ptr,ptr,ctypes.c_uint,ptr,ptr];lib.p138_router.restype=ctypes.c_int
 for f in ('p138_rank','p138_production_rank10'):
  getattr(lib,f).argtypes=[ptr,ptr];getattr(lib,f).restype=ctypes.c_int
 return lib

def run_router(lib,weights,inputs):
 from array import array
 count=len(inputs)//2560;assert count*2560==len(inputs) and inputs.typecode=='H' and weights.typecode=='f'
 logits=array('H',[0])*(count*512);ids=array('I',[0])*(count*16)
 assert lib.p138_router(weights.buffer_info()[0],inputs.buffer_info()[0],count,logits.buffer_info()[0],ids.buffer_info()[0])==0,'nonfinite router inputs/results'
 return logits,ids

def chunks(values,n):return [list(values[i:i+n]) for i in range(0,len(values),n)]

class Weights:
 """Header-validated small tensor reads; never mmap or load the full model."""
 def __init__(self):
  sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/stage1/packet1b'))
  from loaders.headers import gguf_header
  assert sys.byteorder=='little'
  base=P/'inputs/incident-retrospective';self.model=Path(json.loads((base/'input.json').read_text())['model_dir'])
  self.stat={};self.tensors={};self.receipts=[];self.header_receipts=[]
  for line in (base/'identity.tsv').read_text().splitlines():
   name,*numbers=line.split();path=self.model/name;s=path.stat();actual=(s.st_size,s.st_dev,s.st_ino,s.st_mtime_ns,s.st_ctime_ns)
   assert actual==tuple(map(int,numbers)),'GGUF file identity changed';self.stat[name]=actual
   with path.open('rb') as f:h=gguf_header(f,s.st_size)
   with path.open('rb') as f:raw=f.read(h['header_bytes_read'])
   self.header_receipts.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),identity=list(actual)))
   for key,t in h['tensors'].items():
    if key.endswith('.ffn_gate_inp.weight') or any(key.endswith('.ffn_'+part+'_exps.weight') for part in ('gate','up','down')):
     assert key not in self.tensors;self.tensors[key]=(name,t)
  self.plan={}
  for line in (base/'plan.tsv').read_text().splitlines():
   fields=line.split()
   if len(fields)>6:self.plan[fields[1]]=fields
  for key,(name,t) in self.tensors.items():
   r=self.plan[key];assert r[0]==name and int(r[3])==t['type_id'] and int(r[4])==t['data_offset'] and int(r[5])==t['bytes'],'GGUF vs native plan differs'
 def router(self,layer):
  from array import array
  key=f'blk.{layer}.ffn_gate_inp.weight';name,t=self.tensors[key];assert t['type']=='F32' and t['shape']==[512,2560]
  path=self.model/name;s=path.stat();assert (s.st_size,s.st_dev,s.st_ino,s.st_mtime_ns,s.st_ctime_ns)==self.stat[name]
  with path.open('rb') as f:f.seek(t['file_offsets'][0]);raw=f.read(t['bytes'])
  assert len(raw)==512*2560*4
  after=path.stat();assert (after.st_size,after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns)==self.stat[name]
  self.receipts.append(dict(layer=layer,tensor=key,file=str(path),offset=t['file_offsets'][0],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
  weights=array('f');weights.frombytes(raw);return weights
 def sizes(self):
  result=[]
  for layer in range(48):
   parts={part:self.tensors[f'blk.{layer}.ffn_{part}_exps.weight'][1]['bytes']//512 for part in ('gate','up','down')}
   assert all(self.tensors[f'blk.{layer}.ffn_{part}_exps.weight'][1]['shape'][0]==512 for part in parts)
   result.append(dict(layer=layer,parts=parts,bytes=sum(parts.values())))
  return result

PREDICTORS=('router_input','residual_stream0','residual_stream1','residual_stream2','residual_stream3')
def main(args):
 import mmap
 from array import array
 from capture_inputs import require_ready,STRIDE
 from build_engine import limits
 limits()
 if not (P/'evidence/capture-inputs.json').exists():
  save(P/'evidence/analysis-status.json',dict(passed=False,status='pending_real_capture',recall=None,projected_tok_s=None,phase2_decision='pending',device_executed=False))
  print('Real capture pending; no recall or gain invented.');return
 capture=require_ready();suite=json.loads((P/'suite.snapshot.json').read_text());entries=[e for e in suite['prompts'] if e['analysis_included']]
 maps={}
 for row in capture['rows']:
  if row['analysis_included']:
   with (ROOT/row['path']).open('rb') as f:maps[row['prompt_id'],row['rank']]=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 def field(name,layer,offset,count,dtype):
  result=array(dtype);raw=maps[name,layer//24]
  for token in range(48):
   begin=(token*24+layer%24)*STRIDE+offset
   result.frombytes(raw[begin:begin+count*result.itemsize])
  return result
 def combined(layer,offset,count,kind):
  result=array(kind)
  for e in entries:result.extend(field(e['prompt_id'],layer,offset,count,kind))
  return result
 weights=Weights();lib=library();prediction_rows=[];recalls=[];oracle=[]
 start=time.monotonic()
 for layer in range(48):
  w=weights.router(layer)
  actual_inputs=combined(layer,120,2560,'H')
  actual_logits=combined(layer,25720,512,'H')
  actual_routes=chunks(combined(layer,0,30,'I')[::3],10)
  computed,ids=run_router(lib,w,actual_inputs)
  logit_errors=sum(a!=b for a,b in zip(computed,actual_logits));route_errors=sum(a!=b for x,y in zip(chunks(ids,16),actual_routes) for a,b in zip(x[:10],y))
  oracle.append(dict(layer=layer,rows=len(computed)//512,logit_bit_mismatches=logit_errors,route_id_mismatches=route_errors))
  save(P/'evidence/router-oracle-progress.json',dict(passed=False,pending=True,layers=oracle))
  if logit_errors or route_errors:
   save(P/'evidence/analysis-status.json',dict(passed=False,status='exact_router_replay_failed',layer=layer,logit_bit_mismatches=logit_errors,route_id_mismatches=route_errors,phase2_decision='blocked_exactness'))
   raise ValueError(f'exact same-layer router replay failed at layer {layer}')
  if layer:
   for predictor in PREDICTORS:
    offset=120 if predictor=='router_input' else 5240+int(predictor[-1])*5120
    inputs=combined(layer-1,offset,2560,'H')
    _,flat=run_router(lib,w,inputs);predicted=chunks(flat,16)
    for index,e in enumerate(entries):
     lo=index*48;truth=actual_routes[lo:lo+48];guess=predicted[lo:lo+48]
     for k in (10,12,16):
      hits=[len(set(map(int,a))&set(map(int,b[:k]))) for a,b in zip(truth,guess)]
      recalls.append(dict(prompt_id=e['prompt_id'],category=e['category'],target_layer=layer,predictor=predictor,k=k,matched_experts=sum(hits),target_experts=480,recall=sum(hits)/480))
     prediction_rows.append(dict(prompt_id=e['prompt_id'],target_layer=layer,predictor=predictor,ids=guess))
  print('exact router + predictions layer',layer,'of 47; elapsed',round(time.monotonic()-start,1),flush=True)
 truth={}
 for e in entries:
  layers=[chunks(field(e['prompt_id'],layer,0,30,'I')[::3],10) for layer in range(48)]
  truth[e['prompt_id']]=[[layers[layer][token] for layer in range(48)] for token in range(48)]
 by_predictor=[]
 for pred in PREDICTORS:
  for k in (10,12,16):
   group=[r for r in recalls if r['predictor']==pred and r['k']==k]
   by_predictor.append(dict(predictor=pred,k=k,recall=sum(r['matched_experts'] for r in group)/sum(r['target_experts'] for r in group)))
 result=dict(passed=True,device_executed=False,diagnostic_only=True,exact_same_layer=True,oracle=oracle,predictors=by_predictor,per_prompt_layer=recalls,
  weights=weights.receipts,headers=weights.header_receipts,expert_sizes=weights.sizes(),capture_manifest_sha256=sha(P/'evidence/capture-inputs.json'),elapsed_seconds=time.monotonic()-start)
 save(P/'evidence/router-replay.json.gz',result)
 save(P/'evidence/predictions.json.gz',dict(passed=True,capture_manifest_sha256=result['capture_manifest_sha256'],router_replay_sha256=sha(P/'evidence/router-replay.json.gz'),truth=truth,rows=prediction_rows))
 save(P/'evidence/analysis-status.json',dict(passed=True,status='exact_replay_complete',exact_same_layer=True,predictors=by_predictor,phase2_decision='pending_cache_projection',router_replay_sha256=sha(P/'evidence/router-replay.json.gz')))
 for raw in maps.values():raw.close()
 print(json.dumps(by_predictor,indent=2))
if __name__=='__main__':
 os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='4'
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 ap=argparse.ArgumentParser();args=ap.parse_args();main(args)
