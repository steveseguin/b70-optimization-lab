"""Smoke first, B grid, then the exact B winner between fresh A controls."""
import json
from build_engine import P,ROOT,sha,save,check_map
WRAPPER=P.parent/'screen/v4-lanes'
SMOKE_CHOICE='head-split+draft-split'
ORDER=('production','head-split','head-split+draft-split','production')
def view(label):
 assert label in ORDER
 return P/'selections'/label
def jobs(lane):
 assert lane in ('A','B')
 identity=sha(view('head-split+draft-split')/'screen-seal.json')[:12]
 return [dict(index=i,choice=c,lane=lane,mode='grid',out=f'p106b-{identity}-{lane}-grid-{i}-{c}') for i,c in enumerate(ORDER)]
def output(job):return WRAPPER/'evidence'/job['out']
def confirm_jobs(winner='head-split+draft-split'):
 assert winner in ORDER[1:-1]
 identity=sha(view('head-split+draft-split')/'screen-seal.json')[:12]
 return [dict(index=i,choice=c,lane='A',mode='confirm',out=f'p106b-{identity}-A-confirm-{i}') for i,c in enumerate(('production',winner,'production'))]
def qualified_winner():
 from compare import compare_grid,load
 rows=[load(j) for j in jobs('B')]
 result=compare_grid(rows)
 assert result['winners'], 'B grid has no exact improving winner'
 return max((r for r in rows[1:-1] if r['choice'] in result['winners']),key=lambda r:r['rate'])['choice']
def smoke_output():return WRAPPER/'evidence'/('p106b-'+sha(view('head-split+draft-split')/'screen-seal.json')[:12]+'-B-smoke12')
def verify():
 from bootstrap import install
 install();r=json.loads((P/'screen-jobs-seal.json').read_text());check_map(ROOT,r['sources']);assert r['order']==list(ORDER) and r['record_lane']=='A';return r
def seal_jobs():
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('screen_jobs.py','screen_job.py','confirm_job.py','smoke_job.py','smoke_screen.py','smoke_worker.py','smoke_validation.py','device_gate.py','compare.py','run_screen.py','bootstrap.py','worker.py','placement.py','placement-policy.json')}
 for label in set(ORDER):sources[str((view(label)/'screen-seal.json').relative_to(ROOT))]=sha(view(label)/'screen-seal.json')
 sources[str((P.parent/'packet105b-head-split/screen-jobs-seal.json').relative_to(ROOT))]=sha(P.parent/'packet105b-head-split/screen-jobs-seal.json')
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,order=list(ORDER),sources=sources,record_lane='A',qualification='Each placement must beat its two fresh controls with 13/13 exact checks and identical acceptance. A independently confirms; no CPU or B-only record claim.'))

def require_smoke():
 from smoke_validation import require_smoke as combined
 result=combined()
 # Different packet105b target binary has its own complete smoke. Verify in a
 # fresh Python process so packet-local placement modules cannot cross-contaminate.
 import subprocess,sys
 target=P.parent/'packet105b-head-split/smoke_validation.py'
 r=subprocess.run([sys.executable,'-B',str(target)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
 assert r.returncode==0,'packet105b twelve-prompt smoke incomplete: '+r.stderr
 result['target_smoke']=json.loads(r.stdout)
 return result
