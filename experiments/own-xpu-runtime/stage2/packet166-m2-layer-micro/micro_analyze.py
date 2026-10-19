"""Strict layer-event analysis. Projections never become measured model rates."""
import hashlib,json,math,statistics,re
from collections import defaultdict,Counter
from pathlib import Path
P=Path(__file__).resolve().parent
LAYERS={0:'GDN',3:'QSA'}
POSITIONS=(2,3,31)
COMMON={'hc_norm','hc_low_inject','hc_gate_mix','projection','small_tuple','attention_projection','combine','route_shared_activation','expert_gate_up','expert_activation','expert_down','shared_down_mix'}
CLASSES={0:COMMON|{'conv','gdn_recurrence','gdn_norm_gate'},3:COMMON|{'qsa_prepare','qsa_pool','qsa_select','qsa_attention'}}
BASE_COUNTS=dict(hc_norm=2,hc_low_inject=2,hc_gate_mix=2,projection=2,small_tuple=2,attention_projection=2,combine=1,route_shared_activation=1,expert_gate_up=1,expert_activation=1,expert_down=1,shared_down_mix=1)
COUNTS={0:dict(BASE_COUNTS,conv=1,gdn_recurrence=1,gdn_norm_gate=1),3:dict(BASE_COUNTS,projection=6,small_tuple=1,qsa_prepare=1,qsa_pool=1,qsa_select=2,qsa_attention=3)}
def require(ok,message):
 if not ok:raise ValueError(message)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def event_duration(row):
 require(all(type(row.get(k)) is int for k in ('start_ns','end_ns')),'event timestamp type')
 require(row['start_ns']>0 and row['end_ns']>row['start_ns'],'nonpositive event interval')
 return row['end_ns']-row['start_ns']
def read_events(path):
 rows=[]
 with Path(path).open() as stream:
  for line in stream:
   if line.strip():
    row=json.loads(line);require(isinstance(row,dict),'row must be object');rows.append(row)
 return rows
