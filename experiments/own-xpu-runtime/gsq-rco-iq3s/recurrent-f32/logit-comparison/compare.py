#!/usr/bin/env python3
"""Fixed closed-run comparison. Default validates metadata only; root alone uses --read-ranges."""
import argparse, contextlib, hashlib, json, math, os, re, stat, struct
from pathlib import Path
P=Path(__file__).resolve().parent
L=P.parents[1]
E=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-b')
REL='prompt-00-none/rank1/state-2147483647'
NATIVE_REVIEW=L/'recurrent-f32/operating/launch-b/evidence/device-b/review.json'
REFERENCE=L/'reference-cpu/runtime-b/evidence'
PINS={
 str(NATIVE_REVIEW):'08b09b122647c553c4d71c2050cdca6f5f223c613fc88af4a8046ebeddb4e1c3',
 str(REFERENCE/'closed-readback-review.json'):'c028ff21c0c32af97a752fa49db65c1b6463bc3ee2bde104a01ee24cbfc66a7b',
 str(REFERENCE/'actual/request.json'):'d6fe9f8fc8a63e923ef4d4cc6d872c6ae6d1f15c29ff0b7abd596852f4cbfd77',
 str(REFERENCE/'actual/response.json'):'43440c3c22f629cec44b802b6436a6fbb81ac1272be980712468ce3c8d930bdc',
 str(E/'f32-correctness.json'):'6349b64c0706789aa8ccfba2a22d17b6d66fb47bf882a1c2667282f647b4edd6',
}
RANGES={'logits.bin':496640,'position.bin':4,'token.bin':4,'next_token.bin':4}
FILES={'state.bundle','state-index.tsv','state.json','state-seal.txt'}
def require(v,m):
 if not v:raise ValueError(m)
def digest(b):return hashlib.sha256(b).hexdigest()
def unique(pairs):
 d={}
 for k,v in pairs:
  require(k not in d,'duplicate JSON key');d[k]=v
 return d
def loads(b):return json.loads(b,object_pairs_hook=unique)
def stamp(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def small(path,expected):
 require(path.resolve()==path,'canonical metadata path')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  s=os.fstat(fd);require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=16*1024*1024,'bounded metadata')
  b=b''
  while len(b)<s.st_size:
   c=os.read(fd,min(65536,s.st_size-len(b)));require(c,'metadata truncated');b+=c
  require(stamp(s)==stamp(os.fstat(fd))==stamp(os.stat(path,follow_symlinks=False)),'metadata changed')
  require(digest(b)==expected,'metadata SHA '+str(path));return loads(b)
 finally:os.close(fd)
def alignment(result,prompt,reference):
 tokens=result['tokens'];require(len(prompt)==87 and len(tokens)==32 and tokens==reference['tokens'],'same 87/32 prefix')
 require(reference['tokens_evaluated']==87,'reference input count')
 require(all(type(t)is int and 0<=t<248320 for t in prompt+tokens),'token IDs')
 expected=list(enumerate(prompt+tokens[:-1]));trace=result['rank_trace']
 r1=sorted((x for x in trace if x['rank']==1 and x['op']==1),key=lambda x:x['position'])
 require([(x['position'],x['token']) for x in r1]==expected,'rank1 exact consumed prefix')
 pending=None;accepted=[]
 for r in sorted((x for x in trace if x['rank']==0),key=lambda x:x['rank_received']):
  if r['op']==1:pending=r
  elif r['op']==3:pending=None
  elif r['op']==2:
   require(pending is not None,'accept without half');accepted.append((pending['position'],pending['token']));pending=None
 require(accepted==expected and pending is None,'rank0 exact accepted prefix')
 rows=reference['completion_probabilities'];require(len(rows)==32 and [x['id'] for x in rows]==tokens,'reference probability rows')
 return {'input_tokens':87,'generated_tokens':32,'consumed_tokens':118,'last_evaluated_position_zero_based':117,'committed_position':118,'last_consumed_token':tokens[-2],'selected_token':tokens[-1],'conditional_prefix_ids':prompt+tokens[:-1]}
