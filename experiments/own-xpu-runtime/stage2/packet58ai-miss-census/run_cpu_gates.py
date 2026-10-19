"""Bounded tests and real entry/loader/report rehearsals; no device/model reads."""
import json,os,re,resource,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits

def run(args,log):
    with log.open('w') as f,log.with_suffix('.stderr.log').open('w') as errors:
        cp=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=f,
                          stderr=errors if log.suffix=='.json' else subprocess.STDOUT,timeout=120)
    if cp.returncode:raise RuntimeError('CPU check failed: '+str(log))
    return cp

def main():
    limits()
    run([sys.executable,'-B',str(P/'device_import_gate.py')],P/'evidence/device-import-gate.log')
    # Argument probes intentionally inherit unchanged unlimited AS; they do
    # not load weights or execute native code, and retain measured peak RSS.
    run([sys.executable,'-B','-m','unittest','discover','-s',str(P),'-p','test_*.py'],P/'evidence/python-tests.log')
    tests=int(re.search(r'Ran (\d+) tests', (P/'evidence/python-tests.log').read_text()).group(1))
    save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,tests=tests,log_sha256=sha(P/'evidence/python-tests.log')))
    run([sys.executable,'-B',str(P/'argument_gate.py')],P/'evidence/arguments.log')
    proposal=P.parents[1]/'ops/lane-queue/proposed-p58ai-census-A.txt'
    ops=P.parents[1]/'ops'
    report=P/'evidence/shared-entry-report.json'
    run([sys.executable,'-B',str(ops/'rehearse_entry.py'),str(proposal),'--report','--json'],report)
    checked=json.loads(report.read_text())
    assert checked['passed'] is True
    save(P/'evidence/shared-entry.json',dict(passed=True,device_executed=False,
        report='evidence/shared-entry-report.json',report_sha256=sha(report),
        scope='shared sandbox native entry/parser probes and synthetic report adapters; no model or device work'))
    binaries=[str(P/'build/device'/n) for n in ['own-rt-iq3','p58-cache-fixtures']]
    run([sys.executable,'-B',str(ops/'launch_env.py'),*binaries],P/'evidence/loader.log')
    save(P/'evidence/loader.json',dict(passed=True,device_executed=False,log_sha256=sha(P/'evidence/loader.log'),
        binaries={str(Path(x).relative_to(P)):sha(x) for x in binaries}))
    assert resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024<2*1024**3
    save(P/'evidence/cpu-resource-use.json',dict(passed=True,device_executed=False,max_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
    print(f'{tests} tests, 6 native launch paths, 4 import/sensor paths, 2 loaders and 2 report kinds PASS')
if __name__=='__main__':main()
