#!/usr/bin/env python3
"""Real 48-layer setup + submit validation, production extents, CPU backend only."""
import hashlib,json,os,resource,subprocess,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    binary=P/'build/gnu-host/fullshape-submit'
    sources=json.loads((P/'build-gnu-host-receipt.json').read_text())['sources_sha256']
    for x in (Path(__file__),P/'dispatch-speed6.json',P/'selection.json',P.parent/'suite-inputs-20261012/incident-retrospective/plan.tsv'):
        sources[str(x.relative_to(ROOT))]=sha(x)
    assert all(sha(ROOT/n)==v for n,v in sources.items())
    with tempfile.TemporaryDirectory(prefix='fullshape-',dir=P/'build') as tmp:
        out=Path(tmp)/'run'
        run=subprocess.run([str(binary),'--fullshape-submit-test',str(out)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90)
        (P/'evidence/fullshape-submit-cpu.log').write_text(run.stdout+run.stderr)
        assert run.returncode==0,run.stdout+run.stderr
        row=json.loads((out/'result.json').read_text())
        assert row['passed'] and row['legacy_refused'] and row['sites']==1486 and row['contexts']==[32,4096]
        census=json.loads((out/'census.json').read_text())['allocations']
        totals={m:sum(x['bytes'] for x in census if x['memory']==m) for m in ('device','host-pinned')}
        assert len(census)==3446 and totals=={'device':24287732980,'host-pinned':48633091712}
        assert all(next(x['bytes'] for x in census if x['label']=='card0:expert-table:blk.2.ffn_'+name+'_exps.weight')==8192 for name in ('gate','up'))
        row.update(allocation_rows=len(census),arena_totals=totals,device_bytes_match_58f_log=True)
        for leaf in ('census.json','teardown.json','58f-refusal.txt','prepared-arguments-parity0.jsonl'):
            target=P/'evidence'/('fullshape-'+leaf);target.write_bytes((out/leaf).read_bytes())
            sources[str(target.relative_to(ROOT))]=sha(target)
        rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024
        assert rss<8*1024**3, 'fullshape RAM exceeded 8 GiB'
        row['peak_rss_bytes']=rss
        row.update(schema='packet58g.fullshape-submit.v1',binary_sha256=sha(binary),sources=sources,
                   method='Real Engine.initialize, prepare_plan, prepare_commands; real Arena allocation rows; mmap distinct production extents; no payload reads, no compute',
                   legacy='58f one-card table rows through unchanged direct p28 extent predicate',
                   arithmetic='iq3-p49-split32-v1')
    (P/'evidence/fullshape-submit-cpu.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({k:v for k,v in row.items() if k!='sources'}))
if __name__=='__main__':main()
