"""Small arrays only, after the single observer's full-logit neutrality gate passes."""
from pathlib import Path
import hashlib,json,struct,math,subprocess,os
HERE=Path(__file__).resolve().parent
CPU=Path('/dev/shm/sc117-router-observer-model-20261028-r1')
NATIVE=Path('/dev/shm/sc117-router-all48-target244-20261028-r1/output')
REPLAY=Path('/dev/shm/sc117-router-fixture-cpu-20261028-r2/replay')
OUT=Path('/dev/shm/sc117-router-analysis-20261028-r1')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def values(p,kind='f'):
 b=p.read_bytes();return struct.unpack('<'+str(len(b)//4)+kind,b)
def delta(a,b):
 assert len(a)==len(b)
 return dict(unequal=sum(x!=y for x,y in zip(a,b)),max_abs=max(abs(x-y) for x,y in zip(a,b)),rms=math.sqrt(sum((x-y)**2 for x,y in zip(a,b))/len(a)))
def cutoff(logits,probs):
 order=sorted(range(512),key=lambda i:(-probs[i],i));a,b=order[9:11]
 return dict(analysis_tiebreak='probability descending, lower ID (not assertion of ggml equal-key order)',id10=a,id11=b,probability10=probs[a],probability11=probs[b],exact_probability_tie=probs[a]==probs[b],logit10=logits[a],logit11=logits[b],exact_logit_tie=logits[a]==logits[b])
assert json.loads((CPU/'comparison.json').read_text())['passed_full_logit_neutrality']
assert not OUT.exists();OUT.mkdir()
env=os.environ.copy();env['GGML_CPU_EXACT_F64']='1';env['OMP_NUM_THREADS']='1'
rows=[]
for layer in range(48):
 n=NATIVE/'router-captures'/f'layer{layer}';c=CPU/'on'
 rec=json.loads((n/'extraction.json').read_text());assert rec['full_seal_verified']
 for name,h in rec['selected'].items():assert sha(n/name)==h
 ni=values(n/f'blk.{layer}.hc.f.mix.bin');nl=values(n/f'blk.{layer}.router.bin');nid=values(n/f'blk.{layer}.ids.bin','i');nw=values(n/f'blk.{layer}.prob.bin')
 ci=values(c/f'layer-{layer:02d}-input.f32');cl=values(c/f'layer-{layer:02d}-logits.f32');cid=values(c/f'layer-{layer:02d}-ids.i32','i');cw=values(c/f'layer-{layer:02d}-weights.f32');cp=values(c/f'layer-{layer:02d}-probabilities.f32')
 row=dict(layer=layer,input_delta=delta(ni,ci),logits_delta=delta(nl,cl),selected_id_slot_differences=sum(x!=y for x,y in zip(nid,cid)),selected_id_set_equal=set(nid)==set(cid),native_ids=nid,cpu_ids=cid,selected_weights_delta=delta(nw,cw),cpu_actual_cutoff=cutoff(cl,cp),same_input={})
 for label,source in [('cpu_logits',c/f'layer-{layer:02d}-logits.f32')]:
  out=OUT/f'layer{layer}-{label}';cmd=['nice','-n','19','taskset','-c','8-15',str(REPLAY),str(source),str(out)]
  p=subprocess.run(cmd,env=env,capture_output=True,text=True);assert p.returncode==0,(layer,label,p.stderr)
  (out/'run.log').write_text(p.stdout+p.stderr)
  a=values(out/'native-ids.i32','i');b=values(out/'ggml-ids.i32','i');ap=values(out/'native-probs.f32');bp=values(out/'ggml-probs.f32');aw=values(out/'native-weights.f32');bw=values(out/'ggml-weights.f32')
  replay=dict(ids_native=a,ids_ggml=b,id_slot_differences=sum(x!=y for x,y in zip(a,b)),id_set_equal=set(a)==set(b),probabilities_delta=delta(ap,bp),weights_delta=delta(aw,bw),native_cutoff=cutoff(values(source),ap),ggml_cutoff=cutoff(values(source),bp))
  if label=='native_logits':
   replay['recorded_native_ids_equal']=a==nid;replay['recorded_native_weights_bitwise_equal']=(out/'native-weights.f32').read_bytes()==(n/f'blk.{layer}.prob.bin').read_bytes()
   replay['recorded_routes_bitwise_equal']=(out/'native-routes.i32').read_bytes()==(n/f'blk.{layer}.routes.bin').read_bytes()
   replay['recorded_downroutes_bitwise_equal']=(out/'native-routes-down.i32').read_bytes()==(n/f'blk.{layer}.routes.down.bin').read_bytes()
  else:
   replay['recorded_cpu_ids_equal']=b==cid;replay['recorded_cpu_weights_bitwise_equal']=(out/'ggml-weights.f32').read_bytes()==(c/f'layer-{layer:02d}-weights.f32').read_bytes()
   replay['recorded_cpu_probabilities_bitwise_equal']=(out/'ggml-probs.f32').read_bytes()==(c/f'layer-{layer:02d}-probabilities.f32').read_bytes()
  row['same_input'][label]=replay
 rows.append(row)
result=dict(scope='Committed position243 only; actual CPU/native inputs may differ. Same-input replay isolates routing after supplied logits, not router projection or preceding token state; no causal conclusion from drift.',native_token=json.loads((NATIVE/'result.json').read_text())['tokens'],cpu_full_logits_sha256=sha(CPU/'on/logits-243.f32'),replay_binary=str(REPLAY),replay_binary_sha256=sha(REPLAY),rows=rows)
(OUT/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print('actual ID differences',[(r['layer'],r['selected_id_slot_differences']) for r in rows if r['selected_id_slot_differences']])
print('same-input ID differences',[(r['layer'],label) for r in rows for label,v in r['same_input'].items() if v['id_slot_differences']])
print('native exact cutoff ties',[(r['layer'],label) for r in rows for label,v in r['same_input'].items() if v['native_cutoff']['exact_probability_tie']])
print('ggml exact cutoff ties',[(r['layer'],label) for r in rows for label,v in r['same_input'].items() if v['ggml_cutoff']['exact_probability_tie']])
