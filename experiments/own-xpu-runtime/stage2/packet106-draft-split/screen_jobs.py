"""Smoke first, B grid, then the exact B winner between fresh A controls."""
import json
from build_engine import P,ROOT,sha,save,check_map
WRAPPER=P.parent/'screen/v4-lanes'
ORDER=('production','head-split','head-split+draft-split','production')
def view(label):
 assert label in (*ORDER,'draft-split')
 return P/'selections'/label
def jobs(lane):
 assert lane in ('A','B')
 identity=sha(view('head-split+draft-split')/'screen-seal.json')[:12]
 return [dict(index=i,choice=c,lane=lane,mode='grid',out=f'p106-{identity}-{lane}-grid-{i}-{c}') for i,c in enumerate(ORDER)]
def output(job):return WRAPPER/'evidence'/job['out']
def confirm_jobs(winner='head-split+draft-split'):
 assert winner in ORDER[1:-1]
 identity=sha(view('head-split+draft-split')/'screen-seal.json')[:12]
 return [dict(index=i,choice=c,lane='A',mode='confirm',out=f'p106-{identity}-A-confirm-{i}') for i,c in enumerate(('production',winner,'production'))]
def qualified_winner():
 from compare import compare_grid,load
 rows=[load(j) for j in jobs('B')]
 result=compare_grid(rows)
 assert result['winners'], 'B grid has no exact improving winner'
 return max((r for r in rows[1:-1] if r['choice'] in result['winners']),key=lambda r:r['rate'])['choice']
def smoke_output():return WRAPPER/'evidence'/('p106-'+sha(view('head-split+draft-split')/'screen-seal.json')[:12]+'-B-smoke')
def verify():
 from bootstrap import install
 install();r=json.loads((P/'screen-jobs-seal.json').read_text());check_map(ROOT,r['sources']);assert r['order']==list(ORDER) and r['record_lane']=='A';return r
def seal_jobs():
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('screen_jobs.py','screen_job.py','confirm_job.py','smoke_job.py','smoke_screen.py','smoke_worker.py','compare.py','run_screen.py','bootstrap.py','worker.py','placement.py','placement-policy.json')}
 for label in (*set(ORDER),'draft-split'):sources[str((view(label)/'screen-seal.json').relative_to(ROOT))]=sha(view(label)/'screen-seal.json')
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,order=list(ORDER),sources=sources,record_lane='A',qualification='Each placement must beat its two fresh controls with 13/13 exact checks and identical acceptance. A independently confirms; no CPU or B-only record claim.'))

def require_smoke():
 from bootstrap import install
 install()
 from common import sealed
 from types import SimpleNamespace
 root=smoke_output();window=json.loads((root/'window.json').read_text());actual=json.loads((root/'identity.json').read_text())
 lineage=view('head-split+draft-split');expected=sealed(SimpleNamespace(lineage=lineage,seal=lineage/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 assert all(actual.get(k)==v for k,v in expected.items())
 assert window['identity']==actual and window['passed'] and window['device_executed'] and window['device_complete'] and window['lease_released']
 assert not window.get('child_still_running') and not window.get('child_retained') and not window.get('stop_reasons')
 for leaf in ('identity.json','summary.json','run/teardown.json','run/incident64/receipt.json'):
  assert window['files'][leaf]==sha(root/leaf),leaf
 result=json.loads((root/'summary.json').read_text());assert result['passed'] and result['smoke'] and result['request_count']==1 and result['tokens']==64 and result['draft_suffixes']>0
 assert json.loads((root/'run/teardown.json').read_text())['drained']
 coordination=json.loads((root/'lane-coordination.json').read_text());assert coordination['passed'] and coordination['released_before_report']
 return dict(passed=True,path=str(root),window_sha256=sha(root/'window.json'))
