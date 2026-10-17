"""Full CPU rehearsal receipt: source-bound gates, imports, admission and plans."""
import argparse,json,subprocess,sys,os
from build_engine import P,ROOT,B,limits,sha,save
from bundle_selection import views,PLACEMENTS
from chain_seal import check_map
GATES=('cpu-byte-identity.json','retirement-byte-identity.json','protocol.json','full-shape.json','memory-admission.json','cpu-gates.json','screen-plans.json','worker-import.json','all-view-plans.json')

def verify():
    report=json.loads((P/'evidence/dry-run.json').read_text())
    assert report['passed'] and not report['device_executed']
    check_map(ROOT,report['sources'])
    for n in GATES:
        row=json.loads((P/'evidence'/n).read_text());assert row['passed'] and not row['device_executed']
        if row.get('sources'):check_map(ROOT,row['sources'])
    tests=json.loads((P/'evidence/python-tests.json').read_text());assert tests['passed']
    return report

def main():
    limits();ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    if a.verify:verify();print('full CPU dry run verified');return
    from stopped_archive import require_fresh_chain
    require_fresh_chain(B)
    for script in ('screen_plans.py','all_view_plans.py'):
        with (P/'evidence'/(script+'.log')).open('w') as f:
            subprocess.run([sys.executable,'-B',str(P/script)],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True)
    # No optional runtime plugins are loaded into the CPU test runner.
    env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONPATH='/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages',TMPDIR=str(B/'tmp'),OMP_NUM_THREADS='2')
    tests=[]
    groups=[('chain',P),('orchestration',P.parents[1]/'ops/packet80-orchestration')]
    for name,folder in groups:
        log=P/'evidence'/('python-'+name+'.log')
        with log.open('w') as f:r=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',str(folder)],env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
        assert r.returncode==0,'Python tests failed: '+str(log)
        tests.append(dict(group=name,log=str(log.relative_to(ROOT)),sha256=sha(log)))
    save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,groups=tests))
    sources={}
    for n in (*GATES,'python-tests.json'):
        f=P/'evidence'/n;row=json.loads(f.read_text());assert row['passed'] and not row['device_executed'];sources[str(f.relative_to(ROOT))]=sha(f)
        if row.get('sources'):check_map(ROOT,row['sources']);sources.update(row['sources'])
    assert len(json.loads((P/'evidence/full-shape.json').read_text())['runs'])==128
    assert len(json.loads((P/'evidence/screen-plans.json').read_text())['runs'])==128
    assert len(json.loads((P/'evidence/all-view-plans.json').read_text())['runs'])==704
    for f in [*P.glob('*.py'),*P.glob('*.sh'),*P.glob('test_*.py')]:sources[str(f.relative_to(ROOT))]=sha(f)
    ops=P.parents[1]/'ops/packet80-orchestration'
    for f in [*ops.glob('*.py'),*ops.glob('*.sh')]:sources[str(f.relative_to(ROOT))]=sha(f)
    for r in tests:sources[r['log']]=r['sha256']
    size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink())
    assert size<1500000000,size
    save(P/'evidence/dry-run.json',dict(passed=True,device_executed=False,sources=sources,compositions=len(views()),placements=len(PLACEMENTS),chain_window_plans=704,screen_plans=128,build_logical_bytes=size))
    verify();print('full CPU dry run PASS; 64 configurations, 704 chain window plans')
if __name__=='__main__':main()
