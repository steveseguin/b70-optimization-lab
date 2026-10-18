"""Packet97 engine dimensions retained; screens isolate one expert mechanism."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('production','exp-slm','exp-compact-slm','exp-compact-global','down-byte-slm','exp-slm+halfcache','exp-compact-slm+halfcache','exp-compact-global+halfcache')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unregistered packet99 expert choice')
 return dict(route='route-exp32-rank4',recurrence='rec-parallel',hc='production',miss='batch',experts='wide64' if name=='production' else name,packed_dense='production',hc_gate='wide',host_retire='ordered',hc_norm='production',head='production')
def selection(v):
 name=v[0] if not isinstance(v,str) else v
 s=json.loads((P/'selection-template.json').read_text());s['choices']=choices(name);return s
