#!/usr/bin/env python3
"""Seven fixed-prefix observations, one guarded target-only lifetime; no oracle decisions."""
import argparse,hashlib,importlib.util,json,struct,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('remaining_tie_parent',HERE.parent/'native.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
R,C,BASE=P.R,P.C,P.BASE
ROOT=C.ROOT
READER=ROOT/'gsq-rco-iq3s/state-bundle/reader.py'
spec=importlib.util.spec_from_file_location('remaining_sealed_reader',READER);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
REG=HERE/'cases.json';CACHE_PROOF=HERE/'cache-source-proof.json';SENTINEL=2147483647
BINARY='42458c9016fc7e6b62c9f175278d52ecaa6c3a1316a5030a3fcb10fd9fc1425a'

def cases():
 data=json.loads(REG.read_text());result=[]
 for row in data['cases']:
  source=ROOT/row['input'];cpu=ROOT/row['cpu_rows']
  BASE.require(BASE.digest(source)==row['input_sha256'] and BASE.digest(cpu)==row['cpu_rows_sha256'],'fixed saved source authority')
  tokens=json.loads(source.read_text())['tokens'][:row['prefix_tokens']]
  BASE.require(len(tokens)==row['prefix_tokens'] and hashlib.sha256(struct.pack('<'+'i'*len(tokens),*tokens)).hexdigest()==row['prefix_le_i32_sha256'],'exact forced prefix')
  references=[json.loads(x)for x in cpu.read_text().splitlines()];reference=next(x for x in references if x['position']==len(tokens)-1)
  BASE.require(reference['argmax']==row['saved_cpu_argmax'],'posthoc CPU row identity')
  result.append(dict(row,prompt=tokens))
 BASE.require(len(result)==7 and result[0]['prompt']==result[-1]['prompt'],'registered A/B/.../A sequence')
 return result

def make_plan(config):
 p=P.make_plan(config)
 BASE.require(p['binary_sha256']==BINARY and p['reference_tie_diagnostic'] is True,'registered current tie treatment')
 registered=cases();BASE.require(p['prompt_tokens']==registered[0]['prompt'],'first244 authority')
 p.update(schema='ownrt.router-tie.remaining-seven.v1',requests=7,case_registration=str(REG),case_registration_sha256=BASE.digest(REG),diagnostic_only=True,speed_claim=False,expected_output_ids=None,
  evidence_forecast_bytes=6*1024**3,limits='Seven target-only historical fixed-prefix observations in one lifetime, real OP11 resets. CPU expected tokens posthoc only. No current free-running or whole-suite fidelity claim.')
 proof=json.loads(CACHE_PROOF.read_text())
 BASE.require(hashlib.sha256(proof['admit_position_function'].encode()).hexdigest()==proof['admit_position_function_sha256'],'exact source function proof')
 BASE.require(proof['admit_position_function'] in (ROOT/'engine/src/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp').read_text() and proof['half_callsite'] in (ROOT/'engine/src/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp').read_text(),'actual pre-HALF cache rebind source')
 BASE.require(proof['allowed_inventory_fields']==['launch_extent','alternate_launch_extent'],'exact two source-proven cache fields')
 for name,h in proof['source_files'].items():
  f=ROOT/name;BASE.require(BASE.digest(f)==h,'cache rebind source proof changed');p['pins'][str(f)]=h
 for f in [Path(__file__).resolve(),REG,READER,CACHE_PROOF]:p['pins'][str(f)]=BASE.digest(f)
 for row in registered:
  for k in ['input','cpu_rows']:p['pins'][str(ROOT/row[k])]=BASE.digest(ROOT/row[k])
 BASE.require(not any(BASE.option(s['argv'],'--reset-dump')!='none' or BASE.option(s['argv'],'--finish-dump')!='none'for s in p['stages']),'bounded explicit dumps only')
 return p

def exact_files(left,right,check=lambda:None):
 BASE.require(left.stat().st_size==right.stat().st_size,'canonical cold/final extent changed')
 before=[reader.identity(p.stat())for p in (left,right)]
 total=0
 with left.open('rb')as a,right.open('rb')as b:
  while True:
   check();x=a.read(1024**2);y=b.read(1024**2);BASE.require(x==y,'canonical cold/final byte mismatch')
   if not x:break
   total+=len(x)
 BASE.require(before==[reader.identity(p.stat())for p in (left,right)],'compared file identity changed')
 return total

def compare_states(initial,actual,check=lambda:None):
 BASE.require(initial['sources']==actual['sources'],'canonical source mapping differs')
 return exact_files(Path(initial['path'])/'state.bundle',Path(actual['path'])/'state.bundle',check)

def dump(a,t,marker):
 BASE.require(not any(t.pending),'DUMP requires all ranks drained')
 found={}
 for rank in (0,1):
  t.call(rank,4,position=marker)
  path=t.request_output/f'rank{rank}'/f'state-{marker}'
  t.check();verified=reader.read_state(path)
  found[str(rank)]=dict(path=str(path),sources=verified,bundle_sha256=(path/'state-seal.txt').read_text().splitlines()[2])
 return found

def compare_inventory(initial,actual,context=4096):
 fields=('launch_extent','alternate_launch_extent')
 cache={}
 for field in fields:
  x,y=initial[field],actual[field]
  BASE.require(type(x)is int and type(y)is int and 32<=x<=context and 32<=y<=context and x%32==0 and y%32==0,'retained launch cache extent geometry')
  cache[field]=dict(initial=x,retained=y,changed=x!=y,rebound_before_first_HALF_to=32)
 BASE.require({k:v for k,v in initial.items()if k not in fields}=={k:v for k,v in actual.items()if k not in fields},'cold non-cache inventory differs')
 return dict(fields=cache,source_proof_sha256=BASE.digest(CACHE_PROOF),scope='Cold model-state bytes verified; prepared launch extents retained and rebound at first HALF. No complete identical host-state claim.')

def cold(a,t,baseline=None):
 state=dump(a,t,SENTINEL);inventory={}
 for rank in (0,1):
  p=t.request_output/f'rank{rank}/request-state-inventory.json';d=json.loads(p.read_text())
  BASE.require(d['poisoned'] is False and d['bank_parity']==0 and d['logical_event']==0 and not d['lookup_ids_sha256'] and all(not x for x in d['selected']),'actual cold host/selection boundary')
  inventory[str(rank)]=dict(path=str(p),sha256=BASE.digest(p),value=d)
 compared={};cache={}
 if baseline:
  for rank in ('0','1'):
   compared[rank]=compare_states(baseline['state'][rank],state[rank],t.check)
   cache[rank]=compare_inventory(baseline['inventory'][rank]['value'],inventory[rank]['value'])
 return dict(state=state,inventory=inventory,retained_prepared_launch_cache=cache,actual_canonical_bytes_compared=compared,compared_to_first_actual_cold=baseline is not None)

def reset(a,t,dest):
 before=list(t.seq);BASE.require(not any(t.pending),'reset requires drained native owners')
 a.reset(t,dest) # Existing protocol and metadata destination semantics; no duplicate codec.
 BASE.require(list(t.seq)==[x+1 for x in before] and t.request_output==dest and not any(t.pending),'real reset preserves/increments wire sequences')
 receipts={}
 for rank in (0,1):
  p=dest/f'rank{rank}/reset.json';d=json.loads(p.read_text())
  BASE.require(d.get('passed') is True and d.get('allocation_ids_preserved') is True and type(d.get('allocations'))is int and d['allocations']>0 and type(d.get('bytes'))is int and d['bytes']>0,'actual native reset receipt')
  receipts[str(rank)]=dict(path=str(p),sha256=BASE.digest(p),value=d)
 return dict(sequence_before=before,sequence_after=list(t.seq),receipts=receipts)

def validate_trace(result,n,a):
 BASE.require(len(result['tokens'])==1 and result['stats']['guesses']==0,'one actual target-only prediction')
 rows=result['rank_trace'];BASE.require(all(x['speculative'] is False for x in rows),'no speculative work')
 for rank in (0,1):BASE.require([x['position']for x in rows if x['rank']==rank and x['op']==a.BASE.HALF]==list(range(n)),'every actual forced input position')

def journals(t,plan,n):
 found=[]
 for stage in plan['stages']:
  p=t.request_output/f'rank{stage["id"]}/router-tie-diagnostic.jsonl';rows=[json.loads(x)for x in p.read_text().splitlines()]
  expected={(pos,layer)for pos in range(n)for layer in range(stage['begin'],stage['end'])}
  BASE.require(len(rows)==len(expected)and {(x['position'],x['layer'])for x in rows}==expected,'complete actual router journal')
  for x in rows:
   BASE.require(x['verified_upload'] is True and x['schema']=='ownrt.router-tie-diagnostic.v1' and x['weights_before_sha256']==x['weights_after_sha256'],'verified tie upload/unchanged weight bytes')
   changed={i for i,(old,new)in enumerate(zip(x['old_ids'],x['new_ids']))if old!=new};w=x['changed_raw_words']
   BASE.require(len(x['old_ids'])==len(x['new_ids'])==10 and len(set(x['new_ids']))==10 and all(type(v)is int and 0<=v<512 for v in x['old_ids']+x['new_ids']) and x['changed_slots']==len(changed)==len(w)and {v['slot']for v in w}==changed and all(v['old_word']==v['new_word']for v in w),'all changed IDs have equal raw scores')
  found.append(dict(path=str(p),sha256=BASE.digest(p),rows=len(rows),changes=[x for x in rows if x['changed_slots']]))
 return found

def layers(t,plan):
 result=[]
 for stage in plan['stages']:
  folder=t.request_output/f'rank{stage["id"]}/step1';files=list(folder.glob('layer-*.bf16'))
  BASE.require({x.name for x in files}=={f'layer-{i:02d}.bf16'for i in range(stage['begin'],stage['end'])},'actual owned48 capture inventory')
  for f in files:BASE.require(f.is_file()and not f.is_symlink()and f.stat().st_size==40960,'actual F32 layer extent');result.append(dict(path=str(f),sha256=BASE.digest(f),bytes=40960))
 BASE.require(len(result)==48,'48 actual F32 layer captures');return result

def install_sequence_audit(t,path):
 real=t.start
 def start(rank,*args,**kwargs):
  before=list(t.seq);real(rank,*args,**kwargs);expected=list(before);expected[rank]+=1
  BASE.require(list(t.seq)==expected,'actual outer command sequence continuity')
  with path.open('a')as f:f.write(json.dumps(dict(rank=rank,sequence=t.seq[rank],op=args[0]if args else kwargs['op'],sequence_before=before,sequence_after=list(t.seq),scope='Actual outer transport send; existing receive validates matching reply. Internal scalar HALF traces have no wire-sequence field.'))+'\n')
 t.start=start

def request(a,t,plan,began):
 registered=cases();BASE.require(t.out==Path(plan['output'])/'native','existing adapter evidence/output authority')
 BASE.require(__import__('shutil').disk_usage(t.out).free>=plan['evidence_floor_bytes']+plan['evidence_forecast_bytes'],'sixGiB evidence forecast plus unchanged floor')
 install_sequence_audit(t,Path(plan['output'])/'outer-wire-sequences.jsonl')
 baseline=cold(a,t);records=[];all_sequences=[list(t.seq)]
 BASE.save(Path(plan['output'])/'cold-initial.json',baseline)
 for i,row in enumerate(registered):
  maintenance=None
  if i:
   dest=t.out/f'request-{i:02d}';maintenance=reset(a,t,dest);actual_cold=cold(a,t,baseline)
   BASE.save(dest/'cold-proof.json',actual_cold);maintenance['cold_proof']=str(dest/'cold-proof.json')
   if i>1:
    for rank in ('0','1'):BASE.require(maintenance['receipts'][rank]['value']==records[1]['reset']['receipts'][rank]['value'],'reset allocation count/bytes/receipt drift')
  before=list(t.seq);result=a.NativeController(t,a.BASE.Draft('none'),False,False,prefill=0,start=0).run(row['prompt'],1,())
  validate_trace(result,len(row['prompt']),a);BASE.require(list(t.seq)==[x+1 for x in before],'one actual native-controller outer command per rank')
  capture=layers(t,plan);journal=journals(t,plan,len(row['prompt']));state=dump(a,t,len(row['prompt']))
  record=dict(id=row['id'],prefix_tokens=len(row['prompt']),consumed_position=len(row['prompt'])-1,actual_output_ids=result['tokens'],saved_cpu_argmax=row['saved_cpu_argmax'],matches_saved_cpu_argmax=result['tokens']==[row['saved_cpu_argmax']],lifecycle_passed=True,reset=maintenance,sequence_before=before,sequence_after=list(t.seq),result=result,layer_captures=capture,journals=journal,full_state=state)
  BASE.save(Path(plan['output'])/f'request-{i:02d}.json',record);records.append(record);all_sequences.append(list(t.seq))
 repeat={}
 for rank in ('0','1'):
  repeat[rank]=compare_states(records[0]['full_state'][rank],records[-1]['full_state'][rank],t.check)
 BASE.require(records[0]['actual_output_ids']==records[-1]['actual_output_ids'],'repeated A prediction differs')
 return dict(schema='ownrt.router-tie.remaining-seven-result.v1',requests=7,records=records,repeated_A_actual_bytes_compared=repeat,all_wire_sequences=all_sequences,all_saved_cpu_argmax_match=all(x['matches_saved_cpu_argmax']for x in records),initial_cold=baseline,limits='Fixed historical teacher-forced prefixes only. Mismatch is a quality finding, never an oracle-driven retry. All7 requests use one loaded owner set; outer existing lifecycle FINISHes once.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--run',action='store_true');ap.add_argument('--admission',type=Path);ap.add_argument('--unit');x=ap.parse_args()
 if not x.run:BASE.save(x.plan,make_plan(x.config));return
 p=json.loads(x.plan.read_text());BASE.require(p==make_plan(p['config']),'exact registered plan/source pins');ad=json.loads(x.admission.read_text());BASE.require(ad['plan_sha256']==BASE.digest(x.plan),'admission planSHA');C.execute(p,ad,x.unit,request=request)
if __name__=='__main__':main()
