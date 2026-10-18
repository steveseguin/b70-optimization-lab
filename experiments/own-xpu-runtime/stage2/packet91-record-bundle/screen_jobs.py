"""Fixed composition grids; the opposite lane confirms the exact source winner."""
import json,math
from pathlib import Path
from build_engine import P,ROOT,sha
from bundle_selection import KEYS,name
BASE=json.loads((P/'baseline-pins.json').read_text())['selection']
VIEWS={'control':BASE,'route-fast':dict(BASE,route='fast'),'rec-both-plus':dict(BASE,recurrence='rec-both-plus'),'route-fast-rec-both-plus':dict(BASE,route='fast',recurrence='rec-both-plus')}
ORDER=tuple(VIEWS)+('control',)
WRAPPER=P.parent/'screen/v4-lanes'
def view(label):
 v=VIEWS[label];return P/'selections'/(name(*(v[k] for k in KEYS))+'--placement-1')
def jobs(lane,choice=None,mode='grid'):
 assert lane in ('A','B') and mode in ('grid','confirm')
 order=ORDER if mode=='grid' else ('control',choice or 'route-fast','control')
 assert mode=='grid' or order[1] in tuple(VIEWS)[1:]
 return [dict(index=i,choice=c,lane=lane,mode=mode,out=f'p91-{lane}-{mode}-{i}-{c}') for i,c in enumerate(order)]
def output(job):return WRAPPER/'evidence'/job['out']
def verify():
 from bootstrap import install
 install()
 from chain_seal import check_map
 from screen_seal_support import wrapper_seal
 wrapper_seal();r=json.loads((P/'screen-jobs-seal.json').read_text());check_map(ROOT,r['sources'])
 assert r['views']==VIEWS and r['order']==list(ORDER)
 return r
def choose(rows):
 from compare import compare
 result=compare(rows,ORDER)
 best=max(rows[1:-1],key=lambda r:r['rate'])
 if best['rate']<=max(rows[0]['rate'],rows[-1]['rate']):raise ValueError('no candidate beats both same-lane controls')
 return best
def winner(source_lane):
 from compare import load
 return choose([load(job) for job in jobs(source_lane)])
def seal_jobs():
 sources={str(f.relative_to(ROOT)):sha(f) for f in P.glob('*.py')}
 for label in VIEWS:sources[str((view(label)/'screen-seal.json').relative_to(ROOT))]=sha(view(label)/'screen-seal.json')
 for n in ('baseline-pins.json','shared-wrapper-pin.json','extension-slots.json'):sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 (P/'screen-jobs-seal.json').write_text(json.dumps(dict(passed=True,device_executed=False,views=VIEWS,order=list(ORDER),sources=sources),indent=2)+'\n')