def analyze(path,baseline_prefill_tps=None):
 rows=read_events(path);require(rows and rows[-1].get('kind')=='summary','missing final summary')
 final=rows[-1];require(final.get('passed') is True and final.get('drained') is True,'native equality or drain failed')
 require(final.get('identity')=='iq3-p49-split32-v1' and final.get('layer_complete') is True,'not a complete identity-matched layer micro')
 require(final.get('backend')=='device','CPU output is not device timing')
 require(final.get('intermediate_checks_complete') is True,'intermediate/state check coverage incomplete')
 require(all(final.get(k) is True for k in ('zero_errors','finite_outputs','cpu_oracle_match')),'zero-error finite CPU oracle gate missing')
 groups=defaultdict(list);checks=defaultdict(set);order=[];oracles={}
 for row in rows[:-1]:
  require(row.get('kind') in ('sample','bytes','sensor','oracle'),'unknown stream row')
  if row['kind']=='sensor':continue
  require(row.get('layer') in LAYERS and row.get('position') in POSITIONS,'unexpected layer or position')
  if row['kind']=='oracle':
   key=(row['layer'],row['position'],row.get('repeat'),row.get('arm'));require(key not in oracles and row.get('passed') is True and type(row.get('compared_buffers')) is int and row['compared_buffers']>=50,'invalid timed oracle');oracles[key]=row;continue
  if row['kind']=='bytes':
   require(type(row.get('compared_bytes')) is int and row['compared_bytes']>0 and row.get('different_bytes')==0,'byte mismatch/empty check')
   require(re.fullmatch('[0-9a-f]{64}',row.get('sha256','')) is not None,'missing byte digest')
   key=(row['layer'],row['position']);name=row.get('buffer');require(isinstance(name,str) and name and name not in checks[key],'duplicate byte check');checks[key].add(name);continue
  require(all(type(row.get(k)) is int for k in ('repeat','arm','event')),'sample integers')
  require(0<=row['repeat']<200 and row['arm'] in (0,1),'sample repeat/arm range')
  require(row.get('class') in CLASSES[row['layer']],'unexpected op class');event_duration(row)
  key=(row['layer'],row['position'],row['repeat'],row['arm'])
  if not groups[key]:order.append(key)
  require(row['event']==len(groups[key]),'missing/duplicate/out-of-order operation')
  if groups[key]:require(row['start_ns']>=groups[key][-1]['end_ns'],'overlapping ordered events')
  groups[key].append(row)
 expected=[(layer,pos,repeat,(repeat+j)%2) for layer in LAYERS for pos in POSITIONS for repeat in range(200) for j in range(2)]
 require(order==expected,'not 200 complete interleaved pairs at every layer/context')
 require(set(oracles)==set(expected),'timed arm oracle coverage missing')
 outputs=[]
 for layer,name in LAYERS.items():
  for pos in POSITIONS:
   required={'streams','a.norm','a.low','a.act','a.gate','a.mix','a.inject','f.norm','f.low','f.act','f.gate','f.mix','f.inject','router','ids','prob','routes','downroutes','eg','eu','ea','ed','sg','su','sa','down','mixture','moe','error','statusg','statusu','statusd','streams_after_attention','attention','shared_gate'}
   required|={'history','history.first','state','state.first','qkv','conv','alpha','beta','z','y','gated'} if layer==0 else {'qgate','k','v','iq','ik','q','gate','kn','iqn','keys','values','raw','pooled','selected','y'}
   require(required<=checks[(layer,pos)],'missing intermediate/state buffers')
   timing={arm:defaultdict(list) for arm in (0,1)}
   for rep in range(200):
    for arm in (0,1):
     events=groups[layer,pos,rep,arm];totals=defaultdict(int)
     require(Counter(r['class'] for r in events)=={k:v*(2 if arm==0 else 1) for k,v in COUNTS[layer].items()},'operation census differs from selected complete layer')
     for row in events:totals[row['class']]+=event_duration(row)
     require(set(totals)==CLASSES[layer],'missing op class')
     for cls,value in totals.items():timing[arm][cls].append(value)
     timing[arm]['layer_device_sum'].append(sum(totals.values()))
     timing[arm]['layer_device_span'].append(events[-1]['end_ns']-events[0]['start_ns'])
   ops={}
   for cls in timing[0]:
    serial=statistics.median(timing[0][cls]);paired=statistics.median(timing[1][cls]);ops[cls]=dict(two_m1_ns=serial,m1_mean_ns=serial/2,m2_ns=paired,m2_over_m1=2*paired/serial,paired_over_two_serial=paired/serial,repeats_per_arm=200)
   outputs.append(dict(layer=layer,family=name,position=pos,ops=ops))
 # One representative GDN/QSA layer, weighted by the model's 36/12 mix.
 projections=[]
 for pos in POSITIONS:
  selected={r['layer']:r['ops']['layer_device_sum'] for r in outputs if r['position']==pos}
  one=36*selected[0]['m1_mean_ns']+12*selected[3]['m1_mean_ns'];two=36*selected[0]['m2_ns']+12*selected[3]['m2_ns'];ratio=two/one
  projections.append(dict(position=pos,weighted_m2_over_m1=ratio,representative_48_layer_m1_device_ms=one/1e6,representative_m2_verifier_device_ms=two/1e6,implied_extra_verifier_device_ms=(two-one)/1e6,implied_prefill_speedup=2/ratio,implied_prefill_tps=None if baseline_prefill_tps is None else baseline_prefill_tps*2/ratio,scope='projection from one layer of each family; excludes embeddings, PLE, head, transfers, host scheduling and draft'))
 passes=all(r['ops']['layer_device_sum']['m2_over_m1']<=1.5 for r in outputs)
 return dict(schema='packet166.layer-micro.analysis.v1',diagnostic_only=True,model_output_claim=False,full_build_authorized=False,samples_sha256=sha(path),finite_bytes_equal=True,cpu_oracle_match=True,zero_errors=True,decision='build brief: exact M=2 prefill stage 1' if passes else 'close: measured layer M2/M1 > 1.5',threshold=1.5,ratio_definition='2*M2/(M1_row0+M1_row1)',layers=outputs,projections=projections,baseline_prefill_tps=baseline_prefill_tps,baseline_is_provisional=baseline_prefill_tps==90)
def evaluate(output):
 output=Path(output);result=analyze(output/'samples.jsonl',90.0)
 (output/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
 if result['decision'].startswith('build brief:'):
  (output/'BUILD-BRIEF.md').write_text('# Exact M=2 prefill: stage 1\n\nLayer device diagnostic passes the 1.5 ratio gate. Integrate two causal rows using the pinned kernels, retain both row outputs and complete BF16 state, then prove all 48 layers against the unchanged packet49 oracle, odd tails, resets and two fresh processes. Measure complete 512-token TTFT on two fresh servers before any headline. This micro does not authorize publication.\n')
 else:
  with (P/'DO-NOT-REPEAT.md').open('a') as f:f.write('\n| Fully paired causal M=2 layer micro | >1.5 ratio in at least one registered layer/context; close this M=2 prefill stage | '+str(output/'analysis.json')+' | New mechanism with independently justified lower full-layer cost |\n')
 return result
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);args=ap.parse_args();print(json.dumps(evaluate(args.output),indent=2))
