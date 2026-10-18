"""Recheck the CPU-only handoff without launching a native/device binary."""
import json,subprocess,sys
from build_engine import P,ROOT,B,limits,sha,save
def main():
    limits()
    rows=[]
    commands=[('protocol-tests',[sys.executable,'-B','-m','unittest','discover','-s',str(P),'-p','test_micro_gate.py']),
              ('source-audit',[sys.executable,'-B',str(P/'source_audit.py')]),
              ('direct-plan',[sys.executable,'-B',str(P/'run_micro.py'),'--plan'])]
    for name,cmd in commands:
        log=P/'evidence'/(name+'.log')
        with log.open('w') as f:
            subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
        rows.append(dict(name=name,command=cmd,passed=True,log_sha256=sha(log)))
    plan=json.loads((P/'evidence/queue-plan.json').read_text())
    assert plan['passed'] and not plan['device_executed'] and not plan['live_queue_modified']
    assert sha(ROOT/plan['proposal'])==plan['proposal_sha256']
    size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file())
    assert size<=300_000_000
    build=json.loads((P/'evidence/microbench-build.json').read_text())
    save(P/'evidence/final-verification.json',dict(passed=True,device_executed=False,
        live_queue_modified=False,checks=rows,protocol_test_count=13,
        build_logical_bytes=size,build_peak_rss_kib=build['max_rss_kib'],
        pending=['coordinator device micro','GNU/Intel byte execution after micro pass',
                 'all chain-window startup/host-reference paths','full-size VRAM admission',
                 'qualified engine seals','B grid','A confirmation'],
        sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'verify_preparation.py',P/'evidence/source-audit.json',P/'evidence/microbench-build.json',P/'evidence/queue-plan.json',ROOT/plan['proposal'])}))
    print('CPU handoff verified; all device and conditional integration gates remain pending.')
if __name__=='__main__':main()
