"""Isolate packet102 gate/up choices on packet97 wide64+halfcache lineage."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('production', 'exp-lookup-batch2', 'exp-lookup-batch4', 'exp-gateup-shared', 'exp-lookup-batch2-shared', 'exp-lookup-batch4-shared')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unregistered packet102 expert choice')
 result=json.loads((P/'lineage-inputs/control-selection.json').read_text())['choices']
 result['experts']='exp-halfcache' if name=='production' else name
 return result

def selection(v):
 name=v if isinstance(v,str) else v[0]
 s=json.loads((P/'lineage-inputs/control-selection.json').read_text());s['choices']=choices(name);return s
