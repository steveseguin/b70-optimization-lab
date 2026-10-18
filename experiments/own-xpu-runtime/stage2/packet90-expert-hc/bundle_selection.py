"""Three exact packet84-lineage views; one mechanism per candidate."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('production','exp-halfcache','hc-weightcache')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unknown packet90 choice')
 return dict(route='route-exp32-rank4',recurrence='rec-parallel',hc='production',miss='batch',experts='exp-halfcache' if name=='exp-halfcache' else 'wide64',packed_dense='production',hc_gate='hc-weightcache' if name=='hc-weightcache' else 'wide',host_retire='ordered',hc_norm='production')
def selection(name):
 s=json.loads((P/'selection-template.json').read_text());s['choices']=choices(name);return s
