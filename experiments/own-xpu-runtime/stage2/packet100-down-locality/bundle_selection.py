"""Preregistered down views and cross-feature startup corners."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
CANDIDATES=('down-interleave','down-tile16')
GATES=('exp-slm','exp-compact-slm','exp-compact-global','exp-slm+halfcache','exp-compact-slm+halfcache','exp-compact-global+halfcache')
VIEWS=('production',*CANDIDATES,*('compose97-'+c for c in CANDIDATES),*(g+'+'+c for g in GATES for c in CANDIDATES))
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unregistered packet100 view')
 maximal=name.startswith('compose97-')
 expert='wide64' if name=='production' else 'exp-grid-prefetch+halfcache+'+name.removeprefix('compose97-') if maximal else name
 return dict(route='route-fast' if maximal else 'route-exp32-rank4',recurrence='rec-both-plus' if maximal else 'rec-parallel',hc='production',miss='batch',experts=expert,packed_dense='production',hc_gate='wide',host_retire='reply-first' if maximal else 'ordered',hc_norm='consumer' if maximal else 'production',head='head-transpose' if maximal else 'production')
def selection(v):
 name=v if isinstance(v,str) else v[0]
 s=json.loads((P/'selection-template.json').read_text());s['choices']=choices(name);return s
