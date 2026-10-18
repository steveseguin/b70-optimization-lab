"""Packet84 production and host-only reply-first, identical arithmetic."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('production','reply-first')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unknown packet92 view')
 s=json.loads((P/'selection-template.json').read_text())['choices']
 s.update(route='route-exp32-rank4',recurrence='rec-parallel',hc='production',miss='batch',experts='wide64',packed_dense='production',hc_gate='wide',host_retire='reply-first' if name=='reply-first' else 'ordered',hc_norm='production')
 return s
def selection(name):
 s=json.loads((P/'selection-template.json').read_text());s['decision']=None;s['choices']=choices(name);return s
