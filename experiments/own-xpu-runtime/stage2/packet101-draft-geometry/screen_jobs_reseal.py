"""One attention-only bracket per lane; HC aliases must not waste device windows."""
import json
from build_engine import P,ROOT,sha,save,check_map
from reseal import DEST, ROUND, parent_policy
WRAPPER=P.parent/'screen/v4-lanes'
ORDER=('control','draft_attention','control')
def view(label):
    assert label in ('control','draft_attention')
    return DEST/(label+'-'+ROUND)
def jobs(lane):
    assert lane in ('A','B')
    identity=sha(view('draft_attention')/'screen-seal.json')[:12]
    return [dict(index=i,choice=c,lane=lane,mode='grid',out=f'p101-{ROUND}-{identity}-{lane}-grid-{i}-{c}') for i,c in enumerate(ORDER)]
def output(job):return WRAPPER/'evidence'/job['out']
def verify():
    from bootstrap import install
    install()
    row=json.loads((P/'screen-jobs-seal-reseal-20261018.json').read_text());check_map(ROOT,row['sources'])
    assert row['order']==list(ORDER) and row['record_lane']=='A'
    for label in set(ORDER):
        sources=json.loads((view(label)/'screen-seal.json').read_text())['sources']
        assert all(parent_policy(p)=='keep' for p in sources), 'mutable parent input in active seal'
    return row
def seal_jobs():
    sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('screen_jobs_reseal.py','screen_job_reseal.py','compare_reseal.py','reseal.py','run_screen.py','bootstrap.py','worker.py','placement.py','placement-policy.json')}
    for label in set(ORDER):sources[str((view(label)/'screen-seal.json').relative_to(ROOT))]=sha(view(label)/'screen-seal.json')
    save(P/'screen-jobs-seal-reseal-20261018.json',dict(passed=True,device_executed=False,order=list(ORDER),sources=sources,record_lane='A',
         qualification='One exact first-lane win against both controls qualifies composition. Full record chain remains separate.'))
def choose(rows):
    from compare_reseal import compare
    compare(rows)
    assert rows[1]['rate']>max(rows[0]['rate'],rows[2]['rate']),'candidate must beat both controls'
    return rows[1]
