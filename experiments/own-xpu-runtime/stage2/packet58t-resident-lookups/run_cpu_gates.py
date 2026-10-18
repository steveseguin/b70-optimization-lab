"""Bounded policy, real launch refusal, drain race and owner-error gates."""
import ast,json,os,resource,subprocess,sys,re
from pathlib import Path
from build_engine import limits,sha,save
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def main():
    limits()
    for f in P.glob('*.py'):ast.parse(f.read_text(),filename=str(f))
    result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(P),'-v'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    log=P/'evidence/python-cpu-gates.log';log.write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stderr[-6000:]
    n=int(re.search(r'Ran (\d+) tests',result.stderr)[1])
    save(P/'evidence/python-cpu-gates.json',dict(passed=True,device_executed=False,tests=n,log_sha256=sha(log),sources={str(f.relative_to(ROOT)):sha(f) for f in P.glob('*.py')}))
    result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check_drain_fix.py'),str(P),'--json'],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
    row=json.loads(result.stdout);assert row['passed'] and row['counts']['UNFIXED']==0
    row['device_executed']=False;save(P/'evidence/drain-fix.json',row)
    result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check_teardown_on_error.py'),str(P),'--json'],stdin=subprocess.DEVNULL,capture_output=True,text=True)
    row=json.loads(result.stdout);assert row['files'][0]['status']=='MATCH';save(P/'evidence/teardown-inventory.json',row)
    for leaf in ('window.py','screen_window.py'):
        text=(P/leaf).read_text();assert 'from owner_teardown import finish_model_owner' in text and 'finish_model_owner(child,output,admission,waiting_check)' in text
    save(P/'evidence/teardown-integration.json',dict(passed=True,device_executed=False,helper_sha256=sha(P/'teardown_on_error.py'),adapter_sha256=sha(P/'owner_teardown.py'),generic_scanner_status=row['status'],
        local_cases=7,local_test_sha256=sha(P/'test_owner_teardown.py'),reason='Generic scanner has no one-card template; seven local regressions exercise the exact adapter called by both wrappers.'))
    assert resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024<8*1024**3
    print(n,'policy tests; drain and teardown PASS')
if __name__=='__main__':main()