def authority():
 data={p:small(Path(p),h) for p,h in PINS.items()}
 nr=data[str(NATIVE_REVIEW)];rr=data[str(REFERENCE/'closed-readback-review.json')]
 require(nr['passed'] and nr['corrected_target_mtp_exact'] and nr['reference32_equal'] and nr['physical_drain'] and nr['kernel_fault_baseline_unchanged'],'closed native authority')
 require(rr['evidence_review_passed'] and rr['independent_effective_request_validation_passed'] and rr['safe_exit'],'closed CPU authority')
 require(nr['reference_review_sha256']==PINS[str(REFERENCE/'closed-readback-review.json')],'reference join')
 req=data[str(REFERENCE/'actual/request.json')];resp=data[str(REFERENCE/'actual/response.json')]
 require(resp['status']==200 and req['post_sampling_probs'] is False and req['n_probs']==32 and req['return_tokens'] and req['cache_prompt'] is False,'raw-ID pre-sampling request')
 ref=resp['response'];require(ref['generation_settings']['post_sampling_probs'] is False,'reported pre-sampling probabilities')
 full=data[str(E/'f32-correctness.json')];require(full['passed'] and full['corrected_target_mtp_exact'],'full result')
 row=full['rows'][0];require(row['name']=='prompt-00-none' and row['mode']=='none','target-only selected arm')
 align=alignment(row['result'],req['prompt'],ref)
 require(rr['output_tokens']==row['result']['tokens']==nr['arms'][0]['tokens'],'review output joins')
 capture=[c for c in nr['captures'] if c['path']==REL];require(len(capture)==1,'one audited capture')
 return align,ref['completion_probabilities'][-1],capture[0],full['capture_snapshots'][0]['1'],row['state_sha256']['1']
def number(s):
 require(re.fullmatch('0|[1-9][0-9]*',s) is not None,'canonical nonnegative integer');return int(s)
def parse_metadata(index,state,seal,size,physical,logical):
 require(digest(index)==physical['state-index.tsv'] and digest(state)==physical['state.json'] and digest(seal)==physical['state-seal.txt'],'audited metadata digests')
 lines=seal.decode('ascii').splitlines();require(len(lines)==5 and lines[0]=='GSQ_STATE_SEAL_V1' and seal.endswith(b'\n'),'seal format')
 require(number(lines[1])==size and lines[2]==physical['state.bundle'] and lines[3]==digest(index) and lines[4]==digest(state),'audited whole-bundle seal')
 obj=loads(state);names={}
 for k,h in obj['buffers'].items():
  name=('alternate-'+k.split(':',1)[1] if k.startswith('alternate:') else k)+'.bin'
  require(name not in names,'name collision');names[name]=h
 require(names=={k:v for k,v in logical.items() if k!='state.json'} and logical['state.json']==digest(state),'full logical map')
 rows=index.decode('ascii').splitlines();require(index.endswith(b'\n') and rows[0]=='GSQ_STATE_BUNDLE_V1','index format')
 out={};offset=0
 for line in rows[1:]:
  p=line.split('\t');require(len(p)==4,'index columns');name,start,length,h=p
  start=number(start);length=number(length)
  require(name in names and name not in out and h==names[name] and re.fullmatch('[0-9a-f]{64}',h),'indexed name/hash')
  require(start==offset and 0<length<=size-offset,'contiguous bounded index')
  out[name]={'offset':start,'bytes':length,'sha256':h};offset+=length
 require(offset==size and set(out)==set(names),'complete index')
 require(all(out[n]['bytes']==z for n,z in RANGES.items()),'fixed requested extents')
 return out
@contextlib.contextmanager
def held_capture(capture,snapshots,logical):
 path=E/REL;require(path.resolve()==path,'canonical capture directory')
 d=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);ds=os.fstat(d);fds={};st={}
 try:
  require(set(os.listdir(d))==FILES,'exact four sealed files')
  for n in sorted(FILES):
   fd=os.open(n,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=d);fds[n]=fd;s=os.fstat(fd);st[n]=s
   require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and stamp(s)==snapshots[n],'audited held identity '+n)
  def meta(n):
   size=st[n].st_size;require(size<=1024*1024,'bounded bundle metadata');b=os.pread(fds[n],size,0);require(len(b)==size,'metadata shortread');return b
  rows=parse_metadata(meta('state-index.tsv'),meta('state.json'),meta('state-seal.txt'),st['state.bundle'].st_size,capture['physical_sha256'],logical)
  yield fds['state.bundle'],rows
  for n,f in fds.items():require(stamp(st[n])==stamp(os.fstat(f))==stamp(os.stat(n,dir_fd=d,follow_symlinks=False)),'capture changed '+n)
  z=os.stat(path,follow_symlinks=False);require((z.st_dev,z.st_ino)==(ds.st_dev,ds.st_ino) and set(os.listdir(d))==FILES,'capture directory changed')
 finally:
  for f in fds.values():os.close(f)
  os.close(d)
def read_range(fd,row):
 b=os.pread(fd,row['bytes'],row['offset']);require(len(b)==row['bytes'] and digest(b)==row['sha256'],'range byte integrity');return b
