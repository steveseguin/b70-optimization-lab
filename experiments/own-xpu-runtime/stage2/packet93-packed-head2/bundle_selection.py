"""Pinned packet84 production and two exact target-head unpack views."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('production','head-plane','head-transpose')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unknown packet93 view')
 c=json.loads((P/'selection-template.json').read_text())['choices']
 c.update(route='route-exp32-rank4',recurrence='rec-parallel',hc='production',miss='batch',experts='wide64',packed_dense='production',hc_gate='wide',host_retire='ordered',hc_norm='production')
 c['head']=name
 return c
def selection(name):
 s=json.loads((P/'selection-template.json').read_text());s['choices']=choices(name);return s
