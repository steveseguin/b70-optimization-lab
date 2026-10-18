"""Decision-bound control/candidate/control; templates are plan-only."""
import json,hashlib
from build_engine import P,ROOT,sha,save
from bundle_selection import KEYS,name
WRAPPER=P.parent/'screen/v4-lanes'
DEFAULTS=dict(dense='production',hc='hc-wide',experts='wide64',host='ordered',route='production',norm='production',recurrence='rec-parallel',draft_head='production',head='production',hc_norm='production',down='production',draft_attention='production')
def configuration():return json.loads((P/'composition-selection.json').read_text())
def selections():
 r=configuration();return {'control':r['control'],'candidate':r['candidate']}
VIEWS=selections();ORDER=('control','candidate','control')
def view(label):return P/'selections'/(name(*(selections()[label][k] for k in KEYS))+'--placement-1')
def jobs(lane,choice=None,mode='grid'):
 assert lane in ('A','B') and mode=='grid'
 r=configuration();identity=sha(P/'composition-selection.json')[:12]
 return [dict(index=i,choice=c,lane=lane,mode='grid',out=f'p103-{identity}-{lane}-{i}-{c}') for i,c in enumerate(ORDER)]
def output(job):return WRAPPER/'evidence'/job['out']
def verify():
 from bootstrap import install
 install()
 from chain_seal import check_map
 from screen_seal_support import wrapper_seal
 wrapper_seal();r=configuration()
 for key in ('control','candidate'):name(*(r[key][k] for k in KEYS))
 seal=json.loads((P/'screen-jobs-seal.json').read_text());check_map(ROOT,seal['sources']);assert seal['views']==selections() and seal['order']==list(ORDER)
 return seal
def seal_jobs():
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('screen_jobs.py','screen_job.py','compare.py','composition-selection.json','run_screen.py','baseline-pins.json','shared-wrapper-pin.json')}
 for c in ORDER:sources[str((view(c)/'screen-seal.json').relative_to(ROOT))]=sha(view(c)/'screen-seal.json')
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,views=selections(),order=list(ORDER),sources=sources))
def choose(rows):
 from compare import compare
 compare(rows)
 assert rows[1]['rate']>max(rows[0]['rate'],rows[-1]['rate']),'no candidate beats both same-lane controls'
 return rows[1]
