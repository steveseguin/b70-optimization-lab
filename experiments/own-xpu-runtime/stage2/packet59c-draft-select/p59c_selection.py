"""Strict draft selection, with a single native registry and frozen target choices."""
import hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def registry():
 text=(P/'p59c_select.hpp').read_text()
 def entries(name):
  body=text.split('> '+name+'{',1)[1].split('\n};',1)[0]
  return dict(re.findall(r'\{"([^"]+)","([^"]+)"\}',body))
 return entries('sites'),entries('consumers'),entries('dependencies')
SITES,CONSUMERS,DEPENDENCIES=registry()
KEYS=set(SITES.values())|set(DEPENDENCIES)
TARGET={'route':'route-exp32-rank4','recurrence':'rows4-shared','hc':'production'}
def unique(pairs):
 result={}
 for k,v in pairs:
  if k in result:raise ValueError('duplicate JSON field: '+k)
  result[k]=v
 return result
def read(path):return validate(json.loads(Path(path).read_text(),object_pairs_hook=unique))
def validate(s):
 if set(s)!={'schema','choices','decision','draft'} or s['schema']!='packet59c.selection.v1':raise ValueError('selection schema')
 if s['choices']!=TARGET:raise ValueError('target must remain packet56')
 decision={'path':'selection-decision.json','sha256':sha(P/'selection-decision.json')}
 if s['decision']!=decision:raise ValueError('target decision binding')
 m=s['draft']
 if not isinstance(m,dict) or set(m)!=KEYS or any(v not in ('production','packet59') for v in m.values()):raise ValueError('draft keys/choices')
 for key,producer in DEPENDENCIES.items():
  if m[key]=='packet59' and m[producer]!='packet59':raise ValueError('fusion requires candidate producer: '+key)
 return s
def selection(enabled=()):
 return validate(dict(schema='packet59c.selection.v1',choices=TARGET,decision={'path':'selection-decision.json','sha256':sha(P/'selection-decision.json')},draft={k:'packet59' if k in enabled else 'production' for k in sorted(KEYS)}))
GROUPS={
 'screen1-attention':{'qgate','qsa_attention','qsa_k','qsa_v','qsa_iq','qsa_ik','attention_output','fuse_attention_combine'},
 'screen2-hc':{k for k in KEYS if k.startswith('hc_') and not k.endswith('_norm')}|{k for k in KEYS if k.startswith('fuse_hc_')},
 'screen3-experts-route':{'gate_up','down','route','router','shared_gate','shared_up','shared_down','shared_router','fuse_expert_activation','fuse_shared_activation'},
 'screen4-norm-merge':{'embedding_norm','hidden_norm','hc_a_norm','hc_f_norm','final_norm','hidden_projection','embedding_projection','fuse_hidden_merge'},
}
assert set.union(*GROUPS.values())==KEYS and sum(map(len,GROUPS.values()))==len(KEYS)
def profiles():
 result={'default':selection(),'all-packet59':selection(KEYS)}
 result.update({k:selection(v) for k,v in GROUPS.items()})
 for key in sorted(KEYS):result['only-'+key]=selection({key,DEPENDENCIES.get(key,key)})
 return result
if __name__=='__main__':
 d=P/'selections';d.mkdir(exist_ok=True)
 for name,value in profiles().items():save(d/(name+'.json'),value)
 save(P/'selection.json',selection())
 print(json.dumps({'selectable_swaps':len(SITES),'fusions':len(DEPENDENCIES),'gated_choice_sets':len(profiles())}))
