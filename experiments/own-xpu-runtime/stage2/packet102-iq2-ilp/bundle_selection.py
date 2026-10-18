"""Isolate packet102 gate/up choices on packet97 wide64+halfcache lineage."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('production', 'exp-lookup-batch2', 'exp-lookup-batch4', 'exp-gateup-shared', 'exp-lookup-batch2-shared', 'exp-lookup-batch4-shared')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unregistered packet102 expert choice')
 return dict(route='route-exp32-rank4',recurrence='rec-parallel',hc='production',miss='batch',experts='exp-halfcache' if name=='production' else name,packed_dense='production',hc_gate='wide',host_retire='ordered',hc_norm='production',head='production')
def selection(v):
 name=v if isinstance(v,str) else v[0]
 s=json.loads((P/'selection-template.json').read_text());s['choices']=choices(name);return s
