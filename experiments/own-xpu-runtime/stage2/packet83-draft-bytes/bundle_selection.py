"""Preregistered draft-only views; target choices fixed to packet75."""
import json
from pathlib import Path
VIEWS=('production','q4-g32','prefix990','prefix985')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unknown packet83 choice')
 return dict(route='route-exp32-rank4',recurrence='rows4-shared',hc='production',miss='batch',experts='wide64',packed_dense='production',hc_gate='production')
def selection(name):
 s=json.loads((Path(__file__).parent/'selection.json').read_text());s['choices']=choices(name)
 s['draft']['head_format']='q4-g32' if name=='q4-g32' else 'production'
 s['draft']['head_prefix']={'prefix990':'coverage990','prefix985':'coverage985'}.get(name,'production')
 return s
