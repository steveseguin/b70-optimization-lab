"""Fixed packet84 hc-wide/ordered/rec-parallel composition; one new mechanism."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('production','rec-both','rec-both-plus')
ELIGIBLE=('rec-both-plus',) # rec-both is the existing rec-parallel kernel, not a contender.
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unknown packet82b choice')
 return dict(route='route-exp32-rank4',recurrence='rec-parallel' if name=='production' else name,hc='production',miss='batch',experts='wide64',packed_dense='production',hc_gate='wide',host_retire='ordered',hc_norm='production')
def selection(name):
 s=json.loads((P/'selection-template.json').read_text());s['choices']=choices(name);return s
