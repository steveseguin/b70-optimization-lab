"""Packet84 production composition plus the exact E3 candidate. E2 is closed."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('production','exp-grid-prefetch')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unknown packet95 choice')
 return dict(route='route-exp32-rank4',recurrence='rec-parallel',hc='production',miss='batch',experts=name if name!='production' else 'wide64',packed_dense='production',hc_gate='wide',host_retire='ordered',hc_norm='production')
def selection(name):
 s=json.loads((P/'selection-template.json').read_text());s['choices']=choices(name);return s