def bf16(b):
 require(len(b)%2==0,'BF16 byte extent');return [struct.unpack('<f',struct.pack('<I',x<<16))[0] for (x,) in struct.iter_unpack('<H',b)]
def compare(logits,ref):
 require(logits and all(math.isfinite(x) for x in logits),'finite native full logits')
 top=ref['top_logprobs'];ids=[x['id'] for x in top]
 require(0<len(ids)<=len(logits) and len(set(ids))==len(ids) and all(type(i)is int and 0<=i<len(logits) for i in ids),'reference IDs')
 require(all(type(x['logprob']) in (int,float) and math.isfinite(x['logprob']) for x in top),'finite reference top logprobs')
 require(all(a['logprob']>=b['logprob'] for a,b in zip(top,top[1:])),'reference descending rank')
 require(ref['id'] in ids and math.isfinite(ref['logprob']),'selected reference row')
 maximum=max(logits);logden=math.log(math.fsum(math.exp(x-maximum) for x in logits))
 lp=[(x-maximum)-logden for x in logits];order=sorted(range(len(logits)),key=lambda i:(-logits[i],i));rank={t:i+1 for i,t in enumerate(order)}
 records=[]
 for i,r in enumerate(top):
  t=r['id'];greater=sum(x>logits[t] for x in logits);equal=sum(x==logits[t] for x in logits)
  records.append(dict(token_id=t,reference_retained_rank=i+1,native_rank_tie_break_low_id=rank[t],native_tie_rank_interval=[greater+1,greater+equal],native_logit=logits[t],native_logprob=lp[t],reference_logprob=r['logprob'],native_minus_reference_logprob=lp[t]-r['logprob']))
 delta=[abs(x['native_minus_reference_logprob']) for x in records];t=ref['id']
 return dict(native_argmax=order[0],reference_selected=t,argmax_agrees=order[0]==t,selected_native_logprob=lp[t],selected_reference_logprob=ref['logprob'],selected_logprob_delta=lp[t]-ref['logprob'],native_top32=[{'token_id':i,'logit':logits[i],'logprob':lp[i]} for i in order[:32]],reference_top_rows=records,topk_overlap={str(k):len(set(order[:k])&set(ids[:k])) for k in (1,5,10,32) if k<=len(ids)},retained_top_mean_abs_logprob_delta=math.fsum(delta)/len(delta),retained_top_max_abs_logprob_delta=max(delta),normalization='float64 max-shift + math.fsum over every native BF16 logit; descriptive analysis, not reference FP32 softmax reproduction')
def run(read_ranges=False):
 align,ref,capture,snapshots,logical=authority()
 with held_capture(capture,snapshots,logical) as (fd,rows):
  result={'schema':'gsq.same-prefix-logits.v1','passed':False,'metadata_only':not read_ranges,'source_sha256':digest(Path(__file__).read_bytes()),'authority_sha256':PINS,'alignment':align,'ranges':{n:rows[n] for n in RANGES},'maximum_payload_read_bytes':sum(RANGES.values()),'payload_bytes_read':0,'native_whole_bundle_rehashed':False,'whole_bundle_authority':'prior independent full streamed readback + unchanged closed FD/path stamps + seal; this helper only hashes four named ranges','quality_qualified':False}
  if read_ranges:
   data={n:read_range(fd,rows[n]) for n in RANGES};result['payload_bytes_read']=sum(map(len,data.values()))
   expected={'position.bin':118,'token.bin':align['last_consumed_token'],'next_token.bin':align['selected_token']}
   actual={n:struct.unpack('<I',data[n])[0] for n in expected};require(actual==expected,'actual stored conditional prefix counters')
   require(len(ref['top_logprobs'])==32,'32 reference candidates');result['stored_context']=actual;result['comparison']=compare(bf16(data['logits.bin']),ref)
   result['limitations']=['One final position for one shared 118-token conditional prefix, not broad quality certification.','Reference retains only top32 probabilities; no full-reference logits, KL, or full-distribution equality claim.','Native logits are BF16; reference logits/softmax and reported logarithms are FP32. Different arithmetic orders and rounding preclude an assumed bitwise numerical oracle.','No acceptance threshold is invented; passed means alignment/readback/comparison completed, even if argmax or distributions differ.','Original CPU runtime terminal remains failed from the separately audited postresponse validator bug.']
 result['passed']=True;return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--read-ranges',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 # Reserve exclusive receipt before any artifact access; failures never overwrite evidence.
 with a.output.open('x') as f:
  try:out=run(a.read_ranges)
  except BaseException as e:out={'passed':False,'source_sha256':digest(Path(__file__).read_bytes()),'error':repr(e)};json.dump(out,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());raise
  json.dump(out,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
